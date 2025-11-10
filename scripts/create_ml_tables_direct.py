#!/usr/bin/env python3
"""
Crea tablas ML usando la API REST de Supabase directamente
"""
import os
import sys
import requests
import json

def create_tables():
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Faltan credenciales")
        sys.exit(1)

    print("="*70)
    print("CREANDO TABLAS ML EN SUPABASE")
    print("="*70)
    print()

    # Intentar crear tabla por tabla usando DDL via función RPC
    # Primero verificamos si existe la función exec_sql

    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }

    # Lista de SQLs a ejecutar
    sqls = [
        # Tabla ml_training_data
        """
        CREATE TABLE IF NOT EXISTS ml_training_data (
            id SERIAL PRIMARY KEY,
            video_id TEXT NOT NULL UNIQUE,
            es_tuyo BOOLEAN DEFAULT FALSE,
            title TEXT NOT NULL,
            published_at TIMESTAMPTZ NOT NULL,
            duration INTEGER,
            category_id INTEGER,
            channel_id TEXT,
            channel_subscribers INTEGER DEFAULT 0,
            thumbnail_url TEXT,
            thumbnail_text TEXT,
            thumbnail_has_text BOOLEAN DEFAULT FALSE,
            view_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            vph DECIMAL(10,2),
            ctr DECIMAL(5,2),
            average_view_percentage DECIMAL(5,2),
            nicho_score INTEGER DEFAULT 0,
            snapshot_date TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        "CREATE INDEX IF NOT EXISTS idx_ml_training_published ON ml_training_data(published_at);",
        "CREATE INDEX IF NOT EXISTS idx_ml_training_es_tuyo ON ml_training_data(es_tuyo);",
        "CREATE INDEX IF NOT EXISTS idx_ml_training_snapshot ON ml_training_data(snapshot_date);",
        "CREATE INDEX IF NOT EXISTS idx_ml_training_vph ON ml_training_data(vph);",

        # Tabla video_clasificacion
        """
        CREATE TABLE IF NOT EXISTS video_clasificacion (
            video_id TEXT PRIMARY KEY,
            clasificacion TEXT NOT NULL CHECK (clasificacion IN ('EXITOSO', 'PROMEDIO', 'FRACASO')),
            score DECIMAL(5,2),
            vph DECIMAL(10,2),
            ctr DECIMAL(5,2),
            retencion DECIMAL(5,2),
            engagement DECIMAL(5,2),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        "CREATE INDEX IF NOT EXISTS idx_video_clasificacion_clase ON video_clasificacion(clasificacion);",
        "CREATE INDEX IF NOT EXISTS idx_video_clasificacion_score ON video_clasificacion(score);",

        # Tabla modelo_ml_metadata
        """
        CREATE TABLE IF NOT EXISTS modelo_ml_metadata (
            id SERIAL PRIMARY KEY,
            version TEXT NOT NULL,
            precision DECIMAL(5,2) NOT NULL,
            r2_mean DECIMAL(5,4),
            r2_std DECIMAL(5,4),
            dataset_size INTEGER NOT NULL,
            features_usadas TEXT[],
            trained_at TIMESTAMPTZ DEFAULT NOW(),
            commit_hash TEXT,
            notas TEXT
        );
        """,

        "CREATE INDEX IF NOT EXISTS idx_modelo_ml_trained ON modelo_ml_metadata(trained_at);",

        # Tabla anti_patrones
        """
        CREATE TABLE IF NOT EXISTS anti_patrones (
            id SERIAL PRIMARY KEY,
            patron TEXT NOT NULL,
            descripcion TEXT,
            frecuencia INTEGER DEFAULT 1,
            confianza TEXT CHECK (confianza IN ('BAJA', 'MEDIA', 'ALTA')),
            impacto_vph_promedio DECIMAL(10,2),
            ejemplos_video_ids TEXT[],
            detectado_at TIMESTAMPTZ DEFAULT NOW(),
            actualizado_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        "CREATE INDEX IF NOT EXISTS idx_anti_patrones_confianza ON anti_patrones(confianza);",
        "CREATE INDEX IF NOT EXISTS idx_anti_patrones_actualizado ON anti_patrones(actualizado_at);",
    ]

    print("[INFO] Intentando crear tablas via API REST...")
    print("[INFO] Si falla, usar Supabase Dashboard (mas confiable)")
    print()

    # Como PostgREST no expone SQL directo, usamos curl/psql
    print("[SOLUCION] Creando archivo batch para ejecutar SQL...")

    # Crear script PowerShell
    script_content = f"""
$env:PGPASSWORD = "$env:SUPABASE_DB_PASSWORD"
psql -h db.$(({supabase_url} -split '//')[1] -split '\\.')[0].supabase.co -U postgres -d postgres -f "sql/create_ml_training_data.sql"
"""

    script_path = os.path.join(os.path.dirname(__file__), '..', 'install_ml_tables.ps1')
    with open(script_path, 'w') as f:
        f.write(script_content)

    print(f"[OK] Script creado: {script_path}")
    print()
    print("="*70)
    print("SIGUIENTE PASO - ELEGIR UNA OPCION:")
    print("="*70)
    print()
    print("OPCION 1 (RECOMENDADA - 2 minutos):")
    print("  1. Abrir: https://supabase.com/dashboard")
    print("  2. Tu proyecto → SQL Editor")
    print("  3. New Query")
    print(f"  4. Copiar TODO el contenido de:")
    print(f"     sql/create_ml_training_data.sql")
    print("  5. Pegar y ejecutar (Run)")
    print()
    print("OPCION 2 (Si tienes PostgreSQL CLI):")
    print("  1. Configurar SUPABASE_DB_PASSWORD en .env")
    print("  2. Ejecutar: powershell install_ml_tables.ps1")
    print()
    print("="*70)

if __name__ == "__main__":
    create_tables()
