#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ENTRENADOR DEL MODELO GUI
==========================

Analiza todos los guiones de tus videos para aprender:
1. Estructura narrativa (intro, desarrollo, cierre)
2. Ganchos iniciales exitosos
3. Estilo de escritura/voz
4. Palabras clave del nicho
5. Longitud óptima de guiones
6. Patrones de éxito

Uso:
    python train_gui_model.py
"""

import os
import re
import json
from datetime import datetime
from collections import Counter
from supabase import create_client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Conectar a Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def obtener_guiones():
    """Obtiene guiones de ULTIMOS 6 MESES de Supabase"""
    print("[1/7] Obteniendo guiones de Supabase...")

    # Ventana temporal: Ultimos 6 meses
    from datetime import timedelta
    fecha_limite = datetime.now() - timedelta(days=180)

    result = sb.table("video_scripts")\
        .select("*")\
        .gte("processed_at", fecha_limite.isoformat())\
        .execute()

    if not result.data:
        print("[ERROR] No hay guiones en video_scripts")
        print("        Ejecuta primero: python process_captions_to_scripts.py")
        return []

    print(f"[OK] Encontrados {len(result.data)} guiones (ultimos 6 meses)")
    return result.data


def analizar_estructura(guiones):
    """Analiza la estructura narrativa de los guiones"""
    print("\n[2/7] Analizando estructura narrativa...")

    estructuras = []

    for guion in guiones:
        texto = guion["script_text"]
        palabras = texto.split()
        total_palabras = len(palabras)

        if total_palabras < 50:
            continue  # Guión muy corto

        # Dividir en tercios (intro, desarrollo, cierre)
        tercio = total_palabras // 3
        intro = ' '.join(palabras[:tercio])
        desarrollo = ' '.join(palabras[tercio:tercio*2])
        cierre = ' '.join(palabras[tercio*2:])

        estructuras.append({
            "total_palabras": total_palabras,
            "intro_palabras": len(intro.split()),
            "desarrollo_palabras": len(desarrollo.split()),
            "cierre_palabras": len(cierre.split()),
            "ratio_intro": round(len(intro.split()) / total_palabras * 100, 1),
            "ratio_desarrollo": round(len(desarrollo.split()) / total_palabras * 100, 1),
            "ratio_cierre": round(len(cierre.split()) / total_palabras * 100, 1)
        })

    # Promedios
    if estructuras:
        avg_intro = sum(e["ratio_intro"] for e in estructuras) / len(estructuras)
        avg_desarrollo = sum(e["ratio_desarrollo"] for e in estructuras) / len(estructuras)
        avg_cierre = sum(e["ratio_cierre"] for e in estructuras) / len(estructuras)

        resultado = {
            "total_analizados": len(estructuras),
            "ratio_promedio_intro": round(avg_intro, 1),
            "ratio_promedio_desarrollo": round(avg_desarrollo, 1),
            "ratio_promedio_cierre": round(avg_cierre, 1),
            "patron_detectado": f"Intro {avg_intro:.0f}% + Desarrollo {avg_desarrollo:.0f}% + Cierre {avg_cierre:.0f}%"
        }

        print(f"[OK] Patrón estructural: {resultado['patron_detectado']}")
        return resultado

    return {}


def analizar_ganchos(guiones):
    """Analiza los ganchos iniciales (primeras 100 palabras)"""
    print("\n[3/7] Analizando ganchos iniciales...")

    ganchos = []
    patrones_frecuentes = []

    for guion in guiones:
        texto = guion["script_text"]
        palabras = texto.split()

        if len(palabras) < 30:
            continue

        # Primeras 100 palabras = gancho
        gancho = ' '.join(palabras[:100])

        # Detectar patrones
        tiene_pregunta = '?' in gancho or gancho.lower().startswith(("¿", "cómo", "qué", "por qué", "cuál"))
        tiene_beneficio = any(palabra in gancho.lower() for palabra in ["aprende", "descubre", "mejora", "ahorra", "gana", "evita"])
        tiene_urgencia = any(palabra in gancho.lower() for palabra in ["hoy", "ahora", "rápido", "inmediato", "urgente"])

        ganchos.append({
            "longitud": len(gancho.split()),
            "tiene_pregunta": tiene_pregunta,
            "tiene_beneficio": tiene_beneficio,
            "tiene_urgencia": tiene_urgencia,
            "gancho_texto": gancho[:150]  # Primeros 150 caracteres
        })

        if tiene_pregunta:
            patrones_frecuentes.append("Pregunta inicial")
        if tiene_beneficio:
            patrones_frecuentes.append("Promesa de beneficio")
        if tiene_urgencia:
            patrones_frecuentes.append("Urgencia/inmediatez")

    # Estadísticas
    if ganchos:
        total_con_pregunta = sum(1 for g in ganchos if g["tiene_pregunta"])
        total_con_beneficio = sum(1 for g in ganchos if g["tiene_beneficio"])
        total_con_urgencia = sum(1 for g in ganchos if g["tiene_urgencia"])

        patron_contador = Counter(patrones_frecuentes)

        resultado = {
            "total_analizados": len(ganchos),
            "ratio_con_pregunta": round(total_con_pregunta / len(ganchos) * 100, 1),
            "ratio_con_beneficio": round(total_con_beneficio / len(ganchos) * 100, 1),
            "ratio_con_urgencia": round(total_con_urgencia / len(ganchos) * 100, 1),
            "patrones_mas_usados": patron_contador.most_common(3),
            "ejemplos_ganchos_exitosos": [g["gancho_texto"] for g in ganchos[:5]]
        }

        print(f"[OK] Patrones de gancho: Pregunta {resultado['ratio_con_pregunta']}% | Beneficio {resultado['ratio_con_beneficio']}% | Urgencia {resultado['ratio_con_urgencia']}%")
        return resultado

    return {}


def analizar_estilo(guiones):
    """Analiza el estilo de escritura/voz"""
    print("\n[4/7] Analizando estilo de comunicación...")

    texto_completo = ' '.join([g["script_text"] for g in guiones])

    # Contar oraciones
    oraciones = re.split(r'[.!?]+', texto_completo)
    oraciones = [o.strip() for o in oraciones if o.strip()]

    # Contar preguntas y exclamaciones
    preguntas = [o for o in oraciones if '?' in o]
    exclamaciones = [o for o in oraciones if '!' in o]

    # Longitud promedio de oraciones
    longitudes = [len(o.split()) for o in oraciones]
    longitud_promedio = sum(longitudes) / len(longitudes) if longitudes else 0

    # Palabras enfáticas (MAYÚSCULAS)
    palabras_enfaticas = re.findall(r'\b[A-ZÁÉÍÓÚÑ]{3,}\b', texto_completo)

    # Palabras de acción
    palabras_accion = ['aprende', 'descubre', 'mira', 've', 'haz', 'usa', 'prueba',
                       'instala', 'configura', 'activa', 'desactiva', 'soluciona', 'abre', 'cierra']
    contador_accion = sum(1 for palabra in palabras_accion if palabra in texto_completo.lower())

    # Tuteo vs formal
    tuteo_palabras = ['tú', 'te', 'ti', 'tu', 'tus', 'contigo']
    formal_palabras = ['usted', 'ustedes', 'le', 'les', 'su', 'sus']
    contador_tuteo = sum(texto_completo.lower().count(p) for p in tuteo_palabras)
    contador_formal = sum(texto_completo.lower().count(p) for p in formal_palabras)

    resultado = {
        "total_oraciones": len(oraciones),
        "total_preguntas": len(preguntas),
        "total_exclamaciones": len(exclamaciones),
        "ratio_preguntas": round(len(preguntas) / len(oraciones) * 100, 1) if oraciones else 0,
        "ratio_exclamaciones": round(len(exclamaciones) / len(oraciones) * 100, 1) if oraciones else 0,
        "longitud_promedio_oracion": round(longitud_promedio, 1),
        "palabras_enfaticas_count": len(palabras_enfaticas),
        "palabras_de_accion_count": contador_accion,
        "tono": "Tuteo" if contador_tuteo > contador_formal else "Formal"
    }

    print(f"[OK] Estilo: {resultado['ratio_preguntas']}% preguntas | {resultado['longitud_promedio_oracion']} palabras/oración | Tono: {resultado['tono']}")
    return resultado


def analizar_palabras_clave(guiones):
    """Analiza las palabras clave más frecuentes"""
    print("\n[5/7] Analizando palabras clave del nicho...")

    texto_completo = ' '.join([g["script_text"] for g in guiones])
    texto_lower = texto_completo.lower()

    # Extraer palabras
    palabras = re.findall(r'\b[a-záéíóúñü]{4,}\b', texto_lower)

    # Stopwords en español
    stopwords = {
        'que', 'de', 'la', 'el', 'en', 'y', 'a', 'los', 'las', 'un', 'una',
        'por', 'para', 'con', 'no', 'es', 'se', 'al', 'lo', 'como', 'más',
        'del', 'su', 'me', 'te', 'le', 'pero', 'este', 'esta', 'son', 'está',
        'o', 'si', 'ya', 'muy', 'cuando', 'aquí', 'solo', 'todo', 'también',
        'hay', 'hacer', 'tiene', 'sido', 'ahora', 'cada', 'pueden', 'ese',
        'esa', 'sí', 'dos', 'tres', 'bien', 'sin', 'vez', 'nos', 'ni', 'entre',
        'esta', 'este', 'estos', 'estas', 'vamos', 'voy', 'vas', 'donde',
        'cual', 'algo', 'quien', 'sobre', 'desde', 'hasta', 'debe', 'pueden',
        'puedes', 'puede', 'tengo', 'tenemos', 'tienen', 'tienes'
    }

    # Filtrar stopwords
    palabras_filtradas = [p for p in palabras if p not in stopwords]

    # Contar frecuencias
    contador = Counter(palabras_filtradas)
    top_30 = contador.most_common(30)

    # Bigramas (frases de 2 palabras)
    palabras_lista = texto_lower.split()
    bigramas = [' '.join(palabras_lista[i:i+2]) for i in range(len(palabras_lista)-1)]
    contador_bigramas = Counter(bigramas)
    top_10_bigramas = contador_bigramas.most_common(10)

    resultado = {
        "top_30_palabras": top_30,
        "top_10_bigramas": top_10_bigramas,
        "vocabulario_unico": len(set(palabras_filtradas))
    }

    print(f"[OK] Top 3 palabras: {', '.join([p[0] for p in top_30[:3]])}")
    return resultado


def analizar_longitud_optima(guiones):
    """Analiza la longitud óptima de los guiones"""
    print("\n[6/7] Analizando longitud óptima...")

    longitudes = [g["word_count"] for g in guiones if g.get("word_count")]

    if longitudes:
        avg = sum(longitudes) / len(longitudes)
        minimo = min(longitudes)
        maximo = max(longitudes)

        # Rangos
        rango_corto = [l for l in longitudes if l < 300]
        rango_medio = [l for l in longitudes if 300 <= l <= 600]
        rango_largo = [l for l in longitudes if l > 600]

        resultado = {
            "promedio": round(avg, 0),
            "minimo": minimo,
            "maximo": maximo,
            "total_cortos": len(rango_corto),
            "total_medios": len(rango_medio),
            "total_largos": len(rango_largo),
            "rango_recomendado": "300-600 palabras" if len(rango_medio) >= len(rango_corto) else "< 300 palabras"
        }

        print(f"[OK] Longitud promedio: {resultado['promedio']} palabras | Rango recomendado: {resultado['rango_recomendado']}")
        return resultado

    return {}


def guardar_contexto_entrenado(patrones):
    """Guarda el contexto entrenado en Supabase"""
    print("\n[7/7] Guardando contexto entrenado en Supabase...")

    contexto_data = {
        "context_type": "main",
        "total_guiones_analizados": patrones.get("total_guiones", 0),
        "fecha_entrenamiento": datetime.now().isoformat(),
        "patrones": json.dumps(patrones, ensure_ascii=False),
        "confianza": 100 if patrones.get("total_guiones", 0) >= 100 else round(patrones.get("total_guiones", 0) * 1.0, 1),
        "updated_at": datetime.now().isoformat()
    }

    try:
        # Intentar actualizar primero
        existing = sb.table("gui_training_context").select("id").eq("context_type", "main").execute()

        if existing.data:
            sb.table("gui_training_context").update(contexto_data).eq("context_type", "main").execute()
            print("[OK] Contexto actualizado")
        else:
            contexto_data["created_at"] = datetime.now().isoformat()
            sb.table("gui_training_context").insert(contexto_data).execute()
            print("[OK] Contexto creado")

        return True

    except Exception as e:
        print(f"[ERROR] No se pudo guardar contexto: {e}")
        print("        Ejecuta primero: sql_create_gui_training.sql en Supabase")
        return False


def main():
    """Función principal"""
    print("=" * 80)
    print("ENTRENAMIENTO DEL MODELO GUI")
    print("=" * 80)

    # Paso 1: Obtener guiones
    guiones = obtener_guiones()

    if not guiones:
        return

    # Analizar patrones
    estructura = analizar_estructura(guiones)
    ganchos = analizar_ganchos(guiones)
    estilo = analizar_estilo(guiones)
    keywords = analizar_palabras_clave(guiones)
    longitud = analizar_longitud_optima(guiones)

    # Consolidar todos los patrones
    patrones_completos = {
        "total_guiones": len(guiones),
        "estructura": estructura,
        "ganchos": ganchos,
        "estilo": estilo,
        "keywords": keywords,
        "longitud": longitud,
        "entrenado_en": datetime.now().isoformat()
    }

    # Guardar contexto
    exito = guardar_contexto_entrenado(patrones_completos)

    # Resumen final
    print(f"\n{'='*80}")
    print("RESUMEN DEL ENTRENAMIENTO")
    print(f"{'='*80}")
    print(f"  - Total guiones analizados: {len(guiones)}")
    print(f"  - Estructura: {estructura.get('patron_detectado', 'N/A')}")
    print(f"  - Gancho típico: Pregunta {ganchos.get('ratio_con_pregunta', 0)}% + Beneficio {ganchos.get('ratio_con_beneficio', 0)}%")
    print(f"  - Estilo: {estilo.get('ratio_preguntas', 0)}% preguntas | Tono {estilo.get('tono', 'N/A')}")
    print(f"  - Top 3 palabras: {', '.join([p[0] for p in keywords.get('top_30_palabras', [])[:3]])}")
    print(f"  - Longitud óptima: {longitud.get('promedio', 0)} palabras")
    print(f"\n[OK] Modelo GUI entrenado exitosamente")

    if not exito:
        print("\n[ADVERTENCIA] El contexto no se guardó en Supabase")
        print("              Pero puedes usarlo localmente")


if __name__ == "__main__":
    main()
