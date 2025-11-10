#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SINCRONIZACION DE GUIONES: Local -> Supabase
===========================================

Sincroniza los guiones capturados en youtube.db (local) a Supabase (nube)
Para que esten disponibles para entrenamiento de la GUI

Uso:
    python sync_scripts_to_supabase.py
"""

import sqlite3
import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Conectar a Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_local_captions():
    """Obtiene todos los captions de youtube.db local"""
    conn = sqlite3.connect("youtube.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            video_id,
            language,
            caption_text,
            created_at
        FROM captions
    """)

    captions_raw = cursor.fetchall()
    conn.close()

    # Convertir a dict y decodificar bytes a string
    captions = []
    for row in captions_raw:
        cap = dict(row)

        # Si caption_text es bytes, decodificar a UTF-8
        if isinstance(cap['caption_text'], bytes):
            cap['caption_text'] = cap['caption_text'].decode('utf-8')

        captions.append(cap)

    return captions


def sync_to_supabase(captions):
    """Sincroniza captions a Supabase"""
    print(f"\n[1/3] Sincronizando {len(captions)} guiones a Supabase...")

    # Verificar cuántos ya existen
    existing = sb.table("captions").select("video_id").execute()
    existing_ids = {row["video_id"] for row in existing.data}

    nuevos = 0
    actualizados = 0
    errores = 0

    for cap in captions:
        try:
            if cap["video_id"] in existing_ids:
                # Actualizar existente
                sb.table("captions").update({
                    "language": cap["language"],
                    "caption_text": cap["caption_text"],
                    "updated_at": datetime.now().isoformat()
                }).eq("video_id", cap["video_id"]).execute()
                actualizados += 1
            else:
                # Insertar nuevo
                sb.table("captions").insert({
                    "video_id": cap["video_id"],
                    "language": cap["language"],
                    "caption_text": cap["caption_text"],
                    "created_at": cap.get("created_at", datetime.now().isoformat())
                }).execute()
                nuevos += 1

            # Progreso cada 10
            if (nuevos + actualizados) % 10 == 0:
                print(f"  Progreso: {nuevos + actualizados}/{len(captions)}")

        except Exception as e:
            print(f"  [ERROR] Video {cap['video_id']}: {e}")
            errores += 1

    print(f"\n[OK] Sincronización completa:")
    print(f"  - Nuevos: {nuevos}")
    print(f"  - Actualizados: {actualizados}")
    print(f"  - Errores: {errores}")

    return nuevos + actualizados


def main():
    """Función principal"""
    print("=" * 80)
    print("SINCRONIZACION DE GUIONES: Local -> Supabase")
    print("=" * 80)

    # Paso 1: Obtener captions locales
    print("\n[1/2] Obteniendo guiones de youtube.db local...")
    captions = get_local_captions()

    if not captions:
        print("[AVISO] No hay guiones en youtube.db")
        print("        Ejecuta primero: python captura_subtitulos_api_oficial.py")
        return

    print(f"[OK] Encontrados {len(captions)} guiones locales")

    # Paso 2: Sincronizar a Supabase
    print("\n[2/2] Sincronizando a Supabase...")
    total_sync = sync_to_supabase(captions)

    # Verificar en Supabase
    print("\n[3/3] Verificando en Supabase...")
    result = sb.table("captions").select("*", count="exact").execute()
    total_supabase = result.count if hasattr(result, "count") else len(result.data)

    print(f"\n{'='*80}")
    print("RESULTADO FINAL")
    print(f"{'='*80}")
    print(f"  - Total en youtube.db local: {len(captions)}")
    print(f"  - Total en Supabase: {total_supabase}")
    print(f"  - Sincronizados en esta sesión: {total_sync}")
    print(f"\n[OK] Guiones listos para entrenamiento GUI")


if __name__ == "__main__":
    main()
