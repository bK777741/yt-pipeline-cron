# scripts/build_channel_profile.py
import os
import json
import numpy as np
from datetime import datetime, timezone
from supabase import create_client
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import logging

# Configuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Hardened initialization
url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
TOP_N = int(os.getenv('NICHES_TOP_N_VIDEOS', 120))
MODEL_NAME = os.getenv('NICHES_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')

if not url:
    raise SystemExit("ERROR: Missing or empty SUPABASE_URL")
if not key:
    raise SystemExit("ERROR: Missing or empty SUPABASE_SERVICE_KEY")

supabase = create_client(url, key)
model = SentenceTransformer(MODEL_NAME)
EMBEDDING_DIM = model.get_sentence_embedding_dimension()

def fetch_channel_content():
    """Obtiene los videos más recientes del canal junto con sus guiones o transcripciones."""
    logging.info(f"Obteniendo los últimos {TOP_N} videos del canal...")
    videos = supabase.table('videos') \
        .select('video_id, title, description, published_at') \
        .order('published_at', desc=True) \
        .limit(TOP_N) \
        .execute().data
    
    if not videos:
        logging.warning("No se encontraron videos en la tabla 'videos'.")
        return []

    video_ids = [v['video_id'] for v in videos]

    logging.info(f"Obteniendo guiones para {len(video_ids)} videos...")
    scripts_response = supabase.table('video_scripts') \
        .select('video_id, script_structured, transcript_clean') \
        .in_('video_id', video_ids) \
        .execute()

    scripts = scripts_response.data or []
    by_id = {
        s['video_id']: (s.get('script_structured') or s.get('transcript_clean') or '')
        for s in scripts
    }

    for v in videos:
        v['script'] = by_id.get(v['video_id'], '')

    return videos

def generate_embeddings(texts):
    """Genera embeddings para una lista de textos."""
    logging.info(f"Generando embeddings para {len(texts)} textos con el modelo '{MODEL_NAME}'...")
    return model.encode(texts, show_progress_bar=False)

def cluster_embeddings(embeddings, n_clusters=5):
    """
    Agrupa los embeddings usando KMeans de forma determinista y segura.
    Ajusta el número de clusters si hay menos muestras que las deseadas.
    """
    n = min(n_clusters, len(embeddings))
    if n < 1:
        logging.warning("No hay suficientes embeddings para realizar clustering.")
        return []
    
    logging.info(f"Ejecutando KMeans con n_clusters={n}, n_init=10 y random_state=42...")
    km = KMeans(n_clusters=n, n_init=10, random_state=42)
    km.fit(embeddings)
    return km.cluster_centers_

def save_profile(centroids, video_ids):
    """Guarda los centroides del perfil en la tabla 'channel_profile_embeddings'."""
    if not isinstance(centroids, np.ndarray) or centroids.size == 0:
        logging.warning("No hay centroides para guardar.")
        return
        
    data = []
    timestamp = datetime.now(timezone.utc).isoformat()
    
    for i, centroid in enumerate(centroids):
        metadata = {
            'model': MODEL_NAME,
            'k': len(centroids),
            'video_ids_count': len(video_ids),
            'video_ids_sample': video_ids[:10], # Guardar solo una muestra
            'created_at': timestamp
        }
        
        data.append({
            'kind': f'kmeans:{i}',
            'dim': EMBEDDING_DIM,
            'vector': centroid.tolist(),
            'built_from': metadata
        })
    
    logging.info(f"Insertando {len(data)} perfiles de centroides en 'channel_profile_embeddings'...")
    # Primero eliminar perfiles existentes de kmeans
    try:
        supabase.table('channel_profile_embeddings').delete().like('kind', 'kmeans:%').execute()
        logging.info("Perfiles kmeans anteriores eliminados")
    except Exception as e:
        logging.warning(f"No se pudieron eliminar perfiles anteriores: {e}")

    # Insertar nuevos perfiles
    supabase.table('channel_profile_embeddings').insert(data).execute()

def main():
    """Función principal para construir y guardar el perfil del canal."""
    logging.info("Iniciando job: build_channel_profile")
    content = fetch_channel_content()
    if not content:
        logging.warning("No se encontró contenido del canal. El perfil no será actualizado.")
        return
    
    texts = [f"{item['title']} {item['description']} {item['script']}".strip() for item in content]
    video_ids = [item['video_id'] for item in content]
    
    embeddings = generate_embeddings(texts)
    centroids = cluster_embeddings(embeddings)
    save_profile(centroids, video_ids)
    logging.info(f"Job finalizado. Perfil del canal guardado con {len(centroids)} centroides.")

if __name__ == "__main__":
    main()
