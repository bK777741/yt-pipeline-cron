#!/usr/bin/env python3
"""
fetch_monetization_metrics.py
Recoge métricas de monetización.
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

def fetch_monetization(yt_analytics, video_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        report = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=today,
            # FIX 2025-11-01: Eliminadas métricas inválidas (impressions, impressionCtr, averageCpm)
            # Usando solo métricas válidas de YouTube Analytics API v2
            metrics="views,estimatedRevenue,monetizedPlaybacks,playbackBasedCpm,adImpressions",
            filters=f"video=={video_id}"
        ).execute()
        return report.get("rows", [])[0] if report.get("rows") else None
    except Exception as e:
        print(f"Error fetching monetization: {e}")
        return None

def save_monetization(sb, video_id, data):
    # FORZADO 2025-10-31: on_conflict STRING format
    # FIX 2025-11-01: Actualizado para nuevas métricas (views, estimatedRevenue, monetizedPlaybacks, playbackBasedCpm, adImpressions)
    payload = {
        "video_id": video_id,
        "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "views": data[0],
        "estimated_revenue": data[1],
        "monetized_playbacks": data[2],
        "playback_based_cpm": data[3],
        "ad_impressions": data[4]
    }
    # CRÍTICO: "col1,col2" NO ["col1","col2"]
    sb.table("video_analytics").upsert(payload, on_conflict="video_id,snapshot_date").execute()

def main():
    creds, supabase_url, supabase_key = load_env()
    yt_analytics, sb = init_clients(creds, supabase_url, supabase_key)
    
    resp = sb.table("videos").select("video_id").order("imported_at", desc=True).limit(20).execute()
    video_ids = [row["video_id"] for row in resp.data]
    
    for vid in video_ids:
        data = fetch_monetization(yt_analytics, vid)
        if data:
            save_monetization(sb, vid, data)
    
    print(f"[fetch_monetization_metrics] Datos guardados: {len(video_ids)}")

if __name__ == "__main__":
    main()
