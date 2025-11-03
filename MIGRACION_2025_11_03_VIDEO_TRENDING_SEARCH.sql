-- ============================================================================
-- MIGRACIÓN: 2025-11-03 - Agregar columnas para búsqueda activa de trending
-- ============================================================================
-- Propósito: Permitir que fetch_shorts_search.py y fetch_explosive_longs.py
--            inserten datos en video_trending con campos adicionales
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Agregar columnas faltantes a video_trending
-- ============================================================================

-- channel_id (necesario para análisis de competencia)
ALTER TABLE public.video_trending
ADD COLUMN IF NOT EXISTS channel_id TEXT;

-- duration_sec (duración en segundos, más útil que duration TEXT)
ALTER TABLE public.video_trending
ADD COLUMN IF NOT EXISTS duration_sec INTEGER;

-- format (short/long/medium para clasificación)
ALTER TABLE public.video_trending
ADD COLUMN IF NOT EXISTS format TEXT CHECK (format IN ('short', 'long', 'medium'));

-- similarity (score de similitud con perfil del canal)
ALTER TABLE public.video_trending
ADD COLUMN IF NOT EXISTS similarity NUMERIC(5,3) DEFAULT 0.0;

-- topic_key (categorización de contenido para diversidad)
ALTER TABLE public.video_trending
ADD COLUMN IF NOT EXISTS topic_key TEXT;

-- ============================================================================
-- 2. Crear índices para optimizar consultas
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_video_trending_channel_id
    ON public.video_trending(channel_id);

CREATE INDEX IF NOT EXISTS idx_video_trending_format
    ON public.video_trending(format) WHERE format IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_video_trending_duration_sec
    ON public.video_trending(duration_sec);

CREATE INDEX IF NOT EXISTS idx_video_trending_published_at
    ON public.video_trending(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_video_trending_topic_key
    ON public.video_trending(topic_key) WHERE topic_key IS NOT NULL;

-- ============================================================================
-- 3. Actualizar datos existentes (si hay)
-- ============================================================================

-- Convertir duration TEXT a duration_sec INTEGER para registros existentes
-- Formato esperado: "PT15M30S" → 930 segundos
UPDATE public.video_trending
SET duration_sec = (
    CASE
        WHEN duration ~ '^PT(\d+)H(\d+)M(\d+)S$' THEN
            (SUBSTRING(duration FROM 'PT(\d+)H')::INTEGER * 3600) +
            (SUBSTRING(duration FROM '(\d+)M')::INTEGER * 60) +
            (SUBSTRING(duration FROM '(\d+)S$')::INTEGER)
        WHEN duration ~ '^PT(\d+)M(\d+)S$' THEN
            (SUBSTRING(duration FROM 'PT(\d+)M')::INTEGER * 60) +
            (SUBSTRING(duration FROM '(\d+)S$')::INTEGER)
        WHEN duration ~ '^PT(\d+)S$' THEN
            SUBSTRING(duration FROM 'PT(\d+)S$')::INTEGER
        ELSE NULL
    END
)
WHERE duration_sec IS NULL AND duration IS NOT NULL;

-- Clasificar format basado en duration_sec
UPDATE public.video_trending
SET format = CASE
    WHEN duration_sec <= 60 THEN 'short'
    WHEN duration_sec >= 180 THEN 'long'
    ELSE 'medium'
END
WHERE format IS NULL AND duration_sec IS NOT NULL;

-- ============================================================================
-- 4. Comentarios para documentación
-- ============================================================================

COMMENT ON COLUMN public.video_trending.channel_id IS
'ID del canal que publicó el video (para análisis de competencia)';

COMMENT ON COLUMN public.video_trending.duration_sec IS
'Duración del video en segundos (más fácil de consultar que duration TEXT)';

COMMENT ON COLUMN public.video_trending.format IS
'Formato del video: short (≤60s), long (≥180s), medium (61-179s)';

COMMENT ON COLUMN public.video_trending.similarity IS
'Score de similitud con el perfil del canal (0.0-1.0)';

COMMENT ON COLUMN public.video_trending.topic_key IS
'Clave de categorización de contenido para diversidad de temas';

-- ============================================================================
-- 5. Verificación de la migración
-- ============================================================================

-- Mostrar estructura actualizada de la tabla
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'video_trending'
ORDER BY ordinal_position;

-- Estadísticas de datos actualizados
SELECT
    COUNT(*) AS total_videos,
    COUNT(duration_sec) AS con_duration_sec,
    COUNT(format) AS con_format,
    COUNT(DISTINCT format) AS formatos_unicos,
    COUNT(channel_id) AS con_channel_id
FROM public.video_trending;

COMMIT;

-- ============================================================================
-- 6. Verificar que script_execution_log existe (para watermarks)
-- ============================================================================

-- Si no existe, ejecutar CREATE_TABLE_SCRIPT_EXECUTION_LOG.sql primero

-- Verificar tabla
SELECT COUNT(*) AS existe
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'script_execution_log';

-- ============================================================================
-- INSTRUCCIONES DE EJECUCIÓN
-- ============================================================================

-- 1. Copiar este archivo a Supabase SQL Editor
-- 2. Ejecutar el script completo
-- 3. Verificar que las 5 columnas nuevas aparecen en video_trending
-- 4. Verificar que los índices se crearon correctamente
-- 5. (Opcional) Si script_execution_log no existe, ejecutar:
--    CREATE_TABLE_SCRIPT_EXECUTION_LOG.sql

-- ============================================================================
-- ROLLBACK (si es necesario)
-- ============================================================================

-- Para revertir los cambios:
/*
BEGIN;

DROP INDEX IF EXISTS idx_video_trending_channel_id;
DROP INDEX IF EXISTS idx_video_trending_format;
DROP INDEX IF EXISTS idx_video_trending_duration_sec;
DROP INDEX IF EXISTS idx_video_trending_published_at;
DROP INDEX IF EXISTS idx_video_trending_topic_key;

ALTER TABLE public.video_trending DROP COLUMN IF EXISTS channel_id;
ALTER TABLE public.video_trending DROP COLUMN IF EXISTS duration_sec;
ALTER TABLE public.video_trending DROP COLUMN IF EXISTS format;
ALTER TABLE public.video_trending DROP COLUMN IF EXISTS similarity;
ALTER TABLE public.video_trending DROP COLUMN IF EXISTS topic_key;

COMMIT;
*/
