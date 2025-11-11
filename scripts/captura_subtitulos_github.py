#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAPTURA DE SUBTITULOS PARA GITHUB ACTIONS
==========================================

Versión optimizada usando youtube-transcript-api (NO oficial)
- Guarda en Supabase (no SQLite local)
- NO requiere OAuth (sin errores 403)
- NO consume cuota API (GRATIS)
- Límite: 20 videos/día
- Dos fases: Completar histórico → Mantenimiento

CAMBIO v4.2.2 (2025-11-11):
- Reemplazado YouTube Captions API por youtube-transcript-api
- Razón: Error 403 por falta de permisos OAuth
- Ventaja: Sin cuota API, más confiable

CUOTA API:
- youtube-transcript-api: 0 unidades (NO usa API oficial)
- Solo requiere que el video sea público
"""

import os
import sys
import time
from datetime import datetime, timezone
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
from supabase import create_client, Client

# Importar funciones de control de cuota
try:
    from nicho_utils import registrar_uso_cuota
    QUOTA_TRACKING_ENABLED = True
except ImportError:
    print("[WARNING] nicho_utils.py no encontrado - Control de cuota deshabilitado")
    QUOTA_TRACKING_ENABLED = False

# LÍMITE DIARIO: 500 videos (ILIMITADO con youtube-transcript-api)
# FIX 2025-11-11: Aumentado de 20 a 500 porque youtube-transcript-api NO consume cuota API
#
# CÁLCULO DE CUOTA:
# - youtube-transcript-api: 0 unidades (NO usa API oficial de YouTube)
# - Solo hace scraping de transcripciones públicas
# - Límite: Solo depende del tiempo de ejecución de GitHub Actions
#
# ESTRATEGIA:
# - 500 videos/día = Completar histórico en 1 día
# - Si hay problemas de timeout, reducir a 200-300
# - Después del histórico, volver a 20-30 para mantenimiento
LIMIT_DIARIO = 500

# def get_daily_limit():
#     """
#     Calcula límite dinámico basado en si hoy hay trending
#     NOTA: Requiere verificación robusta del día de trending
#     """
#     import datetime
#     today = datetime.datetime.now(datetime.timezone.utc)
#     # Implementar lógica de detección aquí
#     return 20  # Por ahora, retornar valor conservador


def load_env():
    """Cargar credenciales desde variables de entorno"""
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return supabase_url, supabase_key


def init_clients(supabase_url, supabase_key):
    """Inicializar cliente de Supabase"""
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


def get_transcript_for_video(video_id):
    """
    Obtiene el transcript de un video usando youtube-transcript-api

    Args:
        video_id (str): ID del video

    Returns:
        tuple: (transcript_text, language) o (None, None) si falla
    """
    try:
        # Método correcto: get_transcript (no list_transcripts)
        # Intentar obtener transcript en español primero
        try:
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'es-ES', 'es-MX'])
            language = 'es'
        except:
            try:
                # Si no hay español, intentar inglés
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
                language = 'en'
            except:
                # Si no, intentar auto-generated en cualquier idioma
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
                language = 'auto'

        # Convertir a formato SRT simplificado
        srt_lines = []
        for i, entry in enumerate(transcript_data, 1):
            start = entry['start']
            duration = entry['duration']
            text = entry['text']

            # Formato: timestamp + texto
            srt_lines.append(f"{i}")
            srt_lines.append(f"{format_timestamp(start)} --> {format_timestamp(start + duration)}")
            srt_lines.append(text)
            srt_lines.append("")

        transcript_text = '\n'.join(srt_lines)
        return transcript_text, language

    except TranscriptsDisabled:
        print(f"  [AVISO] Transcripciones deshabilitadas para este video")
        return None, None
    except NoTranscriptFound:
        print(f"  [AVISO] No se encontró transcript para este video")
        return None, None
    except VideoUnavailable:
        print(f"  [AVISO] Video no disponible")
        return None, None
    except Exception as e:
        print(f"  [ERROR] Error al obtener transcript: {str(e)[:150]}")
        return None, None


def format_timestamp(seconds):
    """
    Convierte segundos a formato SRT timestamp (HH:MM:SS,mmm)

    Args:
        seconds (float): Segundos

    Returns:
        str: Timestamp en formato SRT
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def save_caption_to_supabase(sb: Client, video_id, language, caption_text):
    """
    Guarda caption en Supabase
    USA UPSERT para NO sobreescribir captions existentes

    Args:
        sb: Cliente de Supabase
        video_id (str): ID del video
        language (str): Código de idioma
        caption_text (str): Texto del caption
    """
    now = datetime.now(timezone.utc).isoformat()

    sb.table("captions").upsert({
        "video_id": video_id,
        "language": language,
        "caption_text": caption_text,
        "imported_at": now
    }, on_conflict=["video_id", "language"]).execute()


def main():
    """Función principal"""
    print("=" * 80)
    print("CAPTURA DE SUBTITULOS - GITHUB ACTIONS")
    print("=" * 80)
    print()

    # Cargar credenciales
    print("[INFO] Cargando credenciales...")
    try:
        supabase_url, supabase_key = load_env()
        sb = init_clients(supabase_url, supabase_key)
        print("[OK] Credenciales cargadas")
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

        # Obtener transcript usando youtube-transcript-api
        transcript_text, language = get_transcript_for_video(video_id)

        if transcript_text:
            # Guardar en Supabase
            save_caption_to_supabase(sb, video_id, language, transcript_text)
            print(f"  [OK] Transcript guardado en '{language}' ({len(transcript_text)} caracteres)")
            success_count += 1
        else:
            error_count += 1

        # Pausa mínima (youtube-transcript-api no tiene rate limit estricto)
        time.sleep(0.2)

    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"[OK] Captions capturados: {success_count}")
    print(f"[ERROR] Errores: {error_count}")
    print(f"[STATS] Tasa de exito: {success_count / len(videos) * 100:.1f}%")
    print()

    # Calcular cuota API usada (0 con youtube-transcript-api)
    quota_used = 0  # youtube-transcript-api NO usa cuota API
    print(f"[API] Cuota usada: {quota_used} unidades (youtube-transcript-api NO consume cuota)")
    print(f"[API] Cuota diaria limite: 10,000 unidades")
    print(f"[API] Cuota disponible: 10,000 unidades")
    print()

    # Registrar cuota usada (aunque sea 0)
    if QUOTA_TRACKING_ENABLED:
        try:
            registrar_uso_cuota("captions", quota_used, sb)
            print(f"[OK] Cuota registrada en sistema de tracking")
        except Exception as e:
            print(f"[WARNING] Error registrando cuota: {e}")

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
