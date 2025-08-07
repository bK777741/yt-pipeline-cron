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
    # Carga variables de entorno desde .env (o desde GitHub Secrets en Actions)
    load_dotenv()

    # Credenciales de YouTube desde variables de entorno
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )

    # URL y clave de Supabase desde variables de entorno
    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]

    # Número de vídeos a traer por día (default 20)
    batch = int(os.environ.get("DAILY_VIDEO_BATCH") or 20)

    # ID de tu canal de YouTube:
    # se intenta leer CHANNEL_ID, pero si no existe, usa directamente este valor:
    DEFAULT_CHANNEL_ID = "UCWkGLaq5XxtF_r-0DKGZh4A"
    channel_id = os.environ.get("CHANNEL_ID") or DEFAULT_CHANNEL_ID

    return creds, supabase_url, supabase_key, batch, channel_id

def init_clients(creds, supabase_url, supabase_key):
    # Inicializa cliente de YouTube y de Supabase
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def get_today_window():
    # Calcula el rango de “hoy” en zona America/Lima
    tz = pytz.timezone("America/Lima")
    now = datetime.now(tz)
    midnight = tz.localize(datetime(now.year, now.month, now.day))
    return midnight, now

def fetch_videos(yt, channel_id, published_after, max_results):
    # Llama a la API de YouTube para buscar vídeos publicados tras `published_after`
    req = yt.search().list(
        part="id",
        channelId=channel_id,
        publishedAfter=published_after.isoformat(),
        order="date",
        type="video",
        maxResults=max_results,
    )
    resp = req.execute()
    # Devuelve lista de IDs de vídeo
    return [item["id"]["videoId"] for item in resp.get("items", [])]

def upsert_videos(sb: Client, video_ids):
    # Inserta o actualiza registros en la tabla "videos" de Supabase
    rows = [{"video_id": vid, "imported_at": "now()"} for vid in video_ids]
    sb.table("videos").upsert(rows, on_conflict=["video_id"]).execute()

def main():
    # 1) Carga configuración
    creds, supabase_url, supabase_key, batch, channel_id = load_env()
    # 2) Inicializa clientes
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    # 3) Calcula ventana de hoy
    start, end = get_today_window()

    # 4) Trae vídeos nuevos de hoy
    videos = fetch_videos(
        yt,
        channel_id=channel_id,
        published_after=start,
        max_results=batch
    )

    # 5) (Opcional) lógica de backlog si videos < batch
    #    …a implementar después…

    # 6) Inserta/actualiza en Supabase
    if videos:
        upsert_videos(sb, videos)

    # 7) Informe en consola
    print(f"[import_daily] Vídeos procesados: {len(videos)}")

if __name__ == "__main__":
    main()
