import os
import numpy as np
from supabase import create_client
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging
from datetime import datetime, timedelta, timezone

# Configuración
logging.basicConfig(level=logging.INFO)
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
    Trae candidatos de la tabla 'video_trending' que hayan sido añadidos
    en las últimas 48 horas. Se usa 'created_at' para ser más robusto.
    """
    since = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    return supabase.table('video_trending').select('*').gte('created_at', since).execute().data

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
    profile_matrix = np.array(profile_vectors)
    filtered = []
    for video in videos:
        # Título + descripción (con fallback por si alguno viene null)
        txt = (video.get('title') or '') + ' ' + (video.get('description') or '')
        video_embedding = model.encode([txt])[0]
        similarities = cosine_similarity([video_embedding], profile_matrix)[0]
        max_sim = float(np.max(similarities))
        if max_sim >= SIM_THRESHOLD:
            video['niche_similarity'] = max_sim
            filtered.append(video)
    return filtered

def save_filtered_videos(videos, region=None):
    """
    Guarda los videos filtrados con una lógica de 'insert-only' para el día actual.
    Verifica los IDs que ya existen para 'run_date' de hoy y solo inserta los nuevos.
    """
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
    
    # Log de resumen útil
    print(f"[refine] aceptados={len(rows)} de candidatos={len(videos)}")


def main():
    candidates = fetch_trending_candidates()
    profile_vectors, emb_col = fetch_channel_profile()
    if not profile_vectors:
        logging.warning("No channel profile found. Skipping refinement.")
        return

    logging.info(f"Usando columna de embeddings: {emb_col}")
    filtered = filter_videos(candidates, profile_vectors)
    save_filtered_videos(filtered)
    logging.info(f"Filtered {len(filtered)}/{len(candidates)} trending videos")

if __name__ == '__main__':
    main()
