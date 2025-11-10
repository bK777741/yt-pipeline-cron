#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROCESADOR DE CAPTIONS -> GUIONES LIMPIOS
=========================================

Procesa captions en formato SRT (con timestamps) a texto limpio
y los guarda en tabla video_scripts para entrenamiento de GUI

Uso:
    python process_captions_to_scripts.py
"""

import os
import re
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Conectar a Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def limpiar_texto_srt(caption_text):
    """
    Limpia el texto SRT removiendo timestamps y números de secuencia

    Args:
        caption_text (str): Texto en formato SRT

    Returns:
        str: Texto limpio sin timestamps
    """
    # Remover números de secuencia
    texto = re.sub(r'^\d+\s*$', '', caption_text, flags=re.MULTILINE)

    # Remover timestamps (formato: 00:00:00,000 --> 00:00:05,000)
    texto = re.sub(r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', '', texto)

    # Remover líneas vacías
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]

    # Unir en un solo texto
    texto_limpio = ' '.join(lineas)

    # Remover espacios múltiples
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio)

    return texto_limpio.strip()


def obtener_captions_supabase():
    """Obtiene todos los captions de Supabase"""
    print("[1/4] Obteniendo captions de Supabase...")

    result = sb.table("captions").select("video_id, language, caption_text").execute()

    print(f"[OK] Encontrados {len(result.data)} captions")
    return result.data


def obtener_video_info(video_id):
    """Obtiene información del video"""
    try:
        result = sb.table("videos").select("title, published_at, view_count").eq("video_id", video_id).execute()
        if result.data:
            return result.data[0]
    except:
        pass
    return {}


def procesar_y_guardar(captions):
    """Procesa captions y los guarda en video_scripts"""
    print(f"\n[2/4] Procesando {len(captions)} captions...")

    # Verificar cuáles ya existen
    existing = sb.table("video_scripts").select("video_id").execute()
    existing_ids = {row["video_id"] for row in existing.data}

    nuevos = 0
    actualizados = 0
    errores = 0

    for idx, cap in enumerate(captions, 1):
        video_id = cap["video_id"]

        try:
            # Limpiar texto
            texto_limpio = limpiar_texto_srt(cap["caption_text"])

            # Obtener info del video
            video_info = obtener_video_info(video_id)

            # Preparar datos
            script_data = {
                "video_id": video_id,
                "script_text": texto_limpio,
                "language": cap["language"],
                "word_count": len(texto_limpio.split()),
                "video_title": video_info.get("title"),
                "video_published_at": video_info.get("published_at"),
                "video_views": video_info.get("view_count"),
                "processed_at": datetime.now().isoformat()
            }

            if video_id in existing_ids:
                # Actualizar
                sb.table("video_scripts").update(script_data).eq("video_id", video_id).execute()
                actualizados += 1
            else:
                # Insertar (sin created_at, la tabla tiene processed_at)
                sb.table("video_scripts").insert(script_data).execute()
                nuevos += 1

            # Progreso
            if idx % 10 == 0:
                print(f"  Progreso: {idx}/{len(captions)}")

        except Exception as e:
            print(f"  [ERROR] Video {video_id}: {e}")
            errores += 1

    print(f"\n[OK] Procesamiento completo:")
    print(f"  - Nuevos: {nuevos}")
    print(f"  - Actualizados: {actualizados}")
    print(f"  - Errores: {errores}")

    return nuevos + actualizados


def main():
    """Función principal"""
    print("=" * 80)
    print("PROCESADOR: Captions -> Guiones Limpios")
    print("=" * 80)

    # Paso 1: Obtener captions
    captions = obtener_captions_supabase()

    if not captions:
        print("[AVISO] No hay captions en Supabase")
        print("        Ejecuta primero: python sync_scripts_to_supabase.py")
        return

    # Paso 2: Procesar y guardar
    total_procesados = procesar_y_guardar(captions)

    # Paso 3: Verificar resultado
    print("\n[3/4] Verificando tabla video_scripts...")
    result = sb.table("video_scripts").select("*", count="exact").execute()
    total_scripts = result.count if hasattr(result, "count") else len(result.data)

    # Paso 4: Estadísticas
    print("\n[4/4] Estadísticas de guiones:")
    if result.data:
        word_counts = [row.get("word_count", 0) for row in result.data]
        avg_words = sum(word_counts) / len(word_counts) if word_counts else 0

        print(f"  - Total guiones: {total_scripts}")
        print(f"  - Palabras promedio: {avg_words:.0f}")
        print(f"  - Guión más corto: {min(word_counts)} palabras")
        print(f"  - Guión más largo: {max(word_counts)} palabras")

    print(f"\n{'='*80}")
    print("RESULTADO FINAL")
    print(f"{'='*80}")
    print(f"  - Total captions procesados: {len(captions)}")
    print(f"  - Total guiones limpios: {total_scripts}")
    print(f"\n[OK] Guiones listos para entrenar GUI")


if __name__ == "__main__":
    main()
