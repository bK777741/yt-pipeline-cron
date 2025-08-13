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
MODEL_NAME = 'all-MiniLM-L6-v2'
model = SentenceTransformer(MODEL_NAME)
EMBEDDING_DIM = model.get_sentence_embedding_dimension()

# --- Parámetros del Perfilado ---
TOP_N_VIDEOS = int(os.getenv('NICHES_TOP_N_VIDEOS', 150))
STORAGE_BUCKET = 'models'  # Bucket privado para modelos
MODEL_FILE_PATH = 'nv.json' # Niche Vector model

def fetch_own_videos():
    """
    Obtiene los videos propios más recientes y con mejor rendimiento para construir el perfil.
    Asume que la tabla 'videos' tiene 'title', 'description', 'views', y 'published_at'.
    """
    logging.info(f"Obteniendo los últimos {TOP_N_VIDEOS} videos para construir el perfil de nicho.")
    try:
        # Ponderamos por una combinación de novedad y vistas.
        # Esta consulta es un ejemplo, podría necesitar ajuste según el esquema exacto.
        response = supabase.table('videos').select(
            'video_id, title, description, views, published_at'
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

    # 1. Preparar textos y pesos de ponderación
    texts = []
    weights = []
    
    # Normalización de vistas para ponderación (evita que un solo video viral domine todo)
    all_views = [v.get('views', 0) for v in videos]
    max_views = max(all_views) if all_views else 1
    
    for v in videos:
        # Texto combinado para embedding
        texts.append(f"{v.get('title', '')}. {v.get('description', '')}")
        
        # Ponderación: 50% por novedad, 50% por rendimiento normalizado.
        # La novedad se infiere por el orden de la query. Aquí damos más peso a los más recientes.
        recency_weight = 1.0 - (videos.index(v) / len(videos)) # Linealmente decreciente
        performance_weight = (v.get('views', 0) / max_views)
        
        weights.append(0.5 * recency_weight + 0.5 * performance_weight)

    logging.info("Generando embeddings para los textos de los videos.")
    embeddings = model.encode(texts, show_progress_bar=False)
    
    # 2. Calcular Niche Vector ponderado
    niche_vector = np.average(embeddings, axis=0, weights=np.array(weights))
    
    # 3. Calcular términos clave con TF-IDF
    logging.info("Calculando términos clave con TF-IDF.")
    vectorizer = TfidfVectorizer(max_features=25, stop_words='english') # Se puede adaptar a 'spanish'
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
        "ts": datetime.now(timezone.utc).isoformat(),
        "embedding_dim": int(EMBEDDING_DIM),
        "nv": niche_vector.tolist(),
        "tfidf_top_terms": top_terms,
        "lang_primary": "es",
        "weights": {
            # Pesos por defecto para el script de escaneo.
            "sim_nv": 0.70, # Aumentado porque no hay clasificador
            "clf_prob": 0.0,
            "vph": 0.20,    # Aumentado
            "eng": 0.10     # Aumentado
        }
    }

    # Convertir a bytes para subirlo
    profile_bytes = json.dumps(profile_data, indent=2).encode('utf-8')

    try:
        # Upsert del archivo en Storage
        supabase.storage.from_(STORAGE_BUCKET).remove([MODEL_FILE_PATH]) # Elimina el anterior para evitar conflictos
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=MODEL_FILE_PATH,
            file=profile_bytes,
            file_options={"content-type": "application/json", "upsert": "true"}
        )
        logging.info(f"Perfil de nicho guardado exitosamente en Storage: '{STORAGE_BUCKET}/{MODEL_FILE_PATH}'")
    except Exception as e:
        logging.error(f"Error al guardar el perfil de nicho en Supabase Storage: {e}")
        # No relanzamos la excepción para no fallar el job de Actions si solo falla el guardado.
        # En un escenario real, aquí podría ir una alerta.

def main():
    logging.info("Iniciando job: build_niche_profile")
    videos = fetch_own_videos()
    if videos:
        niche_vector, top_terms = calculate_niche_vector(videos)
        save_profile_to_storage(niche_vector, top_terms)
    logging.info("Job: build_niche_profile finalizado.")

if __name__ == '__main__':
    main()
