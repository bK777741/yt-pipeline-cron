# scripts/scan_competencia_auto_nicho.py
import os
import json
import numpy as np
import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Inicialización Segura ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("ERROR: SUPABASE_URL y SUPABASE_SERVICE_KEY son obligatorios.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MODEL_NAME = os.getenv('NICHES_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
model = SentenceTransformer(MODEL_NAME)

# --- Parámetros de Escaneo y Puntuación ---
SHADOW_MODE = os.getenv('AUTO_NICHO_SHADOW', 'true').lower() == 'true'
STORAGE_BUCKET = 'models'
REPORTS_BUCKET = 'reports'
MODEL_FILE_PATH = 'nv.json'

# Umbrales y Cuotas leídos de variables de entorno
TH_SHORTS = float(os.getenv('TH_SHORTS', 0.65))
TH_LONGS = float(os.getenv('TH_LONGS', 0.70))
TH_MIN = float(os.getenv('TH_MIN', 0.58)) # Umbral mínimo de similitud para ser considerado

def fetch_niche_profile():
    """Descarga y carga el modelo de nicho (nv.json) desde Supabase Storage."""
    try:
        logging.info(f"Descargando perfil de nicho desde '{STORAGE_BUCKET}/{MODEL_FILE_PATH}'...")
        response = supabase.storage.from_(STORAGE_BUCKET).download(MODEL_FILE_PATH)
        profile = json.loads(response.read())
        profile['nv'] = np.array(profile['nv'])
        logging.info(f"Perfil de nicho cargado (Modelo: {profile.get('model')}).")
        return profile
    except Exception as e:
        logging.error(f"FATAL: No se pudo descargar o parsear el perfil de nicho. Error: {e}")
        return None

def fetch_trending_candidates_for_scoring():
    """
    Lee los videos de la tabla 'video_trending' del día para puntuarlos contra el perfil de nicho.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    logging.info(f"Obteniendo candidatos de la tabla 'video_trending' con run_date={today}")
    try:
        response = supabase.table('video_trending').select('*').eq('run_date', today).execute()
        logging.info(f"Se encontraron {len(response.data)} candidatos de trending para evaluar.")
        return response.data
    except Exception as e:
        logging.error(f"No se pudieron obtener candidatos de 'video_trending'. Error: {e}")
        return []

def calculate_score(video: dict, profile: dict):
    """Calcula el score final para un video candidato."""
    # 1. Similitud con Niche Vector (sim_nv)
    text = f"{video.get('title', '')}. {video.get('description', '')}"
    embedding = model.encode([text], show_progress_bar=False)
    sim_nv = cosine_similarity(embedding, profile['nv'].reshape(1, -1))[0][0]
    
    # 2. Señales de rendimiento (si existen en la data de trending)
    vph_norm = video.get('views_per_hour_norm', 0.0)
    eng_norm = video.get('engagement_rate_norm', 0.0)

    # 4. Ponderación final
    weights = profile.get('weights', {'sim_nv': 0.6, 'vph': 0.25, 'eng': 0.15})
    score = (weights['sim_nv'] * sim_nv +
             weights['vph'] * vph_norm +
             weights['eng'] * eng_norm)

    # 5. Penalización por idioma (si aplica)
    if profile.get('lang_primary') and video.get('lang') != profile['lang_primary']:
        score -= 0.05
    
    return float(score), float(sim_nv)

def save_report_to_storage(bucket, report_data, filename):
    """Guarda un reporte (lista de dicts) como JSONL en Storage."""
    if not report_data:
        return
    
    report_bytes = "\n".join([json.dumps(record, default=str) for record in report_data]).encode('utf-8')
    ts = datetime.now(timezone.utc)
    path = f"auto_nicho/{ts.strftime('%Y/%m/%d')}/{filename}"
    
    try:
        supabase.storage.from_(bucket).upload(
            path=path,
            file=report_bytes,
            file_options={"content-type": "application/jsonl", "upsert": "true"}
        )
        logging.info(f"Reporte '{filename}' guardado en Storage en la ruta: {path}")
    except Exception as e:
        logging.warning(f"No se pudo guardar el reporte '{filename}' en Storage: {e}")

def main():
    """Función principal del scanner."""
    logging.info(f"Iniciando job: scan_competencia_auto_nicho (Shadow Mode: {SHADOW_MODE})")
    
    profile = fetch_niche_profile()
    if not profile:
        return

    all_candidates = fetch_trending_candidates_for_scoring()
    if not all_candidates:
        logging.info("No hay candidatos para escanear. Finalizando job.")
        return

    accepted, rejected = [], []

    for video in all_candidates:
        score, sim_nv = calculate_score(video, profile)
        is_short = video.get('duration_seconds', 61) <= 60
        threshold = TH_SHORTS if is_short else TH_LONGS
        
        video['score_niche'] = score
        video['sim_nv'] = sim_nv

        reason = ""
        if sim_nv < TH_MIN:
            reason = f"Similitud NV muy baja ({sim_nv:.3f} < {TH_MIN})"
        elif score < threshold:
            reason = f"Score insuficiente ({score:.3f} < {threshold:.3f}) (Formato: {'Short' if is_short else 'Long'})"
        
        if reason:
            rejected.append({"video_id": video.get('id'), "title": video.get('title'), "score": score, "sim_nv": sim_nv, "reason": reason})
        else:
            accepted.append(video)
    
    logging.info(f"Evaluación completada. Aceptados: {len(accepted)}, Rechazados: {len(rejected)}")

    # Guardar reportes en Storage
    save_report_to_storage(REPORTS_BUCKET, accepted, "top_niche.jsonl")
    save_report_to_storage(REPORTS_BUCKET, rejected, "rejects_niche.jsonl")

    if not SHADOW_MODE and accepted:
        logging.info(f"Modo Producción: Insertando hasta {len(accepted)} videos en la base de datos.")
        target_table = 'video_trending_filtered'
        today_iso = datetime.now(timezone.utc).date().isoformat()
        
        # Lógica de insert-only: primero consultamos cuáles ya existen para no re-insertar
        accepted_ids = [v['id'] for v in accepted]
        existing_ids_resp = supabase.table(target_table).select('video_id').eq('run_date', today_iso).in_('video_id', accepted_ids).execute()
        existing_ids = {r['video_id'] for r in existing_ids_resp.data}
        
        records_to_insert = []
        for video in accepted:
            if video['id'] in existing_ids:
                continue

            records_to_insert.append({
                "run_date": today_iso,
                'video_id': video['id'],
                'region': video.get('region'),
                'title': video.get('title'),
                'channel_title': video.get('channel_title'),
                'score': video.get('score_niche', 0.0),
                'sim_to_profile': video.get('sim_nv', 0.0),
                'passed': True,
                'reason': 'source: competencia_auto_nicho',
                'source': 'competencia_auto_nicho'
            })
        
        if records_to_insert:
            try:
                logging.info(f"Realizando insert de {len(records_to_insert)} nuevos registros en '{target_table}'.")
                supabase.table(target_table).insert(records_to_insert).execute()
            except Exception as e:
                logging.error(f"Error durante la inserción en Supabase: {e}")
        else:
            logging.info("No hay nuevos registros para insertar (ya existían en la tabla destino para hoy).")

    logging.info("Job scan_competencia_auto_nicho finalizado.")

if __name__ == '__main__':
    main()
