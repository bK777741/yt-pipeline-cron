#!/usr/bin/env python3
"""
import_captions.py
Descarga subtítulos de vídeos nuevos.
"""
import os
import time
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

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
    threshold = datetime.utcnow() - timedelta(minutes=15)
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
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    
    video_ids = fetch_recent_videos(sb)
    for vid in video_ids:
        caption_text = download_caption(yt, vid)
        if caption_text:
            upsert_caption(sb, vid, caption_text)
            time.sleep(1)  # Evitar rate limits
    
    print(f"[import_captions] Subtítulos procesados: {len(video_ids)}")

if __name__ == "__main__":
    main()
