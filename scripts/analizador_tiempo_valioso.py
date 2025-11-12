#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
========================================
CEREBRO 5: Analizador Tiempo Valioso (Regret Index)
========================================

Propósito:
    Predice "arrepentimiento" del espectador usando proxies.
    Diferencia entre "Tiempo Vacío" vs "Tiempo Valioso".

Basado en:
    Conceptos de Gemini - "Valuable Watch Time" (VWT)
    El algoritmo busca contenido de cero arrepentimiento

Costo API:
    YouTube Analytics API: 0 units (GRATIS)
    Usa datos ya capturados + proxies

Frecuencia:
    Semanal (lunes 8 AM UTC)

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


def obtener_videos_propios():
    """
    Obtiene lista de videos propios
    """
    try:
        result = supabase.table("videos")\
            .select("*")\
            .eq("es_tuyo", True)\
            .order("published_at", desc=True)\
            .limit(100)\
            .execute()

        videos = result.data if result.data else []
        print(f"[OK] {len(videos)} videos propios encontrados")
        return videos

    except Exception as e:
        print(f"[ERROR] No se pudieron obtener videos: {e}")
        return []


def calcular_next_video_same_channel_rate(youtube_analytics, video_id, start_date, end_date):
    """
    Calcula tasa de "Siguiente del mismo canal"

    Proxy de confianza:
    - Alto % = Usuario confía, quiere más (Bajo Regret)
    - Bajo % = Usuario no confía, se va (Alto Regret)

    Usa Analytics API (0 units):
    - traffic_source = "END_SCREEN" o "SUGGESTED_VIDEO"
    """
    try:
        result = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}"
        ).execute()

        total_views = 0
        same_channel_views = 0

        if result.get("rows"):
            for row in result["rows"]:
                traffic_source = row[0]
                views = row[1]
                total_views += views

                # Tráfico desde end screens o sugeridos del mismo canal
                if traffic_source in ["END_SCREEN", "SUGGESTED_VIDEO", "RELATED_VIDEO"]:
                    same_channel_views += views

        rate = (same_channel_views / total_views) * 100 if total_views > 0 else 0.0
        return round(rate, 2)

    except Exception as e:
        print(f"[WARN] Error calculando next_video_same_channel_rate: {e}")
        return 0.0


def calcular_engagement_quality_score(video):
    """
    Engagement Quality Score

    Fórmula:
    (likes / views) * 100 + (comments / views) * 500

    Alto engagement = satisfacción (Bajo Regret)
    """
    views = video.get("view_count", 0)
    likes = video.get("like_count", 0)
    comments = video.get("comment_count", 0)

    if views == 0:
        return 0.0

    score = (likes / views) * 100 + (comments / views) * 500
    return round(min(score, 100), 2)  # Cap a 100


def calcular_healthy_retention_score(video):
    """
    Retención Saludable

    Criterios:
    - AVD > 50% = Bueno (base 50 puntos)
    - AVD > 60% = Muy bueno (base 70 puntos)
    - AVD > 70% = Excelente (base 90 puntos)
    - Penaliza: Si parece clickbait (CTR alto + AVD bajo)

    Score: 0-100
    """
    avd = video.get("average_view_percentage", 0.0)
    ctr = video.get("ctr", 0.0)

    # Base score por AVD
    if avd >= 70:
        base_score = 90
    elif avd >= 60:
        base_score = 70
    elif avd >= 50:
        base_score = 50
    else:
        base_score = avd * 0.8  # Penaliza AVD bajo

    # Penaliza clickbait (CTR alto + AVD bajo)
    if ctr > 10 and avd < 40:
        base_score *= 0.5  # Penalización 50%

    return round(min(base_score, 100), 2)


def detectar_es_pasarela(video):
    """
    Detecta si es video pasarela (>40% búsqueda)

    Si es pasarela = resolvió problema = Bajo Regret
    """
    search_percentage = video.get("search_percentage", 0.0)
    return search_percentage >= 40.0


def calcular_regret_index(
    next_video_rate,
    engagement_score,
    retention_score,
    is_gateway
):
    """
    Calcula Regret Index Final

    Score: 0-100
    - 0-20: CERO arrepentimiento (contenido nutritivo)
    - 21-40: BAJO arrepentimiento (buen contenido)
    - 41-60: MEDIO arrepentimiento (contenido promedio)
    - 61-80: ALTO arrepentimiento (contenido vacío)
    - 81-100: CRÍTICO arrepentimiento (comida chatarra)

    Fórmula:
    regret_index = 100 - (
        next_video_rate * 0.35 +
        engagement_score * 0.25 +
        retention_score * 0.25 +
        (is_gateway ? 15 : 0)
    )
    """
    valor_positivo = (
        next_video_rate * 0.35 +
        engagement_score * 0.25 +
        retention_score * 0.25 +
        (15 if is_gateway else 0)
    )

    regret_index = 100 - valor_positivo
    regret_index = max(0, min(100, regret_index))  # Clamp entre 0-100

    return round(regret_index, 2)


def clasificar_valor(regret_index):
    """
    Clasifica contenido según Regret Index

    Clasificación:
    - NUTRITIVO: 0-20 (cero arrepentimiento)
    - BUENO: 21-40 (bajo arrepentimiento)
    - PROMEDIO: 41-60 (medio arrepentimiento)
    - VACIO: 61-80 (alto arrepentimiento)
    - CHATARRA: 81-100 (crítico arrepentimiento)
    """
    if regret_index <= 20:
        return "NUTRITIVO"
    elif regret_index <= 40:
        return "BUENO"
    elif regret_index <= 60:
        return "PROMEDIO"
    elif regret_index <= 80:
        return "VACIO"
    else:
        return "CHATARRA"


def generar_recomendaciones(regret_index, clasificacion, is_gateway, engagement_score):
    """
    Genera recomendaciones específicas
    """
    recomendaciones = []

    if clasificacion == "NUTRITIVO":
        recomendaciones.append("Excelente: Contenido de alto valor, mantén este estándar")
        if is_gateway:
            recomendaciones.append("Videos que resuelven problemas generan fidelidad")
        if engagement_score > 50:
            recomendaciones.append("Alto engagement indica satisfacción del espectador")

    elif clasificacion == "BUENO":
        recomendaciones.append("Buen contenido, puede mejorarse ligeramente")
        if not is_gateway:
            recomendaciones.append("Considera optimizar para búsqueda (resolver problemas)")
        if engagement_score < 30:
            recomendaciones.append("Mejorar engagement: agregar CTAs o preguntas")

    elif clasificacion == "PROMEDIO":
        recomendaciones.append("Contenido promedio, requiere optimización")
        recomendaciones.append("Analizar: ¿El video entrega lo que promete el título?")
        if engagement_score < 20:
            recomendaciones.append("Bajo engagement: revisar calidad del contenido")

    elif clasificacion == "VACIO":
        recomendaciones.append("ALERTA: Contenido con alto arrepentimiento")
        recomendaciones.append("Revisar: ¿Es clickbait? ¿Cumple expectativas del título?")
        recomendaciones.append("Acción: Evitar crear contenido similar")

    elif clasificacion == "CHATARRA":
        recomendaciones.append("CRÍTICO: Contenido chatarra, daña confianza del canal")
        recomendaciones.append("Acción URGENTE: Ocultar video o mejorar drásticamente")
        recomendaciones.append("No replicar estructura/tema de este video")

    return recomendaciones


def guardar_analisis_tiempo_valioso(video, analisis):
    """
    Guarda análisis en Supabase
    """
    try:
        video_type = "SHORT" if video.get("duration", 0) <= 60 else "VOD"

        record = {
            "video_id": video["video_id"],
            "video_title": video["title"],
            "video_type": video_type,
            "next_video_same_channel_rate": analisis["next_video_rate"],
            "engagement_quality_score": analisis["engagement_score"],
            "healthy_retention_score": analisis["retention_score"],
            "is_gateway": analisis["is_gateway"],
            "gateway_search_percentage": video.get("search_percentage", 0.0),
            "regret_index": analisis["regret_index"],
            "clasificacion_valor": analisis["clasificacion"],
            "recomendaciones": analisis["recomendaciones"],
            "analyzed_at": datetime.now().isoformat()
        }

        # Upsert
        supabase.table("tiempo_valioso_analysis").upsert(record).execute()

    except Exception as e:
        print(f"[ERROR] No se pudo guardar análisis: {e}")


def generar_reporte(resultados):
    """
    Genera reporte consolidado
    """
    print("\n" + "="*60)
    print("REPORTE: TIEMPO VALIOSO (REGRET INDEX)")
    print("="*60)

    total_videos = len(resultados)
    nutritivo = sum(1 for r in resultados if r["clasificacion"] == "NUTRITIVO")
    bueno = sum(1 for r in resultados if r["clasificacion"] == "BUENO")
    promedio = sum(1 for r in resultados if r["clasificacion"] == "PROMEDIO")
    vacio = sum(1 for r in resultados if r["clasificacion"] == "VACIO")
    chatarra = sum(1 for r in resultados if r["clasificacion"] == "CHATARRA")

    regret_avg = sum(r["regret_index"] for r in resultados) / total_videos if total_videos > 0 else 0.0

    print(f"\nVideos analizados: {total_videos}")
    print(f"Regret Index promedio: {regret_avg:.2f}")
    print(f"\nClasificación:")
    print(f"  - NUTRITIVO (0-20): {nutritivo} ({nutritivo/total_videos*100:.1f}%)")
    print(f"  - BUENO (21-40): {bueno} ({bueno/total_videos*100:.1f}%)")
    print(f"  - PROMEDIO (41-60): {promedio} ({promedio/total_videos*100:.1f}%)")
    print(f"  - VACIO (61-80): {vacio} ({vacio/total_videos*100:.1f}%)")
    print(f"  - CHATARRA (81-100): {chatarra} ({chatarra/total_videos*100:.1f}%)")

    # Top 5 contenido nutritivo
    top_nutritivo = sorted(
        [r for r in resultados if r["clasificacion"] in ["NUTRITIVO", "BUENO"]],
        key=lambda x: x["regret_index"]
    )[:5]
    print(f"\nTop 5 Contenido Nutritivo (menor regret):")
    for idx, video in enumerate(top_nutritivo, 1):
        print(f"  {idx}. {video['title'][:50]}... (Regret: {video['regret_index']})")

    # Top 5 contenido chatarra
    top_chatarra = sorted(resultados, key=lambda x: x["regret_index"], reverse=True)[:5]
    print(f"\nTop 5 Contenido con Mayor Arrepentimiento:")
    for idx, video in enumerate(top_chatarra, 1):
        print(f"  {idx}. {video['title'][:50]}... (Regret: {video['regret_index']})")

    # Recomendaciones estratégicas
    print(f"\n" + "="*60)
    print("RECOMENDACIONES ESTRATÉGICAS:")
    print("="*60)

    if chatarra > 0:
        print(f"\n[CRÍTICO] {chatarra} videos son contenido CHATARRA (regret > 80)")
        print(f"  Acción: Revisar estos videos urgentemente")
        print(f"  Acción: Considerar ocultarlos o mejorarlos drásticamente")

    if vacio > 0:
        print(f"\n[ALERTA] {vacio} videos tienen alto arrepentimiento (regret 61-80)")
        print(f"  Acción: Analizar qué tienen en común estos videos")
        print(f"  Acción: Evitar replicar estructura/temas similares")

    nutritivo_percent = (nutritivo / total_videos) * 100 if total_videos > 0 else 0
    if nutritivo_percent >= 30:
        print(f"\n[EXCELENTE] {nutritivo_percent:.0f}% de tu contenido es NUTRITIVO")
        print(f"  Acción: Analizar qué hace que este contenido sea valioso")
        print(f"  Acción: Replicar estructura en futuros videos")
    else:
        print(f"\n[MEJORABLE] Solo {nutritivo_percent:.0f}% de tu contenido es NUTRITIVO")
        print(f"  Meta: Llegar a 30%+ de contenido nutritivo")
        print(f"  Acción: Enfocarse en resolver problemas reales")

    print("\n" + "="*60)


def main():
    """
    Función principal
    """
    print("\n" + "="*60)
    print("ANALIZADOR TIEMPO VALIOSO (REGRET INDEX)")
    print("CEREBRO 5: Orquestador Estratégico")
    print("="*60 + "\n")

    # Conectar a YouTube Analytics
    youtube_analytics = obtener_youtube_analytics()

    # Obtener videos propios
    videos = obtener_videos_propios()

    if not videos:
        print("[WARN] No hay videos para analizar")
        return

    # Definir período de análisis (últimos 28 días)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=28)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    print(f"[OK] Período de análisis: {start_date_str} a {end_date_str}")
    print(f"[OK] Analizando {len(videos)} videos...\n")

    # Analizar cada video
    resultados = []

    for idx, video in enumerate(videos, 1):
        print(f"[{idx}/{len(videos)}] Analizando: {video['title'][:50]}...")

        # Calcular proxies
        next_video_rate = calcular_next_video_same_channel_rate(
            youtube_analytics,
            video["video_id"],
            start_date_str,
            end_date_str
        )

        engagement_score = calcular_engagement_quality_score(video)
        retention_score = calcular_healthy_retention_score(video)
        is_gateway = detectar_es_pasarela(video)

        # Calcular Regret Index
        regret_index = calcular_regret_index(
            next_video_rate,
            engagement_score,
            retention_score,
            is_gateway
        )

        # Clasificar
        clasificacion = clasificar_valor(regret_index)

        # Recomendaciones
        recomendaciones = generar_recomendaciones(
            regret_index,
            clasificacion,
            is_gateway,
            engagement_score
        )

        # Analisis completo
        analisis = {
            "next_video_rate": next_video_rate,
            "engagement_score": engagement_score,
            "retention_score": retention_score,
            "is_gateway": is_gateway,
            "regret_index": regret_index,
            "clasificacion": clasificacion,
            "recomendaciones": recomendaciones
        }

        # Guardar en Supabase
        guardar_analisis_tiempo_valioso(video, analisis)

        # Registrar resultado
        resultados.append({
            "video_id": video["video_id"],
            "title": video["title"],
            "regret_index": regret_index,
            "clasificacion": clasificacion
        })

        print(f"  Regret Index: {regret_index} ({clasificacion})")

    # Generar reporte
    generar_reporte(resultados)

    print(f"\n[OK] Análisis completado")
    print(f"[OK] Datos guardados en tabla: tiempo_valioso_analysis")


if __name__ == "__main__":
    main()
