# scripts/scan_competencia_auto_nicho.py
import os
import json
import numpy as np
import logging
from datetime import datetime, timezone, timedelta
import isodate # Necesario para parsear duración ISO 8601
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

# --- Umbrales por Formato ---
TH_SHORTS = float(os.getenv('TH_SHORTS', 0.65))
TH_LONGS = float(os.getenv('TH_LONGS', 0.70))
TH_MIN = float(os.getenv('TH_MIN', 0.58))

# --- Helpers ---
def parse_iso8601_duration(duration_str: str) -> float:
    """Parsea una duración ISO 8601 (ej. 'PT1M30S') a segundos."""
    if not duration_str or not duration_str.startswith('PT'):
        return 0.0
    try:
        duration = isodate.parse_duration(duration_str)
        return duration.total_seconds()
    except (isodate.ISO8601Error, TypeError):
        return 0.0

def percentile_scaler(data: np.ndarray) -> np.ndarray:
    """Escala los datos a un rango [0, 1] usando percentiles 5 y 95."""
    if data.size == 0:
        return data
    min_val = np.percentile(data, 5)
    max_val = np.percentile(data, 95)
    if max_val == min_val:
        return np.zeros_like(data)
    scaled = (data - min_val) / (max_val - min_val)
    return np.clip(scaled, 0, 1)

def ensure_bucket_exists(bucket_name: str):
    """Crea un bucket en Supabase Storage si no existe."""
    try:
        supabase.storage.get_bucket(bucket_name)
    except Exception:
        logging.warning(f"Bucket '{bucket_name}' no encontrado. Intentando crear...")
        try:
            supabase.storage.create_bucket(bucket_name)
            logging.info(f"Bucket '{bucket_name}' creado exitosamente.")
        except Exception as create_error:
            logging.error(f"No se pudo crear el bucket '{bucket_name}': {create_error}")


# --- Funciones Principales ---
def fetch_niche_profile():
    """Descarga y carga el modelo de nicho (nv.json) de forma robusta desde Supabase Storage."""
    try:
        logging.info(f"Descargando perfil de nicho desde '{STORAGE_BUCKET}/{MODEL_FILE_PATH}'...")
        # Carga robusta que funciona si la respuesta es bytes o un stream
        resp = supabase.storage.from_(STORAGE_BUCKET).download(MODEL_FILE_PATH)
        raw = resp if isinstance(resp, (bytes, bytearray)) else resp.read()
        profile = json.loads(raw)
        profile['nv'] = np.array(profile['nv'])
        logging.info(f"Perfil de nicho cargado (Modelo: {profile.get('model')}).")
        return profile
    except Exception as e:
        logging.error(f"FATAL: No se pudo descargar o parsear el perfil de nicho. Error: {e}")
        return None

def fetch_trending_candidates_for_scoring():
    """Lee los videos de la tabla 'video_trending' del día actual."""
    today = datetime.now(timezone.utc).date().isoformat()
    logging.info(f"Obteniendo candidatos de la tabla 'video_trending' con run_date={today}")
    try:
        response = supabase.table('video_trending').select('*').eq('run_date', today).execute()
        logging.info(f"Se encontraron {len(response.data)} candidatos de trending para evaluar.")
        return response.data
    except Exception as e:
        logging.error(f"No se pudieron obtener candidatos de 'video_trending'. Error: {e}")
        return []

def preprocess_candidates(candidates):
    """
    Calcula y normaliza VPH y ENG para el pool de candidatos, usando los nombres de campo correctos.
    """
    now = datetime.now(timezone.utc)
    for v in candidates:
        # --- Alineación de campos y cálculo de señales crudas ---
        v['duration_seconds'] = parse_iso8601_duration(v.get('duration'))
        
        # VPH - Usando view_count y cálculo robusto para videos nuevos
        view_count = v.get('view_count', 0)
        published_at_str = v.get('published_at')
        if published_at_str:
            published_dt = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
            # Mejora: Evita división por cero o números pequeños, asegura un mínimo de 1 hora
            hours_since_published = max(1.0, (now - published_dt).total_seconds() / 3600.0)
            v['vph'] = view_count / hours_since_published
        else:
            v['vph'] = 0.0
            
        # ENG - Usando like_count y view_count
        like_count = v.get('like_count', 0)
        comment_count = v.get('comment_count', 0)
        v['eng'] = ((like_count + comment_count) / view_count) * 100 if view_count > 0 else 0.0

    # --- Normalización por formato ---
    shorts = [v for v in candidates if v['duration_seconds'] <= 60]
    longs = [v for v in candidates if v['duration_seconds'] > 60]

    if shorts:
        vph_shorts = percentile_scaler(np.array([v['vph'] for v in shorts]))
        eng_shorts = percentile_scaler(np.array([v['eng'] for v in shorts]))
        for i, v in enumerate(shorts):
            v['vph_norm'] = vph_shorts[i]
            v['eng_norm'] = eng_shorts[i]
    
    if longs:
        vph_longs = percentile_scaler(np.array([v['vph'] for v in longs]))
        eng_longs = percentile_scaler(np.array([v['eng'] for v in longs]))
        for i, v in enumerate(longs):
            v['vph_norm'] = vph_longs[i]
            v['eng_norm'] = eng_longs[i]

    return shorts + longs

def calculate_score(video: dict, profile: dict):
    """Calcula el score final para un video candidato pre-procesado."""
    # 1. Similitud con Niche Vector (sim_nv)
    text = f"{video.get('title', '')}. {video.get('description', '')}"
    embedding = model.encode([text], show_progress_bar=False)
    sim_nv = cosine_similarity(embedding, profile['nv'].reshape(1, -1))[0][0]
    
    # 2. Señales de rendimiento normalizadas (ya calculadas)
    vph_norm = video.get('vph_norm', 0.0)
    eng_norm = video.get('eng_norm', 0.0)

    # 3. Ponderación final con defaults
    weights = profile.get('weights', {})
    w_sim = weights.get('sim_nv', 0.6)
    w_vph = weights.get('vph', 0.25)
    w_eng = weights.get('eng', 0.15)
    score = (w_sim * sim_nv) + (w_vph * vph_norm) + (w_eng * eng_norm)

    # 4. Penalización suave por idioma
    if profile.get('lang_primary') and video.get('lang') and video.get('lang') != profile['lang_primary']:
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
        # Mejora: Usar contentType (camelCase) para el header
        supabase.storage.from_(bucket).upload(
            path=path,
            file=report_bytes,
            file_options={"contentType": "application/jsonl", "upsert": "true"}
        )
        logging.info(f"Reporte '{filename}' guardado en Storage: {path}")
    except Exception as e:
        logging.warning(f"No se pudo guardar el reporte '{filename}' en Storage: {e}")

def main():
    """Función principal del scanner."""
    logging.info(f"Iniciando job: scan_competencia_auto_nicho (Shadow Mode: {SHADOW_MODE})")
    
    profile = fetch_niche_profile()
    if not profile:
        return

    candidates = fetch_trending_candidates_for_scoring()
    if not candidates:
        logging.info("No hay candidatos para escanear. Finalizando job.")
        return
        
    logging.info("Pre-procesando candidatos para calcular y normalizar VPH/ENG...")
    processed_candidates = preprocess_candidates(candidates)

    accepted, rejected = [], []

    for video in processed_candidates:
        video_id = video.get('video_id')
        if not video_id:
            continue

        score, sim_nv = calculate_score(video, profile)
        is_short = video.get('duration_seconds', 0) <= 60
        threshold = TH_SHORTS if is_short else TH_LONGS
        
        video['score_niche'] = score
        video['sim_nv'] = sim_nv

        reason = ""
        if sim_nv < TH_MIN:
            reason = f"Similitud NV muy baja ({sim_nv:.3f} < {TH_MIN})"
        elif score < threshold:
            reason = f"Score insuficiente ({score:.3f} < {threshold:.3f}) (Formato: {'Short' if is_short else 'Long'})"
        
        if reason:
            rejected.append({"video_id": video_id, "title": video.get('title'), "score": score, "sim_nv": sim_nv, "reason": reason})
        else:
            accepted.append(video)
    
    logging.info(f"Evaluación completada. Aceptados: {len(accepted)}, Rechazados: {len(rejected)}")

    # Asegurar que el bucket para reportes exista
    ensure_bucket_exists(REPORTS_BUCKET)
    
    # Guardar reportes en Storage
    save_report_to_storage(REPORTS_BUCKET, accepted, "top_niche.jsonl")
    save_report_to_storage(REPORTS_BUCKET, rejected, "rejects_niche.jsonl")

    if not SHADOW_MODE and accepted:
        today_iso = datetime.now(timezone.utc).date().isoformat()
        target_table = 'video_trending_filtered'
        accepted_ids = [v['video_id'] for v in accepted]

        # Deduplicar antes de insertar
        existing_ids_resp = supabase.table(target_table).select('video_id').eq('run_date', today_iso).in_('video_id', accepted_ids).execute()
        existing_ids = {r['video_id'] for r in existing_ids_resp.data}
        
        records_to_insert = []
        for video in accepted:
            if video['video_id'] in existing_ids:
                continue
            records_to_insert.append({
                "run_date": today_iso,
                'video_id': video['video_id'],
                'region': video.get('region'),
                'title': video.get('title'),
                'channel_title': video.get('channel_title'),
                'score': video.get('score_niche'),
                'sim_to_profile': video.get('sim_nv'),
                'passed': True,
                'reason': 'source: competencia_auto_nicho',
                'source': 'competencia_auto_nicho'
            })
        
        if records_to_insert:
            try:
                logging.info(f"Modo Producción: Insertando {len(records_to_insert)} nuevos videos en '{target_table}'.")
                supabase.table(target_table).insert(records_to_insert).execute()
            except Exception as e:
                logging.error(f"Error durante la inserción en Supabase: {e}")
        else:
            logging.info("No hay nuevos registros para insertar (ya existían o todos fueron filtrados).")

    logging.info("Job scan_competencia_auto_nicho finalizado.")

if __name__ == '__main__':
    main()
