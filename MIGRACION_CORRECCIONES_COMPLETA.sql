-- ============================================================================
-- MIGRACIÓN COMPLETA - CORRECCIÓN DE ERRORES DEL PIPELINE
-- ============================================================================
-- Fecha: 2025-10-29
-- Propósito: Corregir todos los errores identificados en GitHub Actions
-- ============================================================================

-- ============================================================================
-- PARTE 1: AGREGAR COLUMNA processed_at A TABLA captions
-- ============================================================================
-- Script afectado: convert_captions_to_script.py (línea 36)
-- Error: column captions.processed_at does not exist

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'captions' AND column_name = 'processed_at'
    ) THEN
        ALTER TABLE captions ADD COLUMN processed_at TIMESTAMPTZ;
        RAISE NOTICE 'Columna processed_at agregada a captions';
    ELSE
        RAISE NOTICE 'Columna processed_at ya existe en captions';
    END IF;
END $$;

-- ============================================================================
-- PARTE 2: CREAR TABLA posting_schedule
-- ============================================================================
-- Script afectado: compute_posting_schedule.py (línea 66)
-- Error: column 'hour_bucket' does not exist in posting_schedule

CREATE TABLE IF NOT EXISTS posting_schedule (
    id BIGSERIAL PRIMARY KEY,
    weekday INTEGER NOT NULL,          -- 0=Lunes, 6=Domingo
    hour_bucket INTEGER NOT NULL,      -- 0-11 (bloques de 2 horas)
    avg_views_24h DECIMAL(12, 2),     -- Promedio de vistas en las primeras 24h

    -- Metadatos
    sample_size INTEGER DEFAULT 0,     -- Cantidad de videos en la muestra
    last_calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraint para evitar duplicados
    UNIQUE (weekday, hour_bucket)
);

CREATE INDEX IF NOT EXISTS idx_posting_schedule_weekday ON posting_schedule(weekday);
CREATE INDEX IF NOT EXISTS idx_posting_schedule_views ON posting_schedule(avg_views_24h DESC);

-- Habilitar RLS
ALTER TABLE posting_schedule ENABLE ROW LEVEL SECURITY;

-- Crear política para service_role
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'posting_schedule'
        AND policyname = 'Enable all for service role'
    ) THEN
        CREATE POLICY "Enable all for service role" ON posting_schedule
            FOR ALL TO service_role USING (true) WITH CHECK (true);
        RAISE NOTICE 'Política creada para posting_schedule';
    END IF;
END $$;

-- ============================================================================
-- PARTE 3: CORREGIR REFERENCIAS EN TABLA comments
-- ============================================================================
-- Error: comments.video_id referencia a videos(id) pero debería ser videos(video_id)
-- Nota: Solo aplica si la tabla comments ya existe

DO $$
BEGIN
    -- Verificar si la tabla comments existe
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'comments'
    ) THEN
        -- Eliminar constraint antigua si existe
        IF EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = 'comments'
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name LIKE '%video%'
        ) THEN
            ALTER TABLE comments DROP CONSTRAINT IF EXISTS comments_video_id_fkey;
            RAISE NOTICE 'Constraint antigua eliminada de comments';
        END IF;

        -- Agregar constraint correcta
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE table_name = 'comments'
            AND constraint_type = 'FOREIGN KEY'
            AND constraint_name = 'comments_video_id_fkey_corrected'
        ) THEN
            ALTER TABLE comments
                ADD CONSTRAINT comments_video_id_fkey_corrected
                FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE;
            RAISE NOTICE 'Constraint correcta agregada a comments';
        END IF;

        -- Cambiar columna id a comment_id si es necesario
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'comments' AND column_name = 'comment_id'
        ) AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'comments' AND column_name = 'id'
        ) THEN
            ALTER TABLE comments RENAME COLUMN id TO comment_id;
            RAISE NOTICE 'Columna id renombrada a comment_id en comments';
        END IF;

        -- Agregar columnas faltantes para import_recent_comments.py
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'comments' AND column_name = 'author_channel_url'
        ) THEN
            ALTER TABLE comments ADD COLUMN author_channel_url TEXT;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'comments' AND column_name = 'checked_at'
        ) THEN
            ALTER TABLE comments ADD COLUMN checked_at TIMESTAMPTZ;
        END IF;

        RAISE NOTICE 'Tabla comments corregida';
    ELSE
        RAISE NOTICE 'Tabla comments no existe, se debe crear primero';
    END IF;
END $$;

-- ============================================================================
-- PARTE 4: CORREGIR REFERENCIAS EN OTRAS TABLAS
-- ============================================================================
-- Aplicar correcciones similares a otras tablas que referencian videos(id)

DO $$
DECLARE
    tabla TEXT;
BEGIN
    FOR tabla IN
        SELECT unnest(ARRAY[
            'captions',
            'video_scripts',
            'video_thumbnail_objects',
            'video_thumbnail_text'
        ])
    LOOP
        -- Solo procesar si la tabla existe
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = tabla
        ) THEN
            -- Eliminar constraint antigua
            EXECUTE format('
                ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I
            ', tabla, tabla || '_video_id_fkey');

            -- Agregar constraint correcta
            EXECUTE format('
                ALTER TABLE %I
                    ADD CONSTRAINT %I
                    FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
            ', tabla, tabla || '_video_id_fkey_corrected');

            RAISE NOTICE 'Constraint corregida en tabla %', tabla;
        END IF;
    END LOOP;
END $$;

-- ============================================================================
-- PARTE 5: CREAR VISTA v_video_stats_latest (útil para build_niche_profile.py)
-- ============================================================================
-- Esta vista facilita obtener las estadísticas más recientes de cada video

CREATE OR REPLACE VIEW v_video_stats_latest AS
SELECT DISTINCT ON (v.video_id)
    v.video_id,
    v.channel_id,
    v.title,
    v.description,
    v.published_at,
    v.duration,
    v.category_id,
    v.tags,
    vs.view_count,
    vs.like_count,
    vs.comment_count,
    vs.snapshot_date,
    vs.snapshot_at
FROM videos v
LEFT JOIN video_statistics vs ON v.video_id = vs.video_id
ORDER BY v.video_id, vs.snapshot_at DESC NULLS LAST;

-- ============================================================================
-- VERIFICACIÓN FINAL
-- ============================================================================

-- Verificar tablas creadas/corregidas
SELECT
    table_name,
    CASE
        WHEN table_name = 'posting_schedule' THEN 'Nueva tabla creada'
        WHEN table_name = 'captions' THEN 'Columna processed_at agregada'
        WHEN table_name = 'comments' THEN 'Referencias corregidas'
        ELSE 'Verificada'
    END as status
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_name IN (
        'posting_schedule',
        'captions',
        'comments',
        'video_scripts'
    )
ORDER BY table_name;

-- Verificar columnas críticas
SELECT
    table_name,
    column_name,
    data_type,
    'Columna verificada' as status
FROM information_schema.columns
WHERE table_schema = 'public'
    AND (
        (table_name = 'captions' AND column_name = 'processed_at')
        OR (table_name = 'posting_schedule' AND column_name = 'hour_bucket')
        OR (table_name = 'comments' AND column_name = 'comment_id')
    )
ORDER BY table_name, column_name;

-- ============================================================================
-- FIN DE LA MIGRACIÓN
-- ============================================================================
-- Ejecutar este SQL completo en Supabase SQL Editor
-- URL: https://supabase.com/dashboard/project/jkoqlxfahbcszaysbzsr/editor
-- ============================================================================
