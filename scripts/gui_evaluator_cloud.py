#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CEREBRO 1: EVALUADOR DE GUIONES EN LA NUBE
============================================

Evalúa guiones pendientes de Supabase automáticamente
Versión cloud del evaluator GUI local

Workflow: GitHub Actions cada 6 horas o manual
Detecta guiones con status='pending' → Evalúa → Guarda en gui_evaluations
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
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 80)
print("CEREBRO 1: EVALUADOR DE GUIONES CLOUD")
print("=" * 80)


def obtener_patrones_entrenados():
    """Obtiene los patrones entrenados de Supabase"""
    try:
        result = sb.table("gui_training_context").select("*").eq("context_type", "main").eq("is_active", True).order("created_at", desc=True).limit(1).execute()

        if not result.data:
            print("[WARN] No hay patrones entrenados, usando patrones por defecto")
            return None

        patrones_json = result.data[0]["patrones"]
        patrones = json.loads(patrones_json) if isinstance(patrones_json, str) else patrones_json

        print(f"[OK] Patrones cargados (versión: {result.data[0].get('version', 'unknown')})")
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
    if ratio_pregunta_esperado > 30:
        if tiene_pregunta:
            score += 30
        else:
            puntos_posibles -= 30

    # Beneficio (40 puntos)
    if ratio_beneficio_esperado > 30:
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

    score = min((len(palabras_presentes) / 10) * 100, 100)

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
    score = max(100 - (diff / 10), 0)

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
        "categoria": categoria,
        "recomendacion": f"Longitud óptima ({rango_recomendado})" if 300 <= longitud_real <= 600 else f"Ajustar a {rango_recomendado}"
    }


def evaluar_guion(guion_texto, patrones):
    """Función principal de evaluación"""

    if not patrones:
        # Usar patrones por defecto si no hay entrenados
        patrones = {
            "ganchos": {"ratio_con_pregunta": 45, "ratio_con_beneficio": 65},
            "estructura": {"ratio_promedio_intro": 30, "ratio_promedio_desarrollo": 50, "ratio_promedio_cierre": 20},
            "estilo": {"ratio_preguntas": 12, "longitud_promedio_oracion": 15},
            "keywords": {"top_30_palabras": [["chatgpt", 100], ["whatsapp", 95], ["tutorial", 90]]},
            "longitud": {"promedio": 400, "rango_recomendado": "300-600 palabras"}
        }

    # Evaluar componentes
    eval_gancho = evaluar_gancho(guion_texto, patrones.get("ganchos", {}))
    eval_estructura = evaluar_estructura(guion_texto, patrones.get("estructura", {}))
    eval_estilo = evaluar_estilo(guion_texto, patrones.get("estilo", {}))
    eval_keywords = evaluar_keywords(guion_texto, patrones.get("keywords", {}))
    eval_longitud = evaluar_longitud(guion_texto, patrones.get("longitud", {}))

    # Score total ponderado
    score_total = (
        eval_gancho["score"] * 0.30 +
        eval_estructura["score"] * 0.20 +
        eval_estilo["score"] * 0.15 +
        eval_keywords["score"] * 0.25 +
        eval_longitud["score"] * 0.10
    )

    # Clasificación
    if score_total >= 85:
        clasificacion = "EXITOSO"
        decision = "APROBAR - Crear video"
    elif score_total >= 70:
        clasificacion = "PROMEDIO"
        decision = "APROBAR con ajustes menores"
    elif score_total >= 50:
        clasificacion = "PROMEDIO"
        decision = "MEJORAR antes de crear"
    else:
        clasificacion = "FRACASO"
        decision = "RECHAZAR - Reescribir"

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

    aspectos_positivos = []
    if eval_gancho["score"] >= 70:
        aspectos_positivos.append(f"Gancho efectivo ({eval_gancho['score']:.0f}/100)")
    if eval_keywords["score"] >= 60:
        aspectos_positivos.append(f"Buen uso de keywords ({eval_keywords['score']:.0f}/100)")
    if eval_estructura["score"] >= 70:
        aspectos_positivos.append(f"Estructura sólida ({eval_estructura['score']:.0f}/100)")

    return {
        "gui_score": round(score_total),
        "gui_classification": clasificacion,
        "score_titulo": 0,  # No se evalúa título en esta versión
        "score_miniatura": 0,  # No se evalúa miniatura en esta versión
        "score_hook": round(eval_gancho["score"]),
        "score_duracion": round(eval_longitud["score"]),
        "score_engagement": round(eval_keywords["score"]),
        "notas": decision,
        "aspectos_positivos": " | ".join(aspectos_positivos) if aspectos_positivos else "Necesita mejoras",
        "aspectos_negativos": " | ".join(recomendaciones) if recomendaciones else "Ninguno",
        "recomendaciones": "\n".join(recomendaciones) if recomendaciones else "Guión bien estructurado - listo para producción",
        "evaluaciones_detalladas": json.dumps({
            "gancho": eval_gancho,
            "estructura": eval_estructura,
            "estilo": eval_estilo,
            "keywords": eval_keywords,
            "longitud": eval_longitud
        }, ensure_ascii=False)
    }


def procesar_guiones_pendientes():
    """Procesa todos los guiones pendientes de evaluación"""
    try:
        # Buscar guiones pendientes
        result = sb.table("script_drafts").select("*").eq("status", "pending").order("created_at").execute()

        if not result.data:
            print("\n[INFO] No hay guiones pendientes de evaluación")
            print("[INFO] Total procesados: 0")
            return

        print(f"\n[INFO] Guiones pendientes: {len(result.data)}")

        # Cargar patrones
        patrones = obtener_patrones_entrenados()

        guiones_procesados = 0
        guiones_fallidos = 0

        for draft in result.data:
            draft_id = draft["id"]
            script_text = draft["script_text"]
            titulo_tentativo = draft.get("titulo_tentativo", "Sin título")

            print(f"\n[PROCESANDO] ID: {draft_id[:8]}... | Título: {titulo_tentativo}")

            try:
                # Marcar como evaluando
                sb.table("script_drafts").update({"status": "evaluating"}).eq("id", draft_id).execute()

                # Evaluar
                resultado = evaluar_guion(script_text, patrones)

                # Guardar evaluación en gui_evaluations
                eval_data = {
                    "video_id": f"draft_{draft_id[:8]}",  # ID temporal
                    "gui_score": resultado["gui_score"],
                    "gui_classification": resultado["gui_classification"],
                    "score_titulo": resultado["score_titulo"],
                    "score_miniatura": resultado["score_miniatura"],
                    "score_hook": resultado["score_hook"],
                    "score_duracion": resultado["score_duracion"],
                    "score_engagement": resultado["score_engagement"],
                    "notas": resultado["notas"],
                    "aspectos_positivos": resultado["aspectos_positivos"],
                    "aspectos_negativos": resultado["aspectos_negativos"],
                    "recomendaciones": resultado["recomendaciones"],
                    "evaluated_by": "cerebro1_cloud",
                    "evaluated_at": datetime.now().isoformat()
                }

                eval_result = sb.table("gui_evaluations").insert(eval_data).execute()
                evaluation_id = eval_result.data[0]["id"] if eval_result.data else None

                # Actualizar draft como completado
                sb.table("script_drafts").update({
                    "status": "completed",
                    "evaluated_at": datetime.now().isoformat(),
                    "evaluation_id": evaluation_id
                }).eq("id", draft_id).execute()

                print(f"[OK] Score: {resultado['gui_score']}/100 | Clasificación: {resultado['gui_classification']}")
                print(f"[OK] Decisión: {resultado['notas']}")

                guiones_procesados += 1

            except Exception as e:
                print(f"[ERROR] Fallo al evaluar: {e}")

                # Marcar como fallido
                sb.table("script_drafts").update({
                    "status": "failed",
                    "notas_usuario": f"Error: {str(e)}"
                }).eq("id", draft_id).execute()

                guiones_fallidos += 1

        print("\n" + "=" * 80)
        print("RESUMEN DE PROCESAMIENTO")
        print("=" * 80)
        print(f"Guiones procesados exitosamente: {guiones_procesados}")
        print(f"Guiones fallidos: {guiones_fallidos}")
        print(f"Total: {guiones_procesados + guiones_fallidos}")
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] Fallo al procesar guiones: {e}")


if __name__ == "__main__":
    procesar_guiones_pendientes()
