#!/usr/bin/env python3
"""
fetch_search_trends.py
Recoge tendencias de búsqueda en Latinoamérica.
"""
import os
import sys
import time
from datetime import datetime, timezone
from pytrends.request import TrendReq
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client
from googleapiclient.errors import HttpError  # Importar para manejar cuotas

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

def fetch_youtube_trends(yt, query, region):
    try:
        req = yt.search().list(
            q=query,
            part="snippet",
            type="video",
            order="relevance",
            maxResults=20,
            regionCode=region
        )
        return req.execute().get("items", [])
    except HttpError as e:
        if "quotaExceeded" in str(e):
            print("[fetch_search_trends] quotaExceeded, salto")
            return []
        else:
            raise

def save_trends(sb, trends, region):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inserted_count = 0
    skipped_count = 0

    for idx, item in enumerate(trends):
        search_query = item["snippet"]["title"]

        # Check si ya existe
        existing = sb.table("search_trends") \
            .select("id") \
            .eq("search_query", search_query) \
            .eq("run_date", today) \
            .eq("region", region) \
            .execute()

        if not existing.data:
            payload = {
                "search_query": search_query,
                "run_date": today,
                "region": region,
                "rank": idx + 1
            }
            sb.table("search_trends").insert(payload).execute()
            inserted_count += 1
        else:
            skipped_count += 1

    print(f"[fetch_search_trends] Region '{region}': {inserted_count} insertados, {skipped_count} ya existían")

def main():
    print("[fetch_search_trends] Iniciando...", flush=True)

    creds, supabase_url, supabase_key, channel_name = load_env()
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    pytrends = TrendReq()

    total_inserted = 0
    total_regions_processed = 0

    # Tendencias por región
    for region_name, region_code in REGIONS.items():
        print(f"\n[fetch_search_trends] Procesando región: {region_name} ({region_code})")

        # Búsquedas directas al canal
        channel_results = fetch_youtube_trends(yt, channel_name, region_code)
        if channel_results:
            print(f"[fetch_search_trends] Canal: {len(channel_results)} resultados encontrados")
            save_trends(sb, channel_results, f"canal-{region_name}")
            time.sleep(2)
        else:
            print(f"[fetch_search_trends] Canal: 0 resultados (posible cuota excedida)")

        # Tendencias generales
        try:
            trends_index = pytrends.trending_searches(pn=region_code)
            trends_list = trends_index.tolist() if trends_index is not None else []

            if not trends_list:
                print(f"[fetch_search_trends] pytrends: 0 tendencias para {region_code}")
                continue

            print(f"[fetch_search_trends] pytrends: {len(trends_list)} tendencias encontradas")

        except Exception as e:
            print(f"[fetch_search_trends] ERROR en trending_searches({region_code}): {e}")
            continue

        # Guardar cada término como registro
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        inserted_count = 0
        skipped_count = 0

        for idx, term in enumerate(trends_list):
            # Check si ya existe
            existing = sb.table("search_trends") \
                .select("id") \
                .eq("search_query", str(term)) \
                .eq("run_date", today) \
                .eq("region", region_name) \
                .execute()

            if not existing.data:
                try:
                    payload = {
                        "search_query": str(term),
                        "run_date": today,
                        "region": region_name,
                        "rank": idx + 1
                    }
                    sb.table("search_trends").insert(payload).execute()
                    inserted_count += 1
                except Exception as e:
                    print(f"[fetch_search_trends] ERROR insertando '{term}': {e}")
            else:
                skipped_count += 1

        print(f"[fetch_search_trends] Region '{region_name}': {inserted_count} insertados, {skipped_count} ya existían")
        total_inserted += inserted_count
        total_regions_processed += 1
        time.sleep(2)

    print(f"\n[fetch_search_trends] ✅ COMPLETADO: {total_regions_processed} regiones procesadas, {total_inserted} tendencias insertadas")
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
