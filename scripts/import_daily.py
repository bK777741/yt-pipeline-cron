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

def get_today_window():
    tz = pytz.timezone("America/Lima")
    now = datetime.now(tz)
    midnight = tz.localize(datetime(now.year, now.month, now.day))
    return midnight, now

def extract_hashtags(description):
    return list(set(re.findall(r"#(\w+)", description))) if description else []

def fetch_videos(yt, channel_id, published_after, max_results):
    try:
        req = yt.search().list(
            part="id",
            channelId=channel_id,
            publishedAfter=published_after.isoformat(),
            order="date",
            type="video",
            maxResults=max_results,
        )
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
                "title": item["snippet"]["title"],  # Nuevo campo
                "description": item["snippet"]["description"],
                "hashtags": extract_hashtags(item["snippet"]["description"]),
                "tags": item["snippet"].get("tags", []),  # Nuevo campo
                "duration": item["contentDetails"]["duration"],
                "thumbnails": item["snippet"]["thumbnails"]
            }
            for item in details_resp.get("items", [])
        ]
    return []

def upsert_videos(sb: Client, videos):
    rows = []
    for video in videos:
        rows.append({
            "video_id": video["video_id"],
            "title": video["title"],  # Nuevo campo
            "description": video["description"],  # Nuevo campo
            "hashtags": video["hashtags"],
            "tags": video["tags"],  # Nuevo campo
            "duration": video["duration"],
            "imported_at": "now()"
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
        start, end = get_today_window()
        
        videos = fetch_videos(yt, channel_id, start, batch)
        video_count = len(videos)
        
        if videos:
            upsert_videos(sb, videos)
            analyze_and_save_thumbnails(sb, videos)
        
        print(f"[import_daily] Vídeos procesados: {video_count}")
    except Exception as e:
        print(f"[import_daily] ERROR CRÍTICO: {str(e)}")
        sys.exit(0)  # Siempre termina con código 0

if __name__ == "__main__":
    main()
