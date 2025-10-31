import os
import numpy as np
from supabase import create_client
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging
from datetime import datetime, timezone

# Configuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').strip()
SUPABASE_KEY = (os.getenv('SUPABASE_SERVICE_KEY') or '').strip()
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")

SIM_THRESHOLD = float(os.getenv('NICHES_SIM_THRESHOLD', 0.78))
MODEL_NAME = os.getenv('NICHES_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
model = SentenceTransformer(MODEL_NAME)

def fetch_trending_candidates():
    """
    Trae candidatos de la tabla 'video_trending' para la fecha de ejecución actual (run_date).
    """
    today = datetime.now(timezone.utc).date().isoformat()
    logging.info(f"Obteniendo candidatos de trending para la fecha: {today}")
    return supabase.table('video_trending').select('*').eq('run_date', today).execute().data

def fetch_channel_profile():
    """
    Trae los vectores del perfil del canal y autodetecta la columna de embeddings.
    """
    rows = supabase.table('channel_profile_embeddings').select('*').execute().data
    if not rows:
        return [], None

    candidate_cols = ('vector', 'embedding', 'embedding_vector', 'profile_embedding')
    emb_col = next((c for c in candidate_cols if c in rows[0]), None)
    if not emb_col:
        cols = list(rows[0].keys())
        raise RuntimeError(f"No se encontró la columna de embeddings en channel_profile_embeddings. Columnas: {cols}")

    logging.info(f"Columna de embeddings detectada en 'channel_profile_embeddings': {emb_col}")
    return [r[emb_col] for r in rows], emb_col

def filter_videos(videos, profile_vectors):
    """
    Filtra videos calculando la similitud contra el perfil del canal en lote.
    """
    if not videos or not profile_vectors:
        return []
        
    profile_matrix = np.array(profile_vectors)
    filtered = []
    
    video_texts = [(v.get('title') or '') + ' ' + (v.get('description') or '') for v in videos]
    video_embeddings = model.encode(video_texts, show_progress_bar=False)
    
    similarities = cosine_similarity(video_embeddings, profile_matrix)
    
    for i, video in enumerate(videos):
        max_sim = float(np.max(similarities[i]))
        if max_sim >= SIM_THRESHOLD:
            video['niche_similarity'] = max_sim
            filtered.append(video)
            
    return filtered

def save_filtered_videos(videos):
    """
    Guarda los videos filtrados con lógica insert-only, deduplicando por (run_date, video_id).
    """
    today = datetime.now(timezone.utc).date().isoformat()
    # Usar 'video_id' en lugar de 'id'
    video_ids = [v['video_id'] for v in videos]
    existing_video_ids = set()

    if video_ids:
        # Deduplicar consultando los 'video_id' que ya existen para hoy
        exist_resp = supabase.table('video_trending_filtered') \
            .select('video_id') \
            .eq('run_date', today) \
            .in_('video_id', video_ids) \
            .execute().data
        existing_video_ids = {r['video_id'] for r in (exist_resp or [])}

    rows_to_insert = []
    for v in videos:
        # Saltar si el video_id ya fue insertado hoy
        if v['video_id'] in existing_video_ids:
            continue
            
        rows_to_insert.append({
            'run_date': today,
            'video_id': v['video_id'],
            'region': v.get('region'), # Dejar None si no existe
            'title': v.get('title'),
            'channel_title': v.get('channel_title'),
            'score': float(v.get('niche_similarity', 0.0)),
            'sim_to_profile': float(v.get('niche_similarity', 0.0)),
            'passed': True,
            'reason': '>= similarity threshold',
        })

    if rows_to_insert:
        logging.info(f"Insertando {len(rows_to_insert)} nuevos registros en 'video_trending_filtered'.")
        supabase.table('video_trending_filtered').insert(rows_to_insert).execute()

    return rows_to_insert

def main():
    logging.info("Iniciando job: refine_trending_with_niche")
    candidates = fetch_trending_candidates()
    if not candidates:
        logging.info("No hay candidatos de trending para procesar hoy. Finalizando.")
        return

    profile_vectors, _ = fetch_channel_profile()
    if not profile_vectors:
        logging.warning("No se encontró perfil de canal (channel_profile_embeddings). Saltando refinamiento.")
        return

    filtered_videos = filter_videos(candidates, profile_vectors)
    
    inserted_rows = []
    if filtered_videos:
        inserted_rows = save_filtered_videos(filtered_videos)
    else:
        logging.info("Ningún video superó el umbral de similitud.")

    # Log final con el formato exacto solicitado
    print(f"[refine] aceptados={len(inserted_rows)} de {len(candidates)} candidatos (tras dedup por día)")
    logging.info(f"Job finalizado.")

if __name__ == '__main__':
    main()
