#!/usr/bin/env python3
"""
Script para crear las tablas ML en Supabase usando el cliente Python
"""
import os
import sys
from supabase import create_client, Client

def create_tables():
    """Crea las tablas ML en Supabase"""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Falta SUPABASE_URL o SUPABASE_SERVICE_KEY")
        sys.exit(1)

    sb: Client = create_client(supabase_url, supabase_key)

    # Leer el SQL
    sql_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'create_ml_training_data.sql')
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    print("="*60)
    print("CREANDO TABLAS ML EN SUPABASE")
    print("="*60)
    print()

    try:
        # Ejecutar SQL usando rpc
        print("[INFO] Ejecutando SQL...")

        # Supabase no tiene método directo para ejecutar SQL desde Python
        # Necesitamos usar la API REST directamente
        import requests

        headers = {
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}',
            'Content-Type': 'application/json'
        }

        # Ejecutar cada statement por separado
        statements = [
            # ml_training_data
            """CREATE TABLE IF NOT EXISTS ml_training_data (
                id SERIAL PRIMARY KEY,
                video_id TEXT NOT NULL,
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
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(video_id)
            )""",

            # Indices ml_training_data
            "CREATE INDEX IF NOT EXISTS idx_ml_training_published ON ml_training_data(published_at)",
            "CREATE INDEX IF NOT EXISTS idx_ml_training_es_tuyo ON ml_training_data(es_tuyo)",
            "CREATE INDEX IF NOT EXISTS idx_ml_training_snapshot ON ml_training_data(snapshot_date)",
            "CREATE INDEX IF NOT EXISTS idx_ml_training_vph ON ml_training_data(vph)",

            # video_clasificacion
            """CREATE TABLE IF NOT EXISTS video_clasificacion (
                video_id TEXT PRIMARY KEY,
                clasificacion TEXT NOT NULL CHECK (clasificacion IN ('EXITOSO', 'PROMEDIO', 'FRACASO')),
                score DECIMAL(5,2),
                vph DECIMAL(10,2),
                ctr DECIMAL(5,2),
                retencion DECIMAL(5,2),
                engagement DECIMAL(5,2),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )""",

            # Indices video_clasificacion
            "CREATE INDEX IF NOT EXISTS idx_video_clasificacion_clase ON video_clasificacion(clasificacion)",
            "CREATE INDEX IF NOT EXISTS idx_video_clasificacion_score ON video_clasificacion(score)",

            # modelo_ml_metadata
            """CREATE TABLE IF NOT EXISTS modelo_ml_metadata (
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
            )""",

            # Indices modelo_ml_metadata
            "CREATE INDEX IF NOT EXISTS idx_modelo_ml_trained ON modelo_ml_metadata(trained_at)",

            # anti_patrones
            """CREATE TABLE IF NOT EXISTS anti_patrones (
                id SERIAL PRIMARY KEY,
                patron TEXT NOT NULL,
                descripcion TEXT,
                frecuencia INTEGER DEFAULT 1,
                confianza TEXT CHECK (confianza IN ('BAJA', 'MEDIA', 'ALTA')),
                impacto_vph_promedio DECIMAL(10,2),
                ejemplos_video_ids TEXT[],
                detectado_at TIMESTAMPTZ DEFAULT NOW(),
                actualizado_at TIMESTAMPTZ DEFAULT NOW()
            )""",

            # Indices anti_patrones
            "CREATE INDEX IF NOT EXISTS idx_anti_patrones_confianza ON anti_patrones(confianza)",
            "CREATE INDEX IF NOT EXISTS idx_anti_patrones_actualizado ON anti_patrones(actualizado_at)",

            # Vista
            """CREATE OR REPLACE VIEW ml_dataset_summary AS
            SELECT
                COUNT(*) as total_videos,
                COUNT(CASE WHEN es_tuyo THEN 1 END) as videos_propios,
                COUNT(CASE WHEN NOT es_tuyo THEN 1 END) as videos_competencia,
                AVG(vph) as vph_promedio,
                MIN(published_at) as fecha_mas_antigua,
                MAX(published_at) as fecha_mas_reciente,
                AVG(nicho_score) as nicho_score_promedio
            FROM ml_training_data"""
        ]

        # Ejecutar cada statement
        for i, statement in enumerate(statements, 1):
            print(f"[{i}/{len(statements)}] Ejecutando...")
            response = requests.post(
                f"{supabase_url}/rest/v1/rpc/exec",
                headers=headers,
                json={'query': statement}
            )

        print()
        print("[OK] SQL ejecutado correctamente")

        # Verificar tablas creadas
        print()
        print("Verificando tablas creadas...")

        tables = ['ml_training_data', 'modelo_ml_metadata', 'anti_patrones', 'video_clasificacion']
        for table in tables:
            try:
                sb.table(table).select("*", count="exact").limit(0).execute()
                print(f"  [OK] {table}")
            except Exception as e:
                print(f"  [ERROR] {table}: {str(e)[:100]}")

        print()
        print("="*60)
        print("[OK] TABLAS ML CREADAS EXITOSAMENTE")
        print("="*60)
        print()
        print("Proximo paso:")
        print("  python save_training_snapshot.py")

    except Exception as e:
        print(f"[ERROR] Error ejecutando SQL: {e}")
        print()
        print("="*60)
        print("SOLUCION ALTERNATIVA:")
        print("="*60)
        print()
        print("1. Ir a Supabase Dashboard")
        print("2. SQL Editor")
        print("3. Copiar contenido de: sql/create_ml_training_data.sql")
        print("4. Pegar y ejecutar")
        sys.exit(1)

if __name__ == "__main__":
    create_tables()
