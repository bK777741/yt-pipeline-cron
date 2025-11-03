#!/usr/bin/env python3
"""
fetch_trending_videos.py
Guarda vídeos en tendencia multi-región con filtros avanzados.
"""
import os
import re
import json
import math
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import numpy as np
from googleapiclient.discovery import build
from supabase import create_client, Client
from postgrest.exceptions import APIError

# Importar funciones de filtrado por nicho
try:
    from nicho_utils import es_video_relevante, registrar_uso_cuota
    NICHO_FILTERING_ENABLED = True
except ImportError:
    print("[WARNING] nicho_utils.py no encontrado - Filtrado por nicho deshabilitado")
    NICHO_FILTERING_ENABLED = False

# Configuración global
STOPWORDS = set([
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para', 
    'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero', 'sus', 'le', 'ya', 'o', 'este', 
    'sí', 'porque', 'esta', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'también', 'me', 'hasta', 
    'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos', 'uno', 'les', 'ni', 
    'contra', 'otros', 'ese', 'eso', 'ante', 'ellos', 'e', 'esto', 'mí', 'antes', 'algunos', 
    'qué', 'unos', 'yo', 'otro', 'otras', 'otra', 'él', 'tanto', 'esa', 'estos', 'mucho', 'quienes', 
    'nada', 'muchos', 'cual', 'poco', 'ella', 'estar', 'estas', 'algunas', 'algo', 'nosotros', 
    'mi', 'mis', 'tú', 'te', 'ti', 'tu', 'tus', 'ellas', 'nosotras', 'vosotros', 'vosotras', 'os', 
    'mío', 'mía', 'míos', 'mías', 'tuyo', 'tuya', 'tuyos', 'tuyas', 'suyo', 'suya', 'suyos', 'suyas', 
    'nuestro', 'nuestra', 'nuestros', 'nuestras', 'vuestro', 'vuestra', 'vuestros', 'vuestras', 
    'esos', 'esas', 'estoy', 'estás', 'está', 'estamos', 'estáis', 'están', 'esté', 'estés', 'estemos', 
    'estéis', 'estén', 'estaré', 'estarás', 'estará', 'estaremos', 'estaréis', 'estarán', 'estaría', 
    'estarías', 'estaríamos', 'estaríais', 'estarían', 'estaba', 'estabas', 'estábamos', 'estabais', 
    'estaban', 'estuve', 'estuviste', 'estuvo', 'estuvimos', 'estuvisteis', 'estuvieron', 'estuviera', 
    'estuvieras', 'estuviéramos', 'estuvierais', 'estuvieran', 'estuviese', 'estuvieses', 'estuviésemos', 
    'estuvieseis', 'estuviesen', 'estando', 'estado', 'estada', 'estados', 'estadas', 'estad', 
    'he', 'has', 'ha', 'hemos', 'habéis', 'han', 'haya', 'hayas', 'hayamos', 'hayáis', 'hayan', 'habré', 
    'habrás', 'habrá', 'habremos', 'habréis', 'habrán', 'habría', 'habrías', 'habríamos', 'habríais', 
    'habrían', 'había', 'habías', 'habíamos', 'habíais', 'habían', 'hube', 'hubiste', 'hubo', 'hubimos', 
    'hubisteis', 'hubieron', 'hubiera', 'hubieras', 'hubiéramos', 'hubierais', 'hubieran', 'hubiese', 
    'hubieses', 'hubiésemos', 'hubieseis', 'hubiesen', 'habiendo', 'habido', 'habida', 'habidos', 'habidas', 
    'soy', 'eres', 'es', 'somos', 'sois', 'son', 'sea', 'seas', 'seamos', 'seáis', 'sean', 'seré', 'serás', 
    'será', 'seremos', 'seréis', 'serán', 'sería', 'serías', 'seríamos', 'seríais', 'serían', 'era', 'eras', 
    'éramos', 'erais', 'eran', 'fui', 'fuiste', 'fue', 'fuimos', 'fuisteis', 'fueron', 'fuera', 'fueras', 
    'fuéramos', 'fuerais', 'fueran', 'fuese', 'fueses', 'fuésemos', 'fueseis', 'fuesen', 'sintiendo', 
    'sentido', 'sentida', 'sentidos', 'sentidas', 'siente', 'sentid', 'tengo', 'tienes', 'tiene', 'tenemos', 
    'tenéis', 'tienen', 'tenga', 'tengas', 'tengamos', 'tengáis', 'tengan', 'tendré', 'tendrás', 'tendrá', 
    'tendremos', 'tendréis', 'tendrán', 'tendría', 'tendrías', 'tendríamos', 'tendríais', 'tendrían', 
    'tenía', 'tenías', 'teníamos', 'teníais', 'tenían', 'tuve', 'tuviste', 'tuvo', 'tuvimos', 'tuvisteis', 
    'tuvieron', 'tuviera', 'tuvieras', 'tuviéramos', 'tuvierais', 'tuvieran', 'tuviese', 'tuvieses', 
    'tuviésemos', 'tuvieseis', 'tuviesen', 'teniendo', 'tenido', 'tenida', 'tenidos', 'tenidas', 'tened'
])

def load_env():
    youtube_api_key = os.environ["YOUTUBE_API_KEY"].strip()
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    channel_id = os.environ["CHANNEL_ID"].strip()

    region_codes = [x.strip().upper() for x in os.getenv("REGION_CODES", "PE,MX,AR,CO,CL,ES,US,GB,IN,BR,PT").split(",") if x.strip()]
    allowed_langs = {x.strip().split("-")[0].lower() for x in os.getenv("ALLOWED_LANGS", "es,en,hi,pt").split(",") if x.strip()}
    long_min_seconds = int(os.getenv("LONG_MIN_SECONDS", 180))
    max_shorts = int(os.getenv("MAX_SHORTS_PER_DAY", 20))
    max_longs = int(os.getenv("MAX_LONGS_PER_DAY", 15))
    pages_per_region = int(os.getenv("PAGES_PER_REGION", 1))
    
    return (
        youtube_api_key, 
        supabase_url, 
        supabase_key, 
        channel_id,
        region_codes,
        allowed_langs,
        long_min_seconds,
        max_shorts,
        max_longs,
        pages_per_region
    )

def init_clients(youtube_api_key, supabase_url, supabase_key):
    yt = build("youtube", "v3", developerKey=youtube_api_key)
    sb = create_client(supabase_url, supabase_key)
    return yt, sb

def parse_iso8601_duration(duration):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def classify_format(duration_sec, long_min_seconds=180):
    if duration_sec <= 60:
        return "short"
    if duration_sec >= long_min_seconds:
        return "long"
    return "medium"  # intermedio

def tokenize(text):
    words = re.findall(r'\w+', text.lower())
    return [word for word in words if word not in STOPWORDS and len(word) > 2]

def build_channel_profile(sb, channel_id):
    res = sb.table("videos").select("title, description").eq("channel_id", channel_id).order("published_at", desc=True).limit(200).execute()
    videos = res.data
    
    all_text = " ".join(f"{v['title']} {v.get('description', '')}" for v in videos)
    words = tokenize(all_text)
    
    if not words:
        return {"keywords": set(), "similarity_threshold": 0.0}
    
    word_freq = Counter(words)
    top_words = {word for word, _ in word_freq.most_common(50)}
    
    similarities = []
    for video in videos:
        text = f"{video['title']} {video.get('description', '')}"
        video_words = set(tokenize(text))
        if not top_words:
            similarity = 0.0
        else:
            intersection = top_words & video_words
            union = top_words | video_words
            similarity = len(intersection) / len(union)
        similarities.append(similarity)
    
    similarities.sort()
    threshold = similarities[int(len(similarities) * 0.25)] if similarities else 0.1
    return {"keywords": top_words, "similarity_threshold": threshold}

def fetch_trending_page(yt, region, page_token=None, max_results=50):
    return yt.videos().list(
        chart="mostPopular",
        regionCode=region,
        maxResults=max_results,
        pageToken=page_token,
        part="snippet,statistics,contentDetails,status"
    ).execute()

def already_in_db(sb, video_id):
    today = datetime.now(timezone.utc).date().isoformat()
    res = sb.table("video_trending").select("video_id").eq("video_id", video_id).eq("run_date", today).execute()
    return len(res.data) > 0

def compute_vph(video_info):
    published_at = datetime.fromisoformat(
        video_info["published_at"].replace("Z", "+00:00")
    )
    now = datetime.now(timezone.utc)
    hours_since_pub = max(1, (now - published_at).total_seconds() / 3600.0)
    return int(video_info.get("view_count", 0) or 0) / hours_since_pub

def compute_engagement(video_info):
    likes = int(video_info.get("like_count", 0))
    comments = int(video_info.get("comment_count", 0))
    views = int(video_info["view_count"])
    return (likes + comments) / views if views > 0 else 0

def compute_score(video_info, format, channel_profile, region_count, freshness_hours, topic_counts):
    score = 0
    vph = video_info["vph"]
    eng = video_info["engagement"]
    
    # Base por formato
    base_scores = {"short": 6.0, "long": 4.0}
    score += base_scores.get(format, 3.0)
    
    # Viralidad
    viral_bonus = {
        "short": {"vph": 4.0, "eng": 2.0},
        "long": {"vph": 3.0, "eng": 3.0}
    }
    score += min(vph / 10000, 5) * viral_bonus[format]["vph"]
    score += min(eng * 100, 5) * viral_bonus[format]["eng"]
    
    # Similitud con nicho
    similarity = video_info["similarity"]
    score += similarity * 4.0
    
    # Multi-región
    score += min(region_count * 0.5, 2.0)
    
    # Frescura
    freshness_boost = {
        "short": max(0, 5 - freshness_hours / 3),
        "long": max(0, 3 - freshness_hours / 8)
    }
    score += freshness_boost[format]
    
    # Tamaño del canal
    if video_info["channel_subscribers"] < 100000:
        score += 2.0
    
    # Penalización por saturación de tema
    topic = video_info["topic_key"]
    penalty = min(topic_counts.get(topic, 0), 1.0) * 0.5
    score -= penalty
    
    return score

def topic_key_from_title(title):
    t = re.sub(r"[^a-záéíóúñü0-9\s]", " ", (title or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    return " ".join(t.split()[:8])

def process_video(video, region, channel_profile, allowed_langs, long_min_seconds):
    snippet = video["snippet"]
    stats = video.get("statistics", {})
    content = video["contentDetails"]
    
    # DESCARTAR lives/premieres
    if (snippet.get("liveBroadcastContent") or "none") != "none":
        return None
    
    # Filtrar por idioma (aceptar si no viene idioma)
    lang = (snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "").split("-")[0].lower()
    if lang and lang not in allowed_langs:
        return None
    
    # Duración y formato
    duration_sec = parse_iso8601_duration(content["duration"])
    video_format = classify_format(duration_sec, long_min_seconds)
    
    # Descartar formato medium
    if video_format not in ("short", "long"):
        return None
    
    # Tokenizar y calcular similitud
    text = f"{snippet['title']} {snippet.get('description', '')}"
    video_words = set(tokenize(text))
    
    if not channel_profile["keywords"]:
        similarity = 0.0
    else:
        intersection = channel_profile["keywords"] & video_words
        union = channel_profile["keywords"] | video_words
        similarity = len(intersection) / len(union) if union else 0.0
    
    if similarity < channel_profile["similarity_threshold"]:
        return None

    # Filtrado adicional por keywords de nicho
    # FIX 2025-11-03: Reducir min_score de 50 a 30 para detectar más videos relevantes
    if NICHO_FILTERING_ENABLED:
        es_relevante, nicho_score = es_video_relevante(
            snippet["title"],
            snippet.get("description", ""),
            snippet.get("categoryId"),
            min_score=30  # Score mínimo de relevancia (30 = más permisivo)
        )
        if not es_relevante:
            # Video filtrado por keywords (gaming, retos, etc.)
            return None

    return {
        "video_id": video["id"],
        "region": region,
        "title": snippet["title"],
        "channel_id": snippet["channelId"],
        "channel_title": snippet["channelTitle"],
        "published_at": snippet["publishedAt"],
        "view_count": stats.get("viewCount", 0),
        "like_count": stats.get("likeCount", 0),
        "comment_count": stats.get("commentCount", 0),
        "duration": content["duration"],
        "duration_sec": duration_sec,
        "format": video_format,
        "similarity": similarity,
        "topic_key": topic_key_from_title(snippet["title"]),
        "category_id": snippet.get("categoryId"),
        "tags": snippet.get("tags", [])
    }

def fetch_channel_stats(yt, channel_id):
    res = yt.channels().list(id=channel_id, part="statistics").execute()
    if not res.get("items"):
        return 0
    stats = res["items"][0]["statistics"]
    return int(stats.get("subscriberCount", 0))

def pct(values, p):
    if not values:
        return 0.0
    vs = sorted(values)
    i = max(0, min(len(vs) - 1, int(round((p / 100.0) * (len(vs) - 1)))))
    return vs[i]

def apply_dynamic_viral_filters(items):
    vph_s, eng_s, vph_l, eng_l = [], [], [], []
    
    # Calcular métricas SOLO para short/long
    for it in items:
        if it["format"] not in ("short", "long"):
            continue
        it["vph"] = compute_vph(it)
        it["engagement"] = compute_engagement(it)
        if it["format"] == "short":
            vph_s.append(it["vph"])
            eng_s.append(it["engagement"])
        elif it["format"] == "long":
            vph_l.append(it["vph"])
            eng_l.append(it["engagement"])
    
    # Calcular percentiles solo si hay datos
    thr = {
        "short": {
            "vph": pct(vph_s, 80) if vph_s else 0,
            "eng": pct(eng_s, 60) if eng_s else 0
        },
        "long": {
            "vph": pct(vph_l, 80) if vph_l else 0,
            "eng": pct(eng_l, 60) if eng_l else 0
        }
    }
    
    kept = []
    # Filtrar SOLO short/long que pasen umbrales
    for it in items:
        if it["format"] not in ("short", "long"):
            continue
        t = thr[it["format"]]
        if it["vph"] >= t["vph"] and it["engagement"] >= t["eng"]:
            kept.append(it)
            
    return kept, thr

def collect_candidates(yt, region_codes, pages_per_region, channel_profile, allowed_langs, long_min_seconds, needed_total):
    agg = {}  # video_id -> item con _regions
    for region in region_codes:
        next_page = None
        for _ in range(pages_per_region):
            response = fetch_trending_page(yt, region, next_page)
            videos = response.get("items", [])
            next_page = response.get("nextPageToken")
            
            for video in videos:
                video_info = process_video(
                    video, region, channel_profile, 
                    allowed_langs, long_min_seconds
                )
                
                if not video_info:
                    continue
                
                video_id = video_info["video_id"]
                base = agg.get(video_id)
                if not base:
                    video_info["_regions"] = {region}
                    agg[video_id] = video_info
                else:
                    base["_regions"].add(region)
            
            if not next_page or len(agg) >= needed_total:
                break
        if len(agg) >= needed_total:
            break
            
    return list(agg.values())

def select_top_candidates(candidates, max_shorts, max_longs):
    candidates.sort(key=lambda x: x["score"], reverse=True)
    
    selected = []
    shorts_count = 0
    longs_count = 0
    topic_counts = defaultdict(int)
    
    for candidate in candidates:
        topic = candidate["topic_key"]
        
        # Control diversidad
        if topic_counts[topic] >= 2:
            continue
            
        format = candidate["format"]
        
        # Cupos por formato
        if format == "short" and shorts_count < max_shorts:
            selected.append(candidate)
            shorts_count += 1
            topic_counts[topic] += 1
        elif format == "long" and longs_count < max_longs:
            selected.append(candidate)
            longs_count += 1
            topic_counts[topic] += 1
        # Cross-fill
        elif format == "short" and longs_count < max_longs:
            selected.append(candidate)
            longs_count += 1
            topic_counts[topic] += 1
        elif format == "long" and shorts_count < max_shorts:
            selected.append(candidate)
            shorts_count += 1
            topic_counts[topic] += 1
            
        # Early stop
        if len(selected) >= (max_shorts + max_longs) * 3:
            break
            
    return selected

def save_to_supabase(sb, videos):
    today = datetime.now(timezone.utc).date().isoformat()
    rows = []
    for i, v in enumerate(videos, start=1):
        rows.append({
            "video_id": v["video_id"],
            "run_date": today,
            "rank": i,
            "title": v["title"],
            "channel_title": v["channel_title"],
            "published_at": v["published_at"],
            "view_count": int(v.get("view_count", 0) or 0),
            "like_count": int(v.get("like_count", 0) or 0),
            "comment_count": int(v.get("comment_count", 0) or 0),
            "category_id": v.get("category_id"),
            "tags": v.get("tags", []),
            "duration": v["duration"],
        })

    # Intentar upsert con ignore_duplicates
    try:
        sb.table("video_trending").upsert(
            rows,
            on_conflict="video_id,run_date",
            ignore_duplicates=True
        ).execute()
        return
    except TypeError:
        pass  # Fallback si no soporta ignore_duplicates
    
    # Insertar uno por uno con pre-chequeo
    for row in rows:
        if not already_in_db(sb, row["video_id"]):
            try:
                sb.table("video_trending").insert(row).execute()
            except APIError:
                continue

def enrich_with_channel_stats(yt, finalists):
    for it in finalists:
        try:
            it["channel_subscribers"] = fetch_channel_stats(yt, it["channel_id"])
        except Exception:
            it["channel_subscribers"] = 0

def generate_report(selected_videos, stats):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"trending_report_{today}.md"
    
    with open(filename, "w") as f:
        f.write(f"# Reporte de Tendencias - {today}\n\n")
        f.write(f"**Videos insertados:** {stats['inserted']}\n")
        f.write(f"**Filtrados:** {stats['filtered']}\n")
        f.write(f"**Cortos seleccionados:** {stats['shorts']}\n")
        f.write(f"**Largos seleccionados:** {stats['longs']}\n\n")
        
        f.write("## Top Videos\n")
        f.write("| Rank | Título | Formato | Score | VPH | ENG |\n")
        f.write("|------|--------|---------|-------|-----|-----|\n")
        
        for i, video in enumerate(selected_videos[:20]):
            f.write(f"| {i+1} | {video['title'][:50]} | {video['format']} | {video['score']:.2f} | {int(video['vph'])} | {video['engagement']*100:.2f}% |\n")
    
    return filename

def main():
    # Cargar configuración
    (
        youtube_api_key, supabase_url, supabase_key, channel_id,
        region_codes, allowed_langs, long_min_seconds,
        max_shorts, max_longs, pages_per_region
    ) = load_env()

    # Inicializar clientes
    yt, sb = init_clients(youtube_api_key, supabase_url, supabase_key)

    # Tracking de cuota API (videos().list cuesta 1 unidad por llamada)
    api_calls_count = 0
    
    # Construir perfil del canal
    channel_profile = build_channel_profile(sb, channel_id)
    
    # Estadísticas
    stats = {
        "candidates": 0,
        "similarity_passed": 0,
        "viral_passed": 0,
        "inserted": 0,
        "shorts": 0,
        "longs": 0,
        "filtered": 0
    }
    
    # Procesar regiones con dedup y early-stop
    needed_total = (max_shorts + max_longs) * 3
    candidates = collect_candidates(
        yt, region_codes, pages_per_region, 
        channel_profile, allowed_langs, long_min_seconds, needed_total
    )
    stats["candidates"] = len(candidates)
    
    # Aplicar filtros virales dinámicos
    kept, thr = apply_dynamic_viral_filters(candidates)
    stats["viral_passed"] = len(kept)
    stats["filtered"] = stats["candidates"] - stats["viral_passed"]
    
    # Obtener estadísticas de canal solo para finalistas
    enrich_with_channel_stats(yt, kept)
    
    # Calcular puntajes
    freshness = {}
    for video in kept:
        pub_date = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))
        freshness[video["video_id"]] = (
            datetime.now(timezone.utc) - pub_date
        ).total_seconds() / 3600.0
    
    topic_counts = Counter(v["topic_key"] for v in kept)
    
    for video in kept:
        video["score"] = compute_score(
            video,
            video["format"],
            channel_profile,
            len(video["_regions"]),
            freshness[video["video_id"]],
            topic_counts
        )
    
    # Seleccionar mejores candidatos
    selected = select_top_candidates(kept, max_shorts, max_longs)
    
    # Insertar en Supabase
    if selected:
        save_to_supabase(sb, selected)
        stats["inserted"] = len(selected)
        stats["shorts"] = sum(1 for v in selected if v["format"] == "short")
        stats["longs"] = sum(1 for v in selected if v["format"] == "long")
    
    # Generar reporte
    report_file = generate_report(selected, stats)

    # Registrar uso de cuota API
    # videos().list = 1 unidad por llamada
    # Estimación: regiones × páginas
    total_api_calls = len(region_codes) * pages_per_region
    if NICHO_FILTERING_ENABLED:
        registrar_uso_cuota("videos.list", total_api_calls, sb)
        print(f"[fetch_trending_videos] Cuota API usada: {total_api_calls} unidades")

    print(f"[fetch_trending_videos] Proceso completado. "
          f"Candidatos: {stats['candidates']}, "
          f"Insertados: {stats['inserted']} "
          f"(Shorts: {stats['shorts']}, Longs: {stats['longs']})")
    print(f"[fetch_trending_videos] Reporte generado: {report_file}")

if __name__ == "__main__":
    main()
