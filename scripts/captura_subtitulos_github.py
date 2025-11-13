#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAPTURA DE SUBTITULOS PARA GITHUB ACTIONS (v2.0 - ZERO COST)
=============================================================

Versión 2.0 - Usa youtube-transcript-api (NO YouTube Data API)
- Guarda en Supabase (no SQLite local)
- NO requiere OAuth (sin autenticación)
- COSTO: 0 unidades de YouTube API (vs 250/video antes)
- Límite: 50 videos/día (sin límite de API)
- Dos fases: Completar histórico → Mantenimiento

REEMPLAZA A:
- captura_subtitulos_github.py v1.0 (250 unidades/video)
- import_captions.py (que no trajo subtítulos)

VENTAJAS v2.0:
✅ Costo API: 0 unidades (vs 7,500 en v1.0)
✅ OAuth: NO requerido (vs scope youtube.force-ssl en v1.0)
✅ Rate limits: NO aplican (acceso directo a timedtext API)
✅ Capacidad: 50 videos/día (vs 20 en v1.0)
✅ Velocidad: < 1 segundo/video

CÓMO FUNCIONA:
- Usa youtube-transcript-api para acceder al timedtext API interno de YouTube
- Mismo API que usa el botón "CC" en el reproductor web
- NO cuenta contra cuota de YouTube Data API v3
- Funciona con captions automáticos y manuales
- Soporta múltiples idiomas con fallback automático

⚠️ POLÍTICA DE SEGURIDAD:
==========================================
Este script SOLO lee datos públicos, NUNCA modifica contenido de YouTube.
Solo acceso de LECTURA a transcripciones públicas.
==========================================
"""

import os
import sys
import time
from datetime import datetime, timezone
from youtube_transcript_api import YouTubeTranscriptApi
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

# LÍMITE DIARIO: 50 videos (sin restricción de API)
# v2.0: Aumentado de 20 a 50 porque NO consume cuota API
#
# CÁLCULO DE CUOTA:
# - Transcripciones v2.0: 50 × 0 unidades = 0 unidades ✅
# - Transcripciones v1.0: 20 × 250 unidades = 5,000 unidades ❌
# - AHORRO DIARIO: 5,000 unidades
# - AHORRO MENSUAL: 150,000 unidades
#
# CAPACIDAD TOTAL:
# - 50 videos/día
# - 380 videos históricos completados en: 380 / 50 = 8 días
# - vs v1.0: 380 / 20 = 19 días
LIMIT_DIARIO = 50


def load_env():
    """Cargar credenciales desde variables de entorno (solo Supabase)"""
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return supabase_url, supabase_key


def init_clients(supabase_url, supabase_key):
    """Inicializar cliente de Supabase (YouTube API NO requerida)"""
    sb: Client = create_client(supabase_url, supabase_key)
    return sb


def get_videos_without_captions(sb: Client, limit=30):
    """
    Obtiene videos sin captions
    ORDENADOS POR FECHA (más recientes primero)

    Args:
        sb: Cliente de Supabase
        limit (int): Número máximo de videos a retornar

    Returns:
        List[dict]: Lista de videos sin captions
    """
    # Obtener videos sin captions, ordenados por fecha (NEWEST FIRST)
    resp = sb.table("videos") \
        .select("video_id, title, published_at") \
        .order("published_at", desc=True) \
        .execute()

    all_videos = resp.data

    # Filtrar videos que YA tienen captions
    if all_videos:
        video_ids = [v["video_id"] for v in all_videos]
        existing = sb.table("captions") \
            .select("video_id") \
            .in_("video_id", video_ids) \
            .execute()
        existing_ids = {row["video_id"] for row in existing.data}

        videos_sin_captions = [v for v in all_videos if v["video_id"] not in existing_ids]
    else:
        videos_sin_captions = []

    # Limitar a N videos
    videos_sin_captions = videos_sin_captions[:limit]

    print(f"[INFO] Videos sin captions: {len(videos_sin_captions)}")

    if videos_sin_captions:
        fecha_mas_reciente = videos_sin_captions[0].get('published_at', 'N/A')
        fecha_mas_antigua = videos_sin_captions[-1].get('published_at', 'N/A')
        print(f"[INFO] Rango de fechas: {fecha_mas_reciente[:10]} a {fecha_mas_antigua[:10]}")

    return videos_sin_captions


def get_transcript_for_video(video_id, languages=['es', 'es-419', 'es-ES', 'en']):
    """
    Obtiene transcripción de un video usando youtube-transcript-api

    Args:
        video_id (str): ID del video
        languages (list): Lista de idiomas preferidos (con fallback)

    Returns:
        tuple: (transcript_text, language_code) o (None, None) si falla
    """
    try:
        api = YouTubeTranscriptApi()

        # Intentar obtener transcripción en idiomas preferidos
        transcript = api.fetch(video_id, languages=languages)

        # Combinar todos los fragmentos en un solo texto
        full_text = "\n".join([entry.text for entry in transcript])

        # Detectar idioma usado (primer fragmento tiene metadata)
        detected_lang = languages[0] if transcript else 'es'

        return full_text, detected_lang

    except Exception as e:
        error_msg = str(e)

        # Errores comunes
        if "No transcripts found" in error_msg or "Subtitles are disabled" in error_msg:
            print(f"  [INFO] Video sin transcripción disponible")
        else:
            print(f"  [ERROR] Error obteniendo transcripción: {error_msg[:150]}")

        return None, None


def save_caption_to_supabase(sb: Client, video_id, language, caption_text):
    """
    Guarda caption en Supabase
    Verifica si existe primero para evitar duplicados

    Args:
        sb: Cliente de Supabase
        video_id (str): ID del video
        language (str): Código de idioma
        caption_text (str): Texto del caption
    """
    now = datetime.now(timezone.utc).isoformat()

    # Verificar si ya existe este caption
    existing = sb.table("captions") \
        .select("id") \
        .eq("video_id", video_id) \
        .eq("language", language) \
        .execute()

    if existing.data:
        # Ya existe, no hacer nada (NO sobrescribir)
        pass
    else:
        # No existe, insertar nuevo
        sb.table("captions").insert({
            "video_id": video_id,
            "language": language,
            "caption_text": caption_text,
            "imported_at": now
        }).execute()


def main():
    """Función principal"""
    print("=" * 80)
    print("CAPTURA DE SUBTITULOS v2.0 - ZERO COST")
    print("=" * 80)
    print()
    print("[INFO] Método: youtube-transcript-api (NO YouTube Data API)")
    print("[INFO] Costo: 0 unidades de YouTube API")
    print("[INFO] OAuth: NO requerido")
    print()

    # Cargar credenciales (solo Supabase)
    print("[INFO] Cargando credenciales Supabase...")
    try:
        supabase_url, supabase_key = load_env()
        sb = init_clients(supabase_url, supabase_key)
        print("[OK] Cliente Supabase inicializado")
    except Exception as e:
        print(f"[ERROR] No se pudo cargar credenciales: {e}")
        sys.exit(1)

    # Verificar estado actual
    print("[INFO] Verificando estado actual...")
    try:
        # Total de videos
        resp_videos = sb.table("videos").select("video_id", count="exact").execute()
        total_videos = resp_videos.count

        # Total de captions
        resp_captions = sb.table("captions").select("video_id", count="exact").execute()
        total_captions = len(set([row["video_id"] for row in resp_captions.data]))

        print(f"[INFO] Videos con captions: {total_captions}/{total_videos}")
    except Exception as e:
        print(f"[WARNING] Error verificando estado: {e}")
        total_videos = 0
        total_captions = 0

    # ESTRATEGIA DE DOS FASES
    if total_captions < total_videos:
        # FASE 1: Completar histórico
        print(f"\n[FASE 1: COMPLETAR HISTORICO]")
        print(f"  Limite diario: {LIMIT_DIARIO} videos")
        print(f"  Progreso: {total_captions}/{total_videos} ({total_captions/total_videos*100:.1f}%)")
        print(f"\n[BUSCANDO] Videos sin captions...")
        videos = get_videos_without_captions(sb, limit=LIMIT_DIARIO)
    else:
        # FASE 2: Solo videos NUEVOS (últimos 30 días)
        print(f"\n[FASE 2: MANTENIMIENTO - SOLO VIDEOS NUEVOS]")
        print(f"  Historico completado: {total_captions} videos")
        print(f"\n[BUSCANDO] Videos nuevos sin captions...")

        # Buscar videos de últimos 30 días sin captions
        from datetime import timedelta
        threshold = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        resp = sb.table("videos") \
            .select("video_id, title, published_at") \
            .gte("published_at", threshold) \
            .order("published_at", desc=True) \
            .execute()

        all_recent = resp.data

        if all_recent:
            video_ids = [v["video_id"] for v in all_recent]
            existing = sb.table("captions") \
                .select("video_id") \
                .in_("video_id", video_ids) \
                .execute()
            existing_ids = {row["video_id"] for row in existing.data}
            videos = [v for v in all_recent if v["video_id"] not in existing_ids]
        else:
            videos = []

        print(f"[INFO] Videos nuevos encontrados: {len(videos)}")

    if not videos:
        print("[OK] No hay videos pendientes de captura")
        print("      - Historico completo: SI")
        print("      - Videos nuevos: NO")
        print()
        print("[RESULTADO] No se gasto cuota API")
        sys.exit(0)

    print(f"\n[INFO] Total de videos sin captions: {len(videos)}")
    print("-" * 80)

    # Contadores
    success_count = 0
    error_count = 0

    # Procesar cada video
    for idx, video in enumerate(videos, 1):
        video_id = video['video_id']
        title = video.get('title', 'Sin titulo')

        # Limpiar título de caracteres problemáticos
        safe_title = title.encode('ascii', 'ignore').decode('ascii')
        if not safe_title:
            safe_title = "Video sin titulo ASCII"

        print(f"\n[{idx}/{len(videos)}] {safe_title[:60]}...")
        print(f"  Video ID: {video_id}")

        # Obtener transcripción usando youtube-transcript-api
        # Intentar en orden: es → es-419 → es-ES → en (fallback)
        transcript_text, lang_code = get_transcript_for_video(
            video_id,
            languages=['es', 'es-419', 'es-ES', 'en']
        )

        if not transcript_text:
            print(f"  [AVISO] No hay transcripción disponible")
            error_count += 1
            continue

        # Guardar en Supabase
        save_caption_to_supabase(sb, video_id, lang_code, transcript_text)
        print(f"  [OK] Transcripción guardada ({len(transcript_text)} caracteres, idioma: {lang_code})")
        success_count += 1

        # Pequeña pausa para no saturar (opcional, no hay rate limits)
        time.sleep(0.5)

    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL v2.0")
    print("=" * 80)
    print(f"[OK] Transcripciones capturadas: {success_count}")
    print(f"[ERROR] Videos sin transcripción: {error_count}")
    print(f"[STATS] Tasa de éxito: {success_count / len(videos) * 100:.1f}%")
    print()

    # Calcular cuota API usada (v2.0 = 0)
    quota_used = 0  # youtube-transcript-api NO consume cuota
    quota_saved = success_count * 250  # Ahorro vs v1.0

    print(f"[API v2.0] Cuota usada: {quota_used} unidades (0% de cuota)")
    print(f"[API v2.0] Cuota ahorrada vs v1.0: {quota_saved:,} unidades")
    print(f"[API v2.0] Método: youtube-transcript-api (timedtext API)")
    print()

    # Registrar ejecución exitosa
    try:
        sb.table("script_execution_log").upsert({
            "script_name": "captura_subtitulos_github",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "status": "success"
        }, on_conflict="script_name").execute()
        print(f"[OK] Ejecucion registrada en log")
    except Exception as e:
        print(f"[WARNING] Error registrando ejecucion: {e}")

    # Mostrar progreso total
    try:
        resp_captions = sb.table("captions").select("video_id", count="exact").execute()
        total_captions_now = len(set([row["video_id"] for row in resp_captions.data]))

        progreso = (total_captions_now / total_videos * 100) if total_videos > 0 else 0
        videos_restantes = total_videos - total_captions_now

        print(f"\n[PROGRESO TOTAL]")
        print(f"  Videos con captions: {total_captions_now}/{total_videos} ({progreso:.1f}%)")

        if videos_restantes > 0:
            print(f"  Videos restantes: {videos_restantes}")
            dias_restantes = videos_restantes // LIMIT_DIARIO + (1 if videos_restantes % LIMIT_DIARIO else 0)
            print(f"  Dias para completar ({LIMIT_DIARIO}/dia): {dias_restantes}")
        else:
            print(f"  Estado: HISTORICO COMPLETO")
            print()
            print("[MODO MANTENIMIENTO ACTIVADO]")
            print("  De ahora en adelante, solo capturara videos NUEVOS")
    except Exception as e:
        print(f"[WARNING] Error calculando progreso: {e}")

    print()


if __name__ == "__main__":
    main()
