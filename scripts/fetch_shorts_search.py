#!/usr/bin/env python3
"""
fetch_shorts_search.py
Búsqueda activa de shorts virales del nicho usando search.list API

COSTO: 340 unidades API (300 búsquedas + 40 stats)
FRECUENCIA: Cada 3 días
RESULTADO: 20-30 shorts nuevos del nicho
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

# Importar utilidades de nicho
# FIX 2025-11-07: Agregar scripts/ al path para que funcione en GitHub Actions
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from nicho_utils import es_video_relevante, registrar_uso_cuota, debe_ejecutarse_hoy
    NICHO_FILTERING_ENABLED = True
except ImportError as e:
    print(f"[ERROR] nicho_utils.py requerido para este script: {e}")
    sys.exit(1)

# Keywords estratégicas para búsqueda de shorts
SEARCH_KEYWORDS = [
    "chatgpt trucos",
    "windows tutorial",
    "ia gratis"
]

MAX_RESULTS_PER_KEYWORD = 50
MIN_NICHO_SCORE = 15

def load_env():
    """Cargar variables de entorno"""
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
    """Inicializar clientes de YouTube y Supabase"""
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def get_existing_video_ids(sb: Client):
    """Obtener IDs de videos ya en la base de datos para evitar duplicados"""
    try:
        # Verificar en video_trending
        trending = sb.table("video_trending").select("video_id").execute()
        # Verificar en videos (canal propio)
        videos = sb.table("videos").select("video_id").execute()

        existing_ids = set()
        if trending.data:
            existing_ids.update([row["video_id"] for row in trending.data])
        if videos.data:
            existing_ids.update([row["video_id"] for row in videos.data])

        print(f"[fetch_shorts_search] Videos existentes en BD: {len(existing_ids)}")
        return existing_ids
    except Exception as e:
        print(f"[WARNING] Error obteniendo videos existentes: {e}")
        return set()

def search_shorts(yt, keyword, max_results=50):
    """
    Buscar shorts con una keyword específica

    Costo: 100 unidades API por búsqueda
    """
    try:
        # Fecha límite: últimos 30 días
        published_after = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        request = yt.search().list(
            part="id,snippet",
            q=keyword,
            type="video",
            videoDuration="short",  # Solo shorts (<60s)
            publishedAfter=published_after,
            maxResults=max_results,
            order="viewCount",  # Ordenar por vistas (virales primero)
            relevanceLanguage="es"  # Priorizar español
        )

        response = request.execute()

        video_ids = []
        for item in response.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                video_ids.append(item["id"]["videoId"])

        print(f"[fetch_shorts_search] Keyword '{keyword}': {len(video_ids)} shorts encontrados")
        return video_ids

    except Exception as e:
        print(f"[ERROR] Búsqueda fallida para '{keyword}': {e}")
        return []

def get_video_details(yt, video_ids):
    """
    Obtener detalles de videos (stats, snippet, contentDetails)

    Costo: 1 unidad API por video
    """
    if not video_ids:
        return []

    videos = []

    # Procesar en lotes de 50 (límite de API)
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]

        try:
            request = yt.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch)
            )
            response = request.execute()

            for item in response.get("items", []):
                videos.append(item)

        except Exception as e:
            print(f"[ERROR] Error obteniendo detalles: {e}")
            continue

    return videos

def parse_duration(duration_iso):
    """Convertir duración ISO 8601 a segundos"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_iso)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def filter_and_process_shorts(videos, existing_ids, min_score=60):
    """
    Filtrar shorts por nicho y relevancia

    Returns:
        Lista de shorts válidos (nuevos, del nicho, sin duplicados)
    """
    valid_shorts = []
    stats = {
        "total": len(videos),
        "duplicados": 0,
        "no_short": 0,
        "bajo_score": 0,
        "validos": 0
    }

    for video in videos:
        video_id = video["id"]
        snippet = video["snippet"]
        content = video["contentDetails"]
        statistics = video.get("statistics", {})

        # 1. Verificar duplicados
        if video_id in existing_ids:
            stats["duplicados"] += 1
            continue

        # 2. Verificar que sea realmente un short (≤60s)
        duration_sec = parse_duration(content["duration"])
        if duration_sec > 60:
            stats["no_short"] += 1
            continue

        # 3. Filtro de nicho
        es_relevante, nicho_score = es_video_relevante(
            snippet["title"],
            snippet.get("description", ""),
            snippet.get("categoryId"),
            min_score=min_score
        )

        if not es_relevante:
            stats["bajo_score"] += 1
            continue

        # 4. Video válido - preparar para inserción
        stats["validos"] += 1

        valid_shorts.append({
            "video_id": video_id,
            "title": snippet["title"],
            "channel_id": snippet["channelId"],
            "channel_title": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0)),
            "comment_count": int(statistics.get("commentCount", 0)),
            "duration_sec": duration_sec,
            "nicho_score": nicho_score,
            "search_source": "active_search_shorts"
        })

    print(f"\n[fetch_shorts_search] 📊 FILTRADO:")
    print(f"  - Total procesados: {stats['total']}")
    print(f"  - Duplicados: {stats['duplicados']}")
    print(f"  - No shorts (>60s): {stats['no_short']}")
    print(f"  - Bajo score nicho: {stats['bajo_score']}")
    print(f"  - ✅ Válidos para insertar: {stats['validos']}")

    return valid_shorts

def insert_shorts_to_supabase(sb: Client, shorts):
    """Insertar shorts en video_trending"""
    if not shorts:
        print("[fetch_shorts_search] No hay shorts para insertar")
        return

    today = datetime.now(timezone.utc).date().isoformat()
    inserted = 0

    for short in shorts:
        try:
            # Insertar en video_trending
            sb.table("video_trending").insert({
                "video_id": short["video_id"],
                "run_date": today,
                "rank": 0,  # Búsqueda activa no tiene ranking
                "title": short["title"],
                "channel_id": short["channel_id"],
                "channel_title": short["channel_title"],
                "published_at": short["published_at"],
                "view_count": short["view_count"],
                "like_count": short["like_count"],
                "comment_count": short["comment_count"],
                "duration_sec": short["duration_sec"],
                "format": "short",
                "similarity": 0.0,
                "topic_key": "tech_shorts",
                "region": "SEARCH"
            }).execute()

            inserted += 1

        except Exception as e:
            # Ignorar errores de duplicados (unique constraint)
            if "duplicate key" in str(e).lower():
                continue
            else:
                print(f"[WARNING] Error insertando {short['video_id']}: {e}")

    print(f"[fetch_shorts_search] ✅ Shorts insertados: {inserted}/{len(shorts)}")

def main():
    print("[fetch_shorts_search] 🚀 Iniciando búsqueda activa de shorts...")

    # Cargar entorno
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    # Verificar frecuencia (cada 3 días)
    if not debe_ejecutarse_hoy("fetch_shorts_search", sb):
        print("[fetch_shorts_search] ⏭️ No debe ejecutarse hoy (frecuencia: cada 3 días)")
        sys.exit(0)

    # Obtener videos existentes para evitar duplicados
    existing_ids = get_existing_video_ids(sb)

    # Búsqueda de shorts con keywords estratégicas
    all_video_ids = []
    api_calls = 0

    for keyword in SEARCH_KEYWORDS:
        video_ids = search_shorts(yt, keyword, MAX_RESULTS_PER_KEYWORD)
        all_video_ids.extend(video_ids)
        api_calls += 1  # search.list = 100 unidades

    # Deduplicar IDs de búsqueda
    all_video_ids = list(set(all_video_ids))
    print(f"\n[fetch_shorts_search] Total shorts únicos encontrados: {len(all_video_ids)}")

    # Obtener detalles de videos
    videos = get_video_details(yt, all_video_ids)
    api_calls += len(all_video_ids)  # videos.list = 1 unidad por video

    # Filtrar por nicho y sin duplicados
    valid_shorts = filter_and_process_shorts(videos, existing_ids, MIN_NICHO_SCORE)

    # Insertar en Supabase
    insert_shorts_to_supabase(sb, valid_shorts)

    # Registrar cuota usada
    total_units = (len(SEARCH_KEYWORDS) * 100) + len(all_video_ids)
    registrar_uso_cuota("search_shorts", total_units, sb)
    print(f"\n[fetch_shorts_search] 📊 Cuota API usada: {total_units} unidades")

    # Registrar watermark (última ejecución)
    try:
        sb.table("script_execution_log").upsert({
            "script_name": "fetch_shorts_search",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "status": "success"
        }, on_conflict="script_name").execute()
    except Exception as e:
        print(f"[WARNING] Error registrando watermark: {e}")

    print(f"\n[fetch_shorts_search] ✅ Proceso completado")
    print(f"  - Keywords buscadas: {len(SEARCH_KEYWORDS)}")
    print(f"  - Shorts encontrados: {len(all_video_ids)}")
    print(f"  - Shorts insertados: {len(valid_shorts)}")
    print(f"  - Cuota usada: {total_units} unidades")

if __name__ == "__main__":
    main()
