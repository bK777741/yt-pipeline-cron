import os
import numpy as np
from supabase import create_client
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
SIM_THRESHOLD = float(os.getenv('NICHES_SIM_THRESHOLD', 0.78))
MODEL_NAME = 'all-MiniLM-L6-v2'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
model = SentenceTransformer(MODEL_NAME)

def fetch_trending_candidates():
    return supabase.table('video_trending').select('*').execute().data

def fetch_channel_profile():
    return supabase.table('channel_profile_embeddings').select('embedding').execute().data

def filter_videos(videos, profile_embeddings):
    profile_matrix = np.array([item['embedding'] for item in profile_embeddings])
    filtered = []
    for video in videos:
        video_embedding = model.encode([video['title'] + video['description']])[0]
        similarities = cosine_similarity([video_embedding], profile_matrix)[0]
        max_sim = np.max(similarities)
        if max_sim >= SIM_THRESHOLD:
            video['niche_similarity'] = float(max_sim)
            filtered.append(video)
    return filtered

def save_filtered_videos(videos):
    for video in videos:
        data = {
            'video_id': video['id'],
            'similarity_score': video['niche_similarity'],
            'reason': 'Above similarity threshold'
        }
        supabase.table('video_trending_filtered').upsert(data).execute()

def main():
    candidates = fetch_trending_candidates()
    profile = fetch_channel_profile()
    if not profile:
        logging.warning("No channel profile found. Skipping refinement.")
        return
    
    filtered = filter_videos(candidates, profile)
    save_filtered_videos(filtered)
    logging.info(f"Filtered {len(filtered)}/{len(candidates)} trending videos")

if __name__ == '__main__':
    main()
