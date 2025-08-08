#!/usr/bin/env python3
"""
import_daily.py
Trae vídeos nuevos de YouTube y guarda hashtags + duración.
"""
import os
import re
from datetime import datetime
import pytz
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client
from googleapiclient.errors import HttpError  # Importar para manejar cuotas

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
                "description": item["snippet"]["description"],
                "hashtags": extract_hashtags(item["snippet"]["description"]),
                "duration": item["contentDetails"]["duration"]
            }
            for item in details_resp.get("items", [])
        ]
    return []

def upsert_videos(sb: Client, videos):
    rows = []
    for video in videos:
        rows.append({
            "video_id": video["video_id"],
            "hashtags": video["hashtags"],
            "duration": video["duration"],
            "imported_at": "now()"
        })
    sb.table("videos").upsert(rows, on_conflict=["video_id"]).execute()

def main():
    creds, supabase_url, supabase_key, batch, channel_id = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    start, end = get_today_window()
    
    videos = fetch_videos(yt, channel_id, start, batch)
    
    if videos:
        upsert_videos(sb, videos)
    
    print(f"[import_daily] Vídeos procesados: {len(videos)}")

if __name__ == "__main__":
    main()
