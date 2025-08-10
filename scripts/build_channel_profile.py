import os
import numpy as np
from supabase import create_client
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import logging

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
TOP_N = int(os.getenv('NICHES_TOP_N_VIDEOS', 120))
MODEL_NAME = 'all-MiniLM-L6-v2'

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
model = SentenceTransformer(MODEL_NAME)

def fetch_channel_content():
    query = supabase.table('channel_content') \
        .select('id', 'title', 'description', 'script') \
        .order('published_at', desc=True) \
        .limit(TOP_N)
    return query.execute().data

def generate_embeddings(texts):
    return model.encode(texts)

def cluster_embeddings(embeddings, n_clusters=5):
    kmeans = KMeans(n_clusters=n_clusters)
    kmeans.fit(embeddings)
    return kmeans.cluster_centers_

def save_profile(centroids):
    data = [{'embedding': centroid.tolist()} for centroid in centroids]
    supabase.table('channel_profile_embeddings').upsert(data).execute()

def main():
    content = fetch_channel_content()
    if not content:
        logging.warning("No channel content found")
        return
    
    texts = [f"{item['title']} {item['description']} {item.get('script', '')}" for item in content]
    embeddings = generate_embeddings(texts)
    centroids = cluster_embeddings(embeddings)
    save_profile(centroids)
    logging.info(f"Saved channel profile with {len(centroids)} centroids")

if __name__ == '__main__':
    main()
