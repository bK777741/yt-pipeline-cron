#!/usr/bin/env python3
"""
import_captions.py
Descarga subtítulos de vídeos nuevos.
OPTIMIZADO: Límite de 2 videos/día para ahorrar cuota API
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client, Client

# Importar funciones de control de cuota
try:
    from nicho_utils import debe_ejecutarse_hoy, registrar_uso_cuota
    QUOTA_TRACKING_ENABLED = True
except ImportError:
    print("[WARNING] nicho_utils.py no encontrado - Control de cuota deshabilitado")
    QUOTA_TRACKING_ENABLED = False

# Límite diario de videos a procesar (ahorro de cuota)
MAX_VIDEOS_PER_DAY = 2

def load_env():
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
    yt = build("youtube", "v3", credentials=creds)
    sb: Client = create_client(supabase_url, supabase_key)
    return yt, sb

def fetch_recent_videos(sb: Client):
    threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
    resp = sb.table("videos") \
             .select("video_id") \
             .gte("imported_at", threshold.isoformat()) \
             .execute()
    return [row["video_id"] for row in resp.data]

def download_caption(yt, video_id, language="es"):
    try:
        captions = yt.captions().list(part="id", videoId=video_id).execute()
        for item in captions.get("items", []):
            if item.get("snippet", {}).get("language") == language:
                caption = yt.captions().download(id=item["id"]).execute()
                return caption.decode("utf-8")
    except Exception as e:
        print(f"Error downloading caption: {e}")
    return None

def upsert_caption(sb: Client, video_id, text, language="es"):
    sb.table("captions").upsert({
        "video_id": video_id,
        "language": language,
        "caption_text": text,
        "imported_at": "now()"
    }, on_conflict=["video_id", "language"]).execute()

def main():
    creds, supabase_url, supabase_key = load_env()
    yt, sb = init_clients(creds, supabase_url, supabase_key)

    # Control de frecuencia (ejecutar cada 3 días)
    # FIX 2025-11-03: Verificar watermarks correctamente
    if QUOTA_TRACKING_ENABLED:
        if not debe_ejecutarse_hoy("import_captions", sb):
            # Obtener días transcurridos para debug
            try:
                result = sb.table("script_execution_log") \
                    .select("last_run") \
                    .eq("script_name", "import_captions") \
                    .order("last_run", desc=True) \
                    .limit(1) \
                    .execute()

                if result.data:
                    from datetime import timezone as tz
                    last_run = datetime.fromisoformat(result.data[0]["last_run"].replace('Z', '+00:00'))
                    dias = (datetime.now(tz.utc) - last_run).days
                    print(f"[import_captions] Última ejecución: {last_run.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    print(f"[import_captions] Días transcurridos: {dias}/3")
                    print("[import_captions] No debe ejecutarse hoy (frecuencia: cada 3 días)")
                else:
                    print("[import_captions] No se encontró registro previo en script_execution_log")
            except Exception as e:
                print(f"[import_captions] Error verificando watermark: {e}")

            print("[import_captions] Saltando ejecución para ahorrar cuota")
            sys.exit(0)

    video_ids = fetch_recent_videos(sb)

    # Limitar a MAX_VIDEOS_PER_DAY para ahorrar cuota
    if len(video_ids) > MAX_VIDEOS_PER_DAY:
        print(f"[import_captions] Limitando a {MAX_VIDEOS_PER_DAY} videos (de {len(video_ids)} disponibles)")
        video_ids = video_ids[:MAX_VIDEOS_PER_DAY]

    # Tracking de cuota API
    api_calls = 0
    captions_downloaded = 0

    for vid in video_ids:
        caption_text = download_caption(yt, vid)
        api_calls += 1  # captions().list = 50 unidades

        if caption_text:
            upsert_caption(sb, vid, caption_text)
            api_calls += 1  # captions().download = 200 unidades
            captions_downloaded += 1
            time.sleep(1)  # Evitar rate limits

    # Registrar cuota usada
    if QUOTA_TRACKING_ENABLED and api_calls > 0:
        # Costo estimado: list (50) + download (200) por video exitoso
        total_units = (captions_downloaded * 250)  # 50 + 200 por caption descargado
        registrar_uso_cuota("captions", total_units, sb)
        print(f"[import_captions] Cuota API usada: {total_units} unidades")

    # FIX 2025-11-01: Registrar ejecución exitosa para watermark
    if QUOTA_TRACKING_ENABLED:
        try:
            from datetime import timezone as tz
            sb.table("script_execution_log").upsert({
                "script_name": "import_captions",
                "last_run": datetime.now(tz.utc).isoformat(),
                "status": "success"
            }, on_conflict="script_name").execute()
        except Exception as e:
            print(f"[WARNING] Error registrando watermark: {e}")

    print(f"[import_captions] Subtítulos procesados: {captions_downloaded}/{len(video_ids)}")

if __name__ == "__main__":
    main()
