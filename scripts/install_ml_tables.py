#!/usr/bin/env python3
"""
Script para crear las tablas ML en Supabase usando conexión directa PostgreSQL
"""
import os
import sys

def create_tables():
    """Crea las tablas ML en Supabase"""
    try:
        import psycopg2
    except ImportError:
        print("[ERROR] psycopg2 no instalado")
        print("[INFO] Instalar con: pip install psycopg2-binary")
        sys.exit(1)

    # Obtener connection string de Supabase
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url:
        print("[ERROR] Falta SUPABASE_URL")
        sys.exit(1)

    # Construir connection string
    # Supabase URL format: https://xxxxx.supabase.co
    # PostgreSQL connection: postgresql://postgres:[password]@db.xxxxx.supabase.co:5432/postgres

    project_ref = supabase_url.split("//")[1].split(".")[0]

    # Necesitamos la contraseña de la BD
    db_password = os.environ.get("SUPABASE_DB_PASSWORD", "")

    if not db_password:
        print("[ERROR] Falta SUPABASE_DB_PASSWORD")
        print()
        print("Para obtener la contraseña:")
        print("1. Ir a Supabase Dashboard")
        print("2. Settings → Database")
        print("3. Copiar 'Database password'")
        print("4. Agregar a .env: SUPABASE_DB_PASSWORD=tu_password")
        print()
        print("ALTERNATIVA: Usar Supabase Dashboard SQL Editor")
        print("1. Ir a SQL Editor")
        print("2. Copiar contenido de: sql/create_ml_training_data.sql")
        print("3. Ejecutar")
        sys.exit(1)

    conn_string = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"

    print("="*70)
    print("INSTALANDO TABLAS ML EN SUPABASE")
    print("="*70)
    print()

    try:
        # Conectar
        print("[1/3] Conectando a Supabase PostgreSQL...")
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()
        print("  [OK] Conectado")

        # Leer SQL
        print()
        print("[2/3] Ejecutando SQL...")
        sql_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'create_ml_training_data.sql')

        with open(sql_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        # Ejecutar
        cur.execute(sql)
        conn.commit()
        print("  [OK] Tablas creadas")

        # Verificar
        print()
        print("[3/3] Verificando tablas...")

        tables = ['ml_training_data', 'modelo_ml_metadata', 'anti_patrones', 'video_clasificacion']
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  [OK] {table} - {count} registros")

        cur.close()
        conn.close()

        print()
        print("="*70)
        print("[OK] TABLAS ML INSTALADAS EXITOSAMENTE")
        print("="*70)
        print()
        print("Proximo paso:")
        print("  cd scripts")
        print("  python save_training_snapshot.py")
        print()

    except Exception as e:
        print(f"  [ERROR] {e}")
        print()
        print("="*70)
        print("SOLUCION ALTERNATIVA (MAS FACIL):")
        print("="*70)
        print()
        print("1. Ir a Supabase Dashboard → SQL Editor")
        print("2. Copiar contenido de: sql/create_ml_training_data.sql")
        print("3. Pegar y ejecutar (Run)")
        print()
        sys.exit(1)

if __name__ == "__main__":
    create_tables()
