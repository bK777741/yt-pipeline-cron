#!/usr/bin/env python3
"""
maint_metrics.py
Actualiza métricas de los últimos 50 vídeos importados.
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

def load_env():
    load_dotenv()
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

def fetch_recent_videos(sb: Client, limit: int = 50):
    resp = sb.table("videos") \
             .select("video_id") \
             .order("imported_at", desc=True) \
             .limit(limit) \
             .execute()
    return [row["video_id"] for row in resp.data]

def fetch_video_metrics(yt, video_id: str):
    req = yt.videos().list(part="statistics", id=video_id)
    resp = req.execute()
    if not resp.get("items"):
        return {}
    stats = resp["items"][0]["statistics"]
    return {
        "view_count": stats.get("viewCount"),
        "like_count": stats.get("likeCount"),
        "comment_count": stats.get("commentCount"),
    }

def upsert_metrics(sb: Client, video_id: str, metrics: dict):
    row = {"video_id": video_id, **metrics, "updated_at": "now()"}
    sb.table("video_statistics").upsert(row, on_conflict=["video_id"]).execute()

def main():
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    vids = fetch_recent_videos(sb, limit=50)
    for vid in vids:
        m = fetch_video_metrics(yt, vid)
        if m:
            upsert_metrics(sb, vid, m)

    print(f"[maint_metrics] Métricas actualizadas para {len(vids)} vídeos")

if __name__ == "__main__":
    main()
