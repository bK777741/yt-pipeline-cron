#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
========================================
CEREBRO 5: Planificador de Contenido Atómico
========================================

Propósito:
    Genera plan de contenido multi-formato (VOD + Shorts + Podcast).
    Los "átomos" son auto-conclusivos, NO son clips del VOD.

Basado en:
    Conceptos de Gemini - "Contenido Atómico Pre-estructurado"
    Diseñar desde el átomo, no cortar después

Costo API:
    Gemini API: GRATIS (free tier: 15 req/min, 1,500/día)
    YouTube API: 0 units

Frecuencia:
    On-demand (manual, cuando usuario planea nuevo video)

Versión: 4.4.0
Fecha: 2025-11-12
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# Importar Gemini API
try:
    import google.generativeai as genai
except ImportError:
    print("[ERROR] Instalar: pip install google-generativeai")
    sys.exit(1)

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configuración
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Cliente
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


def obtener_contexto_canal():
    """
    Obtiene contexto del canal (patrones de éxito)
    """
    try:
        # Obtener videos exitosos recientes
        result = supabase.table("videos")\
            .select("title, vph, ctr")\
            .eq("es_tuyo", True)\
            .gte("vph", 50)\
            .order("published_at", desc=True)\
            .limit(20)\
            .execute()

        videos_exitosos = result.data if result.data else []

        contexto = {
            "videos_exitosos_count": len(videos_exitosos),
            "temas_exitosos": [v["title"] for v in videos_exitosos[:10]],
            "vph_promedio": sum(v.get("vph", 0) for v in videos_exitosos) / len(videos_exitosos) if videos_exitosos else 0
        }

        return contexto

    except Exception as e:
        print(f"[WARN] No se pudo obtener contexto: {e}")
        return {
            "videos_exitosos_count": 0,
            "temas_exitosos": [],
            "vph_promedio": 0
        }


def generar_proyecto_atomico_con_gemini(tema, contexto):
    """
    Genera plan de contenido atómico usando Gemini

    Returns:
        dict con estructura completa del proyecto
    """
    print(f"[OK] Generando proyecto atómico para: '{tema}'...")
    print("[OK] Consultando Gemini API...")

    prompt = f"""
Eres un experto en estrategia de contenido para YouTube.

CONTEXTO DEL CANAL:
- Videos exitosos recientes: {contexto['videos_exitosos_count']}
- VPH promedio: {contexto['vph_promedio']:.1f}
- Ejemplos de títulos exitosos:
{chr(10).join([f"  - {t}" for t in contexto['temas_exitosos'][:5]])}

TAREA:
Diseña un "Proyecto de Contenido Atómico" para el tema: "{tema}"

IMPORTANTE: Los átomos son auto-conclusivos, NO son clips del VOD.
Cada átomo funciona 100% solo, pero temáticamente se relaciona con el núcleo.

ESTRUCTURA REQUERIDA:

1. NÚCLEO (VOD 15-20 min):
   - Título optimizado (80-100 caracteres)
   - Duración objetivo en segundos
   - Guion dividido en 5 secciones:
     * intro (30-60 seg)
     * seccion_1 (título + contenido + duración)
     * seccion_2 (título + contenido + duración)
     * seccion_3 (título + contenido + duración)
     * conclusion (30-60 seg)

2. ÁTOMOS DE BUCLE (10 Shorts de 60 seg):
   - Cada Short es una historia auto-conclusiva
   - Temáticamente relacionados con el VOD, pero funcionan solos
   - Cada uno tiene: número, título, duración (60s), gancho, desarrollo, loop

3. ÁTOMO DE AUDIO (Podcast 20-30 min):
   - Título para podcast
   - Duración objetivo
   - Guion SIN referencias visuales
   - Reemplazar "como pueden ver" por "imagina que..."

OUTPUT: Solo JSON, sin explicaciones adicionales.

Formato JSON:
{{
  "project_name": "Nombre del proyecto",
  "tema_principal": "{tema}",
  "vod": {{
    "titulo": "Título optimizado del VOD",
    "duracion_objetivo": 1200,
    "guion": {{
      "intro": "Texto de introducción...",
      "seccion_1": {{"titulo": "...", "contenido": "...", "duracion_estimada": 180}},
      "seccion_2": {{"titulo": "...", "contenido": "...", "duracion_estimada": 240}},
      "seccion_3": {{"titulo": "...", "contenido": "...", "duracion_estimada": 300}},
      "conclusion": "Texto de cierre..."
    }}
  }},
  "shorts": [
    {{
      "short_numero": 1,
      "titulo": "Título del Short 1",
      "duracion": 60,
      "gancho": "Primera frase que atrapa...",
      "desarrollo": "Contenido principal...",
      "loop": "Frase final que invita a ver de nuevo o comentar"
    }},
    ...10 Shorts en total
  ],
  "podcast": {{
    "titulo": "Título del episodio de podcast",
    "duracion_objetivo": 1500,
    "guion_sin_visuales": "Guion adaptado para audio puro...",
    "notas": "Consideraciones para grabación de audio"
  }}
}}
"""

    try:
        response = model.generate_content(prompt)
        texto_respuesta = response.text

        # Extraer JSON (Gemini a veces agrega markdown)
        if "```json" in texto_respuesta:
            inicio = texto_respuesta.find("```json") + 7
            fin = texto_respuesta.rfind("```")
            texto_respuesta = texto_respuesta[inicio:fin].strip()
        elif "```" in texto_respuesta:
            inicio = texto_respuesta.find("```") + 3
            fin = texto_respuesta.rfind("```")
            texto_respuesta = texto_respuesta[inicio:fin].strip()

        proyecto = json.loads(texto_respuesta)
        print("[OK] Proyecto generado exitosamente")
        return proyecto

    except json.JSONDecodeError as e:
        print(f"[ERROR] Respuesta de Gemini no es JSON válido: {e}")
        print(f"[DEBUG] Respuesta: {response.text[:500]}...")
        return None
    except Exception as e:
        print(f"[ERROR] Error al generar proyecto con Gemini: {e}")
        return None


def calcular_atomicity_score(proyecto):
    """
    Calcula score de atomicidad (qué tan "nativos" son los átomos)

    Criterios:
    - Shorts tienen gancho+desarrollo+loop propio (40 puntos)
    - Audio no tiene referencias visuales (30 puntos)
    - VOD estructurado en secciones claras (30 puntos)

    Score: 0-100
    """
    score = 0

    # Verificar Shorts (40 puntos)
    if "shorts" in proyecto:
        shorts = proyecto["shorts"]
        if len(shorts) >= 8:  # Al menos 8 Shorts
            score += 15

        # Verificar que cada Short tiene estructura completa
        shorts_completos = sum(
            1 for s in shorts
            if "gancho" in s and "desarrollo" in s and "loop" in s
        )
        score += (shorts_completos / len(shorts)) * 25 if shorts else 0

    # Verificar Audio (30 puntos)
    if "podcast" in proyecto:
        podcast = proyecto["podcast"]
        guion_audio = podcast.get("guion_sin_visuales", "")

        # Penalizar referencias visuales
        referencias_visuales = [
            "como pueden ver",
            "miren",
            "observen",
            "en la pantalla",
            "en esta gráfica"
        ]
        tiene_referencias = any(ref in guion_audio.lower() for ref in referencias_visuales)

        if not tiene_referencias and len(guion_audio) > 200:
            score += 30
        elif len(guion_audio) > 200:
            score += 15  # Parcial

    # Verificar VOD estructurado (30 puntos)
    if "vod" in proyecto and "guion" in proyecto["vod"]:
        guion = proyecto["vod"]["guion"]
        secciones_requeridas = ["intro", "seccion_1", "seccion_2", "conclusion"]
        secciones_presentes = sum(1 for s in secciones_requeridas if s in guion)
        score += (secciones_presentes / len(secciones_requeridas)) * 30

    return round(min(score, 100), 2)


def guardar_proyecto_en_supabase(proyecto, atomicity_score):
    """
    Guarda proyecto en Supabase
    """
    try:
        # Convertir estructura para JSONB
        vod_guion = proyecto["vod"]["guion"]
        shorts_planeados = proyecto["shorts"]
        podcast_planeado = proyecto["podcast"]

        record = {
            "project_name": proyecto["project_name"],
            "tema_principal": proyecto["tema_principal"],
            "estado": "PLANIFICADO",
            "vod_titulo_planeado": proyecto["vod"]["titulo"],
            "vod_duracion_objetivo": proyecto["vod"]["duracion_objetivo"],
            "vod_guion": vod_guion,
            "shorts_planeados": shorts_planeados,
            "shorts_publicados": 0,
            "podcast_planeado": podcast_planeado,
            "atomicity_score": atomicity_score,
            "created_at": datetime.now().isoformat()
        }

        result = supabase.table("atomic_content_projects").insert(record).execute()

        if result.data:
            project_id = result.data[0]["id"]
            print(f"[OK] Proyecto guardado con ID: {project_id}")
            return project_id
        else:
            print("[ERROR] No se pudo guardar el proyecto")
            return None

    except Exception as e:
        print(f"[ERROR] Error al guardar en Supabase: {e}")
        return None


def mostrar_proyecto(proyecto, atomicity_score):
    """
    Muestra el proyecto generado
    """
    print("\n" + "="*60)
    print("PROYECTO DE CONTENIDO ATÓMICO GENERADO")
    print("="*60)

    print(f"\nNombre del proyecto: {proyecto['project_name']}")
    print(f"Tema principal: {proyecto['tema_principal']}")
    print(f"Atomicity Score: {atomicity_score}/100")

    # VOD
    print(f"\n--- NÚCLEO (VOD) ---")
    print(f"Título: {proyecto['vod']['titulo']}")
    print(f"Duración objetivo: {proyecto['vod']['duracion_objetivo']}s ({proyecto['vod']['duracion_objetivo']//60} min)")
    print(f"Secciones del guion:")
    for seccion_key, seccion_data in proyecto['vod']['guion'].items():
        if isinstance(seccion_data, dict):
            print(f"  - {seccion_key}: {seccion_data.get('titulo', 'N/A')}")
        else:
            print(f"  - {seccion_key}: (texto)")

    # Shorts
    print(f"\n--- ÁTOMOS DE BUCLE (SHORTS) ---")
    print(f"Total de Shorts planeados: {len(proyecto['shorts'])}")
    for short in proyecto['shorts'][:3]:  # Mostrar solo los primeros 3
        print(f"\nShort #{short['short_numero']}: {short['titulo']}")
        print(f"  Gancho: {short['gancho'][:60]}...")
        print(f"  Loop: {short['loop'][:60]}...")
    print(f"... y {len(proyecto['shorts']) - 3} Shorts más")

    # Podcast
    print(f"\n--- ÁTOMO DE AUDIO (PODCAST) ---")
    print(f"Título: {proyecto['podcast']['titulo']}")
    print(f"Duración objetivo: {proyecto['podcast']['duracion_objetivo']}s ({proyecto['podcast']['duracion_objetivo']//60} min)")
    print(f"Notas: {proyecto['podcast'].get('notas', 'N/A')}")

    print("\n" + "="*60)
    print("RECOMENDACIONES:")
    print("="*60)
    print("1. Revisar y ajustar los guiones según tu estilo personal")
    print("2. Grabar los Shorts como videos independientes (NO recortar del VOD)")
    print("3. Grabar audio del podcast SIN referencias visuales")
    print("4. Publicar VOD primero, luego Shorts gradualmente")
    print("5. Monitorear CTI (Context Transfer Index) en siguientes análisis")
    print("="*60 + "\n")


def main():
    """
    Función principal
    """
    parser = argparse.ArgumentParser(description="Planificador de Contenido Atómico")
    parser.add_argument("--tema", type=str, required=True, help="Tema del proyecto (ej: 'Trucos avanzados de ChatGPT')")
    args = parser.parse_args()

    tema = args.tema

    print("\n" + "="*60)
    print("PLANIFICADOR DE CONTENIDO ATÓMICO")
    print("CEREBRO 5: Orquestador Estratégico")
    print("="*60 + "\n")

    # Obtener contexto del canal
    print("[OK] Obteniendo contexto del canal...")
    contexto = obtener_contexto_canal()

    # Generar proyecto con Gemini
    proyecto = generar_proyecto_atomico_con_gemini(tema, contexto)

    if not proyecto:
        print("[ERROR] No se pudo generar el proyecto")
        sys.exit(1)

    # Calcular atomicity score
    atomicity_score = calcular_atomicity_score(proyecto)
    print(f"[OK] Atomicity Score: {atomicity_score}/100")

    # Guardar en Supabase
    project_id = guardar_proyecto_en_supabase(proyecto, atomicity_score)

    if project_id:
        # Mostrar proyecto
        mostrar_proyecto(proyecto, atomicity_score)

        # Guardar JSON local (opcional)
        output_file = f"proyecto_atomico_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = Path(__file__).parent.parent / "output" / output_file
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(proyecto, f, indent=2, ensure_ascii=False)

        print(f"[OK] Proyecto guardado localmente: {output_file}")
        print(f"[OK] Proyecto guardado en Supabase con ID: {project_id}")
    else:
        print("[ERROR] No se pudo guardar el proyecto")


if __name__ == "__main__":
    main()
