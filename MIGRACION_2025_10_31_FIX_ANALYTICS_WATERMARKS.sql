-- ============================================================================
-- MIGRACIÓN 2025-10-31 - CORRECCIONES CRÍTICAS
-- ============================================================================
-- Propósito: Resolver errores del pipeline identificados el 31/10/2025
-- ============================================================================
-- ERROR 1: video_analytics falta columna 'average_view_percentage'
-- ERROR 2: Tabla sync_watermarks no existe
-- ============================================================================

-- ============================================================================
-- PARTE 1: VERIFICAR Y CORREGIR TABLA video_analytics
-- ============================================================================

-- Verificar si la tabla video_analytics existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'video_analytics'
    ) THEN
        -- Si la tabla NO existe, crearla completa
        CREATE TABLE video_analytics (
            id BIGSERIAL PRIMARY KEY,
            video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
            snapshot_date DATE NOT NULL,

            -- Métricas de visualización y retención
            estimated_minutes_watched BIGINT,
            average_view_duration DECIMAL(10, 2),
            average_view_percentage DECIMAL(5, 2),
            subscribers_gained INTEGER,

            -- Métricas de monetización
            impressions BIGINT,
            impression_ctr DECIMAL(5, 4),
            average_cpm DECIMAL(10, 4),
            estimated_revenue DECIMAL(10, 4),
            ad_impressions BIGINT,
            estimated_monetized_playbacks BIGINT,

            -- Timestamps
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),

            -- Constraint para evitar duplicados
            UNIQUE (video_id, snapshot_date)
        );

        CREATE INDEX idx_video_analytics_video_id ON video_analytics(video_id);
        CREATE INDEX idx_video_analytics_snapshot_date ON video_analytics(snapshot_date DESC);
        CREATE INDEX idx_video_analytics_revenue ON video_analytics(estimated_revenue DESC);

        RAISE NOTICE '✅ Tabla video_analytics creada completamente';
    ELSE
        RAISE NOTICE '✓ Tabla video_analytics ya existe, verificando columnas...';
    END IF;
END $$;

-- Agregar columna average_view_percentage si falta
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'video_analytics'
        AND column_name = 'average_view_percentage'
    ) THEN
        ALTER TABLE video_analytics
            ADD COLUMN average_view_percentage DECIMAL(5, 2);
        RAISE NOTICE '✅ Columna average_view_percentage agregada a video_analytics';
    ELSE
        RAISE NOTICE '✓ Columna average_view_percentage ya existe';
    END IF;
END $$;

-- Agregar otras columnas críticas si faltan
DO $$
BEGIN
    -- estimated_minutes_watched
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'video_analytics'
        AND column_name = 'estimated_minutes_watched'
    ) THEN
        ALTER TABLE video_analytics
            ADD COLUMN estimated_minutes_watched BIGINT;
        RAISE NOTICE '✅ Columna estimated_minutes_watched agregada';
    END IF;

    -- average_view_duration
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'video_analytics'
        AND column_name = 'average_view_duration'
    ) THEN
        ALTER TABLE video_analytics
            ADD COLUMN average_view_duration DECIMAL(10, 2);
        RAISE NOTICE '✅ Columna average_view_duration agregada';
    END IF;

    -- subscribers_gained
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'video_analytics'
        AND column_name = 'subscribers_gained'
    ) THEN
        ALTER TABLE video_analytics
            ADD COLUMN subscribers_gained INTEGER;
        RAISE NOTICE '✅ Columna subscribers_gained agregada';
    END IF;
END $$;

-- Habilitar RLS si no está habilitado
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename = 'video_analytics'
        AND rowsecurity = true
    ) THEN
        ALTER TABLE video_analytics ENABLE ROW LEVEL SECURITY;
        RAISE NOTICE '✅ RLS habilitado en video_analytics';
    ELSE
        RAISE NOTICE '✓ RLS ya está habilitado';
    END IF;
END $$;

-- Crear política para service_role
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'video_analytics'
        AND policyname = 'Enable all for service role'
    ) THEN
        CREATE POLICY "Enable all for service role" ON video_analytics
            FOR ALL TO service_role USING (true) WITH CHECK (true);
        RAISE NOTICE '✅ Política creada para video_analytics';
    ELSE
        RAISE NOTICE '✓ Política ya existe';
    END IF;
END $$;

-- ============================================================================
-- PARTE 2: CREAR TABLA sync_watermarks
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_watermarks (
    table_name TEXT PRIMARY KEY,
    max_watermark TIMESTAMPTZ,
    total_rows INTEGER DEFAULT 0,
    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Habilitar RLS
ALTER TABLE sync_watermarks ENABLE ROW LEVEL SECURITY;

-- Crear política para service_role
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'sync_watermarks'
        AND policyname = 'Enable all for service role'
    ) THEN
        CREATE POLICY "Enable all for service role" ON sync_watermarks
            FOR ALL TO service_role USING (true) WITH CHECK (true);
        RAISE NOTICE '✅ Tabla sync_watermarks creada con RLS';
    ELSE
        RAISE NOTICE '✓ Tabla sync_watermarks ya existe';
    END IF;
END $$;

-- ============================================================================
-- VERIFICACIÓN FINAL
-- ============================================================================

-- Verificar columnas de video_analytics
SELECT
    'video_analytics' as tabla,
    column_name,
    data_type,
    '✓ Verificada' as status
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name = 'video_analytics'
    AND column_name IN (
        'average_view_percentage',
        'estimated_minutes_watched',
        'average_view_duration',
        'subscribers_gained'
    )
ORDER BY column_name;

-- Verificar tabla sync_watermarks
SELECT
    'sync_watermarks' as tabla,
    column_name,
    data_type,
    '✓ Verificada' as status
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name = 'sync_watermarks'
ORDER BY column_name;

-- ============================================================================
-- FIN DE LA MIGRACIÓN
-- ============================================================================
-- INSTRUCCIONES:
-- 1. Copiar TODO este SQL
-- 2. Ir a: https://supabase.com/dashboard/project/jkoqlxfahbcszaysbzsr/sql/new
-- 3. Pegar el SQL
-- 4. Click en "Run"
-- 5. Verificar que NO hay errores
-- 6. Ejecutar workflow de GitHub Actions nuevamente
-- ============================================================================
