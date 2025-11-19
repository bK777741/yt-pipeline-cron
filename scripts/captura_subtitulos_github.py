#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAPTURA DE SUBTITULOS PARA GITHUB ACTIONS (v3.0 - YouTube Data API)
====================================================================

Versión 3.0 - Usa YouTube Data API v3 con OAuth
- Guarda en Supabase (no SQLite local)
- REQUIERE OAuth con scope youtube.force-ssl
- COSTO: 51 unidades de YouTube API por video
- Límite: 20 videos/día (para no exceder cuota)
- Dos fases: Completar histórico → Mantenimiento

RAZÓN DEL CAMBIO v2.0 → v3.0:
- youtube-transcript-api NO funciona desde GitHub Actions
- YouTube bloquea IPs de cloud providers (Azure/AWS/GCP)
- Error: RequestBlocked desde todas las IPs de GitHub Actions
- Solución: Usar YouTube Data API v3 oficial con autenticación

COSTO v3.0:
- captions.list: 50 unidades
- captions.download: 1 unidad
- TOTAL: 51 unidades por video
- 20 videos/día = 1,020 unidades/día (dentro de cuota 10,000)

⚠️ POLÍTICA DE SEGURIDAD:
==========================================
Este script SOLO lee datos públicos, NUNCA modifica contenido de YouTube.
Solo acceso de LECTURA a subtítulos publicados.
==========================================
"""

import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

# LÍMITE DIARIO: 20 videos (ajustado por cuota API)
# v3.0: Reducido de 50 a 20 por costo de API
#
# CÁLCULO DE CUOTA:
# - Transcripciones v3.0: 20 × 51 unidades = 1,020 unidades/día
# - Cuota diaria disponible: 10,000 unidades
# - Uso para captions: 10.2% de cuota diaria
# - Resto disponible para otros scripts: 8,980 unidades
#
# CAPACIDAD TOTAL:
# - 20 videos/día
# - 310 videos históricos completados en: 310 / 20 = 16 días
LIMIT_DIARIO = 20


def load_env():
    """Cargar credenciales desde variables de entorno"""
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()

    # Credenciales OAuth de YouTube
    client_id = os.environ["YT_CLIENT_ID"].strip()
    client_secret = os.environ["YT_CLIENT_SECRET"].strip()
    refresh_token = os.environ["YT_REFRESH_TOKEN"].strip()

    return supabase_url, supabase_key, client_id, client_secret, refresh_token


def init_clients(supabase_url, supabase_key, client_id, client_secret, refresh_token):
    """Inicializar clientes de Supabase y YouTube"""
    sb: Client = create_client(supabase_url, supabase_key)

    # Crear credenciales OAuth
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]
    )

    # Crear cliente de YouTube Data API
    youtube = build("youtube", "v3", credentials=creds)

    return sb, youtube


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


def get_caption_for_video(youtube, video_id, languages=['es', 'es-419', 'es-ES', 'en']):
    """
    Obtiene caption de un video usando YouTube Data API v3

    COSTO: 51 unidades (50 list + 1 download)

    Args:
        youtube: Cliente de YouTube Data API
        video_id (str): ID del video
        languages (list): Lista de idiomas preferidos (con fallback)

    Returns:
        tuple: (caption_text, language_code) o (None, None) si falla
    """
    try:
        # Listar captions disponibles (50 unidades)
        captions_response = youtube.captions().list(
            part="snippet",
            videoId=video_id
        ).execute()

        captions = captions_response.get("items", [])

        if not captions:
            print(f"  [INFO] Video sin captions disponibles")
            return None, None

        # Buscar caption en idioma preferido
        selected_caption = None
        detected_lang = 'es'

        for lang in languages:
            for caption in captions:
                if caption["snippet"]["language"].startswith(lang):
                    selected_caption = caption
                    detected_lang = caption["snippet"]["language"]
                    break
            if selected_caption:
                break

        # Si no encontró, usar el primero disponible
        if not selected_caption:
            selected_caption = captions[0]
            detected_lang = selected_caption["snippet"]["language"]

        caption_id = selected_caption["id"]

        # Descargar caption (1 unidad)
        caption_text = youtube.captions().download(
            id=caption_id,
            tfmt="srt"  # Formato SRT (texto plano con timestamps)
        ).execute()

        # Convertir bytes a string si es necesario
        if isinstance(caption_text, bytes):
            caption_text = caption_text.decode('utf-8')

        # Limpiar formato SRT (remover timestamps)
        lines = caption_text.split('\n')
        clean_text = []
        for line in lines:
            # Saltar líneas de número y timestamp
            if line.strip() and not line.strip().isdigit() and '-->' not in line:
                clean_text.append(line.strip())

        full_text = '\n'.join(clean_text)

        return full_text, detected_lang

    except HttpError as e:
        error_msg = str(e)

        if "forbidden" in error_msg.lower() or "403" in error_msg:
            print(f"  [ERROR] No hay permisos para descargar captions (requiere youtube.force-ssl scope)")
        elif "notFound" in error_msg or "404" in error_msg:
            print(f"  [INFO] Video sin captions disponibles")
        else:
            print(f"  [ERROR] Error obteniendo caption: {error_msg[:150]}")

        return None, None

    except Exception as e:
        print(f"  [ERROR] Error inesperado: {str(e)[:150]}")
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
    print("CAPTURA DE SUBTITULOS v3.0 - YouTube Data API")
    print("=" * 80)
    print()
    print("[INFO] Método: YouTube Data API v3 con OAuth")
    print("[INFO] Costo: 51 unidades de YouTube API por video")
    print("[INFO] OAuth: youtube.force-ssl scope requerido")
    print()

    # Cargar credenciales (Supabase + YouTube)
    print("[INFO] Cargando credenciales...")
    try:
        supabase_url, supabase_key, client_id, client_secret, refresh_token = load_env()
        sb, youtube = init_clients(supabase_url, supabase_key, client_id, client_secret, refresh_token)
        print("[OK] Clientes Supabase y YouTube inicializados")
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

        # Obtener caption usando YouTube Data API v3
        # Intentar en orden: es → es-419 → es-ES → en (fallback)
        caption_text, lang_code = get_caption_for_video(
            youtube,
            video_id,
            languages=['es', 'es-419', 'es-ES', 'en']
        )

        if not caption_text:
            print(f"  [AVISO] No hay caption disponible")
            error_count += 1
            continue

        # Guardar en Supabase
        save_caption_to_supabase(sb, video_id, lang_code, caption_text)
        print(f"  [OK] Caption guardado ({len(caption_text)} caracteres, idioma: {lang_code})")
        success_count += 1

        # Pequeña pausa para respetar rate limits
        time.sleep(1)

    # Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN FINAL v3.0")
    print("=" * 80)
    print(f"[OK] Captions capturados: {success_count}")
    print(f"[ERROR] Videos sin caption: {error_count}")
    print(f"[STATS] Tasa de éxito: {success_count / len(videos) * 100:.1f}%")
    print()

    # Calcular cuota API usada (v3.0 = 51 por video)
    quota_used = success_count * 51  # 50 list + 1 download
    quota_percentage = (quota_used / 10000) * 100

    print(f"[API v3.0] Cuota usada: {quota_used} unidades ({quota_percentage:.1f}% de cuota diaria)")
    print(f"[API v3.0] Método: YouTube Data API v3 (captions.list + captions.download)")
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
