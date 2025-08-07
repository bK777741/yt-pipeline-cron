#!/usr/bin/env python3
"""
fetch_trending_videos.py
Guarda vídeos en tendencia de Perú.
"""
import os
from datetime import datetime
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

def fetch_trending(yt, max_results=50):
    req = yt.videos().list(
        chart="mostPopular",
        regionCode="PE",
        maxResults=max_results,
        part="snippet,statistics,contentDetails"
    )
    return req.execute().get("items", [])

def save_trending(sb, videos):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for idx, video in enumerate(videos):
        snippet = video["snippet"]
        stats = video["statistics"]
        sb.table("video_trending").upsert({
            "video_id": video["id"],
            "run_date": today,
            "rank": idx + 1,
            "title": snippet["title"],
            "channel_title": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "view_count": stats.get("viewCount"),
            "like_count": stats.get("likeCount"),
            "comment_count": stats.get("commentCount"),
            "duration": video["contentDetails"]["duration"]
        }, on_conflict=["video_id", "run_date"]).execute()

def main():
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)
    
    videos = fetch_trending(yt)
    save_trending(sb, videos)
    
    print(f"[fetch_trending_videos] Trending videos guardados: {len(videos)}")

if __name__ == "__main__":
    main()
