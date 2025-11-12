#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
========================================
CEREBRO 5: Orquestador Estratégico (MAESTRO)
========================================

Propósito:
    Ejecuta todos los análisis estratégicos y genera insights consolidados.
    Integra: Conversión Shorts→VOD + Tiempo Valioso + Proyectos Atómicos

Basado en:
    Conceptos de Gemini - Visión estratégica completa del canal

Costo API:
    YouTube Analytics API: 0 units (GRATIS)
    Gemini API: GRATIS (1 request para recomendaciones)

Frecuencia:
    Semanal (lunes 9 AM UTC)

Versión: 4.4.0
Fecha: 2025-11-12
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configuración
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Cliente
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Paths de scripts
SCRIPT_DIR = Path(__file__).parent
CONVERSION_SCRIPT = SCRIPT_DIR / "analizador_conversion_shorts_vod.py"
TIEMPO_VALIOSO_SCRIPT = SCRIPT_DIR / "analizador_tiempo_valioso.py"


def ejecutar_script(script_path, descripcion):
    """
    Ejecuta un script Python y captura su salida
    """
    print(f"\n{'='*60}")
    print(f"EJECUTANDO: {descripcion}")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos máximo
        )

        print(result.stdout)

        if result.returncode != 0:
            print(f"[ERROR] Script falló con código: {result.returncode}")
            print(result.stderr)
            return False

        return True

    except subprocess.TimeoutExpired:
        print(f"[ERROR] Script excedió tiempo límite de 10 minutos")
        return False
    except Exception as e:
        print(f"[ERROR] Error ejecutando script: {e}")
        return False


def obtener_analisis_conversion_shorts():
    """
    Obtiene resumen del análisis de conversión Shorts→VOD
    """
    try:
        # Obtener datos de últimos 7 días
        fecha_limite = datetime.now() - timedelta(days=7)

        result = supabase.table("short_vod_conversion")\
            .select("*")\
            .gte("analyzed_at", fecha_limite.isoformat())\
            .execute()

        shorts = result.data if result.data else []

        if not shorts:
            return {
                "shorts_analyzed": 0,
                "conversion_rate_avg": 0.0,
                "best_converting_short": None,
                "conversion_trend": "SIN_DATOS"
            }

        conversion_avg = sum(s.get("conversion_rate", 0) for s in shorts) / len(shorts)

        best_short = max(shorts, key=lambda s: s.get("conversion_rate", 0))

        # Detectar tendencia (comparar con semana anterior)
        fecha_semana_anterior = fecha_limite - timedelta(days=7)
        result_anterior = supabase.table("short_vod_conversion")\
            .select("conversion_rate")\
            .gte("analyzed_at", fecha_semana_anterior.isoformat())\
            .lt("analyzed_at", fecha_limite.isoformat())\
            .execute()

        shorts_anterior = result_anterior.data if result_anterior.data else []

        if shorts_anterior:
            conversion_anterior = sum(s.get("conversion_rate", 0) for s in shorts_anterior) / len(shorts_anterior)
            if conversion_avg > conversion_anterior * 1.1:
                trend = "MEJORANDO"
            elif conversion_avg < conversion_anterior * 0.9:
                trend = "EMPEORANDO"
            else:
                trend = "ESTABLE"
        else:
            trend = "PRIMER_ANALISIS"

        return {
            "shorts_analyzed": len(shorts),
            "conversion_rate_avg": round(conversion_avg, 2),
            "best_converting_short": best_short.get("short_video_id"),
            "conversion_trend": trend
        }

    except Exception as e:
        print(f"[WARN] Error obteniendo análisis de conversión: {e}")
        return {
            "shorts_analyzed": 0,
            "conversion_rate_avg": 0.0,
            "best_converting_short": None,
            "conversion_trend": "ERROR"
        }


def obtener_analisis_tiempo_valioso():
    """
    Obtiene resumen del análisis de Tiempo Valioso
    """
    try:
        fecha_limite = datetime.now() - timedelta(days=7)

        result = supabase.table("tiempo_valioso_analysis")\
            .select("*")\
            .gte("analyzed_at", fecha_limite.isoformat())\
            .execute()

        videos = result.data if result.data else []

        if not videos:
            return {
                "videos_analyzed": 0,
                "regret_index_avg": 0.0,
                "nutritious_content_percentage": 0.0,
                "worst_regret_video": None
            }

        regret_avg = sum(v.get("regret_index", 0) for v in videos) / len(videos)

        nutritious_count = sum(1 for v in videos if v.get("regret_index", 100) <= 20)
        nutritious_percent = (nutritious_count / len(videos)) * 100

        worst_video = max(videos, key=lambda v: v.get("regret_index", 0))

        return {
            "videos_analyzed": len(videos),
            "regret_index_avg": round(regret_avg, 2),
            "nutritious_content_percentage": round(nutritious_percent, 2),
            "worst_regret_video": worst_video.get("video_id")
        }

    except Exception as e:
        print(f"[WARN] Error obteniendo análisis de tiempo valioso: {e}")
        return {
            "videos_analyzed": 0,
            "regret_index_avg": 0.0,
            "nutritious_content_percentage": 0.0,
            "worst_regret_video": None
        }


def obtener_analisis_proyectos_atomicos():
    """
    Obtiene resumen de proyectos atómicos
    """
    try:
        result_active = supabase.table("atomic_content_projects")\
            .select("*")\
            .in_("estado", ["PLANIFICADO", "EN_PRODUCCION"])\
            .execute()

        result_completed = supabase.table("atomic_content_projects")\
            .select("*")\
            .eq("estado", "ANALIZADO")\
            .execute()

        active = result_active.data if result_active.data else []
        completed = result_completed.data if result_completed.data else []

        if completed:
            cti_avg = sum(p.get("cti_global", 0) for p in completed if p.get("cti_global")) / len(completed)
            best_project = max(completed, key=lambda p: p.get("cti_global", 0))
            best_project_id = best_project.get("id")
        else:
            cti_avg = 0.0
            best_project_id = None

        return {
            "atomic_projects_active": len(active),
            "atomic_projects_completed": len(completed),
            "cti_global_avg": round(cti_avg, 2),
            "best_atomic_project": best_project_id
        }

    except Exception as e:
        print(f"[WARN] Error obteniendo análisis de proyectos atómicos: {e}")
        return {
            "atomic_projects_active": 0,
            "atomic_projects_completed": 0,
            "cti_global_avg": 0.0,
            "best_atomic_project": None
        }


def detectar_oportunidades_estrategicas(conversion_data, tiempo_valioso_data, atomicos_data):
    """
    Detecta oportunidades estratégicas basadas en los análisis
    """
    oportunidades = []

    # Oportunidad 1: Shorts infrautilizados
    if conversion_data["shorts_analyzed"] > 0:
        if conversion_data["conversion_rate_avg"] < 10.0:
            oportunidades.append({
                "tipo": "SHORT_INFRAUTILIZADO",
                "prioridad": "ALTA",
                "descripcion": f"Shorts tienen conversión promedio de {conversion_data['conversion_rate_avg']:.1f}% (bajo)",
                "accion": "Rediseñar Shorts para incluir 'gancho' hacia VODs. Agregar CTA al final."
            })

    # Oportunidad 2: Contenido vacío
    if tiempo_valioso_data["videos_analyzed"] > 0:
        if tiempo_valioso_data["regret_index_avg"] > 60:
            oportunidades.append({
                "tipo": "CONTENIDO_VACIO",
                "prioridad": "CRÍTICA",
                "descripcion": f"Regret Index promedio es {tiempo_valioso_data['regret_index_avg']:.1f} (alto arrepentimiento)",
                "accion": "Revisar contenido reciente. Enfocar en resolver problemas reales del espectador."
            })

        if tiempo_valioso_data["worst_regret_video"]:
            oportunidades.append({
                "tipo": "VIDEO_CHATARRA",
                "prioridad": "ALTA",
                "descripcion": f"Video {tiempo_valioso_data['worst_regret_video']} tiene regret crítico",
                "accion": "Ocultar video o mejorar drásticamente. No replicar estructura."
            })

    # Oportunidad 3: Contenido nutritivo (positivo)
    if tiempo_valioso_data["nutritious_content_percentage"] > 30:
        oportunidades.append({
            "tipo": "CONTENIDO_NUTRITIVO",
            "prioridad": "MEDIA",
            "descripcion": f"{tiempo_valioso_data['nutritious_content_percentage']:.0f}% de tu contenido es NUTRITIVO (excelente)",
            "accion": "Analizar qué hace que este contenido sea valioso. Replicar estructura."
        })

    # Oportunidad 4: Proyectos atómicos exitosos
    if atomicos_data["best_atomic_project"]:
        if atomicos_data["cti_global_avg"] > 15:
            oportunidades.append({
                "tipo": "PROYECTO_ATOMICO_EXITOSO",
                "prioridad": "MEDIA",
                "descripcion": f"Proyecto {atomicos_data['best_atomic_project']} tiene CTI={atomicos_data['cti_global_avg']:.1f}% (excelente)",
                "accion": "Replicar estructura de este proyecto en futuros contenidos."
            })

    # Oportunidad 5: Tendencia de conversión
    if conversion_data["conversion_trend"] == "MEJORANDO":
        oportunidades.append({
            "tipo": "TENDENCIA_POSITIVA",
            "prioridad": "BAJA",
            "descripcion": "Conversión Shorts→VOD está mejorando",
            "accion": "Mantener estrategia actual de Shorts."
        })
    elif conversion_data["conversion_trend"] == "EMPEORANDO":
        oportunidades.append({
            "tipo": "TENDENCIA_NEGATIVA",
            "prioridad": "ALTA",
            "descripcion": "Conversión Shorts→VOD está empeorando",
            "accion": "Revisar últimos Shorts. ¿Están conectados temáticamente con VODs?"
        })

    return oportunidades


def calcular_channel_health_score(conversion_data, tiempo_valioso_data, atomicos_data):
    """
    Calcula score de salud del canal (0-100)

    Ponderación:
    - Conversion Rate (30%)
    - Regret Index bajo (30%)
    - CTI alto (20%)
    - Contenido nutritivo (20%)
    """
    score = 0

    # Conversion Rate (30 puntos)
    if conversion_data["conversion_rate_avg"] >= 15:
        score += 30
    elif conversion_data["conversion_rate_avg"] >= 10:
        score += 20
    elif conversion_data["conversion_rate_avg"] >= 5:
        score += 10

    # Regret Index bajo (30 puntos)
    if tiempo_valioso_data["regret_index_avg"] <= 30:
        score += 30
    elif tiempo_valioso_data["regret_index_avg"] <= 50:
        score += 20
    elif tiempo_valioso_data["regret_index_avg"] <= 70:
        score += 10

    # CTI alto (20 puntos)
    if atomicos_data["cti_global_avg"] >= 20:
        score += 20
    elif atomicos_data["cti_global_avg"] >= 10:
        score += 10

    # Contenido nutritivo (20 puntos)
    if tiempo_valioso_data["nutritious_content_percentage"] >= 40:
        score += 20
    elif tiempo_valioso_data["nutritious_content_percentage"] >= 20:
        score += 10

    # Clasificar salud
    if score >= 80:
        health_status = "EXCELENTE"
    elif score >= 60:
        health_status = "BUENO"
    elif score >= 40:
        health_status = "REGULAR"
    else:
        health_status = "CRÍTICO"

    return round(score, 2), health_status


def guardar_strategic_insights(
    period_start,
    period_end,
    conversion_data,
    tiempo_valioso_data,
    atomicos_data,
    oportunidades,
    channel_health_score,
    health_status
):
    """
    Guarda insights estratégicos en Supabase
    """
    try:
        record = {
            "analysis_date": datetime.now().date().isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "shorts_analyzed": conversion_data["shorts_analyzed"],
            "conversion_rate_avg": conversion_data["conversion_rate_avg"],
            "best_converting_short": conversion_data["best_converting_short"],
            "conversion_trend": conversion_data["conversion_trend"],
            "videos_analyzed": tiempo_valioso_data["videos_analyzed"],
            "regret_index_avg": tiempo_valioso_data["regret_index_avg"],
            "nutritious_content_percentage": tiempo_valioso_data["nutritious_content_percentage"],
            "worst_regret_video": tiempo_valioso_data["worst_regret_video"],
            "atomic_projects_active": atomicos_data["atomic_projects_active"],
            "atomic_projects_completed": atomicos_data["atomic_projects_completed"],
            "cti_global_avg": atomicos_data["cti_global_avg"],
            "best_atomic_project": atomicos_data["best_atomic_project"],
            "oportunidades": oportunidades,
            "channel_health_score": channel_health_score,
            "health_status": health_status,
            "created_at": datetime.now().isoformat()
        }

        supabase.table("strategic_insights").insert(record).execute()
        print("[OK] Insights estratégicos guardados en Supabase")

    except Exception as e:
        print(f"[ERROR] No se pudieron guardar insights: {e}")


def generar_reporte_consolidado(
    conversion_data,
    tiempo_valioso_data,
    atomicos_data,
    oportunidades,
    channel_health_score,
    health_status
):
    """
    Genera reporte consolidado en consola
    """
    print("\n" + "="*60)
    print("REPORTE ESTRATÉGICO CONSOLIDADO")
    print("CEREBRO 5: Orquestador Estratégico")
    print("="*60)

    print(f"\n--- SALUD DEL CANAL ---")
    print(f"Score: {channel_health_score}/100")
    print(f"Estado: {health_status}")

    print(f"\n--- CONVERSIÓN SHORTS→VOD ---")
    print(f"Shorts analizados: {conversion_data['shorts_analyzed']}")
    print(f"Conversión promedio: {conversion_data['conversion_rate_avg']:.2f}%")
    print(f"Tendencia: {conversion_data['conversion_trend']}")

    print(f"\n--- TIEMPO VALIOSO ---")
    print(f"Videos analizados: {tiempo_valioso_data['videos_analyzed']}")
    print(f"Regret Index promedio: {tiempo_valioso_data['regret_index_avg']:.2f}")
    print(f"Contenido nutritivo: {tiempo_valioso_data['nutritious_content_percentage']:.1f}%")

    print(f"\n--- PROYECTOS ATÓMICOS ---")
    print(f"Activos: {atomicos_data['atomic_projects_active']}")
    print(f"Completados: {atomicos_data['atomic_projects_completed']}")
    print(f"CTI promedio: {atomicos_data['cti_global_avg']:.2f}%")

    print(f"\n--- OPORTUNIDADES ESTRATÉGICAS ({len(oportunidades)}) ---")
    for idx, opp in enumerate(oportunidades, 1):
        print(f"\n{idx}. [{opp['prioridad']}] {opp['tipo']}")
        print(f"   {opp['descripcion']}")
        print(f"   Acción: {opp['accion']}")

    print("\n" + "="*60)


def main():
    """
    Función principal
    """
    print("\n" + "="*60)
    print("ORQUESTADOR ESTRATÉGICO")
    print("CEREBRO 5: Integración Completa")
    print("="*60 + "\n")

    inicio = datetime.now()

    # PASO 1: Ejecutar análisis de Conversión Shorts→VOD
    exito_conversion = ejecutar_script(
        CONVERSION_SCRIPT,
        "Análisis Conversión Shorts→VOD"
    )

    # PASO 2: Ejecutar análisis de Tiempo Valioso
    exito_tiempo_valioso = ejecutar_script(
        TIEMPO_VALIOSO_SCRIPT,
        "Análisis Tiempo Valioso (Regret Index)"
    )

    # PASO 3: Obtener datos consolidados
    print(f"\n{'='*60}")
    print("CONSOLIDANDO DATOS...")
    print(f"{'='*60}\n")

    period_end = datetime.now()
    period_start = period_end - timedelta(days=7)

    conversion_data = obtener_analisis_conversion_shorts()
    tiempo_valioso_data = obtener_analisis_tiempo_valioso()
    atomicos_data = obtener_analisis_proyectos_atomicos()

    # PASO 4: Detectar oportunidades
    oportunidades = detectar_oportunidades_estrategicas(
        conversion_data,
        tiempo_valioso_data,
        atomicos_data
    )

    # PASO 5: Calcular salud del canal
    channel_health_score, health_status = calcular_channel_health_score(
        conversion_data,
        tiempo_valioso_data,
        atomicos_data
    )

    # PASO 6: Guardar insights
    guardar_strategic_insights(
        period_start,
        period_end,
        conversion_data,
        tiempo_valioso_data,
        atomicos_data,
        oportunidades,
        channel_health_score,
        health_status
    )

    # PASO 7: Generar reporte
    generar_reporte_consolidado(
        conversion_data,
        tiempo_valioso_data,
        atomicos_data,
        oportunidades,
        channel_health_score,
        health_status
    )

    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    print(f"\n[OK] Análisis estratégico completado")
    print(f"[OK] Duración total: {duracion:.0f} segundos ({duracion/60:.1f} minutos)")
    print(f"[OK] Insights guardados en tabla: strategic_insights")


if __name__ == "__main__":
    main()
