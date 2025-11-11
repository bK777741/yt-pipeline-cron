#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONITOR DE STORAGE
==================

Muestra uso actual de Supabase Free (500 MB limite)
Proyecta cuando se llenara
Alerta si cerca del limite

EJECUCION:
- Manual: python scripts/monitor_storage.py
- Automatico: GitHub Actions (semanal)
"""

import os
import sys
from datetime import datetime, timedelta
from supabase import create_client, Client


def generar_barra_visual(porcentaje, ancho=40):
    """
    Genera barra visual de progreso
    """
    lleno = int((porcentaje / 100) * ancho)
    vacio = ancho - lleno

    if porcentaje > 90:
        color = "[CRITICO]"
    elif porcentaje > 70:
        color = "[ALERTA]"
    else:
        color = "[OK]"

    barra = "█" * lleno + "░" * vacio
    return f"{barra} {porcentaje:5.1f}% {color}"


def monitorear_storage(sb: Client):
    """
    Genera reporte completo de storage
    """
    print()
    print("=" * 80)
    print("MONITOR DE STORAGE - SUPABASE FREE")
    print("=" * 80)
    print()

    # Configuracion
    LIMITE_MB = 500
    TABLAS_INFO = [
        ('videos', 2),           # KB por fila (promedio)
        ('captions', 50),        # KB por fila
        ('video_trending', 3),   # KB por fila
        ('shorts_explosive', 2), # KB por fila
        ('ml_suggestions', 1),   # KB por fila
        ('ml_feedback', 2),      # KB por fila
        ('patrones_exito', 0.5), # KB por fila
        ('anti_patrones', 0.5),  # KB por fila
    ]

    total_mb = 0
    detalles = []

    print("USO POR TABLA:")
    print("-" * 80)
    print(f"{'Tabla':<25} | {'Filas':>8} | {'Tamaño':>10} | Uso")
    print("-" * 80)

    for tabla, kb_por_fila in TABLAS_INFO:
        try:
            # Contar filas
            result = sb.table(tabla).select("*", count="exact").execute()
            count = result.count if hasattr(result, 'count') else 0

            # Calcular tamaño
            size_mb = (count * kb_por_fila) / 1024
            total_mb += size_mb

            # Porcentaje del total
            porcentaje = (size_mb / LIMITE_MB) * 100

            # Barra visual
            barra = "█" * min(int(porcentaje * 2), 40)

            detalles.append({
                'tabla': tabla,
                'filas': count,
                'size_mb': size_mb,
                'porcentaje': porcentaje
            })

            print(f"{tabla:<25} | {count:>8} | {size_mb:>8.2f} MB | {barra}")

        except Exception as e:
            print(f"{tabla:<25} | ERROR: {str(e)[:40]}")

    print("-" * 80)
    print(f"{'TOTAL':<25} | {' ':>8} | {total_mb:>8.2f} MB |")
    print()

    # Resumen
    espacio_libre = LIMITE_MB - total_mb
    porcentaje_usado = (total_mb / LIMITE_MB) * 100

    print("=" * 80)
    print("RESUMEN")
    print("=" * 80)
    print()
    print(f"Limite Supabase Free: {LIMITE_MB} MB")
    print(f"Espacio usado:        {total_mb:.2f} MB ({porcentaje_usado:.1f}%)")
    print(f"Espacio libre:        {espacio_libre:.2f} MB")
    print()

    # Barra de progreso total
    print("Uso total:")
    print(generar_barra_visual(porcentaje_usado, 60))
    print()

    # Alertas
    if porcentaje_usado > 90:
        print("🚨 CRITICO: Ejecutar purga URGENTE")
        print("   Comando: python scripts/purga_inteligente.py")
    elif porcentaje_usado > 70:
        print("⚠️  ALERTA: Cerca del limite, programar purga pronto")
        print("   Comando: python scripts/purga_inteligente.py --dry-run")
    else:
        print("✅ Espacio OK - Sin accion requerida")
    print()

    # Proyeccion
    try:
        proyeccion = proyectar_llenado(sb, total_mb, LIMITE_MB)

        if proyeccion:
            print("=" * 80)
            print("PROYECCION")
            print("=" * 80)
            print()
            print(f"Crecimiento estimado: {proyeccion['crecimiento_diario_mb']:.2f} MB/dia")
            print(f"Dias hasta lleno:     ~{proyeccion['dias_restantes']} dias")
            print(f"Fecha estimada:       {proyeccion['fecha_estimada']}")
            print()

            if proyeccion['dias_restantes'] < 30:
                print("⚠️  Programar purga en menos de 1 mes")
            else:
                print("✅ Margen de tiempo suficiente")
            print()
    except Exception as e:
        print(f"[INFO] No se pudo calcular proyeccion: {e}")
        print()

    # Tablas mas grandes
    print("=" * 80)
    print("TOP 3 TABLAS MAS GRANDES")
    print("=" * 80)
    print()

    top_tablas = sorted(detalles, key=lambda x: x['size_mb'], reverse=True)[:3]

    for i, tabla_info in enumerate(top_tablas, 1):
        print(f"{i}. {tabla_info['tabla']}")
        print(f"   Tamaño: {tabla_info['size_mb']:.2f} MB")
        print(f"   Filas: {tabla_info['filas']:,}")
        print()

    return {
        'total_mb': total_mb,
        'porcentaje_usado': porcentaje_usado,
        'espacio_libre': espacio_libre
    }


def proyectar_llenado(sb: Client, total_mb_actual, limite_mb):
    """
    Proyecta cuando se llenara Supabase
    """
    # Obtener registros de hace 7 dias para calcular crecimiento
    fecha_hace_7d = (datetime.now() - timedelta(days=7)).isoformat()

    try:
        # Contar videos de ultimos 7 dias
        videos_recientes = sb.table("videos")\
            .select("*", count="exact")\
            .gte("published_at", fecha_hace_7d)\
            .execute()

        videos_por_semana = videos_recientes.count if hasattr(videos_recientes, 'count') else 0

        if videos_por_semana == 0:
            return None

        # Estimar crecimiento (2 KB por video + 50 KB subtitulos)
        crecimiento_semanal_mb = (videos_por_semana * 52) / 1024  # 52 KB total por video
        crecimiento_diario_mb = crecimiento_semanal_mb / 7

        # Calcular dias restantes
        espacio_restante = limite_mb - total_mb_actual
        dias_restantes = int(espacio_restante / crecimiento_diario_mb) if crecimiento_diario_mb > 0 else 999

        # Fecha estimada
        fecha_estimada = (datetime.now() + timedelta(days=dias_restantes)).strftime("%Y-%m-%d")

        return {
            'crecimiento_diario_mb': crecimiento_diario_mb,
            'dias_restantes': dias_restantes,
            'fecha_estimada': fecha_estimada
        }

    except Exception as e:
        return None


def main():
    """
    Ejecuta monitor de storage
    """
    # Cargar env
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables de entorno no configuradas")
        print("        SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    # Crear cliente
    sb = create_client(supabase_url, supabase_key)

    # Monitorear
    resultado = monitorear_storage(sb)

    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
