#!/usr/bin/env python3
"""
IMPORTAR TODOS TUS VIDEOS AL DATASET ML
========================================

Este script captura TODOS tus videos de la tabla 'videos'
y los guarda en ml_training_data para entrenar el modelo.

IMPORTANTE: Solo se ejecuta UNA VEZ (al inicio)
"""
import os
import sys
import re
from datetime import datetime, timezone
from supabase import create_client, Client


def load_env():
    """Cargar variables de entorno"""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    return supabase_url, supabase_key


def parse_duration_iso8601(duration_str):
    """
    Convierte duration ISO 8601 a segundos
    Ejemplo: "PT3M30S" -> 210 segundos
    """
    if not duration_str:
        return 0

    try:
        # Patrón: PT[H]H[M]M[S]S
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)

        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds
    except:
        return 0


def calcular_vph(video):
    """Calcula VPH basado en edad del video"""
    try:
        published = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
        edad_horas = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        vph = video.get('view_count', 0) / max(edad_horas, 1)
        return round(vph, 2)
    except Exception as e:
        print(f"[WARNING] Error calculando VPH: {e}")
        return 0.0


def importar_todos_mis_videos(sb: Client):
    """
    Importa TODOS tus videos de la tabla 'videos' a ml_training_data
    """
    print("="*80)
    print("IMPORTANDO TODOS TUS VIDEOS AL DATASET ML")
    print("="*80)
    print()

    # Obtener TODOS tus videos
    print("[1/3] Obteniendo todos tus videos...")
    try:
        result = sb.table("videos")\
            .select("*")\
            .execute()

        videos = result.data if result.data else []
        print(f"  Total de videos encontrados: {len(videos)}")

    except Exception as e:
        print(f"[ERROR] Error obteniendo videos: {e}")
        return 0

    if not videos:
        print("[WARNING] No hay videos para importar")
        return 0

    # Procesar cada video
    print()
    print("[2/3] Procesando videos...")

    saved_count = 0
    skipped_count = 0
    error_count = 0

    for idx, video in enumerate(videos, 1):
        video_id = video.get('video_id')

        if not video_id:
            error_count += 1
            continue

        # Verificar si ya existe en ml_training_data
        try:
            existing = sb.table("ml_training_data")\
                .select("video_id")\
                .eq("video_id", video_id)\
                .execute()

            if existing.data:
                skipped_count += 1
                if idx % 50 == 0:
                    print(f"  Procesados: {idx}/{len(videos)} (guardados: {saved_count}, ya existian: {skipped_count})")
                continue

            # Calcular VPH
            vph = calcular_vph(video)

            # Convertir duration ISO 8601 a segundos
            duration_segundos = parse_duration_iso8601(video.get('duration', ''))

            # Preparar snapshot
            snapshot = {
                'video_id': video_id,
                'es_tuyo': True,  # ESTOS SON TUYOS
                'title': video.get('title', ''),
                'published_at': video.get('published_at'),
                'duration': duration_segundos,
                'category_id': video.get('category_id'),
                'channel_id': video.get('channel_id', ''),
                'channel_subscribers': video.get('channel_subscribers', 0),
                'thumbnail_url': video.get('thumbnail_url', ''),
                'thumbnail_text': video.get('thumbnail_text', ''),
                'thumbnail_has_text': bool(video.get('thumbnail_text', '')),
                'view_count': video.get('view_count', 0),
                'like_count': video.get('like_count', 0),
                'comment_count': video.get('comment_count', 0),
                'vph': vph,
                'ctr': video.get('ctr', 0),
                'average_view_percentage': video.get('average_view_percentage', 0),
                'nicho_score': video.get('nicho_score', 0),
                'snapshot_date': datetime.now(timezone.utc).isoformat()
            }

            # Guardar
            sb.table("ml_training_data").insert(snapshot).execute()
            saved_count += 1

            if idx % 50 == 0:
                print(f"  Procesados: {idx}/{len(videos)} (guardados: {saved_count}, ya existian: {skipped_count})")

        except Exception as e:
            print(f"  [WARNING] Error guardando {video_id}: {str(e)[:100]}")
            error_count += 1

    # Resumen
    print()
    print("[3/3] Verificando resultado...")

    result = sb.table("ml_training_data")\
        .select("*", count="exact")\
        .eq("es_tuyo", True)\
        .execute()

    total_propios = result.count if hasattr(result, 'count') else 0

    print()
    print("="*80)
    print("RESUMEN")
    print("="*80)
    print(f"Videos procesados: {len(videos)}")
    print(f"  Guardados: {saved_count}")
    print(f"  Ya existian: {skipped_count}")
    print(f"  Errores: {error_count}")
    print()
    print(f"Total en ml_training_data (es_tuyo=TRUE): {total_propios}")
    print()

    if saved_count > 0:
        print("[OK] TUS VIDEOS IMPORTADOS EXITOSAMENTE")
        print()
        print("Ahora el modelo se entrenara con:")
        print(f"  - {total_propios} videos TUYOS (PRINCIPAL)")
        print(f"  - Videos de competencia (SECUNDARIO)")
    else:
        print("[INFO] Todos los videos ya estaban importados")

    print("="*80)

    return saved_count


def main():
    """Función principal"""
    print("\n")
    print("="*80)
    print("IMPORTACION INICIAL - TODOS TUS VIDEOS")
    print("="*80)
    print()
    print("[IMPORTANTE] Este script solo se ejecuta UNA VEZ")
    print("[IMPORTANTE] Importa todos tus videos de la tabla 'videos'")
    print("[IMPORTANTE] NO consume cuota API (solo lee de Supabase)")
    print()

    # Cargar entorno
    supabase_url, supabase_key = load_env()
    sb: Client = create_client(supabase_url, supabase_key)

    # Importar todos tus videos
    saved = importar_todos_mis_videos(sb)

    if saved > 0:
        print()
        print("[PROXIMO PASO] Ejecutar entrenamiento del modelo:")
        print("  cd scripts")
        print("  python train_predictor_model.py")
        print()

    print()


if __name__ == "__main__":
    main()
