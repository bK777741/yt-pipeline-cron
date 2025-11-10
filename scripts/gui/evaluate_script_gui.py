#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVALUADOR DE GUIONES GUI
=========================

Evalúa un nuevo guión comparándolo con los patrones aprendidos
del entrenamiento de la GUI

Uso:
    python evaluate_script_gui.py

    O programáticamente:
    from evaluate_script_gui import evaluar_guion
    resultado = evaluar_guion("Tu guión aquí...")
"""

import os
import re
import json
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Conectar a Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def obtener_patrones_entrenados():
    """Obtiene los patrones entrenados de Supabase"""
    try:
        result = sb.table("gui_training_context").select("*").eq("context_type", "main").execute()

        if not result.data:
            print("[ERROR] No hay patrones entrenados")
            print("        Ejecuta primero: python train_gui_model.py")
            return None

        patrones_json = result.data[0]["patrones"]
        patrones = json.loads(patrones_json) if isinstance(patrones_json, str) else patrones_json

        return patrones

    except Exception as e:
        print(f"[ERROR] No se pudieron cargar patrones: {e}")
        return None


def evaluar_gancho(guion, patrones_ganchos):
    """Evalúa el gancho inicial del guión"""
    palabras = guion.split()

    if len(palabras) < 30:
        return {
            "score": 0,
            "problema": "Guión muy corto (< 30 palabras)",
            "recomendacion": "Escribir mínimo 30 palabras"
        }

    gancho = ' '.join(palabras[:100])

    # Detectar patrones
    tiene_pregunta = '?' in gancho or gancho.lower().startswith(("¿", "cómo", "qué", "por qué", "cuál"))
    tiene_beneficio = any(palabra in gancho.lower() for palabra in ["aprende", "descubre", "mejora", "ahorra", "gana", "evita", "soluciona"])
    tiene_urgencia = any(palabra in gancho.lower() for palabra in ["hoy", "ahora", "rápido", "inmediato", "urgente"])

    # Comparar con patrones aprendidos
    ratio_pregunta_esperado = patrones_ganchos.get("ratio_con_pregunta", 0)
    ratio_beneficio_esperado = patrones_ganchos.get("ratio_con_beneficio", 0)

    score = 0
    puntos_posibles = 100

    # Pregunta (30 puntos)
    if ratio_pregunta_esperado > 30:  # Si usas preguntas frecuentemente
        if tiene_pregunta:
            score += 30
        else:
            puntos_posibles -= 30

    # Beneficio (40 puntos)
    if ratio_beneficio_esperado > 30:  # Si usas beneficios frecuentemente
        if tiene_beneficio:
            score += 40
        else:
            puntos_posibles -= 40

    # Longitud del gancho (30 puntos)
    if len(gancho.split()) >= 50:
        score += 30

    score_final = round((score / puntos_posibles) * 100, 1) if puntos_posibles > 0 else 50

    return {
        "score": score_final,
        "tiene_pregunta": tiene_pregunta,
        "tiene_beneficio": tiene_beneficio,
        "tiene_urgencia": tiene_urgencia,
        "recomendacion": "Agregar pregunta inicial" if not tiene_pregunta and ratio_pregunta_esperado > 30 else "Agregar beneficio claro" if not tiene_beneficio else "Gancho bien estructurado"
    }


def evaluar_estructura(guion, patrones_estructura):
    """Evalúa la estructura del guión"""
    palabras = guion.split()
    total_palabras = len(palabras)

    if total_palabras < 100:
        return {
            "score": 50,
            "problema": "Guión muy corto para analizar estructura",
            "recomendacion": "Escribir mínimo 200 palabras"
        }

    # Dividir en tercios
    tercio = total_palabras // 3
    intro_real = len(' '.join(palabras[:tercio]).split())
    desarrollo_real = len(' '.join(palabras[tercio:tercio*2]).split())
    cierre_real = len(' '.join(palabras[tercio*2:]).split())

    ratio_intro_real = round(intro_real / total_palabras * 100, 1)
    ratio_desarrollo_real = round(desarrollo_real / total_palabras * 100, 1)
    ratio_cierre_real = round(cierre_real / total_palabras * 100, 1)

    # Comparar con patrones
    ratio_intro_esperado = patrones_estructura.get("ratio_promedio_intro", 33)
    ratio_desarrollo_esperado = patrones_estructura.get("ratio_promedio_desarrollo", 33)
    ratio_cierre_esperado = patrones_estructura.get("ratio_promedio_cierre", 33)

    # Calcular diferencias
    diff_intro = abs(ratio_intro_real - ratio_intro_esperado)
    diff_desarrollo = abs(ratio_desarrollo_real - ratio_desarrollo_esperado)
    diff_cierre = abs(ratio_cierre_real - ratio_cierre_esperado)

    # Score (menos diferencia = más puntos)
    score = 100 - (diff_intro + diff_desarrollo + diff_cierre) / 3

    return {
        "score": max(round(score, 1), 0),
        "ratio_intro_real": ratio_intro_real,
        "ratio_desarrollo_real": ratio_desarrollo_real,
        "ratio_cierre_real": ratio_cierre_real,
        "ratio_intro_esperado": ratio_intro_esperado,
        "ratio_desarrollo_esperado": ratio_desarrollo_esperado,
        "ratio_cierre_esperado": ratio_cierre_esperado,
        "recomendacion": "Estructura coincide con tu estilo" if score > 80 else f"Ajustar proporciones (esperado: intro {ratio_intro_esperado:.0f}%, desarrollo {ratio_desarrollo_esperado:.0f}%, cierre {ratio_cierre_esperado:.0f}%)"
    }


def evaluar_estilo(guion, patrones_estilo):
    """Evalúa el estilo de escritura"""
    # Contar oraciones
    oraciones = re.split(r'[.!?]+', guion)
    oraciones = [o.strip() for o in oraciones if o.strip()]

    if len(oraciones) < 5:
        return {
            "score": 50,
            "problema": "Muy pocas oraciones para analizar estilo",
            "recomendacion": "Escribir más contenido"
        }

    # Análisis
    preguntas = [o for o in oraciones if '?' in o]
    exclamaciones = [o for o in oraciones if '!' in o]

    ratio_preguntas_real = round(len(preguntas) / len(oraciones) * 100, 1)
    ratio_exclamaciones_real = round(len(exclamaciones) / len(oraciones) * 100, 1)

    longitudes = [len(o.split()) for o in oraciones]
    longitud_promedio_real = round(sum(longitudes) / len(longitudes), 1)

    # Comparar con patrones
    ratio_preguntas_esperado = patrones_estilo.get("ratio_preguntas", 10)
    longitud_esperada = patrones_estilo.get("longitud_promedio_oracion", 15)

    # Score
    diff_preguntas = abs(ratio_preguntas_real - ratio_preguntas_esperado)
    diff_longitud = abs(longitud_promedio_real - longitud_esperada)

    score = 100 - (diff_preguntas * 2 + diff_longitud)

    return {
        "score": max(round(score, 1), 0),
        "ratio_preguntas_real": ratio_preguntas_real,
        "ratio_preguntas_esperado": ratio_preguntas_esperado,
        "longitud_promedio_real": longitud_promedio_real,
        "longitud_esperada": longitud_esperada,
        "recomendacion": "Estilo coincide con tu voz" if score > 80 else f"Ajustar: usar más preguntas ({ratio_preguntas_esperado:.0f}% esperado)" if diff_preguntas > 5 else "Oraciones muy largas/cortas"
    }


def evaluar_keywords(guion, patrones_keywords):
    """Evalúa el uso de palabras clave del nicho"""
    guion_lower = guion.lower()

    # Top palabras del nicho
    top_palabras = patrones_keywords.get("top_30_palabras", [])

    if not top_palabras:
        return {
            "score": 50,
            "problema": "No hay keywords de referencia",
            "recomendacion": "Entrenar modelo con más guiones"
        }

    # Contar cuántas de las top 30 palabras están presentes
    palabras_presentes = []
    for palabra, freq in top_palabras[:30]:
        if palabra in guion_lower:
            palabras_presentes.append(palabra)

    # Score basado en presencia de keywords (mínimo 3 de top 10)
    top_10_presentes = sum(1 for palabra, _ in top_palabras[:10] if palabra in guion_lower)

    score = min((len(palabras_presentes) / 10) * 100, 100)  # 10 keywords = 100 puntos

    return {
        "score": round(score, 1),
        "keywords_presentes": palabras_presentes[:10],
        "keywords_faltantes": [p[0] for p in top_palabras[:5] if p[0] not in palabras_presentes],
        "recomendacion": "Buen uso de keywords del nicho" if top_10_presentes >= 3 else f"Agregar keywords clave: {', '.join([p[0] for p in top_palabras[:3]])}"
    }


def evaluar_longitud(guion, patrones_longitud):
    """Evalúa la longitud del guión"""
    palabras = guion.split()
    longitud_real = len(palabras)

    longitud_promedio = patrones_longitud.get("promedio", 400)
    rango_recomendado = patrones_longitud.get("rango_recomendado", "300-600 palabras")

    # Score basado en cercanía al promedio
    diff = abs(longitud_real - longitud_promedio)
    score = max(100 - (diff / 10), 0)  # Cada 10 palabras de diferencia = -1 punto

    # Categoría
    if longitud_real < 200:
        categoria = "Muy corto"
    elif longitud_real < 400:
        categoria = "Corto"
    elif longitud_real <= 600:
        categoria = "Óptimo"
    elif longitud_real <= 800:
        categoria = "Largo"
    else:
        categoria = "Muy largo"

    return {
        "score": round(score, 1),
        "longitud_real": longitud_real,
        "longitud_promedio": longitud_promedio,
        "categoria": categoria,
        "rango_recomendado": rango_recomendado,
        "recomendacion": f"Longitud óptima ({rango_recomendado})" if 300 <= longitud_real <= 600 else f"Ajustar a {rango_recomendado}"
    }


def evaluar_guion(guion_texto):
    """Función principal de evaluación"""

    # Obtener patrones
    patrones = obtener_patrones_entrenados()

    if not patrones:
        return {
            "error": "No hay patrones entrenados",
            "solucion": "Ejecutar primero: python train_gui_model.py"
        }

    # Evaluar componentes
    eval_gancho = evaluar_gancho(guion_texto, patrones.get("ganchos", {}))
    eval_estructura = evaluar_estructura(guion_texto, patrones.get("estructura", {}))
    eval_estilo = evaluar_estilo(guion_texto, patrones.get("estilo", {}))
    eval_keywords = evaluar_keywords(guion_texto, patrones.get("keywords", {}))
    eval_longitud = evaluar_longitud(guion_texto, patrones.get("longitud", {}))

    # Score total ponderado
    score_total = (
        eval_gancho["score"] * 0.30 +      # Gancho: 30%
        eval_estructura["score"] * 0.20 +  # Estructura: 20%
        eval_estilo["score"] * 0.15 +      # Estilo: 15%
        eval_keywords["score"] * 0.25 +    # Keywords: 25%
        eval_longitud["score"] * 0.10      # Longitud: 10%
    )

    # Clasificación
    if score_total >= 85:
        clasificacion = "EXCELENTE"
        decision = "✓ APROBAR - Crear video"
    elif score_total >= 70:
        clasificacion = "BUENO"
        decision = "✓ APROBAR con ajustes menores"
    elif score_total >= 50:
        clasificacion = "REGULAR"
        decision = "⚠ MEJORAR antes de crear"
    else:
        clasificacion = "MALO"
        decision = "✗ RECHAZAR - Reescribir"

    # Recomendaciones priorizadas
    recomendaciones = []
    if eval_gancho["score"] < 70:
        recomendaciones.append(f"[CRÍTICO] Gancho: {eval_gancho['recomendacion']}")
    if eval_keywords["score"] < 60:
        recomendaciones.append(f"[IMPORTANTE] Keywords: {eval_keywords['recomendacion']}")
    if eval_estructura["score"] < 70:
        recomendaciones.append(f"[MODERADO] Estructura: {eval_estructura['recomendacion']}")
    if eval_longitud["score"] < 80:
        recomendaciones.append(f"[MENOR] Longitud: {eval_longitud['recomendacion']}")

    return {
        "score_total": round(score_total, 1),
        "clasificacion": clasificacion,
        "decision": decision,
        "scores_detallados": {
            "gancho": eval_gancho["score"],
            "estructura": eval_estructura["score"],
            "estilo": eval_estilo["score"],
            "keywords": eval_keywords["score"],
            "longitud": eval_longitud["score"]
        },
        "evaluaciones": {
            "gancho": eval_gancho,
            "estructura": eval_estructura,
            "estilo": eval_estilo,
            "keywords": eval_keywords,
            "longitud": eval_longitud
        },
        "recomendaciones": recomendaciones if recomendaciones else ["Guión bien estructurado - listo para producción"],
        "total_palabras": len(guion_texto.split()),
        "evaluado_en": datetime.now().isoformat()
    }


def mostrar_resultado(resultado):
    """Muestra el resultado de la evaluación en formato legible"""
    print("\n" + "=" * 80)
    print(f"SCORE TOTAL: {resultado['score_total']}/100 - {resultado['clasificacion']}")
    print("=" * 80)
    print(f"\n{resultado['decision']}\n")

    print("SCORES DETALLADOS:")
    print(f"  - Gancho (30%):      {resultado['scores_detallados']['gancho']:.1f}/100")
    print(f"  - Estructura (20%):  {resultado['scores_detallados']['estructura']:.1f}/100")
    print(f"  - Estilo (15%):      {resultado['scores_detallados']['estilo']:.1f}/100")
    print(f"  - Keywords (25%):    {resultado['scores_detallados']['keywords']:.1f}/100")
    print(f"  - Longitud (10%):    {resultado['scores_detallados']['longitud']:.1f}/100")

    print("\nRECOMENDACIONES:")
    for rec in resultado['recomendaciones']:
        print(f"  • {rec}")

    print(f"\n{'='*80}")


def main():
    """Función principal - modo interactivo"""
    print("=" * 80)
    print("EVALUADOR DE GUIONES GUI")
    print("=" * 80)
    print("\nPega tu guión a continuación (Ctrl+D o Ctrl+Z para finalizar):\n")

    # Leer guión desde stdin
    lineas = []
    try:
        while True:
            linea = input()
            lineas.append(linea)
    except EOFError:
        pass

    guion_texto = '\n'.join(lineas).strip()

    if not guion_texto:
        print("[ERROR] No se proporcionó ningún guión")
        return

    # Evaluar
    print("\n[INFO] Evaluando guión...")
    resultado = evaluar_guion(guion_texto)

    if "error" in resultado:
        print(f"[ERROR] {resultado['error']}")
        print(f"[SOLUCIÓN] {resultado['solucion']}")
        return

    # Mostrar resultado
    mostrar_resultado(resultado)


if __name__ == "__main__":
    main()
