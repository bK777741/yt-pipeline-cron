#!/usr/bin/env python3
"""
Script rápido para verificar si las tablas ML existen en Supabase
"""
import os
import sys
from supabase import create_client, Client

def check_tables():
    """Verifica si las tablas ML existen"""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Falta SUPABASE_URL o SUPABASE_SERVICE_KEY")
        print("[INFO] Configurar variables de entorno primero")
        sys.exit(1)

    sb: Client = create_client(supabase_url, supabase_key)

    tables_to_check = [
        'ml_training_data',
        'modelo_ml_metadata',
        'anti_patrones',
        'video_clasificacion'
    ]

    print("="*60)
    print("VERIFICACIÓN DE TABLAS ML")
    print("="*60)
    print()

    all_exist = True

    for table in tables_to_check:
        try:
            result = sb.table(table).select("*", count="exact").limit(0).execute()
            print(f"✅ {table} - EXISTE")
        except Exception as e:
            print(f"❌ {table} - NO EXISTE")
            print(f"   Error: {str(e)[:100]}")
            all_exist = False

    print()
    print("="*60)

    if all_exist:
        print("✅ TODAS LAS TABLAS ML EXISTEN")
        print()
        print("Sistema listo para usar!")
        print("Próximo paso: python save_training_snapshot.py")
    else:
        print("❌ FALTAN TABLAS ML")
        print()
        print("ACCIÓN REQUERIDA:")
        print("1. Ir a Supabase → SQL Editor")
        print("2. Copiar contenido de: sql/create_ml_training_data.sql")
        print("3. Ejecutar el script")
        print("4. Volver a ejecutar este script para verificar")

    print("="*60)

if __name__ == "__main__":
    check_tables()
