#!/usr/bin/env python3
"""
maint_metrics.py
Actualiza métricas de los últimos 50 vídeos importados.
"""
import os
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

# Firma de versión para verificar en CI
REV = "maint_metrics REV=fix-on_conflict-STRING"

# on_conflict debe ser CADENA exacta
ON_CONFLICT = "video_id,snapshot_date"

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

def fetch_recent_videos(sb: Client, limit: int = 50):
    # Toma los últimos videos por fecha de publicación
    resp = (
        sb.table("videos")
        .select("video_id")
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [row["video_id"] for row in resp.data if row.get("video_id")]

def fetch_video_metrics(yt, video_id: str):
    req = yt.videos().list(part="statistics", id=video_id)
    resp = req.execute()
    if not resp.get("items"):
        return {}

    stats = resp["items"][0]["statistics"]

    def safe_int(value):
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "view_count": safe_int(stats.get("viewCount")),
        "like_count": safe_int(stats.get("likeCount")),
        "comment_count": safe_int(stats.get("commentCount")),
    }

def upsert_metrics(sb: Client, video_id: str, metrics: dict, snapshot_date: str):
    row = {
        "video_id": video_id,
        "snapshot_date": snapshot_date,  # YYYY-MM-DD
        "view_count": metrics.get("view_count"),
        "like_count": metrics.get("like_count"),
        "comment_count": metrics.get("comment_count"),
    }
    # Uso explícito de cadena en on_conflict
    sb.table("video_statistics").upsert(row, on_conflict=ON_CONFLICT).execute()

def main():
    print(REV)
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    vids = fetch_recent_videos(sb, limit=50)
    snapshot_date = datetime.now(timezone.utc).date().isoformat()

    for vid in vids:
        m = fetch_video_metrics(yt, vid)
        if m:
            upsert_metrics(sb, vid, m, snapshot_date)

    print(f"[maint_metrics] Métricas actualizadas para {len(vids)} videos (snapshot: {snapshot_date})")

if __name__ == "__main__":
    main()
