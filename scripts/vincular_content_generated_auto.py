#!/usr/bin/env python3
"""
VINCULACION AUTOMATICA - content_generated con videos
======================================================
Vincula automáticamente contenido generado con videos publicados en YouTube

Flujo:
1. Lee videos capturados en tabla 'videos' (is_tuyo=1)
2. Lee content_generated con status='borrador' o video_id=NULL
3. Busca coincidencias por similitud de título
4. Vincula automáticamente y marca como 'published'

Frecuencia: DIARIO (después de import_daily.py)
Repo: Cuenta 1 (bK777741/yt-pipeline-cron)
"""
import os, sys
from datetime import datetime, timedelta
from supabase import create_client
from difflib import SequenceMatcher

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

def conectar():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] Faltan credenciales Supabase")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def similitud_titulos(titulo1, titulo2):
    """Calcula similitud entre 2 titulos (0-100%)"""
    if not titulo1 or not titulo2:
        return 0

    # Normalizar: lowercase, sin espacios extras
    t1 = " ".join(titulo1.lower().strip().split())
    t2 = " ".join(titulo2.lower().strip().split())

    # SequenceMatcher de difflib
    ratio = SequenceMatcher(None, t1, t2).ratio()
    return round(ratio * 100, 2)

def main():
    print("="*60)
    print("VINCULACION AUTOMATICA - content_generated con videos")
    print(f"Fecha: {datetime.now()}")
    print("="*60)

    sb = conectar()

    # 1. Obtener videos publicados (últimos 30 días)
    print("\n[1/4] Obteniendo videos publicados...")
    fecha_limite = (datetime.now() - timedelta(days=30)).isoformat()

    videos = sb.table("videos").select(
        "video_id, title, published_at"
    ).eq("is_tuyo", True).gte("published_at", fecha_limite).execute()

    print(f"   [OK] {len(videos.data)} videos encontrados (últimos 30 días)")

    if not videos.data:
        print("\n[INFO] No hay videos recientes para vincular")
        return

    # 2. Obtener content_generated sin vincular
    print("\n[2/4] Obteniendo content_generated sin vincular...")

    # Buscar: status='borrador' O video_id=NULL
    contents = sb.table("content_generated").select(
        "id, tema_base, titulo_final, created_at"
    ).or_("status.eq.borrador,video_id.is.null").execute()

    print(f"   [OK] {len(contents.data)} contenidos sin vincular")

    if not contents.data:
        print("\n[INFO] Todos los contenidos ya están vinculados")
        return

    # 3. Vincular por similitud de título
    print("\n[3/4] Vinculando por similitud de título...")

    vinculados = 0
    UMBRAL_SIMILITUD = 70  # 70% de similitud mínima

    for content in contents.data:
        titulo_generado = content.get("titulo_final") or content.get("tema_base", "")

        if not titulo_generado:
            continue

        mejor_match = None
        mejor_similitud = 0

        # Buscar mejor coincidencia
        for video in videos.data:
            titulo_video = video.get("title", "")
            similitud = similitud_titulos(titulo_generado, titulo_video)

            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_match = video

        # Si similitud >= 70%, vincular
        if mejor_similitud >= UMBRAL_SIMILITUD and mejor_match:
            video_id = mejor_match["video_id"]
            published_at = mejor_match["published_at"]

            print(f"\n   [MATCH] Similitud: {mejor_similitud}%")
            print(f"   Generado: {titulo_generado[:60]}...")
            print(f"   Video:    {mejor_match['title'][:60]}...")
            print(f"   Video ID: {video_id}")

            # Actualizar content_generated
            try:
                sb.table("content_generated").update({
                    "video_id": video_id,
                    "status": "published",
                    "published_at": published_at,
                    "updated_at": datetime.now().isoformat()
                }).eq("id", content["id"]).execute()

                vinculados += 1
                print(f"   [OK] Vinculado exitosamente")

            except Exception as e:
                print(f"   [ERROR] No se pudo vincular: {e}")

        elif mejor_similitud > 50:
            # Similitud media (50-69%) - solo reportar
            print(f"\n   [SKIP] Similitud media: {mejor_similitud}% (< {UMBRAL_SIMILITUD}%)")
            print(f"   Generado: {titulo_generado[:50]}...")
            print(f"   Video:    {mejor_match['title'][:50] if mejor_match else 'N/A'}...")

    # 4. Reporte final
    print(f"\n{'='*60}")
    print(f"[OK] Proceso completado")
    print(f"{'='*60}")
    print(f"Videos analizados: {len(videos.data)}")
    print(f"Contenidos sin vincular: {len(contents.data)}")
    print(f"Vinculaciones exitosas: {vinculados}")
    print(f"{'='*60}")

    # Estadísticas finales
    total_vinculados = sb.table("content_generated").select(
        "id", count="exact"
    ).eq("status", "published").not_.is_("video_id", "null").execute()

    print(f"\nTotal content_generated vinculados: {total_vinculados.count}")
    print(f"Listos para Feedback Loop: {total_vinculados.count}")

if __name__ == "__main__":
    main()
