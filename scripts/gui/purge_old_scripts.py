#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PURGA AUTOMATICA DE GUIONES ANTIGUOS
=====================================

Elimina guiones con mas de 6 meses de antiguedad.
Mantiene el modelo actualizado con patrones recientes.

YouTube cambia constantemente:
- Algoritmo evoluciona
- Tendencias cambian
- Audiencia se transforma

Mantener solo ultimos 6 meses = Modelo siempre relevante

Uso:
    python purge_old_scripts.py
"""

import os
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Conectar a Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Ventana temporal: 6 meses
MESES_ANTIGUEDAD = 6


def purgar_guiones_antiguos():
    """Elimina guiones con mas de 6 meses"""
    print("=" * 80)
    print("PURGA AUTOMATICA DE GUIONES ANTIGUOS")
    print("=" * 80)
    print(f"\nVentana temporal: Ultimos {MESES_ANTIGUEDAD} meses")

    # Calcular fecha limite
    fecha_limite = datetime.now() - timedelta(days=MESES_ANTIGUEDAD * 30)
    print(f"Fecha limite: {fecha_limite.strftime('%Y-%m-%d')}")
    print(f"Eliminar guiones procesados ANTES de esta fecha\n")

    # Paso 1: Contar guiones totales
    print("[1/4] Contando guiones...")
    result_total = sb.table("video_scripts").select("*", count="exact").execute()
    total_antes = len(result_total.data)
    print(f"[OK] Total guiones: {total_antes}")

    # Paso 2: Identificar guiones antiguos
    print("\n[2/4] Identificando guiones antiguos...")
    result_antiguos = sb.table("video_scripts")\
        .select("*")\
        .lt("processed_at", fecha_limite.isoformat())\
        .execute()

    guiones_antiguos = len(result_antiguos.data)
    print(f"[OK] Guiones antiguos (> {MESES_ANTIGUEDAD} meses): {guiones_antiguos}")

    if guiones_antiguos == 0:
        print("\n[OK] No hay guiones antiguos para eliminar")
        print("=" * 80)
        return

    # Paso 3: Eliminar guiones antiguos
    print(f"\n[3/4] Eliminando {guiones_antiguos} guiones antiguos...")
    sb.table("video_scripts")\
        .delete()\
        .lt("processed_at", fecha_limite.isoformat())\
        .execute()

    print("[OK] Guiones antiguos eliminados")

    # Paso 4: Verificar resultado
    print("\n[4/4] Verificando resultado...")
    result_final = sb.table("video_scripts").select("*", count="exact").execute()
    total_despues = len(result_final.data)

    print(f"[OK] Total guiones restantes: {total_despues}")

    # Resumen
    print("\n" + "=" * 80)
    print("RESUMEN DE PURGA")
    print("=" * 80)
    print(f"  - Guiones antes:      {total_antes}")
    print(f"  - Guiones eliminados: {guiones_antiguos}")
    print(f"  - Guiones restantes:  {total_despues}")
    print(f"  - Ventana temporal:   Ultimos {MESES_ANTIGUEDAD} meses")
    print("\n[OK] Purga completada exitosamente")
    print("=" * 80)


def purgar_captions_antiguos():
    """Elimina captions con mas de 6 meses (opcional)"""
    print("\n" + "=" * 80)
    print("PURGA DE CAPTIONS ANTIGUOS")
    print("=" * 80)

    # Calcular fecha limite
    fecha_limite = datetime.now() - timedelta(days=MESES_ANTIGUEDAD * 30)

    # Contar captions totales
    result_total = sb.table("captions").select("*", count="exact").execute()
    total_antes = len(result_total.data)

    print(f"Total captions: {total_antes}")

    # Identificar captions antiguos
    result_antiguos = sb.table("captions")\
        .select("*")\
        .lt("created_at", fecha_limite.isoformat())\
        .execute()

    captions_antiguos = len(result_antiguos.data)
    print(f"Captions antiguos: {captions_antiguos}")

    if captions_antiguos == 0:
        print("[OK] No hay captions antiguos para eliminar\n")
        return

    # Eliminar
    sb.table("captions")\
        .delete()\
        .lt("created_at", fecha_limite.isoformat())\
        .execute()

    print(f"[OK] {captions_antiguos} captions eliminados")

    # Verificar
    result_final = sb.table("captions").select("*", count="exact").execute()
    total_despues = len(result_final.data)

    print(f"[OK] Total captions restantes: {total_despues}\n")


if __name__ == "__main__":
    try:
        # Purgar guiones
        purgar_guiones_antiguos()

        # Purgar captions (opcional)
        purgar_captions_antiguos()

        print("\n[EXITO] Purga automatica completada")
        print("El modelo se mantendra actualizado con datos recientes")

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        exit(1)
