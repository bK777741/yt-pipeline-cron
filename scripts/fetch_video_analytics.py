#!/usr/bin/env python3
"""
fetch_video_analytics.py
Recoge métricas avanzadas de retención y engagement.
"""
import os
from datetime import datetime, timezone
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
    yt_analytics = build("youtubeAnalytics", "v2", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt_analytics, sb

def fetch_analytics(yt_analytics, video_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        report = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=today,
            metrics="estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained",
            filters=f"video=={video_id}"
        ).execute()
        return report.get("rows", [])[0] if report.get("rows") else None
    except Exception as e:
        print(f"Error fetching analytics: {e}")
        return None

def save_analytics(sb, video_id, data):
    # FORZADO 2025-10-31: on_conflict debe ser STRING, NO lista
    payload = {
        "video_id": video_id,
        "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "estimated_minutes_watched": data[0],
        "average_view_duration": data[1],
        "average_view_percentage": data[2],
        "subscribers_gained": data[3]
    }
    # CRÍTICO: String format "col1,col2" NO lista ["col1","col2"]
    sb.table("video_analytics").upsert(payload, on_conflict="video_id,snapshot_date").execute()

def main():
    creds, supabase_url, supabase_key = load_env()
    yt_analytics, sb = init_clients(creds, supabase_url, supabase_key)
    
    # Obtener últimos 20 vídeos
    resp = sb.table("videos").select("video_id").order("imported_at", desc=True).limit(20).execute()
    video_ids = [row["video_id"] for row in resp.data]
    
    for vid in video_ids:
        data = fetch_analytics(yt_analytics, vid)
        if data:
            save_analytics(sb, vid, data)
    
    print(f"[fetch_video_analytics] Métricas guardadas: {len(video_ids)}")

if __name__ == "__main__":
    main()
