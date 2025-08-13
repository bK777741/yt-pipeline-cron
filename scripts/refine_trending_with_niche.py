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
    Opción A (preferida): Trae candidatos de la tabla 'video_trending' para la fecha de ejecución actual.
    Esto asume que un proceso anterior ya ha poblado la tabla con un 'run_date'.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    logging.info(f"Obteniendo candidatos de trending para la fecha: {today}")
    return supabase.table('video_trending').select('*').eq('run_date', today).execute().data

def fetch_channel_profile():
    # Trae todas las columnas y detecta el nombre real de la columna de embeddings
    rows = supabase.table('channel_profile_embeddings').select('*').execute().data
    if not rows:
        return [], None  # no hay perfil aún

    candidate_cols = ('embedding', 'embedding_vector', 'profile_embedding', 'vector')
    emb_col = next((c for c in candidate_cols if c in rows[0]), None)
    if not emb_col:
        cols = list(rows[0].keys())
        raise RuntimeError(f"No se encontró la columna de embeddings en channel_profile_embeddings. Columnas: {cols}")

    # Devuelve la lista de vectores y el nombre detectado de la columna
    return [r[emb_col] for r in rows], emb_col

def filter_videos(videos, profile_vectors):
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

def save_filtered_videos(videos, region=None):
    today = datetime.now(timezone.utc).date().isoformat()
    ids = [v['id'] for v in videos]
    ya = set()
    if ids:
        exist = supabase.table('video_trending_filtered') \
            .select('video_id') \
            .eq('run_date', today) \
            .in_('video_id', ids) \
            .execute().data
        ya = {r['video_id'] for r in (exist or [])}

    rows = []
    for v in videos:
        if v['id'] in ya:
            continue
        rows.append({
            'run_date': today,
            'video_id': v['id'],
            'region': v.get('region') or region,
            'title': v.get('title'),
            'channel_title': v.get('channel_title'),
            'score': float(v.get('niche_similarity', 0.0)),
            'sim_to_profile': float(v.get('niche_similarity', 0.0)),
            'passed': True,
            'reason': '>= similarity threshold',
        })
    if rows:
        supabase.table('video_trending_filtered').insert(rows).execute()

    return rows

def main():
    logging.info("Iniciando job: refine_trending_with_niche")
    candidates = fetch_trending_candidates()
    if not candidates:
        logging.info("No hay candidatos de trending para procesar hoy. Finalizando.")
        return

    profile_vectors, emb_col = fetch_channel_profile()
    if not profile_vectors:
        logging.warning("No se encontró perfil de canal (channel_profile_embeddings). Saltando refinamiento.")
        return

    logging.info(f"Usando columna de embeddings '{emb_col}' para el perfil.")
    filtered_videos = filter_videos(candidates, profile_vectors)
    
    inserted_rows = []
    if filtered_videos:
        logging.info(f"Guardando {len(filtered_videos)} videos que superaron el umbral.")
        inserted_rows = save_filtered_videos(filtered_videos)
    else:
        logging.info("Ningún video superó el umbral de similitud.")

    print(f"[refine] aceptados={len(inserted_rows)} de {len(candidates)} candidatos (tras dedup por día)")
    logging.info(f"Job finalizado.")

if __name__ == '__main__':
    main()
