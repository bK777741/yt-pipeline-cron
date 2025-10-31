#!/usr/bin/env python3
"""
fetch_search_trends.py
Recoge tendencias de búsqueda en Latinoamérica.
"""
import os
import time
from datetime import datetime, timezone
from pytrends.request import TrendReq
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client
from googleapiclient.errors import HttpError  # Importar para manejar cuotas

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
    for idx, item in enumerate(trends):
        query = item["snippet"]["title"]
        # FORZADO 2025-10-31: on_conflict STRING format
        payload = {
            "query": query,
            "run_date": today,
            "region": region,
            "rank": idx + 1
        }
        sb.table("search_trends").upsert(payload, on_conflict="query,run_date,region").execute()

def main():
    creds, supabase_url, supabase_key, channel_name = load_env()
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    pytrends = TrendReq()
    
    # Tendencias por región
    for region_name, region_code in REGIONS.items():
        # Búsquedas directas al canal
        channel_results = fetch_youtube_trends(yt, channel_name, region_code)
        if channel_results:
            save_trends(sb, channel_results, f"canal-{region_name}")
            time.sleep(2)
        
        # Tendencias generales
        try:
            trends_index = pytrends.trending_searches(pn=region_code)
        except Exception as e:
            print(f"[fetch_search_trends] Warning, fallo trending_searches({region_code}): {e}")
            continue
            
        trends_list = trends_index.tolist()
        # Guardar cada término como registro
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for idx, term in enumerate(trends_list):
            # FORZADO 2025-10-31: on_conflict STRING format
            payload = {
                "query": term,
                "run_date": today,
                "region": region_name,
                "rank": idx + 1
            }
            sb.table("search_trends").upsert(payload, on_conflict="query,run_date,region").execute()
        time.sleep(2)
    
    print("[fetch_search_trends] Tendencias guardadas")
