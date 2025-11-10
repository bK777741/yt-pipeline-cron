#!/usr/bin/env python3
"""
save_training_snapshot.py
Guarda snapshot de videos ANTES de que sean purgados
Este script se ejecuta automáticamente antes de purga_trending_30dias.py

PROPÓSITO:
- Capturar datos de competencia antes de ser eliminados (>30 días)
- Guardar en ml_training_data para entrenamiento ML futuro
- NO consume cuota API (solo lee de Supabase)

EJECUCIÓN:
- GitHub Actions: Cada mes antes de purgar
- Manual: python scripts/save_training_snapshot.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# Configuración
TU_CHANNEL_ID = "UCH-TuIdAqui"  # Cambiar por tu channel_id real

def load_env():
    """Cargar variables de entorno"""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    return supabase_url, supabase_key

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

def guardar_snapshot_competencia(sb: Client):
    """
    Guarda snapshot de videos de competencia que serán purgados pronto
    (Videos de 23-30 días de antigüedad)
    """
    print("\n[SNAPSHOT COMPETENCIA] Guardando videos de competencia...")

    # Rango: Videos de 23-30 días (próximos a ser purgados)
    fecha_inicio = datetime.now(timezone.utc) - timedelta(days=30)
    fecha_fin = datetime.now(timezone.utc) - timedelta(days=23)

    print(f"  Rango: {fecha_inicio.date()} a {fecha_fin.date()}")

    # Tablas de competencia (solo las que existen)
    tablas = [
        'video_trending'
    ]

    saved_count = 0
    skipped_count = 0

    for tabla in tablas:
        try:
            print(f"\n[{tabla}] Procesando...")

            # Obtener videos en rango
            result = sb.table(tabla)\
                .select("*")\
                .gte("published_at", fecha_inicio.isoformat())\
                .lt("published_at", fecha_fin.isoformat())\
                .execute()

            videos = result.data if result.data else []
            print(f"  Encontrados: {len(videos)} videos")

            for video in videos:
                video_id = video.get('video_id')

                if not video_id:
                    continue

                # Verificar si ya existe en ml_training_data
                existing = sb.table("ml_training_data")\
                    .select("video_id")\
                    .eq("video_id", video_id)\
                    .execute()

                if existing.data:
                    skipped_count += 1
                    continue

                # Calcular VPH
                vph = calcular_vph(video)

                # Preparar snapshot
                snapshot = {
                    'video_id': video_id,
                    'es_tuyo': False,  # Es competencia
                    'title': video.get('title', ''),
                    'published_at': video.get('published_at'),
                    'duration': video.get('duration', 0),
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
                try:
                    sb.table("ml_training_data").insert(snapshot).execute()
                    saved_count += 1
                except Exception as e:
                    print(f"    [WARNING] Error guardando {video_id}: {e}")

        except Exception as e:
            print(f"  [ERROR] Error procesando {tabla}: {e}")

    print(f"\n[SNAPSHOT COMPETENCIA] [OK] Completado")
    print(f"  Guardados: {saved_count}")
    print(f"  Ya existian: {skipped_count}")

    return saved_count

def guardar_snapshot_propios(sb: Client):
    """
    Guarda snapshot de tus videos propios que serán purgados pronto
    (Videos de 173-180 días de antigüedad)
    """
    print("\n[SNAPSHOT PROPIOS] Guardando tus videos...")

    # Rango: Videos de 173-180 días (próximos a ser purgados por purga_inteligente)
    fecha_inicio = datetime.now(timezone.utc) - timedelta(days=180)
    fecha_fin = datetime.now(timezone.utc) - timedelta(days=173)

    print(f"  Rango: {fecha_inicio.date()} a {fecha_fin.date()}")

    try:
        # Obtener tus videos en rango
        result = sb.table("videos")\
            .select("*")\
            .gte("published_at", fecha_inicio.isoformat())\
            .lt("published_at", fecha_fin.isoformat())\
            .execute()

        videos = result.data if result.data else []
        print(f"  Encontrados: {len(videos)} videos")

        saved_count = 0
        skipped_count = 0

        for video in videos:
            video_id = video.get('video_id')

            if not video_id:
                continue

            # Verificar si ya existe
            existing = sb.table("ml_training_data")\
                .select("video_id")\
                .eq("video_id", video_id)\
                .execute()

            if existing.data:
                skipped_count += 1
                continue

            # Calcular VPH
            vph = calcular_vph(video)

            # Preparar snapshot
            snapshot = {
                'video_id': video_id,
                'es_tuyo': True,  # Es tu video
                'title': video.get('title', ''),
                'published_at': video.get('published_at'),
                'duration': video.get('duration', 0),
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
            try:
                sb.table("ml_training_data").insert(snapshot).execute()
                saved_count += 1
            except Exception as e:
                print(f"    [WARNING] Error guardando {video_id}: {e}")

        print(f"\n[SNAPSHOT PROPIOS] [OK] Completado")
        print(f"  Guardados: {saved_count}")
        print(f"  Ya existian: {skipped_count}")

        return saved_count

    except Exception as e:
        print(f"[ERROR] Error procesando videos propios: {e}")
        return 0

def verificar_estado_dataset(sb: Client):
    """Verifica el estado del dataset ML"""
    try:
        result = sb.table("ml_training_data")\
            .select("*", count="exact")\
            .execute()

        total = result.count if hasattr(result, 'count') else 0

        # Contar por tipo
        propios = sb.table("ml_training_data")\
            .select("*", count="exact")\
            .eq("es_tuyo", True)\
            .execute()

        competencia = sb.table("ml_training_data")\
            .select("*", count="exact")\
            .eq("es_tuyo", False)\
            .execute()

        print(f"\n[DATASET ML] Estado actual:")
        print(f"  Total: {total} videos")
        print(f"  Tuyos: {propios.count if hasattr(propios, 'count') else 0}")
        print(f"  Competencia: {competencia.count if hasattr(competencia, 'count') else 0}")

        return total

    except Exception as e:
        print(f"[WARNING] Error verificando dataset: {e}")
        return 0

def main():
    """Función principal"""
    print("="*80)
    print("GUARDAR SNAPSHOT PARA ML")
    print("="*80)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Cargar entorno
    supabase_url, supabase_key = load_env()
    sb: Client = create_client(supabase_url, supabase_key)

    # Estado antes
    print("[ESTADO ANTES]")
    total_antes = verificar_estado_dataset(sb)

    # Guardar snapshots
    saved_competencia = guardar_snapshot_competencia(sb)
    saved_propios = guardar_snapshot_propios(sb)

    total_saved = saved_competencia + saved_propios

    # Estado después
    print("\n[ESTADO DESPUÉS]")
    total_despues = verificar_estado_dataset(sb)

    # Resumen
    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)
    print(f"Videos guardados: {total_saved}")
    print(f"  - Competencia: {saved_competencia}")
    print(f"  - Propios: {saved_propios}")
    print(f"Dataset ML: {total_antes} -> {total_despues} videos")
    print(f"Crecimiento: +{total_despues - total_antes} videos")
    print("\n" + "="*80)
    print("[OK] SNAPSHOT COMPLETADO")
    print("="*80)
    print("\n[IMPORTANTE] Estos datos se usarán para entrenar el modelo ML")
    print("[IMPORTANTE] NO se consumen unidades de YouTube API")
    print("[IMPORTANTE] Los datos en ml_training_data NUNCA se purgan\n")

if __name__ == "__main__":
    main()
