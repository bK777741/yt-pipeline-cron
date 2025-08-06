#!/usr/bin/env python3
"""
import_daily.py
Trae hasta DAILY_VIDEO_BATCH vídeos nuevos de YouTube y los guarda en Supabase.
"""

import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

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
    batch = int(os.environ.get("DAILY_VIDEO_BATCH", 20))
    return creds, supabase_url, supabase_key, batch

def init_clients(creds, supabase_url, supabase_key):
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def get_today_window():
    tz = pytz.timezone("America/Lima")
    now = datetime.now(tz)
    midnight = tz.localize(datetime(now.year, now.month, now.day))
    return midnight, now

def fetch_videos(yt, published_after, max_results):
    req = yt.search().list(
        part="id",
        channelId="YOUR_CHANNEL_ID",  # ¡cambia esto!
        publishedAfter=published_after.isoformat(),
        order="date",
        type="video",
        maxResults=max_results,
    )
    resp = req.execute()
    video_ids = [item["id"]["videoId"] for item in resp.get("items", [])]
    return video_ids

def upsert_videos(sb: Client, video_ids):
    rows = [{"video_id": vid, "imported_at": "now()"} for vid in video_ids]
    sb.table("videos").upsert(rows, on_conflict=["video_id"]).execute()

def main():
    creds, supabase_url, supabase_key, batch = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    start, end = get_today_window()

    # 1) Traer vídeos nuevos de hoy
    videos = fetch_videos(yt, published_after=start, max_results=batch)

    # 2) Si faltan, completar con backlog (omitido por ahora)

    # 3) Guardar en Supabase
    if videos:
        upsert_videos(sb, videos)
    print(f"[import_daily] Vídeos procesados: {len(videos)}")

if __name__ == "__main__":
    main()

