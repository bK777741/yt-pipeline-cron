#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAPTURA DE SUBTITULOS PARA GITHUB ACTIONS
==========================================

Versión optimizada de captura_subtitulos_api_oficial.py para GitHub Actions
- Guarda en Supabase (no SQLite local)
- Usa credenciales de GitHub Secrets
- Límite: 30 videos/día (vs 2 del script viejo)
- Dos fases: Completar histórico → Mantenimiento

REEMPLAZA A: import_captions.py (que no trajo subtítulos)

CUOTA API:
- captions.list(): 50 unidades
- captions.download(): 200 unidades
- Total: 250 unidades por video
- 30 videos/día = 7,500 unidades
"""

import os
import sys
import time
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

# Importar funciones de control de cuota
try:
    from nicho_utils import registrar_uso_cuota
    QUOTA_TRACKING_ENABLED = True
except ImportError:
    print("[WARNING] nicho_utils.py no encontrado - Control de cuota deshabilitado")
    QUOTA_TRACKING_ENABLED = False

# LÍMITE DIARIO: 20 videos (optimizado para cuota API)
# FIX 2025-11-10: Reducido de 30 a 20 para evitar exceder cuota
#
# CÁLCULO DE CUOTA:
# - Transcripciones: 20 × 250 unidades = 5,000 unidades
# - Maint metrics: 50 unidades
# - Otros jobs: 500 unidades
# - DÍAS NORMALES: 5,550 unidades (margen: 4,450)
# - DÍAS CON TRENDING: 5,550 + 2,500 = 8,050 unidades (margen: 1,950) ✓
#
# ALTERNATIVA OPTIMIZADA (requiere detección de trending):
# - Días SIN trending: 30 videos (8,050 unidades, margen 1,950)
# - Días CON trending: 15 videos (6,250 unidades, margen 3,750)
#
# Para habilitar límite dinámico:
# 1. Uncomment la función get_daily_limit() abajo
# 2. Cambiar LIMIT_DIARIO = 20 por LIMIT_DIARIO = get_daily_limit()
LIMIT_DIARIO = 20

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


def list_captions_for_video(youtube, video_id):
    """
    Lista los captions disponibles para un video

    Args:
        youtube: Objeto de servicio de YouTube API
        video_id (str): ID del video

    Returns:
        list: Lista de captions disponibles
    """
    try:
        request = youtube.captions().list(
            part="snippet",
            videoId=video_id
        )
        response = request.execute()
        return response.get('items', [])
    except Exception as e:
        print(f"  [ERROR] No se pudo listar captions: {str(e)[:150]}")
        return []


def download_caption(youtube, caption_id, tfmt='srt'):
    """
    Descarga un caption específico

    Args:
        youtube: Objeto de servicio de YouTube API
        caption_id (str): ID del caption
        tfmt (str): Formato (srt, vtt, sbv, ttml)

    Returns:
        str: Texto del caption o None
    """
    try:
        request = youtube.captions().download(
            id=caption_id,
            tfmt=tfmt
        )
        caption_text = request.execute()
        # Decodificar bytes a string
        if isinstance(caption_text, bytes):
            return caption_text.decode('utf-8')
        return caption_text
    except Exception as e:
        print(f"  [ERROR] No se pudo descargar caption: {str(e)[:150]}")
        return None


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
        creds, supabase_url, supabase_key = load_env()
        yt, sb = init_clients(creds, supabase_url, supabase_key)
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

        # Listar captions disponibles
        captions_list = list_captions_for_video(yt, video_id)

        if not captions_list:
            print(f"  [AVISO] No hay captions disponibles para este video")
            error_count += 1
            continue

        print(f"  [OK] {len(captions_list)} caption(s) disponibles")

        # Intentar descargar caption en español primero
        spanish_langs = ['es', 'es-419', 'es-ES', 'es-MX', 'es-AR', 'es-CO']
        caption_downloaded = False

        for cap in captions_list:
            lang = cap['snippet']['language']
            if lang in spanish_langs:
                caption_id = cap['id']
                print(f"  [DESCARGANDO] Caption en español ({lang})...")

                caption_text = download_caption(yt, caption_id, tfmt='srt')

                if caption_text:
                    # Guardar en Supabase
                    save_caption_to_supabase(sb, video_id, lang, caption_text)
                    print(f"  [OK] Caption guardado ({len(caption_text)} caracteres)")
                    success_count += 1
                    caption_downloaded = True
                    break

        if not caption_downloaded:
            # Si no hay en español, intentar con el primero disponible
            first_cap = captions_list[0]
            lang = first_cap['snippet']['language']
            caption_id = first_cap['id']
            print(f"  [DESCARGANDO] Caption en {lang} (no hay español)...")

            caption_text = download_caption(yt, caption_id, tfmt='srt')

            if caption_text:
                save_caption_to_supabase(sb, video_id, lang, caption_text)
                print(f"  [OK] Caption guardado ({len(caption_text)} caracteres)")
                success_count += 1
            else:
                error_count += 1

        # Evitar rate limits
        time.sleep(1)

    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print(f"[OK] Captions capturados: {success_count}")
    print(f"[ERROR] Errores: {error_count}")
    print(f"[STATS] Tasa de exito: {success_count / len(videos) * 100:.1f}%")
    print()

    # Calcular cuota API usada
    quota_used = success_count * 250  # 50 (list) + 200 (download)
    print(f"[API] Cuota estimada usada: {quota_used:,} unidades")
    print(f"[API] Cuota diaria limite: 10,000 unidades")
    print(f"[API] Cuota disponible: {10000 - quota_used:,} unidades")
    print()

    # Registrar cuota usada
    if QUOTA_TRACKING_ENABLED and quota_used > 0:
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
