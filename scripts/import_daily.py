#!/usr/bin/env python3
"""
import_daily.py
Trae hasta DAILY_VIDEO_BATCH vídeos nuevos de YouTube y los guarda en Supabase.
"""

import os
from datetime import datetime
import pytz
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

def load_env():
    # Carga variables de entorno
    load_dotenv()
    # Credenciales de YouTube
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    # Supabase
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    # Batch diario
    batch = int(os.environ.get("DAILY_VIDEO_BATCH") or 20)
    # ID de tu canal (añadido como secret en GitHub)
    channel_id = os.environ["CHANNEL_ID"]
    return creds, supabase_url, supabase_key, batch, channel_id

def init_clients(creds, supabase_url, supabase_key):
    # Inicializa cliente de YouTube y Supabase
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def get_today_window():
    # Calcula “inicio de día” y “ahora” en hora Lima
    tz = pytz.timezone("America/Lima")
    now = datetime.now(tz)
    midnight = tz.localize(datetime(now.year, now.month, now.day))
    return midnight, now

def fetch_videos(yt, channel_id, published_after, max_results):
    # Pide la lista de vídeos publicados tras published_after
    req = yt.search().list(
        part="id",
        channelId=channel_id,
        publishedAfter=published_after.isoformat(),
        order="date",
        type="video",
        maxResults=max_results,
    )
    resp = req.execute()
    return [item["id"]["videoId"] for item in resp.get("items", [])]

def upsert_videos(sb: Client, video_ids):
    # Inserta o actualiza los registros en la tabla videos
    rows = [{"video_id": vid, "imported_at": "now()"} for vid in video_ids]
    sb.table("videos").upsert(rows, on_conflict=["video_id"]).execute()

def main():
    # 1) Carga configuración y entornos
    creds, supabase_url, supabase_key, batch, channel_id = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    start, end = get_today_window()

    # 2) Trae vídeos nuevos de hoy
    videos = fetch_videos(yt, channel_id=channel_id,
                          published_after=start, max_results=batch)

    # 3) (Opcional) completar con backlog si videos < batch
    #    …a implementar más adelante…

    # 4) Guardar en Supabase
    if videos:
        upsert_videos(sb, videos)

    # 5) Informe en consola
    print(f"[import_daily] Vídeos procesados: {len(videos)}")

if __name__ == "__main__":
    main()

