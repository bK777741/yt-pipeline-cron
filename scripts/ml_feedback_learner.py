#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE APRENDIZAJE POR FEEDBACK HUMANO
==========================================

Este script analiza las modificaciones humanas y actualiza los modelos
para aprender de las decisiones del creador.

EJECUTA: Automáticamente cada 7 días (GitHub Actions)

PROCESO:
1. Obtener sugerencias con resultados medidos
2. Analizar modificaciones: ¿Funcionaron mejor o peor?
3. Extraer patrones de las modificaciones exitosas
4. Actualizar pesos de features en los modelos
5. Re-entrenar modelos con feedback incorporado

META: Tasa de aceptación (sin modificar) → 100%
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from collections import Counter
from supabase import create_client, Client


def load_env():
    """Cargar credenciales"""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    return supabase_url, supabase_key


def get_suggestions_with_feedback(sb: Client, days=30):
    """
    Obtiene sugerencias con feedback de resultados reales

    Args:
        sb: Cliente de Supabase
        days: Días hacia atrás para analizar

    Returns:
        List[dict]: Sugerencias con métricas
    """
    fecha_limite = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Obtener sugerencias recientes
    sugg_resp = sb.table("ml_suggestions") \
        .select("*") \
        .gte("published_at", fecha_limite) \
        .not_.is_("video_id", "null") \
        .execute()

    suggestions = sugg_resp.data

    # Para cada sugerencia, obtener su feedback
    suggestions_with_feedback = []

    for sug in suggestions:
        feedback_resp = sb.table("ml_feedback") \
            .select("*") \
            .eq("suggestion_id", sug["id"]) \
            .execute()

        if feedback_resp.data:
            sug["feedback"] = feedback_resp.data[0]
            suggestions_with_feedback.append(sug)

    return suggestions_with_feedback


def analyze_modification_impact(suggestion):
    """
    Analiza el impacto de una modificación humana

    Returns:
        dict: Análisis del impacto
    """
    feedback = suggestion["feedback"]

    # Comparar con predicción
    predicted_vph = suggestion.get("predicted_vph", 0)
    actual_vph = feedback.get("vph_24h", 0)

    if predicted_vph > 0:
        vph_improvement = ((actual_vph - predicted_vph) / predicted_vph) * 100
    else:
        vph_improvement = 0

    # Comparar con promedio del canal
    vs_average = feedback.get("vs_channel_average_percent", 0)

    # Clasificar resultado
    if vs_average > 50:
        result = "excellent"
    elif vs_average > 20:
        result = "good"
    elif vs_average > -20:
        result = "average"
    else:
        result = "poor"

    return {
        "was_modified": suggestion["was_modified"],
        "vph_predicted": predicted_vph,
        "vph_actual": actual_vph,
        "vph_improvement_percent": vph_improvement,
        "vs_channel_average_percent": vs_average,
        "result_quality": result,
        "original": suggestion["original_suggestion"],
        "final": suggestion["final_version"],
        "changes": suggestion.get("changes_summary", {})
    }


def extract_learning_patterns(analyses):
    """
    Extrae patrones de aprendizaje de las modificaciones

    Returns:
        dict: Patrones encontrados
    """
    patterns = {
        "successful_modifications": [],
        "failed_modifications": [],
        "accepted_suggestions": [],
        "common_changes": Counter(),
        "word_effectiveness": {}
    }

    for analysis in analyses:
        if analysis["was_modified"]:
            # Fue modificado
            if analysis["result_quality"] in ["excellent", "good"]:
                # Modificación exitosa
                patterns["successful_modifications"].append(analysis)

                # Analizar qué cambió
                changes = analysis.get("changes", {})
                if "added_words" in changes:
                    for word in changes["added_words"]:
                        patterns["common_changes"][f"added:{word}"] += 1
                if "removed_words" in changes:
                    for word in changes["removed_words"]:
                        patterns["common_changes"][f"removed:{word}"] += 1
            else:
                # Modificación que no funcionó bien
                patterns["failed_modifications"].append(analysis)

        else:
            # Fue aceptado sin modificar
            if analysis["result_quality"] in ["excellent", "good"]:
                # Modelo acertó
                patterns["accepted_suggestions"].append(analysis)

    return patterns


def calculate_acceptance_rate(suggestions):
    """
    Calcula tasa de aceptación del modelo

    Returns:
        float: Porcentaje de sugerencias aceptadas sin modificar
    """
    if not suggestions:
        return 0

    accepted = sum(1 for s in suggestions if not s["was_modified"])
    return (accepted / len(suggestions)) * 100


def generate_learning_report(patterns, acceptance_rate):
    """Genera reporte de aprendizaje"""
    print("\n" + "=" * 80)
    print("REPORTE DE APRENDIZAJE - FEEDBACK HUMANO")
    print("=" * 80)
    print()

    # Tasa de aceptación
    print(f"[MÉTRICA CLAVE] Tasa de Aceptación: {acceptance_rate:.1f}%")
    print(f"                (Meta: 100% = modelo perfecto)")
    print()

    # Modificaciones exitosas
    successful = patterns["successful_modifications"]
    failed = patterns["failed_modifications"]
    accepted = patterns["accepted_suggestions"]

    print(f"[ANÁLISIS]")
    print(f"  Sugerencias aceptadas sin modificar: {len(accepted)}")
    print(f"  Modificaciones exitosas: {len(successful)}")
    print(f"  Modificaciones que no funcionaron: {len(failed)}")
    print()

    # Patrones comunes
    if patterns["common_changes"]:
        print(f"[PATRONES DE CAMBIOS MÁS COMUNES]")
        print("-" * 80)
        for change, count in patterns["common_changes"].most_common(10):
            print(f"  {change}: {count} veces")
        print()

    # Ejemplos de aprendizaje
    if successful:
        print(f"[EJEMPLOS DE MODIFICACIONES EXITOSAS]")
        print("-" * 80)
        for i, mod in enumerate(successful[:3], 1):
            print(f"  {i}. Original: {mod['original'][:60]}...")
            print(f"     Final:    {mod['final'][:60]}...")
            print(f"     Mejora:   +{mod['vph_improvement_percent']:.1f}% VPH")
            print()

    if len(accepted) > 0:
        print(f"[EJEMPLOS DE MODELO CORRECTO (aceptado sin modificar)]")
        print("-" * 80)
        for i, acc in enumerate(accepted[:3], 1):
            print(f"  {i}. {acc['original'][:60]}...")
            print(f"     Resultado: {acc['result_quality'].upper()}")
            print(f"     vs Promedio: +{acc['vs_channel_average_percent']:.1f}%")
            print()


def update_model_with_feedback(patterns):
    """
    Actualiza modelo con aprendizaje de feedback

    TODO: Implementar ajustes de pesos basados en patrones
    """
    print("[INFO] Actualizando modelos con feedback humano...")
    print("      (Implementación pendiente)")


def main():
    print("=" * 80)
    print("SISTEMA DE APRENDIZAJE POR FEEDBACK HUMANO")
    print("=" * 80)
    print()

    # Cargar credenciales
    supabase_url, supabase_key = load_env()
    sb = create_client(supabase_url, supabase_key)

    # Obtener sugerencias con feedback (últimos 30 días)
    print("[1/5] Obteniendo sugerencias con feedback...")
    suggestions = get_suggestions_with_feedback(sb, days=30)
    print(f"      {len(suggestions)} sugerencias con métricas")

    if len(suggestions) == 0:
        print()
        print("[INFO] No hay suficientes datos de feedback aún")
        print("      Espera a que se publiquen videos con sugerencias del modelo")
        sys.exit(0)

    # Analizar impacto de cada modificación
    print("\n[2/5] Analizando impacto de modificaciones...")
    analyses = [analyze_modification_impact(s) for s in suggestions]

    # Extraer patrones
    print("\n[3/5] Extrayendo patrones de aprendizaje...")
    patterns = extract_learning_patterns(analyses)

    # Calcular tasa de aceptación
    print("\n[4/5] Calculando métricas de modelo...")
    acceptance_rate = calculate_acceptance_rate(suggestions)

    # Generar reporte
    generate_learning_report(patterns, acceptance_rate)

    # Actualizar modelo
    print("\n[5/5] Actualizando modelos con feedback...")
    update_model_with_feedback(patterns)

    print()
    print("=" * 80)
    print("APRENDIZAJE COMPLETADO")
    print("=" * 80)
    print()
    print(f"[RESUMEN]")
    print(f"  Sugerencias analizadas: {len(suggestions)}")
    print(f"  Tasa de aceptación: {acceptance_rate:.1f}%")
    print(f"  Modificaciones exitosas: {len(patterns['successful_modifications'])}")
    print(f"  Patrones extraídos: {len(patterns['common_changes'])}")
    print()


if __name__ == "__main__":
    main()
