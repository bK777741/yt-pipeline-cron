#!/usr/bin/env python3
"""
fetch_search_trends.py
Recoge tendencias de búsqueda en Latinoamérica usando YouTube Trending.
ACTUALIZADO: 2025-11-05 - Eliminada dependencia de pytrends (Error 404)
"""
import os
import sys
import time
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client
from googleapiclient.errors import HttpError

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

REGIONS = {
    "latam-pe": "PE",
    "latam-mx": "MX",
    "latam-ar": "AR",
    "latam-co": "CO",
    "latam-cl": "CL",
    "hispanic": "ES",
    "global": "US"
}

MAX_TRENDING_VIDEOS = 20  # Videos trending a extraer por región

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
    channel_name = os.environ["CHANNEL_NAME"].strip()
    return creds, supabase_url, supabase_key, channel_name

def fetch_youtube_trending(yt, region, max_results=20):
    """
    Obtiene videos trending de YouTube para una región.
    Retorna lista de títulos de videos trending.
    """
    try:
        req = yt.videos().list(
            part="snippet",
            chart="mostPopular",
            regionCode=region,
            maxResults=max_results,
            videoCategoryId="28"  # Categoría 28 = Science & Technology
        )
        response = req.execute()

        # Extraer títulos de videos trending
        trending_titles = []
        for item in response.get("items", []):
            title = item["snippet"]["title"]
            trending_titles.append(title)

        return trending_titles
    except HttpError as e:
        if "quotaExceeded" in str(e):
            print(f"[fetch_search_trends] quotaExceeded para {region}", flush=True)
            return []
        else:
            print(f"[fetch_search_trends] Error HTTP para {region}: {e}", flush=True)
            return []

def save_trends(sb, titles, region):
    """
    Guarda títulos trending en la tabla search_trends.
    titles: lista de strings (títulos de videos)
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inserted_count = 0
    skipped_count = 0

    for idx, title in enumerate(titles):
        # Check si ya existe
        existing = sb.table("search_trends") \
            .select("id") \
            .eq("search_query", title) \
            .eq("run_date", today) \
            .eq("region", region) \
            .execute()

        if not existing.data:
            try:
                payload = {
                    "search_query": title,
                    "run_date": today,
                    "region": region,
                    "rank": idx + 1
                }
                sb.table("search_trends").insert(payload).execute()
                inserted_count += 1
            except Exception as e:
                print(f"[fetch_search_trends] ERROR insertando '{title}': {e}", flush=True)
        else:
            skipped_count += 1

    print(f"[fetch_search_trends] Region '{region}': {inserted_count} insertados, {skipped_count} ya existían", flush=True)
    return inserted_count

def main():
    print("[fetch_search_trends] Iniciando...", flush=True)

    creds, supabase_url, supabase_key, channel_name = load_env()
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)

    total_inserted = 0
    total_regions_processed = 0

    # Obtener tendencias de YouTube por región
    for region_name, region_code in REGIONS.items():
        print(f"\n[fetch_search_trends] Procesando región: {region_name} ({region_code})", flush=True)

        # Obtener videos trending de YouTube
        trending_titles = fetch_youtube_trending(yt, region_code, MAX_TRENDING_VIDEOS)

        if trending_titles:
            print(f"[fetch_search_trends] YouTube Trending: {len(trending_titles)} videos encontrados", flush=True)
            inserted = save_trends(sb, trending_titles, region_name)
            total_inserted += inserted
            total_regions_processed += 1
        else:
            print(f"[fetch_search_trends] YouTube Trending: 0 videos (posible cuota excedida o región sin datos)", flush=True)

        time.sleep(2)  # Respetar rate limits

    print(f"\n[fetch_search_trends] ✅ COMPLETADO: {total_regions_processed} regiones procesadas, {total_inserted} tendencias insertadas", flush=True)
    sys.stdout.flush()

if __name__ == "__main__":
    print("[fetch_search_trends] Script iniciado", flush=True)
    try:
        main()
    except Exception as e:
        print(f"[fetch_search_trends] ERROR FATAL: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
