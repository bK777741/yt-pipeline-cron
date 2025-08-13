# scripts/scan_competencia_auto_nicho.py
import os
import json
import numpy as np
import logging
import random
from datetime import datetime, timezone
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Inicialización Segura ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY") # Necesario para buscar videos
if not SUPABASE_URL or not SUPABASE_KEY or not YOUTUBE_API_KEY:
    raise SystemExit("ERROR: SUPABASE_URL, SUPABASE_SERVICE_KEY, y YOUTUBE_API_KEY son obligatorios.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MODEL_NAME = 'all-MiniLM-L6-v2'
model = SentenceTransformer(MODEL_NAME)

# --- Parámetros de Escaneo y Puntuación ---
SHADOW_MODE = os.getenv('AUTO_NICHO_SHADOW', 'true').lower() == 'true'
STORAGE_BUCKET = 'models'
REPORTS_BUCKET = 'reports'
MODEL_FILE_PATH = 'nv.json'

# Umbrales y Cuotas
TH_SHORTS = float(os.getenv('TH_SHORTS', 0.65))
TH_LONGS = float(os.getenv('TH_LONGS', 0.70))
TH_MIN = float(os.getenv('TH_MIN', 0.58))
TARGET_SHORTS = int(os.getenv('TARGET_SHORTS', 15))
TARGET_LONGS = int(os.getenv('TARGET_LONGS', 10))

# --- Funciones de Soporte ---

def fetch_niche_profile():
    """Descarga el modelo de nicho (nv.json) desde Supabase Storage."""
    try:
        logging.info(f"Descargando perfil de nicho desde '{STORAGE_BUCKET}/{MODEL_FILE_PATH}'")
        response = supabase.storage.from_(STORAGE_BUCKET).download(MODEL_FILE_PATH)
        profile = json.loads(response.read())
        profile['nv'] = np.array(profile['nv'])
        return profile
    except Exception as e:
        logging.error(f"FATAL: No se pudo descargar o parsear el perfil de nicho. Error: {e}")
        return None

def fetch_competitors_from_youtube_api(region_code, max_results=50):
    """
    Función placeholder para escanear la API de YouTube.
    En una implementación real, aquí se usaría google-api-python-client.
    Devuelve una lista de diccionarios con datos de video.
    """
    # ESTA ES UNA SIMULACIÓN. Reemplazar con llamadas reales a la API de YouTube.
    logging.info(f"SIMULACIÓN: Buscando videos en YouTube para la región '{region_code}'...")
    # Mock data
    mock_videos = []
    for i in range(max_results):
        is_short = random.choice([True, False])
        mock_videos.append({
            "video_id": f"fake_{region_code}_{i}_{random.randint(1000, 9999)}",
            "title": f"Video de prueba sobre {random.choice(['finanzas', 'tecnología', 'vlogs'])} en {region_code}",
            "description": "Esta es una descripción de ejemplo para el video.",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "channel_title": f"Canal de Competencia {i}",
            "views": random.randint(1000, 500000),
            "likes": random.randint(100, 10000),
            "comments": random.randint(10, 500),
            "duration_seconds": random.randint(30, 60) if is_short else random.randint(300, 1200),
            "lang": "es" if region_code in ['MX', 'ES'] else "en",
            "country_code": region_code
        })
    logging.info(f"SIMULACIÓN: Se obtuvieron {len(mock_videos)} candidatos.")
    return mock_videos

def calculate_score(video: dict, profile: dict):
    """Calcula el score final para un video candidato."""
    # 1. Similitud con Niche Vector (sim_nv)
    text = f"{video.get('title', '')}. {video.get('description', '')}"
    embedding = model.encode([text], show_progress_bar=False)
    sim_nv = cosine_similarity(embedding, profile['nv'].reshape(1, -1))[0][0]
    
    # 2. Vistas por Hora Normalizadas (vph_norm)
    # Placeholder: la normalización real requeriría un baseline estadístico.
    # Aquí usamos una normalización simple para la demo.
    now = datetime.now(timezone.utc)
    published = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
    hours_since_published = max(1, (now - published).total_seconds() / 3600)
    vph = video.get('views', 0) / hours_since_published
    vph_norm = min(1.0, vph / 10000) # Asumimos 10k VPH como un buen VPH para normalizar

    # 3. Engagement Normalizado (eng_norm)
    engagement = video.get('likes', 0) + video.get('comments', 0)
    eng_per_1k_views = (engagement / max(1, video.get('views', 0))) * 1000
    eng_norm = min(1.0, eng_per_1k_views / 50) # Asumimos 50 como un buen engagement para normalizar

    # 4. Ponderación final
    weights = profile['weights']
    score = (weights['sim_nv'] * sim_nv +
             weights['vph'] * vph_norm +
             weights['eng'] * eng_norm)

    # 5. Penalización por idioma
    if video.get('lang') != profile['lang_primary']:
        score -= 0.05
    
    return score, sim_nv, vph_norm, eng_norm

def save_report_to_storage(bucket, report_data, filename):
    """Guarda un reporte (lista de dicts) como JSONL en Storage."""
    if not report_data:
        return
    
    report_bytes = "\n".join([json.dumps(record) for record in report_data]).encode('utf-8')
    ts = datetime.now(timezone.utc)
    path = f"auto_nicho/{ts.strftime('%Y/%m/%d')}/{filename}"
    
    try:
        supabase.storage.from_(bucket).upload(
            path=path,
            file=report_bytes,
            file_options={"content-type": "application/jsonl", "upsert": "true"}
        )
        logging.info(f"Reporte '{filename}' guardado en Storage.")
    except Exception as e:
        logging.warning(f"No se pudo guardar el reporte '{filename}' en Storage: {e}")

def main():
    """Función principal del scanner."""
    logging.info(f"Iniciando job: scan_competencia_auto_nicho (Shadow Mode: {SHADOW_MODE})")
    
    profile = fetch_niche_profile()
    if not profile:
        return

    # Definir regiones a escanear para esta ronda (ej. mañana)
    priority_1 = ['MX', 'ES', 'AR', 'CO', 'CL', 'PE'] # ... y el resto
    priority_2 = ['US', 'GB', 'IN', 'BR']
    
    all_candidates = []
    for region in priority_1:
        all_candidates.extend(fetch_competitors_from_youtube_api(region))

    accepted, rejected = [], []
    current_th_shorts, current_th_longs = TH_SHORTS, TH_LONGS

    for video in all_candidates:
        score, sim_nv, vph, eng = calculate_score(video, profile)
        is_short = video.get('duration_seconds', 61) <= 60
        threshold = current_th_shorts if is_short else current_th_longs
        
        reason = ""
        if sim_nv < TH_MIN:
            reason = f"Similitud NV muy baja ({sim_nv:.2f} < {TH_MIN})"
        elif score < threshold:
            reason = f"Score insuficiente ({score:.2f} < {threshold:.2f})"
        
        if reason:
            rejected.append({"video_id": video['video_id'], "score": score, "reason": reason})
        else:
            video['score'] = score
            accepted.append(video)

    # Lógica de umbrales dinámicos
    selected_shorts = [v for v in accepted if v.get('duration_seconds', 61) <= 60]
    selected_longs = [v for v in accepted if v.get('duration_seconds', 61) > 60]

    if len(selected_shorts) < 0.6 * TARGET_SHORTS:
        current_th_shorts = max(TH_MIN, current_th_shorts - 0.02)
        logging.info(f"Relajando umbral de Shorts a {current_th_shorts:.2f}")

    if len(selected_longs) > 1.3 * TARGET_LONGS:
        current_th_longs += 0.02
        logging.info(f"Endureciendo umbral de Largos a {current_th_longs:.2f}")

    # Reportes
    save_report_to_storage(REPORTS_BUCKET, accepted, "top.jsonl")
    save_report_to_storage(REPORTS_BUCKET, rejected, "rejects.jsonl")

    # Inserción en DB si no estamos en Shadow Mode
    if not SHADOW_MODE:
        logging.info(f"Modo Producción: Insertando {len(accepted)} videos en la base de datos.")
        records_to_insert = []
        for video in accepted:
            records_to_insert.append({
                "video_id": video['video_id'],
                "title": video['title'],
                "description": video['description'],
                "source": "competencia_auto_nicho",
                "score": video['score'],
                # ... otros campos que existan en tu tabla 'video_trending'
            })
        
        if records_to_insert:
            try:
                # Usamos upsert para la lógica de insert-only/update-on-improve.
                # Requiere una PRIMARY KEY o UNIQUE constraint en 'video_id'.
                # La lógica 'update-on-improve' debe manejarse con un trigger en la DB
                # o actualizando todos y dejando que la DB decida.
                supabase.table('video_trending').upsert(records_to_insert).execute()
                logging.info("Inserción completada.")
            except Exception as e:
                logging.error(f"Error durante la inserción en Supabase: {e}")

    logging.info(f"Job finalizado. Evaluados: {len(all_candidates)}, Aceptados: {len(accepted)}, Rechazados: {len(rejected)}")

if __name__ == '__main__':
    main()
