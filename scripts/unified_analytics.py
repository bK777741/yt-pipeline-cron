#!/usr/bin/env python3
"""
unified_analytics.py
Consolidación de fetch_video_analytics + fetch_monetization_metrics
Captura TODAS las métricas en una sola ejecución optimizada.

FIX 2025-11-04: Consolidado para evitar duplicación y optimizar ejecución
Incluye: retención, engagement, monetización, CTR, tráfico sources
"""
import os
from datetime import datetime, timezone, timedelta
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

def fetch_complete_analytics(yt_analytics, video_id):
    """
    Obtiene TODAS las métricas en una sola llamada optimizada.
    Incluye: retención, engagement, monetización, CTR
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        # MÉTRICAS COMPLETAS (todas las que importan para tu visión)
        metrics = ",".join([
            # Engagement y retención
            "views",
            "estimatedMinutesWatched",
            "averageViewDuration",
            "averageViewPercentage",

            # Suscriptores
            "subscribersGained",
            "subscribersLost",

            # Likes y engagement
            "likes",
            "dislikes",
            "comments",
            "shares",

            # Monetización
            "estimatedRevenue",
            "monetizedPlaybacks",
            "playbackBasedCpm",
            "adImpressions",

            # Impresiones y CTR (CRÍTICO para tu visión)
            "cardImpressions",
            "cardClicks",
            "cardClickRate",
        ])

        report = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",  # Lifetime
            endDate=today,
            metrics=metrics,
            filters=f"video=={video_id}"
        ).execute()

        rows = report.get("rows", [])
        if not rows:
            return None

        data = rows[0]

        # Empaquetar en diccionario para claridad
        return {
            # Engagement
            "views": data[0] if len(data) > 0 else 0,
            "estimated_minutes_watched": data[1] if len(data) > 1 else 0,
            "average_view_duration": data[2] if len(data) > 2 else 0,
            "average_view_percentage": data[3] if len(data) > 3 else 0,

            # Suscriptores
            "subscribers_gained": data[4] if len(data) > 4 else 0,
            "subscribers_lost": data[5] if len(data) > 5 else 0,

            # Likes
            "likes": data[6] if len(data) > 6 else 0,
            "dislikes": data[7] if len(data) > 7 else 0,
            "comments": data[8] if len(data) > 8 else 0,
            "shares": data[9] if len(data) > 9 else 0,

            # Monetización
            "estimated_revenue": data[10] if len(data) > 10 else 0,
            "monetized_playbacks": data[11] if len(data) > 11 else 0,
            "playback_based_cpm": data[12] if len(data) > 12 else 0,
            "ad_impressions": data[13] if len(data) > 13 else 0,

            # CTR
            "card_impressions": data[14] if len(data) > 14 else 0,
            "card_clicks": data[15] if len(data) > 15 else 0,
            "card_click_rate": data[16] if len(data) > 16 else 0,
        }
    except Exception as e:
        print(f"[unified_analytics] ❌ Error fetching analytics for {video_id}: {e}")
        return None

def fetch_traffic_sources(yt_analytics, video_id):
    """
    NUEVO: Obtiene fuentes de tráfico (de dónde vienen las vistas)
    CRÍTICO para entender qué está funcionando
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    try:
        report = yt_analytics.reports().query(
            ids="channel==MINE",
            startDate=thirty_days_ago,
            endDate=today,
            metrics="views,estimatedMinutesWatched",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}",
            sort="-views"
        ).execute()

        return report.get("rows", [])
    except Exception as e:
        print(f"[unified_analytics] ⚠️ Traffic sources not available for {video_id}: {e}")
        return []

def save_complete_analytics(sb, video_id, analytics_data, traffic_data):
    """
    Guarda TODAS las métricas en video_analytics (tabla consolidada)
    """
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Preparar traffic sources como JSONB
    traffic_sources = []
    if traffic_data:
        for row in traffic_data:
            traffic_sources.append({
                "source_type": row[0] if len(row) > 0 else "UNKNOWN",
                "views": row[1] if len(row) > 1 else 0,
                "watch_time_minutes": row[2] if len(row) > 2 else 0
            })

    payload = {
        "video_id": video_id,
        "snapshot_date": snapshot_date,

        # Engagement
        "views": analytics_data.get("views", 0),
        "estimated_minutes_watched": analytics_data.get("estimated_minutes_watched", 0),
        "average_view_duration": analytics_data.get("average_view_duration", 0),
        "average_view_percentage": analytics_data.get("average_view_percentage", 0),

        # Suscriptores
        "subscribers_gained": analytics_data.get("subscribers_gained", 0),
        "subscribers_lost": analytics_data.get("subscribers_lost", 0),

        # Engagement social
        "likes": analytics_data.get("likes", 0),
        "dislikes": analytics_data.get("dislikes", 0),
        "comments_count": analytics_data.get("comments", 0),
        "shares": analytics_data.get("shares", 0),

        # Monetización
        "estimated_revenue": analytics_data.get("estimated_revenue", 0),
        "monetized_playbacks": analytics_data.get("monetized_playbacks", 0),
        "playback_based_cpm": analytics_data.get("playback_based_cpm", 0),
        "ad_impressions": analytics_data.get("ad_impressions", 0),

        # CTR
        "card_impressions": analytics_data.get("card_impressions", 0),
        "card_clicks": analytics_data.get("card_clicks", 0),
        "card_click_rate": analytics_data.get("card_click_rate", 0),

        # Traffic sources (JSONB)
        "traffic_sources": traffic_sources if traffic_sources else None,
    }

    try:
        sb.table("video_analytics").upsert(
            payload,
            on_conflict="video_id,snapshot_date"
        ).execute()
        print(f"[unified_analytics] ✅ Saved analytics for {video_id}")
    except Exception as e:
        print(f"[unified_analytics] ❌ Error saving analytics for {video_id}: {e}")

def main():
    print("[unified_analytics] 🚀 Iniciando captura unificada de analytics")

    creds, supabase_url, supabase_key = load_env()
    yt_analytics, sb = init_clients(creds, supabase_url, supabase_key)

    # Obtener videos recientes para analizar
    # Por defecto: últimos 30 videos (ajustable)
    limit = int(os.environ.get("ANALYTICS_VIDEO_LIMIT", "30"))

    resp = sb.table("videos").select("video_id, title") \
        .order("published_at", desc=True) \
        .limit(limit) \
        .execute()

    video_ids = [(row["video_id"], row.get("title", "")) for row in resp.data]

    print(f"[unified_analytics] 📊 Procesando {len(video_ids)} videos...")

    success_count = 0
    for video_id, title in video_ids:
        # Capturar analytics completos
        analytics_data = fetch_complete_analytics(yt_analytics, video_id)

        if not analytics_data:
            print(f"[unified_analytics] ⚠️ No data for {video_id} ({title[:50]})")
            continue

        # Capturar traffic sources
        traffic_data = fetch_traffic_sources(yt_analytics, video_id)

        # Guardar todo
        save_complete_analytics(sb, video_id, analytics_data, traffic_data)
        success_count += 1

    print(f"[unified_analytics] ✅ COMPLETADO: {success_count}/{len(video_ids)} videos procesados")
    print(f"[unified_analytics] 💰 Cuota API usada: 0 unidades (YouTube Analytics API es gratis)")

if __name__ == "__main__":
    main()
