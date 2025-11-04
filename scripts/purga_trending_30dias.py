#!/usr/bin/env python3
"""
purga_trending_30dias.py
Eliminar TODOS los datos de competencia mayores a 30 días de Supabase

FRECUENCIA: Diaria (ligero, sin costo API)
OBJETIVO: Mantener solo contenido fresco del mes actual

TABLAS DE COMPETENCIA PURGADAS:
- video_trending (published_at)
- hidden_gems (discovered_at)
- video_trending_filtered (run_date)

FIX 2025-11-04: Ampliado para purgar TODAS las tablas de competencia
"""

import os
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

def load_env():
    """Cargar variables de entorno"""
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return supabase_url, supabase_key

def purge_old_trending_videos(sb: Client, days=30):
    """
    Eliminar videos de video_trending más antiguos que N días

    Args:
        sb: Cliente de Supabase
        days: Días de antigüedad para purga (default: 30)
    """
    try:
        # Calcular fecha límite
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat()

        print(f"[purga_trending_30dias] Eliminando videos con published_at < {cutoff_date.strftime('%Y-%m-%d')}")

        # Contar videos a eliminar (para estadísticas)
        count_result = sb.table("video_trending") \
            .select("video_id", count="exact") \
            .lt("published_at", cutoff_iso) \
            .execute()

        videos_to_delete = count_result.count if hasattr(count_result, 'count') else 0

        if videos_to_delete == 0:
            print("[purga_trending_30dias] ✅ No hay videos para purgar")
            return 0

        # Eliminar videos antiguos
        delete_result = sb.table("video_trending") \
            .delete() \
            .lt("published_at", cutoff_iso) \
            .execute()

        print(f"[purga_trending_30dias] ✅ Videos eliminados: {videos_to_delete}")
        return videos_to_delete

    except Exception as e:
        print(f"[ERROR] Error en purga: {e}")
        return 0

def purge_old_hidden_gems(sb: Client, days=30):
    """
    Eliminar hidden gems más antiguos que N días

    Args:
        sb: Cliente de Supabase
        days: Días de antigüedad para purga (default: 30)
    """
    try:
        # Calcular fecha límite
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat()

        print(f"[purga_trending_30dias] Eliminando hidden gems con discovered_at < {cutoff_date.strftime('%Y-%m-%d')}")

        # Contar gems a eliminar (para estadísticas)
        count_result = sb.table("hidden_gems") \
            .select("video_id", count="exact") \
            .lt("discovered_at", cutoff_iso) \
            .execute()

        gems_to_delete = count_result.count if hasattr(count_result, 'count') else 0

        if gems_to_delete == 0:
            print("[purga_trending_30dias] ✅ No hay hidden gems para purgar")
            return 0

        # Eliminar gems antiguos
        delete_result = sb.table("hidden_gems") \
            .delete() \
            .lt("discovered_at", cutoff_iso) \
            .execute()

        print(f"[purga_trending_30dias] ✅ Hidden gems eliminados: {gems_to_delete}")
        return gems_to_delete

    except Exception as e:
        print(f"[ERROR] Error en purga de hidden gems: {e}")
        return 0

def purge_old_trending_filtered(sb: Client, days=30):
    """
    Eliminar video_trending_filtered más antiguos que N días

    Args:
        sb: Cliente de Supabase
        days: Días de antigüedad para purga (default: 30)
    """
    try:
        # Calcular fecha límite
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_date_str = cutoff_date.date().isoformat()

        print(f"[purga_trending_30dias] Eliminando trending_filtered con run_date < {cutoff_date_str}")

        # Contar registros a eliminar (para estadísticas)
        count_result = sb.table("video_trending_filtered") \
            .select("video_id", count="exact") \
            .lt("run_date", cutoff_date_str) \
            .execute()

        filtered_to_delete = count_result.count if hasattr(count_result, 'count') else 0

        if filtered_to_delete == 0:
            print("[purga_trending_30dias] ✅ No hay trending_filtered para purgar")
            return 0

        # Eliminar registros antiguos
        delete_result = sb.table("video_trending_filtered") \
            .delete() \
            .lt("run_date", cutoff_date_str) \
            .execute()

        print(f"[purga_trending_30dias] ✅ Trending filtered eliminados: {filtered_to_delete}")
        return filtered_to_delete

    except Exception as e:
        print(f"[ERROR] Error en purga de trending_filtered: {e}")
        return 0

def purge_orphaned_data(sb: Client):
    """
    Eliminar datos huérfanos relacionados con videos eliminados

    - Captions de videos que ya no existen
    - Analytics de videos eliminados
    - Etc.
    """
    try:
        # Obtener IDs de videos trending actuales
        trending_videos = sb.table("video_trending").select("video_id").execute()
        valid_ids = {row["video_id"] for row in trending_videos.data} if trending_videos.data else set()

        # Obtener IDs de videos propios del canal
        own_videos = sb.table("videos").select("video_id").execute()
        if own_videos.data:
            valid_ids.update({row["video_id"] for row in own_videos.data})

        print(f"[purga_trending_30dias] Videos válidos totales: {len(valid_ids)}")

        # Purgar captions huérfanos
        all_captions = sb.table("captions").select("video_id").execute()
        orphaned_count = 0

        if all_captions.data:
            for caption in all_captions.data:
                if caption["video_id"] not in valid_ids:
                    try:
                        sb.table("captions").delete().eq("video_id", caption["video_id"]).execute()
                        orphaned_count += 1
                    except:
                        pass

        if orphaned_count > 0:
            print(f"[purga_trending_30dias] ✅ Captions huérfanos eliminados: {orphaned_count}")
        else:
            print(f"[purga_trending_30dias] ✅ No hay captions huérfanos")

        return orphaned_count

    except Exception as e:
        print(f"[WARNING] Error purgando datos huérfanos: {e}")
        return 0

def get_storage_stats(sb: Client):
    """Obtener estadísticas de almacenamiento"""
    try:
        # Contar videos trending
        trending_count = sb.table("video_trending").select("video_id", count="exact").execute()
        trending_total = trending_count.count if hasattr(trending_count, 'count') else 0

        # Contar hidden gems
        gems_count = sb.table("hidden_gems").select("video_id", count="exact").execute()
        gems_total = gems_count.count if hasattr(gems_count, 'count') else 0

        # Contar trending filtered
        filtered_count = sb.table("video_trending_filtered").select("video_id", count="exact").execute()
        filtered_total = filtered_count.count if hasattr(filtered_count, 'count') else 0

        # Contar videos propios
        own_count = sb.table("videos").select("video_id", count="exact").execute()
        own_total = own_count.count if hasattr(own_count, 'count') else 0

        # Contar captions
        captions_count = sb.table("captions").select("video_id", count="exact").execute()
        captions_total = captions_count.count if hasattr(captions_count, 'count') else 0

        print(f"\n[purga_trending_30dias] 📊 ESTADÍSTICAS DE ALMACENAMIENTO:")
        print(f"  - Videos trending: {trending_total}")
        print(f"  - Hidden gems: {gems_total}")
        print(f"  - Trending filtered: {filtered_total}")
        print(f"  - Videos propios del canal: {own_total}")
        print(f"  - Captions totales: {captions_total}")

        return {
            "trending": trending_total,
            "hidden_gems": gems_total,
            "trending_filtered": filtered_total,
            "own_videos": own_total,
            "captions": captions_total
        }

    except Exception as e:
        print(f"[WARNING] Error obteniendo estadísticas: {e}")
        return {}

def main():
    print("[purga_trending_30dias] 🗑️ Iniciando purga de TODOS los datos de competencia antiguos...")

    # Cargar entorno
    supabase_url, supabase_key = load_env()
    sb: Client = create_client(supabase_url, supabase_key)

    # Estadísticas ANTES de purga
    print("\n--- ANTES DE PURGA ---")
    stats_before = get_storage_stats(sb)

    # Purgar videos > 30 días
    deleted_trending = purge_old_trending_videos(sb, days=30)

    # Purgar hidden gems > 30 días
    deleted_gems = purge_old_hidden_gems(sb, days=30)

    # Purgar trending filtered > 30 días
    deleted_filtered = purge_old_trending_filtered(sb, days=30)

    # Purgar datos huérfanos
    deleted_orphaned = purge_orphaned_data(sb)

    # Estadísticas DESPUÉS de purga
    print("\n--- DESPUÉS DE PURGA ---")
    stats_after = get_storage_stats(sb)

    # Resumen
    print(f"\n[purga_trending_30dias] ✅ RESUMEN:")
    print(f"  - Videos trending eliminados: {deleted_trending}")
    print(f"  - Hidden gems eliminados: {deleted_gems}")
    print(f"  - Trending filtered eliminados: {deleted_filtered}")
    print(f"  - Datos huérfanos eliminados: {deleted_orphaned}")

    if stats_before and stats_after:
        saved_trending = stats_before.get("trending", 0) - stats_after.get("trending", 0)
        saved_gems = stats_before.get("hidden_gems", 0) - stats_after.get("hidden_gems", 0)
        saved_filtered = stats_before.get("trending_filtered", 0) - stats_after.get("trending_filtered", 0)
        saved_captions = stats_before.get("captions", 0) - stats_after.get("captions", 0)
        print(f"  - Espacio liberado (trending): {saved_trending} registros")
        print(f"  - Espacio liberado (hidden_gems): {saved_gems} registros")
        print(f"  - Espacio liberado (trending_filtered): {saved_filtered} registros")
        print(f"  - Espacio liberado (captions): {saved_captions} registros")

    print("\n[purga_trending_30dias] ✅ Proceso completado - TODOS los datos de competencia >30 días han sido eliminados")

if __name__ == "__main__":
    main()
