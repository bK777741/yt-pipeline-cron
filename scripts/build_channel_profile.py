# scripts/build_channel_profile.py
import os
import json
import numpy as np
from datetime import datetime
from supabase import create_client
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import logging

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')  # Usar service key
TOP_N = int(os.getenv('NICHES_TOP_N_VIDEOS', 120))
MODEL_NAME = 'all-MiniLM-L6-v2'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
model = SentenceTransformer(MODEL_NAME)
EMBEDDING_DIM = model.get_sentence_embedding_dimension()

def fetch_channel_content():
    # Obtener videos más recientes
    videos = supabase.table('videos') \
        .select('video_id, title, description, published_at') \
        .order('published_at', desc=True) \
        .limit(TOP_N) \
        .execute().data
    
    if not videos:
        return []

    video_ids = [v['video_id'] for v in videos]

    # Traer ambos campos y decidir en Python
    scripts = supabase.table('video_scripts') \
        .select('video_id, script_structured, transcript_clean') \
        .in_('video_id', video_ids) \
        .execute().data

    # Usar script_structured si existe, si no transcript_clean
    by_id = {
        s['video_id']: (s.get('script_structured') or s.get('transcript_clean') or '')
        for s in scripts
    }

    for v in videos:
        v['script'] = by_id.get(v['video_id'], '')

    return videos

def generate_embeddings(texts):
    return model.encode(texts)

def cluster_embeddings(embeddings, n_clusters=5):
    kmeans = KMeans(n_clusters=n_clusters)
    kmeans.fit(embeddings)
    return kmeans.cluster_centers_

def save_profile(centroids, video_ids):
    data = []
    timestamp = datetime.utcnow().isoformat()
    
    for i, centroid in enumerate(centroids):
        metadata = {
            'model': MODEL_NAME,
            'k': len(centroids),
            'video_ids': video_ids,
            'created_at': timestamp
        }
        
        data.append({
            'kind': f'kmeans:{i}',
            'dim': EMBEDDING_DIM,
            'vector': centroid.tolist(),
            'built_from': metadata
        })
    
    # Insertar datos
    supabase.table('channel_profile_embeddings').upsert(data).execute()

def main():
    content = fetch_channel_content()
    if not content:
        logging.warning("No channel content found")
        return
    
    texts = [f"{item['title']} {item['description']} {item['script']}" for item in content]
    video_ids = [item['video_id'] for item in content]
    
    embeddings = generate_embeddings(texts)
    centroids = cluster_embeddings(embeddings)
    save_profile(centroids, video_ids)
    logging.info(f"Saved channel profile with {len(centroids)} centroids")

if __name__ == '__main__':
    main()
