#!/usr/bin/env python3
"""
import_captions.py
Descarga subtítulos de vídeos nuevos.
OPTIMIZADO: Límite de 2 videos/día para ahorrar cuota API
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

# Importar funciones de control de cuota
try:
    from nicho_utils import debe_ejecutarse_hoy, registrar_uso_cuota
    QUOTA_TRACKING_ENABLED = True
except ImportError:
    print("[WARNING] nicho_utils.py no encontrado - Control de cuota deshabilitado")
    QUOTA_TRACKING_ENABLED = False

# Límite diario de videos a procesar (ahorro de cuota)
MAX_VIDEOS_PER_DAY = 2

def load_env():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        client_id=os.environ["YT_CLIENT_ID"].strip(),
        client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
    )
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return creds, supabase_url, supabase_key

def init_clients(creds, supabase_url, supabase_key):
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def fetch_recent_videos(sb: Client):
    threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
    resp = sb.table("videos") \
             .select("video_id") \
             .gte("imported_at", threshold.isoformat()) \
             .execute()
    return [row["video_id"] for row in resp.data]

def download_caption(yt, video_id, language="es"):
    try:
        captions = yt.captions().list(part="id", videoId=video_id).execute()
        for item in captions.get("items", []):
            if item.get("snippet", {}).get("language") == language:
                caption = yt.captions().download(id=item["id"]).execute()
                return caption.decode("utf-8")
    except Exception as e:
        print(f"Error downloading caption: {e}")
    return None

def upsert_caption(sb: Client, video_id, text, language="es"):
    sb.table("captions").upsert({
        "video_id": video_id,
        "language": language,
        "caption_text": text,
        "imported_at": "now()"
    }, on_conflict=["video_id", "language"]).execute()

def main():
    # Control de frecuencia (ejecutar cada 3 días)
    if QUOTA_TRACKING_ENABLED:
        if not debe_ejecutarse_hoy("import_captions"):
            print("[import_captions] No debe ejecutarse hoy (frecuencia: cada 3 días)")
            print("[import_captions] Saltando ejecución para ahorrar cuota")
            sys.exit(0)

    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    video_ids = fetch_recent_videos(sb)

    # Limitar a MAX_VIDEOS_PER_DAY para ahorrar cuota
    if len(video_ids) > MAX_VIDEOS_PER_DAY:
        print(f"[import_captions] Limitando a {MAX_VIDEOS_PER_DAY} videos (de {len(video_ids)} disponibles)")
        video_ids = video_ids[:MAX_VIDEOS_PER_DAY]

    # Tracking de cuota API
    api_calls = 0
    captions_downloaded = 0

    for vid in video_ids:
        caption_text = download_caption(yt, vid)
        api_calls += 1  # captions().list = 50 unidades

        if caption_text:
            upsert_caption(sb, vid, caption_text)
            api_calls += 1  # captions().download = 200 unidades
            captions_downloaded += 1
            time.sleep(1)  # Evitar rate limits

    # Registrar cuota usada
    if QUOTA_TRACKING_ENABLED and api_calls > 0:
        # Costo estimado: list (50) + download (200) por video exitoso
        total_units = (captions_downloaded * 250)  # 50 + 200 por caption descargado
        registrar_uso_cuota("captions", total_units, sb)
        print(f"[import_captions] Cuota API usada: {total_units} unidades")

    print(f"[import_captions] Subtítulos procesados: {captions_downloaded}/{len(video_ids)}")

if __name__ == "__main__":
    main()
