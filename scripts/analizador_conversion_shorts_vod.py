#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
========================================
CEREBRO 5: Analizador Conversión Shorts→VOD
========================================

Propósito:
    Analiza qué Shorts convierten espectadores a videos largos (VODs).
    Detecta "Loops de Dopamina" vs "Trailers de Valor".

Basado en:
    Conceptos de Gemini - "Format Conversion Rate" (FCR)
    "Short-to-VOD View" es la métrica más valiosa en YouTube 2024-2025

Costo API:
    YouTube Analytics API: 0 units (GRATIS)

Frecuencia:
    Semanal (lunes 7 AM UTC)

Versión: 4.4.0
Fecha: 2025-11-12
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from supabase import create_client
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configuración
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
YT_CLIENT_ID = os.getenv("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.getenv("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.getenv("YT_REFRESH_TOKEN")

# Constantes
THRESHOLD_LOOP_DOPAMINA = 5.0  # <5% conversión = Loop de Dopamina
THRESHOLD_TRAILER_VALOR = 15.0  # >15% conversión = Puente Perfecto

# Clientes
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def obtener_youtube_analytics():
    """
    Obtiene cliente de YouTube Analytics API
    """
    try:
        credentials = Credentials(
            token=None,
            refresh_token=YT_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET
        )

        youtube_analytics = build("youtubeAnalytics", "v2", credentials=credentials)
        print("[OK] Conectado a YouTube Analytics API")
        return youtube_analytics

    except Exception as e:
        print(f"[ERROR] No se pudo conectar a YouTube Analytics API: {e}")
        sys.exit(1)


def obtener_shorts_propios():
    """
    Obtiene lista de Shorts propios (videos < 60 segundos)
    """
    try:
        result = supabase.table("videos")\
            .select("video_id, title, published_at, view_count, vph, ctr, average_view_percentage, duration")\
            .eq("es_tuyo", True)\
            .lt("duration", 61)\
            .order("published_at", desc=True)\
            .execute()

        shorts = result.data if result.data else []
        print(f"[OK] {len(shorts)} Shorts propios encontrados")
        return shorts

    except Exception as e:
        print(f"[ERROR] No se pudieron obtener Shorts: {e}")
        return []


def analizar_conversion_short_a_vod(youtube_analytics, short_video_id, start_date, end_date):
    """
    Analiza conversión de un Short a VODs

    Usa YouTube Analytics API (0 units - GRATIS):
    - traffic_source_detail para detectar origen del tráfico
    - Filtra: Videos largos (>60s) con tráfico desde Shorts

    Returns:
        dict con métricas de conversión
    """
    try:
        # Query 1: Obtener views del Short
        result_short = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="video",
            filters=f"video=={short_video_id}"
        ).execute()

        short_views = 0
        if result_short.get("rows"):
            short_views = result_short["rows"][0][1]

        if short_views == 0:
            return {
                "short_views": 0,
                "vod_views_from_short": 0,
                "conversion_rate": 0.0,
                "top_vods": []
            }

        # Query 2: Obtener views de VODs desde Shorts (tráfico)
        # Nota: YouTube Analytics no expone directamente "desde qué Short específico"
        # Usamos proxy: Videos largos con tráfico desde "YT_SHORT" en el período
        result_vods = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="video,insightTrafficSourceDetail",
            filters="insightTrafficSourceType==YT_SHORT",
            sort="-views",
            maxResults=10
        ).execute()

        vod_views_from_short = 0
        top_vods = []

        if result_vods.get("rows"):
            for row in result_vods["rows"]:
                video_id = row[0]
                traffic_detail = row[1]
                views = row[2]

                # Filtrar solo VODs (>60s)
                video_info = supabase.table("videos")\
                    .select("title, duration")\
                    .eq("video_id", video_id)\
                    .eq("es_tuyo", True)\
                    .single()\
                    .execute()

                if video_info.data and video_info.data.get("duration", 0) > 60:
                    vod_views_from_short += views
                    top_vods.append({
                        "video_id": video_id,
                        "title": video_info.data.get("title", ""),
                        "views": views
                    })

        # Calcular tasa de conversión
        conversion_rate = (vod_views_from_short / short_views) * 100 if short_views > 0 else 0.0

        return {
            "short_views": short_views,
            "vod_views_from_short": vod_views_from_short,
            "conversion_rate": round(conversion_rate, 2),
            "top_vods": top_vods[:5]
        }

    except Exception as e:
        print(f"[WARN] Error analizando conversión de Short {short_video_id}: {e}")
        return {
            "short_views": 0,
            "vod_views_from_short": 0,
            "conversion_rate": 0.0,
            "top_vods": []
        }


def clasificar_short(conversion_rate):
    """
    Clasifica Short según tasa de conversión

    Clasificación:
    - LOOP_DOPAMINA: <5% (solo entretiene, no convierte)
    - TRAILER_VALOR: 5-15% (convierte decente)
    - PUENTE_PERFECTO: >15% (excelente embudo)
    """
    if conversion_rate < THRESHOLD_LOOP_DOPAMINA:
        return "LOOP_DOPAMINA"
    elif conversion_rate < THRESHOLD_TRAILER_VALOR:
        return "TRAILER_VALOR"
    else:
        return "PUENTE_PERFECTO"


def guardar_analisis_conversion(short_data, conversion_data, clasificacion):
    """
    Guarda análisis en Supabase
    """
    try:
        record = {
            "short_video_id": short_data["video_id"],
            "short_title": short_data["title"],
            "short_published_at": short_data["published_at"],
            "short_views": short_data["view_count"],
            "short_vph": float(short_data.get("vph", 0.0)),
            "short_ctr": float(short_data.get("ctr", 0.0)),
            "short_avg_view_percentage": float(short_data.get("average_view_percentage", 0.0)),
            "vod_views_from_short": conversion_data["vod_views_from_short"],
            "conversion_rate": conversion_data["conversion_rate"],
            "clasificacion": clasificacion,
            "top_vods_visited": conversion_data["top_vods"],
            "analyzed_at": datetime.now().isoformat()
        }

        # Upsert (insertar o actualizar)
        supabase.table("short_vod_conversion").upsert(record).execute()

    except Exception as e:
        print(f"[ERROR] No se pudo guardar análisis: {e}")


def generar_reporte(resultados):
    """
    Genera reporte consolidado
    """
    print("\n" + "="*60)
    print("REPORTE: CONVERSIÓN SHORTS → VOD")
    print("="*60)

    total_shorts = len(resultados)
    loop_dopamina = sum(1 for r in resultados if r["clasificacion"] == "LOOP_DOPAMINA")
    trailer_valor = sum(1 for r in resultados if r["clasificacion"] == "TRAILER_VALOR")
    puente_perfecto = sum(1 for r in resultados if r["clasificacion"] == "PUENTE_PERFECTO")

    conversion_avg = sum(r["conversion_rate"] for r in resultados) / total_shorts if total_shorts > 0 else 0.0

    print(f"\nShorts analizados: {total_shorts}")
    print(f"Tasa de conversión promedio: {conversion_avg:.2f}%")
    print(f"\nClasificación:")
    print(f"  - LOOP_DOPAMINA (<5%): {loop_dopamina} ({loop_dopamina/total_shorts*100:.1f}%)")
    print(f"  - TRAILER_VALOR (5-15%): {trailer_valor} ({trailer_valor/total_shorts*100:.1f}%)")
    print(f"  - PUENTE_PERFECTO (>15%): {puente_perfecto} ({puente_perfecto/total_shorts*100:.1f}%)")

    # Top 5 mejores convertidores
    top_5 = sorted(resultados, key=lambda x: x["conversion_rate"], reverse=True)[:5]
    print(f"\nTop 5 Shorts con mejor conversión:")
    for idx, short in enumerate(top_5, 1):
        print(f"  {idx}. {short['title'][:50]}... ({short['conversion_rate']:.2f}%)")

    # Recomendaciones estratégicas
    print(f"\n" + "="*60)
    print("RECOMENDACIONES ESTRATÉGICAS:")
    print("="*60)

    if puente_perfecto > 0:
        print(f"\n[EXCELENTE] {puente_perfecto} Shorts son Puentes Perfectos (>15% conversión)")
        print(f"  Acción: Analizar qué tienen en común estos Shorts")
        print(f"  Acción: Replicar estructura en futuros Shorts")

    if loop_dopamina > total_shorts * 0.5:
        print(f"\n[ALERTA] {loop_dopamina} Shorts son Loops de Dopamina (<5% conversión)")
        print(f"  Problema: {loop_dopamina/total_shorts*100:.0f}% de tus Shorts NO convierten a VODs")
        print(f"  Acción: Rediseñar Shorts para incluir 'gancho' hacia VODs")
        print(f"  Acción: Agregar CTA al final: 'Mira video completo en canal'")

    if trailer_valor > 0:
        print(f"\n[BUENO] {trailer_valor} Shorts son Trailers de Valor (5-15% conversión)")
        print(f"  Acción: Optimizar para llegar a >15% (Puente Perfecto)")

    print("\n" + "="*60)


def main():
    """
    Función principal
    """
    print("\n" + "="*60)
    print("ANALIZADOR CONVERSIÓN SHORTS → VOD")
    print("CEREBRO 5: Orquestador Estratégico")
    print("="*60 + "\n")

    # Conectar a YouTube Analytics
    youtube_analytics = obtener_youtube_analytics()

    # Obtener Shorts propios
    shorts = obtener_shorts_propios()

    if not shorts:
        print("[WARN] No hay Shorts para analizar")
        return

    # Definir período de análisis (últimos 28 días)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=28)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    print(f"[OK] Período de análisis: {start_date_str} a {end_date_str}")
    print(f"[OK] Analizando {len(shorts)} Shorts...\n")

    # Analizar cada Short
    resultados = []

    for idx, short in enumerate(shorts, 1):
        print(f"[{idx}/{len(shorts)}] Analizando: {short['title'][:50]}...")

        # Analizar conversión
        conversion_data = analizar_conversion_short_a_vod(
            youtube_analytics,
            short["video_id"],
            start_date_str,
            end_date_str
        )

        # Clasificar
        clasificacion = clasificar_short(conversion_data["conversion_rate"])

        # Guardar en Supabase
        guardar_analisis_conversion(short, conversion_data, clasificacion)

        # Registrar resultado
        resultados.append({
            "video_id": short["video_id"],
            "title": short["title"],
            "conversion_rate": conversion_data["conversion_rate"],
            "clasificacion": clasificacion
        })

        print(f"  Conversión: {conversion_data['conversion_rate']:.2f}% ({clasificacion})")

    # Generar reporte
    generar_reporte(resultados)

    print(f"\n[OK] Análisis completado")
    print(f"[OK] Datos guardados en tabla: short_vod_conversion")


if __name__ == "__main__":
    main()
