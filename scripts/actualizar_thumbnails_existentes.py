#!/usr/bin/env python3
"""
Script temporal para actualizar thumbnails de videos existentes
Ejecutar UNA SOLA VEZ después del fix de import_daily.py
"""
import os
from dotenv import load_dotenv
from supabase import create_client
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

load_dotenv()

# Configuración
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
YT_API_KEY = (os.getenv("YOUTUBE_API_KEY") or "").strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL y SUPABASE_SERVICE_KEY son requeridos en .env")
if not YT_API_KEY:
    raise RuntimeError("YOUTUBE_API_KEY es requerida en .env")

# Cliente Supabase
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cliente YouTube (sin OAuth, solo API key para detalles públicos)
yt = build("youtube", "v3", developerKey=YT_API_KEY) if YT_API_KEY else None

def obtener_videos_sin_thumbnails():
    """Obtiene todos los videos que NO tienen thumbnails"""
    result = sb.table("videos") \
        .select("video_id") \
        .is_("thumbnail_high", "null") \
        .execute()
    return [row["video_id"] for row in result.data]

def obtener_thumbnails_youtube(video_ids):
    """Obtiene thumbnails desde YouTube API (batch de 50)"""
    if not yt:
        print("[ERROR] YOUTUBE_API_KEY no configurada")
        return {}

    thumbnails_map = {}

    # YouTube API permite máximo 50 IDs por request
    batch_size = 50
    for i in range(0, len(video_ids), batch_size):
        batch = video_ids[i:i+batch_size]

        try:
            response = yt.videos().list(
                id=",".join(batch),
                part="snippet"
            ).execute()

            for item in response.get("items", []):
                video_id = item["id"]
                thumbnails = item["snippet"]["thumbnails"]

                thumbnails_map[video_id] = {
                    "thumbnail_default": thumbnails.get("default", {}).get("url"),
                    "thumbnail_medium": thumbnails.get("medium", {}).get("url"),
                    "thumbnail_high": thumbnails.get("high", {}).get("url"),
                    "thumbnail_standard": thumbnails.get("standard", {}).get("url"),
                    "thumbnail_maxres": thumbnails.get("maxres", {}).get("url")
                }

            print(f"[INFO] Procesados {len(batch)} videos (total: {i+len(batch)}/{len(video_ids)})")

        except Exception as e:
            print(f"[ERROR] Error obteniendo thumbnails batch {i}: {e}")

    return thumbnails_map

def actualizar_thumbnails_db(thumbnails_map):
    """Actualiza thumbnails en la base de datos"""
    total_actualizados = 0

    for video_id, thumbnails in thumbnails_map.items():
        try:
            sb.table("videos").update(thumbnails).eq("video_id", video_id).execute()
            total_actualizados += 1

            if total_actualizados % 50 == 0:
                print(f"[INFO] Actualizados {total_actualizados}/{len(thumbnails_map)} videos")

        except Exception as e:
            print(f"[ERROR] Error actualizando {video_id}: {e}")

    return total_actualizados

def main():
    print("="*80)
    print("ACTUALIZACIÓN DE THUMBNAILS PARA VIDEOS EXISTENTES")
    print("="*80)

    # 1. Obtener videos sin thumbnails
    print("\n[1/3] Obteniendo videos sin thumbnails...")
    video_ids = obtener_videos_sin_thumbnails()
    print(f"      Encontrados: {len(video_ids)} videos")

    if not video_ids:
        print("\n✅ Todos los videos ya tienen thumbnails!")
        return

    # 2. Obtener thumbnails desde YouTube API
    print(f"\n[2/3] Obteniendo thumbnails desde YouTube API...")
    print(f"      Esto usará ~{len(video_ids)} unidades de cuota API")
    thumbnails_map = obtener_thumbnails_youtube(video_ids)
    print(f"      Thumbnails obtenidos: {len(thumbnails_map)}")

    # 3. Actualizar base de datos
    print(f"\n[3/3] Actualizando base de datos...")
    total = actualizar_thumbnails_db(thumbnails_map)

    print("\n" + "="*80)
    print(f"✅ COMPLETADO: {total} videos actualizados con thumbnails")
    print("="*80)

    # Verificación final
    print("\n[VERIFICACIÓN] Consultando videos sin thumbnails...")
    pendientes = obtener_videos_sin_thumbnails()
    print(f"                Videos pendientes: {len(pendientes)}")

    if len(pendientes) == 0:
        print("\n🎉 ¡TODOS LOS VIDEOS TIENEN THUMBNAILS!")
    else:
        print(f"\n⚠️  Todavía quedan {len(pendientes)} videos sin thumbnails")
        print("    (Probablemente fueron eliminados de YouTube)")

if __name__ == "__main__":
    main()
