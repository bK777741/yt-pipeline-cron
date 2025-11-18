#!/usr/bin/env python3
"""
import_daily.py (MODIFICADO)
Ahora incluye análisis de miniaturas con manejo robusto de errores.
"""
import os
import re
import io
import sys
import requests
import numpy as np
from datetime import datetime
import pytz
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from supabase import create_client, Client
from PIL import Image
import cv2
import imagehash
import pytesseract  # Nueva dependencia para OCR

# --- Nuevas funciones para análisis de miniaturas ---
def download_thumbnail(url):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))
    except Exception as e:
        print(f"Error downloading thumbnail: {str(e)}")
        return None

def get_best_thumbnail(thumbnails):
    for res in ['maxres', 'high', 'medium', 'default']:
        if res in thumbnails and thumbnails[res].get('url'):
            return thumbnails[res]['url'], res
    return None, None

def analyze_thumbnail(thumbnail_url):
    if not thumbnail_url:
        return None
    
    img = download_thumbnail(thumbnail_url)
    if not img:
        return None
    
    try:
        # Convertir a array numpy para OpenCV
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Dominant color y paleta (usando k-means simplificado)
        pixels = img_cv.reshape((-1, 3))
        pixels = np.float32(pixels)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, 5, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
        )
        centers = np.uint8(centers)
        dominant_color = '#%02x%02x%02x' % tuple(centers[0].tolist())
        palette = ['#%02x%02x%02x' % tuple(color.tolist()) for color in centers]
        
        # Brillo y contraste
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        brightness_mean = np.mean(gray)
        contrast_std = np.std(gray)
        
        # Detección de caras con fallback seguro
        faces_count = 0
        try:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            faces_count = len(faces)
        except Exception:
            pass  # Si falla, mantiene 0 caras
        
        # Valores por defecto para saliencia
        saliency_score = 0.0
        saliency_center = [0.5, 0.5]
        
        # pHash con fallback
        phash = ""
        try:
            phash = str(imagehash.phash(img))
        except Exception:
            pass
        
        # --- NUEVO: Análisis OCR para text_area_ratio ---
        text_area_ratio = 0.0
        enable_ocr = os.getenv("ENABLE_THUMBNAIL_OCR", "true").lower() == "true"
        
        if enable_ocr:
            try:
                # Convertir a RGB para Tesseract
                img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                # Obtener bounding boxes de texto
                ocr_data = pytesseract.image_to_data(img_rgb, output_type=pytesseract.Output.DICT)
                
                total_text_area = 0
                img_area = img.width * img.height
                
                for i in range(len(ocr_data['text'])):
                    if int(ocr_data['conf'][i]) > 0:  # Solo áreas con texto detectado
                        x, y, w, h = (
                            ocr_data['left'][i],
                            ocr_data['top'][i],
                            ocr_data['width'][i],
                            ocr_data['height'][i]
                        )
                        total_text_area += w * h
                
                if img_area > 0:
                    text_area_ratio = total_text_area / img_area
            except Exception as e:
                print(f"Error en OCR: {str(e)}")
                text_area_ratio = 0.0
        
        return {
            'dominant_color': dominant_color,
            'palette': palette,
            'brightness_mean': float(brightness_mean),
            'contrast_std': float(contrast_std),
            'faces_count': faces_count,
            'saliency_score': float(saliency_score),
            'saliency_center': saliency_center,
            'phash': phash,
            'text_area_ratio': float(text_area_ratio)  # Nueva métrica
        }
    
    except Exception as e:
        print(f"Error in thumbnail analysis: {str(e)}")
        return None

# --- Funciones existentes modificadas ---
def load_env():
    load_dotenv()
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    batch = int(os.environ.get("DAILY_VIDEO_BATCH") or 20)
    channel_id = os.environ.get("CHANNEL_ID") or "UCWkGLaq5XxtF_r-0DKGZh4A"
    return creds, supabase_url, supabase_key, batch, channel_id

def init_clients(creds, supabase_url, supabase_key):
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def extract_hashtags(description):
    return list(set(re.findall(r"#(\w+)", description))) if description else []

def fetch_videos(yt, channel_id, published_after, max_results):
    try:
        # Construir parámetros de la solicitud
        request_params = {
            "part": "id",
            "channelId": channel_id,
            "order": "date",
            "type": "video",
            "maxResults": max_results,
        }

        # Agregar filtro de fecha si se proporciona
        if published_after:
            request_params["publishedAfter"] = published_after.isoformat()

        req = yt.search().list(**request_params)
        resp = req.execute()
    except HttpError as e:
        if "quotaExceeded" in str(e):
            print("[import_daily] quotaExceeded, salto")
            return []
        else:
            raise

    video_ids = [item["id"]["videoId"] for item in resp.get("items", [])]

    # Obtener detalles completos
    if video_ids:
        try:
            details_req = yt.videos().list(
                id=",".join(video_ids),
                part="snippet,contentDetails"
            )
            details_resp = details_req.execute()
        except HttpError as e:
            if "quotaExceeded" in str(e):
                print("[import_daily] quotaExceeded en detalles, salto")
                return []
            else:
                raise
        return [
            {
                "video_id": item["id"],
                "channel_id": item["snippet"]["channelId"],
                "title": item["snippet"]["title"],  # Nuevo campo
                "description": item["snippet"]["description"],
                "hashtags": extract_hashtags(item["snippet"]["description"]),
                "tags": item["snippet"].get("tags", []),  # Nuevo campo
                "duration": item["contentDetails"]["duration"],
                "thumbnails": item["snippet"]["thumbnails"],
                "published_at": item["snippet"]["publishedAt"]  # Nuevo campo
            }
            for item in details_resp.get("items", [])
        ]
    return []

def fetch_videos_with_pagination(yt, channel_id, published_before, max_results):
    """
    Busca videos progresivamente hacia atrás en el tiempo.
    - Si published_before es None: trae los 50 más recientes
    - Si published_before tiene fecha: trae los 50 anteriores a esa fecha
    """
    try:
        # Construir parámetros de la solicitud
        request_params = {
            "part": "id",
            "channelId": channel_id,
            "order": "date",  # Orden descendente (más recientes primero)
            "type": "video",
            "maxResults": max_results,
        }

        # Si hay fecha límite, buscar videos ANTES de esa fecha
        if published_before:
            request_params["publishedBefore"] = published_before.isoformat()

        req = yt.search().list(**request_params)
        resp = req.execute()
    except HttpError as e:
        if "quotaExceeded" in str(e):
            print("[import_daily] quotaExceeded, salto")
            return []
        else:
            raise

    video_ids = [item["id"]["videoId"] for item in resp.get("items", [])]

    # Obtener detalles completos
    if video_ids:
        try:
            details_req = yt.videos().list(
                id=",".join(video_ids),
                part="snippet,contentDetails"
            )
            details_resp = details_req.execute()
        except HttpError as e:
            if "quotaExceeded" in str(e):
                print("[import_daily] quotaExceeded en detalles, salto")
                return []
            else:
                raise
        return [
            {
                "video_id": item["id"],
                "channel_id": item["snippet"]["channelId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "hashtags": extract_hashtags(item["snippet"]["description"]),
                "tags": item["snippet"].get("tags", []),
                "duration": item["contentDetails"]["duration"],
                "thumbnails": item["snippet"]["thumbnails"],
                "published_at": item["snippet"]["publishedAt"]
            }
            for item in details_resp.get("items", [])
        ]
    return []

def upsert_videos(sb: Client, videos):
    rows = []
    for video in videos:
        # Extraer URLs de thumbnails
        thumbnails = video.get("thumbnails", {})

        rows.append({
            "video_id": video["video_id"],
            "channel_id": video["channel_id"],
            "title": video["title"],
            "description": video["description"],
            "hashtags": video["hashtags"],
            "tags": video["tags"],
            "duration": video["duration"],
            "published_at": video["published_at"],
            "imported_at": "now()",
            # FIX 2025-11-01: Agregar thumbnails que faltaban
            "thumbnail_default": thumbnails.get("default", {}).get("url"),
            "thumbnail_medium": thumbnails.get("medium", {}).get("url"),
            "thumbnail_high": thumbnails.get("high", {}).get("url"),
            "thumbnail_standard": thumbnails.get("standard", {}).get("url"),
            "thumbnail_maxres": thumbnails.get("maxres", {}).get("url")
        })
    sb.table("videos").upsert(rows, on_conflict=["video_id"]).execute()

# --- Función mejorada para análisis de miniaturas ---
def analyze_and_save_thumbnails(sb: Client, videos):
    for video in videos:
        try:
            best_url, source_size = get_best_thumbnail(video["thumbnails"])
            if not best_url:
                print(f"Sin miniatura para {video['video_id']}")
                continue
                
            analysis = analyze_thumbnail(best_url)
            if not analysis:
                continue
                
            analysis["video_id"] = video["video_id"]
            analysis["source_size"] = source_size
            
            try:
                sb.table("video_thumbnail_analysis").upsert(
                    analysis, 
                    on_conflict=["video_id"]
                ).execute()
            except Exception as e:
                print(f"Error al guardar análisis para {video['video_id']}: {str(e)}")
                
        except Exception as e:
            print(f"Error procesando miniatura de {video['video_id']}: {str(e)}")

def main():
    try:
        creds, supabase_url, supabase_key, batch, channel_id = load_env()
        yt, sb = init_clients(creds, supabase_url, supabase_key)

        # Obtener todos los videos existentes en Supabase
        existing_videos_response = sb.table("videos").select("video_id").execute()
        existing_ids = {video["video_id"] for video in existing_videos_response.data}

        # PASO 1: BUSCAR VIDEOS NUEVOS (publicados DESPUÉS del más reciente)
        print("[import_daily] PASO 1: Buscando videos NUEVOS...")
        newest_video_response = sb.table("videos").select("published_at").order("published_at", desc=True).limit(1).execute()

        videos_nuevos = []
        if newest_video_response.data:
            # Si ya tenemos videos, buscar DESPUÉS del más reciente
            newest_date = newest_video_response.data[0]["published_at"]
            from datetime import datetime
            published_after = datetime.fromisoformat(newest_date.replace('Z', '+00:00'))
            print(f"[import_daily] Buscando videos publicados DESPUES de: {published_after.isoformat()}")
            videos_nuevos = fetch_videos(yt, channel_id, published_after, max_results=50)
        else:
            print("[import_daily] Primera importacion: buscando los 50 videos mas recientes")
            videos_nuevos = fetch_videos_with_pagination(yt, channel_id, None, max_results=50)

        # Filtrar nuevos que no estén en Supabase
        videos_nuevos_filtrados = [v for v in videos_nuevos if v["video_id"] not in existing_ids]

        if videos_nuevos_filtrados:
            print(f"[import_daily] Encontrados {len(videos_nuevos_filtrados)} videos NUEVOS. Insertando...")
            upsert_videos(sb, videos_nuevos_filtrados)
            print(f"[import_daily] Videos NUEVOS insertados: {len(videos_nuevos_filtrados)}")

            # Analizar miniaturas de videos nuevos
            thumbs_response = sb.table("video_thumbnail_analysis").select("video_id", count="exact").execute()
            analyzed_total = thumbs_response.count if thumbs_response.count else 0

            if analyzed_total < 120:
                analizar_restantes = 120 - analyzed_total
                analizar_videos = videos_nuevos_filtrados[:analizar_restantes]
                analyze_and_save_thumbnails(sb, analizar_videos)
                print(f"[import_daily] Videos analizados a fondo: {len(analizar_videos)}")

            return  # Si encontramos videos nuevos, terminamos aquí

        print("[import_daily] No hay videos nuevos.")

        # PASO 2: BUSCAR VIDEOS ANTIGUOS (solo si NO hay nuevos)
        print("[import_daily] PASO 2: Buscando videos ANTIGUOS...")
        oldest_video_response = sb.table("videos").select("published_at").order("published_at", desc=False).limit(1).execute()

        published_before = None
        if oldest_video_response.data:
            # Buscar ANTES del más antiguo (hacia atrás en el tiempo)
            oldest_date = oldest_video_response.data[0]["published_at"]
            from datetime import datetime
            published_before = datetime.fromisoformat(oldest_date.replace('Z', '+00:00'))
            print(f"[import_daily] Buscando videos publicados ANTES de: {published_before.isoformat()}")

        # Obtener hasta 50 videos antiguos
        videos_antiguos = fetch_videos_with_pagination(yt, channel_id, published_before, max_results=50)

        # Filtrar los que ya están en Supabase
        new_videos = [v for v in videos_antiguos if v["video_id"] not in existing_ids]

        if not new_videos:
            print("[import_daily] No hay videos antiguos nuevos para insertar.")
            print(f"[import_daily] Total de videos en Supabase: {len(existing_ids)}")
            return

        # Insertar nuevos videos
        upsert_videos(sb, new_videos)
        print(f"[import_daily] Vídeos insertados: {len(new_videos)}")

        # Contar cuántos análisis de miniaturas ya existen
        thumbs_response = sb.table("video_thumbnail_analysis").select("video_id", count="exact").execute()
        analyzed_total = thumbs_response.count if thumbs_response.count else 0
        
        # Analizar solo si no hemos alcanzado el límite de 120
        if analyzed_total < 120:
            analizar_restantes = 120 - analyzed_total
            analizar_videos = new_videos[:analizar_restantes]
            analyze_and_save_thumbnails(sb, analizar_videos)
            print(f"[import_daily] Videos analizados a fondo: {len(analizar_videos)}")
        else:
            print("[import_daily] Límite de 120 análisis profundos ya alcanzado.")

    except Exception as e:
        print(f"[import_daily] ERROR CRÍTICO: {str(e)}")
        sys.exit(0)  # Siempre termina con código 0

if __name__ == "__main__":
    main()
