#!/usr/bin/env python3
"""
fetch_explosive_longs.py
Búsqueda activa de videos LARGOS con crecimiento explosivo del nicho

COSTO: 100 unidades API
FRECUENCIA: Cada 3 días
RESULTADO: 10-15 videos largos virales del nicho
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

# Importar utilidades de nicho
try:
    from nicho_utils import es_video_relevante, registrar_uso_cuota, debe_ejecutarse_hoy
    NICHO_FILTERING_ENABLED = True
except ImportError:
    print("[ERROR] nicho_utils.py requerido para este script")
    sys.exit(1)

# Keyword para búsqueda de videos largos explosivos
SEARCH_KEYWORD = "tutorial tech 2025"  # Keyword genérica para encontrar tutoriales recientes
MAX_RESULTS = 50
MIN_NICHO_SCORE = 15
MIN_DURATION_SECONDS = 180  # Mínimo 3 minutos para considerar "largo"

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
        trending = sb.table("video_trending").select("video_id").execute()
        videos = sb.table("videos").select("video_id").execute()

        existing_ids = set()
        if trending.data:
            existing_ids.update([row["video_id"] for row in trending.data])
        if videos.data:
            existing_ids.update([row["video_id"] for row in videos.data])

        print(f"[fetch_explosive_longs] Videos existentes en BD: {len(existing_ids)}")
        return existing_ids
    except Exception as e:
        print(f"[WARNING] Error obteniendo videos existentes: {e}")
        return set()

def search_explosive_longs(yt, max_results=50):
    """
    Buscar videos largos con crecimiento explosivo

    Costo: 100 unidades API
    """
    try:
        # Fecha límite: últimos 7 días (videos MUY recientes con explosión viral)
        published_after = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        request = yt.search().list(
            part="id,snippet",
            q=SEARCH_KEYWORD,
            type="video",
            videoDuration="medium",  # Videos medianos/largos (>4 min)
            publishedAfter=published_after,
            maxResults=max_results,
            order="viewCount",  # Ordenar por vistas (explosivos primero)
            relevanceLanguage="es"
        )

        response = request.execute()

        video_ids = []
        for item in response.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                video_ids.append(item["id"]["videoId"])

        print(f"[fetch_explosive_longs] Videos encontrados: {len(video_ids)}")
        return video_ids

    except Exception as e:
        print(f"[ERROR] Búsqueda fallida: {e}")
        return []

def get_video_details(yt, video_ids):
    """
    Obtener detalles de videos

    Costo: 1 unidad API por video
    """
    if not video_ids:
        return []

    videos = []

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

def calculate_vph(views, published_at):
    """Calcular views per hour (indicador de explosividad)"""
    try:
        pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        hours = (now - pub_date).total_seconds() / 3600
        if hours > 0:
            return views / hours
        return 0
    except:
        return 0

def filter_and_process_longs(videos, existing_ids, min_score=15, min_duration=180):
    """
    Filtrar videos largos por nicho, relevancia y explosividad

    Returns:
        Lista de videos largos válidos
    """
    valid_longs = []
    stats = {
        "total": len(videos),
        "duplicados": 0,
        "muy_cortos": 0,
        "bajo_score": 0,
        "baja_explosividad": 0,
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

        # 2. Verificar duración (debe ser video largo >3 min)
        duration_sec = parse_duration(content["duration"])
        if duration_sec < min_duration:
            stats["muy_cortos"] += 1
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

        # 4. Filtro de explosividad (VPH mínimo para considerar "explosivo")
        views = int(statistics.get("viewCount", 0))
        vph = calculate_vph(views, snippet["publishedAt"])

        # Mínimo 100 vph para considerar explosivo (ajustable)
        if vph < 100:
            stats["baja_explosividad"] += 1
            continue

        # 5. Video válido - preparar para inserción
        stats["validos"] += 1

        valid_longs.append({
            "video_id": video_id,
            "title": snippet["title"],
            "channel_id": snippet["channelId"],
            "channel_title": snippet["channelTitle"],
            "published_at": snippet["publishedAt"],
            "view_count": views,
            "like_count": int(statistics.get("likeCount", 0)),
            "comment_count": int(statistics.get("commentCount", 0)),
            "duration_sec": duration_sec,
            "nicho_score": nicho_score,
            "vph": vph,
            "search_source": "active_search_explosive"
        })

    print(f"\n[fetch_explosive_longs] 📊 FILTRADO:")
    print(f"  - Total procesados: {stats['total']}")
    print(f"  - Duplicados: {stats['duplicados']}")
    print(f"  - Muy cortos (<3 min): {stats['muy_cortos']}")
    print(f"  - Bajo score nicho: {stats['bajo_score']}")
    print(f"  - Baja explosividad (<100 vph): {stats['baja_explosividad']}")
    print(f"  - ✅ Válidos para insertar: {stats['validos']}")

    return valid_longs

def insert_longs_to_supabase(sb: Client, longs):
    """Insertar videos largos en video_trending"""
    if not longs:
        print("[fetch_explosive_longs] No hay videos para insertar")
        return

    today = datetime.now(timezone.utc).date().isoformat()
    inserted = 0

    for long_video in longs:
        try:
            sb.table("video_trending").insert({
                "video_id": long_video["video_id"],
                "run_date": today,
                "rank": 0,
                "title": long_video["title"],
                "channel_id": long_video["channel_id"],
                "channel_title": long_video["channel_title"],
                "published_at": long_video["published_at"],
                "view_count": long_video["view_count"],
                "like_count": long_video["like_count"],
                "comment_count": long_video["comment_count"],
                "duration_sec": long_video["duration_sec"],
                "format": "long",
                "similarity": 0.0,
                "topic_key": "tech_explosive",
                "region": "SEARCH"
            }).execute()

            inserted += 1

        except Exception as e:
            if "duplicate key" in str(e).lower():
                continue
            else:
                print(f"[WARNING] Error insertando {long_video['video_id']}: {e}")

    print(f"[fetch_explosive_longs] ✅ Videos insertados: {inserted}/{len(longs)}")

def main():
    print("[fetch_explosive_longs] 🚀 Iniciando búsqueda de videos largos explosivos...")

    # Cargar entorno
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    # Verificar frecuencia (cada 3 días)
    if not debe_ejecutarse_hoy("fetch_explosive_longs", sb):
        print("[fetch_explosive_longs] ⏭️ No debe ejecutarse hoy (frecuencia: cada 3 días)")
        sys.exit(0)

    # Obtener videos existentes
    existing_ids = get_existing_video_ids(sb)

    # Búsqueda de videos explosivos
    video_ids = search_explosive_longs(yt, MAX_RESULTS)

    # Obtener detalles
    videos = get_video_details(yt, video_ids)

    # Filtrar por nicho y explosividad
    valid_longs = filter_and_process_longs(videos, existing_ids, MIN_NICHO_SCORE, MIN_DURATION_SECONDS)

    # Insertar en Supabase
    insert_longs_to_supabase(sb, valid_longs)

    # Registrar cuota usada (100 search + N videos.list)
    total_units = 100 + len(video_ids)
    registrar_uso_cuota("search_explosive", total_units, sb)
    print(f"\n[fetch_explosive_longs] 📊 Cuota API usada: {total_units} unidades")

    # Registrar watermark
    try:
        sb.table("script_execution_log").upsert({
            "script_name": "fetch_explosive_longs",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "status": "success"
        }, on_conflict="script_name").execute()
    except Exception as e:
        print(f"[WARNING] Error registrando watermark: {e}")

    print(f"\n[fetch_explosive_longs] ✅ Proceso completado")
    print(f"  - Videos encontrados: {len(video_ids)}")
    print(f"  - Videos insertados: {len(valid_longs)}")
    print(f"  - Cuota usada: {total_units} unidades")

if __name__ == "__main__":
    main()
