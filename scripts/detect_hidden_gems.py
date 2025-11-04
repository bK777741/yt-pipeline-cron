#!/usr/bin/env python3
"""
detect_hidden_gems.py
Detecta "minas de oro": canales PEQUEÑOS con videos EXPLOSIVOS

FILOSOFÍA:
- Canal de 5k subs con video de 500k views = ORO PURO
- Canal de 500k subs con video de 50k views = Normal
- Priorizar canales <50k subs con explosion_ratio >100

COSTO API: ~200 unidades/día
FRECUENCIA: Diaria
OUTPUT: Tabla hidden_gems

FIX 2025-11-04: Creado para detectar la VERDADERA mina de oro
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

# Importar utilidades
try:
    from nicho_utils import es_video_relevante, registrar_uso_cuota
    NICHO_FILTERING_ENABLED = True
except ImportError:
    print("[WARNING] nicho_utils.py no encontrado")
    NICHO_FILTERING_ENABLED = False

# CONFIGURACIÓN: Definición de "canal pequeño" y "explosión"
SMALL_CHANNEL_MAX_SUBS = 50000  # <50k subs = canal pequeño
MICRO_CHANNEL_MAX_SUBS = 10000  # <10k subs = micro canal (bonus extra)
NANO_CHANNEL_MAX_SUBS = 1000    # <1k subs = nano canal (jackpot)

MIN_EXPLOSION_RATIO = 100       # Video debe tener 100x más vistas de lo esperado
MIN_VIEWS_ABSOLUTE = 50000      # Mínimo 50k vistas absolutas (filtrar basura)
MAX_AGE_DAYS = 30               # Solo videos <30 días (momentum reciente)

# SEARCH KEYWORDS para encontrar videos del nicho
SEARCH_KEYWORDS = [
    "chatgpt tutorial español",
    "inteligencia artificial tutorial",
    "windows trucos 2025",
    "whatsapp trucos"
]

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

def search_recent_videos(yt, keyword, max_results=50):
    """
    Buscar videos recientes por keyword
    Costo: 100 unidades
    """
    try:
        published_after = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).isoformat()

        request = yt.search().list(
            part="id,snippet",
            q=keyword,
            type="video",
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

        return video_ids
    except Exception as e:
        print(f"[detect_hidden_gems] ❌ Error searching for '{keyword}': {e}")
        return []

def get_video_details(yt, video_ids):
    """
    Obtener detalles completos de videos
    Costo: 1 unidad por cada 50 videos
    """
    if not video_ids:
        return []

    try:
        # YouTube API permite hasta 50 IDs por request
        chunks = [video_ids[i:i+50] for i in range(0, len(video_ids), 50)]
        all_videos = []

        for chunk in chunks:
            request = yt.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(chunk)
            )
            response = request.execute()
            all_videos.extend(response.get("items", []))

        return all_videos
    except Exception as e:
        print(f"[detect_hidden_gems] ❌ Error getting video details: {e}")
        return []

def get_channel_stats(yt, channel_id):
    """
    Obtener estadísticas del canal (especialmente subscriber count)
    Costo: 1 unidad
    """
    try:
        request = yt.channels().list(
            part="statistics,snippet",
            id=channel_id
        )
        response = request.execute()

        if not response.get("items"):
            return None

        channel = response["items"][0]
        stats = channel["statistics"]
        snippet = channel["snippet"]

        return {
            "channel_id": channel_id,
            "channel_title": snippet.get("title", ""),
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
        }
    except Exception as e:
        print(f"[detect_hidden_gems] ⚠️ Error getting channel stats for {channel_id}: {e}")
        return None

def calculate_explosion_ratio(views, subscribers):
    """
    Calcular ratio de explosión

    FÓRMULA:
    explosion_ratio = views / (subscribers * avg_view_rate)

    avg_view_rate ≈ 0.05 (5% de suscriptores ven cada video)

    INTERPRETACIÓN:
    - ratio < 10: Video normal
    - ratio 10-50: Buen video
    - ratio 50-100: Video muy exitoso
    - ratio 100-500: VIDEO EXPLOSIVO 🔥
    - ratio > 500: MINA DE ORO ABSOLUTA 💎
    """
    if subscribers == 0:
        return 0

    # Promedio: 5% de suscriptores ven cada video
    avg_view_rate = 0.05
    expected_views = subscribers * avg_view_rate

    if expected_views == 0:
        return 0

    return views / expected_views

def classify_channel_size(subscribers):
    """Clasificar tamaño de canal"""
    if subscribers < NANO_CHANNEL_MAX_SUBS:
        return "nano"       # <1k
    elif subscribers < MICRO_CHANNEL_MAX_SUBS:
        return "micro"      # 1k-10k
    elif subscribers < SMALL_CHANNEL_MAX_SUBS:
        return "small"      # 10k-50k
    elif subscribers < 100000:
        return "medium"     # 50k-100k
    elif subscribers < 500000:
        return "large"      # 100k-500k
    else:
        return "huge"       # >500k

def parse_duration(duration_iso):
    """Parsear duración ISO 8601"""
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_iso)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def analyze_hidden_gems(yt, video_ids):
    """
    Analizar videos para detectar hidden gems
    """
    if not video_ids:
        return []

    print(f"[detect_hidden_gems] 🔍 Analizando {len(video_ids)} videos...")

    # Obtener detalles de videos
    videos = get_video_details(yt, video_ids)
    print(f"[detect_hidden_gems] 📊 Detalles obtenidos: {len(videos)} videos")

    # Obtener estadísticas de canales únicos
    channel_ids = list(set([v["snippet"]["channelId"] for v in videos]))
    print(f"[detect_hidden_gems] 👥 Canales únicos: {len(channel_ids)}")

    channel_stats = {}
    for channel_id in channel_ids:
        stats = get_channel_stats(yt, channel_id)
        if stats:
            channel_stats[channel_id] = stats

    print(f"[detect_hidden_gems] ✅ Estadísticas de canales obtenidas: {len(channel_stats)}")

    # Analizar cada video
    hidden_gems = []

    for video in videos:
        video_id = video["id"]
        snippet = video["snippet"]
        stats = video["statistics"]
        content = video["contentDetails"]

        channel_id = snippet["channelId"]
        if channel_id not in channel_stats:
            continue

        channel = channel_stats[channel_id]
        subscribers = channel["subscriber_count"]
        views = int(stats.get("viewCount", 0))

        # Filtro 1: Solo canales pequeños
        if subscribers > SMALL_CHANNEL_MAX_SUBS:
            continue

        # Filtro 2: Mínimo de vistas absolutas
        if views < MIN_VIEWS_ABSOLUTE:
            continue

        # Calcular explosion ratio
        explosion_ratio = calculate_explosion_ratio(views, subscribers)

        # Filtro 3: Ratio de explosión mínimo
        if explosion_ratio < MIN_EXPLOSION_RATIO:
            continue

        # Filtrar por relevancia al nicho (si está habilitado)
        if NICHO_FILTERING_ENABLED:
            es_relevante, nicho_score = es_video_relevante(
                snippet.get("title", ""),
                snippet.get("description", ""),
                snippet.get("tags", [])
            )
            if nicho_score < 30:  # Umbral mínimo de relevancia
                continue
        else:
            nicho_score = 0

        # ¡ENCONTRAMOS UNA MINA DE ORO!
        channel_size = classify_channel_size(subscribers)
        duration_sec = parse_duration(content.get("duration", "PT0S"))

        hidden_gem = {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "channel_id": channel_id,
            "channel_title": channel["channel_title"],
            "channel_subscribers": subscribers,
            "channel_size": channel_size,
            "view_count": views,
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration_seconds": duration_sec,
            "published_at": snippet.get("publishedAt", ""),
            "explosion_ratio": round(explosion_ratio, 2),
            "nicho_score": nicho_score,
            "tags": snippet.get("tags", []),
            "discovered_at": datetime.now(timezone.utc).isoformat()
        }

        hidden_gems.append(hidden_gem)

        # Log de hallazgo
        print(f"[detect_hidden_gems] 💎 MINA DE ORO: {channel['channel_title']} ({subscribers:,} subs)")
        print(f"    📹 Video: {snippet.get('title', '')[:60]}...")
        print(f"    👁️  Views: {views:,} | Ratio: {explosion_ratio:.1f}x | Tamaño: {channel_size}")

    return hidden_gems

def save_hidden_gems(sb: Client, gems):
    """Guardar hidden gems en Supabase"""
    if not gems:
        print("[detect_hidden_gems] ℹ️ No se encontraron hidden gems")
        return 0

    # Obtener IDs existentes para evitar duplicados
    try:
        existing = sb.table("hidden_gems").select("video_id").execute()
        existing_ids = {row["video_id"] for row in existing.data}
    except:
        existing_ids = set()

    # Filtrar duplicados
    new_gems = [g for g in gems if g["video_id"] not in existing_ids]

    if not new_gems:
        print(f"[detect_hidden_gems] ℹ️ Todos los {len(gems)} gems ya existen en la base de datos")
        return 0

    # Insertar nuevos gems
    try:
        sb.table("hidden_gems").insert(new_gems).execute()
        print(f"[detect_hidden_gems] ✅ Guardados {len(new_gems)} nuevos hidden gems")
        return len(new_gems)
    except Exception as e:
        print(f"[detect_hidden_gems] ❌ Error guardando hidden gems: {e}")
        return 0

def main():
    print("[detect_hidden_gems] 🚀 Iniciando detección de minas de oro (hidden gems)")
    print(f"[detect_hidden_gems] 🎯 Configuración:")
    print(f"  - Canal pequeño: <{SMALL_CHANNEL_MAX_SUBS:,} suscriptores")
    print(f"  - Explosión mínima: {MIN_EXPLOSION_RATIO}x")
    print(f"  - Views mínimas: {MIN_VIEWS_ABSOLUTE:,}")
    print(f"  - Edad máxima: {MAX_AGE_DAYS} días")

    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    all_video_ids = []
    api_calls = 0

    # Buscar videos por cada keyword
    for keyword in SEARCH_KEYWORDS:
        print(f"\n[detect_hidden_gems] 🔎 Buscando: '{keyword}'")
        video_ids = search_recent_videos(yt, keyword, max_results=50)
        all_video_ids.extend(video_ids)
        api_calls += 1  # search.list = 100 unidades

        print(f"[detect_hidden_gems]   Encontrados: {len(video_ids)} videos")

    # Eliminar duplicados
    all_video_ids = list(set(all_video_ids))
    print(f"\n[detect_hidden_gems] 📊 Total de videos únicos: {len(all_video_ids)}")

    # Analizar videos
    hidden_gems = analyze_hidden_gems(yt, all_video_ids)
    api_calls += len(all_video_ids) // 50 + 1  # videos.list
    api_calls += len(set([g["channel_id"] for g in hidden_gems]))  # channels.list

    # Guardar en base de datos
    saved_count = save_hidden_gems(sb, hidden_gems)

    # Registrar uso de cuota
    estimated_api_units = api_calls * 100  # Estimado conservador
    if NICHO_FILTERING_ENABLED:
        registrar_uso_cuota("detect_hidden_gems", estimated_api_units, sb)

    print(f"\n[detect_hidden_gems] ✅ COMPLETADO:")
    print(f"  - Videos analizados: {len(all_video_ids)}")
    print(f"  - Hidden gems encontrados: {len(hidden_gems)}")
    print(f"  - Nuevos gems guardados: {saved_count}")
    print(f"  - Cuota API usada: ~{estimated_api_units} unidades")

if __name__ == "__main__":
    main()
