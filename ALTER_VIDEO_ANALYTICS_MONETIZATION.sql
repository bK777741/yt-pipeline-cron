-- ============================================================================
-- MIGRACIÓN: Agregar columnas de monetización a video_analytics
-- Fecha: 2025-11-01
-- Propósito: Corregir fetch_monetization_metrics.py que usa nuevas métricas
-- ============================================================================

-- PROBLEMA:
-- El script fetch_monetization_metrics.py fue actualizado para usar métricas válidas
-- de YouTube Analytics API v2, pero la tabla video_analytics no tiene esas columnas.
--
-- MÉTRICAS ANTIGUAS (INVÁLIDAS):
-- - impressions, impressionCtr, averageCpm, estimatedRevenue, adImpressions, estimatedMonetizedPlaybacks
--
-- MÉTRICAS NUEVAS (VÁLIDAS):
-- - views, estimatedRevenue, monetizedPlaybacks, playbackBasedCpm, adImpressions

-- ============================================================================
-- PASO 1: Verificar columnas existentes
-- ============================================================================

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'video_analytics'
ORDER BY ordinal_position;

-- ============================================================================
-- PASO 2: Agregar nuevas columnas (si no existen)
-- ============================================================================

-- Columna: views (total de visualizaciones)
ALTER TABLE public.video_analytics
ADD COLUMN IF NOT EXISTS views BIGINT;

-- Columna: monetized_playbacks (reproducciones monetizadas)
ALTER TABLE public.video_analytics
ADD COLUMN IF NOT EXISTS monetized_playbacks BIGINT;

-- Columna: playback_based_cpm (CPM basado en reproducciones)
ALTER TABLE public.video_analytics
ADD COLUMN IF NOT EXISTS playback_based_cpm NUMERIC(10, 2);

-- Columna: estimated_revenue (ya debería existir, pero por si acaso)
ALTER TABLE public.video_analytics
ADD COLUMN IF NOT EXISTS estimated_revenue NUMERIC(10, 2);

-- Columna: ad_impressions (ya debería existir, pero por si acaso)
ALTER TABLE public.video_analytics
ADD COLUMN IF NOT EXISTS ad_impressions BIGINT;

-- ============================================================================
-- PASO 3: Agregar comentarios a las nuevas columnas
-- ============================================================================

COMMENT ON COLUMN public.video_analytics.views IS
'Total de visualizaciones del video (YouTube Analytics API v2)';

COMMENT ON COLUMN public.video_analytics.monetized_playbacks IS
'Número de reproducciones donde se mostró al menos un anuncio (YouTube Analytics API v2)';

COMMENT ON COLUMN public.video_analytics.playback_based_cpm IS
'CPM basado en reproducciones monetizadas en USD (YouTube Analytics API v2)';

COMMENT ON COLUMN public.video_analytics.estimated_revenue IS
'Ingresos estimados en USD (YouTube Analytics API v2)';

COMMENT ON COLUMN public.video_analytics.ad_impressions IS
'Total de impresiones de anuncios mostrados (YouTube Analytics API v2)';

-- ============================================================================
-- PASO 4: Verificar que las columnas se agregaron correctamente
-- ============================================================================

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'video_analytics'
  AND column_name IN ('views', 'monetized_playbacks', 'playback_based_cpm',
                      'estimated_revenue', 'ad_impressions')
ORDER BY column_name;

-- ============================================================================
-- PASO 5: (OPCIONAL) Eliminar columnas antiguas si ya no se usan
-- ============================================================================

-- ADVERTENCIA: Solo ejecutar si estás seguro de que estas columnas ya no se usan
-- y no contienen datos importantes.

-- ALTER TABLE public.video_analytics DROP COLUMN IF EXISTS impressions;
-- ALTER TABLE public.video_analytics DROP COLUMN IF EXISTS impression_ctr;
-- ALTER TABLE public.video_analytics DROP COLUMN IF EXISTS average_cpm;
-- ALTER TABLE public.video_analytics DROP COLUMN IF EXISTS estimated_monetized_playbacks;

-- ============================================================================
-- NOTAS FINALES
-- ============================================================================

-- Después de ejecutar esta migración:
-- 1. El script fetch_monetization_metrics.py funcionará correctamente
-- 2. Las métricas de monetización se guardarán en las columnas correctas
-- 3. Los datos antiguos (si existen) permanecerán intactos en sus columnas originales

-- Si quieres migrar datos antiguos a las nuevas columnas, ejecuta:
-- UPDATE video_analytics
-- SET monetized_playbacks = estimated_monetized_playbacks
-- WHERE monetized_playbacks IS NULL
--   AND estimated_monetized_playbacks IS NOT NULL;
