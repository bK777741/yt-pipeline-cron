# scripts/build_niche_profile.py
import os
import json
import numpy as np
import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

# --- Configuración ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Inicialización Segura de Clientes y Modelos ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit("ERROR: SUPABASE_URL y SUPABASE_SERVICE_KEY son obligatorios.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MODEL_NAME = os.getenv('NICHES_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
model = SentenceTransformer(MODEL_NAME)
EMBEDDING_DIM = model.get_sentence_embedding_dimension()

# --- Parámetros del Perfilado ---
TOP_N_VIDEOS = int(os.getenv('NICHES_TOP_N_VIDEOS', 150))
STORAGE_BUCKET = 'models'  # Bucket privado para modelos
MODEL_FILE_PATH = 'nv.json' # Niche Vector model

def fetch_own_videos():
    """
    Obtiene los videos propios más recientes y con mejor rendimiento para construir el perfil.
    Usa la vista v_video_stats_latest que combina videos con sus estadísticas más recientes.
    """
    logging.info(f"Obteniendo los últimos {TOP_N_VIDEOS} videos para construir el perfil de nicho.")
    try:
        response = supabase.table('v_video_stats_latest').select(
            'video_id, title, description, view_count, published_at'
        ).order('published_at', desc=True).limit(TOP_N_VIDEOS).execute()

        if not response.data:
            logging.warning("No se encontraron videos para construir el perfil.")
            return []
        return response.data
    except Exception as e:
        logging.error(f"Error al obtener videos de Supabase: {e}")
        return []

def calculate_niche_vector(videos: list):
    """
    Calcula el Niche Vector (NV) ponderado y los términos TF-IDF más relevantes.
    """
    if not videos:
        return None, []

    texts = [f"{v.get('title', '')}. {v.get('description', '')}" for v in videos]
    
    # Ponderación simple por novedad (más peso a los más recientes)
    weights = np.linspace(1.5, 0.5, num=len(videos))

    logging.info(f"Generando embeddings para {len(texts)} textos con el modelo '{MODEL_NAME}'.")
    embeddings = model.encode(texts, show_progress_bar=False)
    
    # Calcular Niche Vector ponderado
    niche_vector = np.average(embeddings, axis=0, weights=weights)
    
    # Calcular términos clave con TF-IDF
    logging.info("Calculando términos clave con TF-IDF.")
    vectorizer = TfidfVectorizer(max_features=25, stop_words='english')
    vectorizer.fit_transform(texts)
    top_terms = vectorizer.get_feature_names_out().tolist()

    return niche_vector, top_terms

def save_profile_to_storage(niche_vector: np.ndarray, top_terms: list):
    """
    Guarda el perfil de nicho completo en un archivo JSON en Supabase Storage.
    """
    if niche_vector is None:
        logging.error("No se pudo generar el Niche Vector. No se guardará el perfil.")
        return

    profile_data = {
        "model": MODEL_NAME,
        "ts": datetime.now(timezone.utc).isoformat(),
        "embedding_dim": int(EMBEDDING_DIM),
        "nv": niche_vector.tolist(),
        "tfidf_top_terms": top_terms,
        "lang_primary": "es",
        "weights": {
            "sim_nv": 0.6,
            "vph": 0.25,
            "eng": 0.15
        }
    }

    profile_bytes = json.dumps(profile_data, indent=2).encode('utf-8')

    try:
        logging.info(f"Subiendo perfil de nicho '{MODEL_FILE_PATH}' al bucket '{STORAGE_BUCKET}'...")
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=MODEL_FILE_PATH,
            file=profile_bytes,
            file_options={"content-type": "application/json", "upsert": "true"}
        )
        logging.info(f"Perfil de nicho (nv.json) guardado exitosamente en Supabase Storage.")
    except Exception as e:
        logging.error(f"FATAL: No se pudo subir el perfil de nicho a Storage: {e}")

def main():
    logging.info("Iniciando job: build_niche_profile")
    videos = fetch_own_videos()
    if videos:
        niche_vector, top_terms = calculate_niche_vector(videos)
        save_profile_to_storage(niche_vector, top_terms)
    logging.info("Job: build_niche_profile finalizado.")

if __name__ == '__main__':
    main()
