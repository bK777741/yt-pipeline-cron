-- ================================================================================
-- MIGRACIÓN: SISTEMA DE DETECCIÓN DE HIDDEN GEMS (MINAS DE ORO)
-- Fecha: 2025-11-04
-- Propósito: Detectar canales PEQUEÑOS con videos EXPLOSIVOS
-- ================================================================================

-- ================================================================================
-- TABLA: hidden_gems
-- Propósito: Almacenar "minas de oro" - canales pequeños con explosión viral
-- ================================================================================

CREATE TABLE IF NOT EXISTS public.hidden_gems (
    id SERIAL PRIMARY KEY,
    video_id TEXT NOT NULL UNIQUE,

    -- INFORMACIÓN DEL VIDEO
    title TEXT NOT NULL,
    view_count BIGINT NOT NULL,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    duration_seconds INTEGER,
    published_at TIMESTAMP,

    -- INFORMACIÓN DEL CANAL
    channel_id TEXT NOT NULL,
    channel_title TEXT,
    channel_subscribers INTEGER NOT NULL,
    channel_size TEXT CHECK (channel_size IN ('nano', 'micro', 'small', 'medium', 'large', 'huge')),

    -- MÉTRICAS DE EXPLOSIÓN (LO MÁS IMPORTANTE)
    explosion_ratio NUMERIC(10,2) NOT NULL,  -- views / (subscribers * 0.05)
    nicho_score INTEGER DEFAULT 0,            -- Relevancia al nicho (0-100)

    -- METADATA
    tags TEXT[],
    discovered_at TIMESTAMP DEFAULT NOW(),

    -- ÍNDICES PARA ANÁLISIS
    CONSTRAINT positive_explosion CHECK (explosion_ratio > 0),
    CONSTRAINT positive_subscribers CHECK (channel_subscribers > 0)
);

-- ================================================================================
-- ÍNDICES PARA BÚSQUEDAS RÁPIDAS
-- ================================================================================

-- Índice principal: ordenar por explosion ratio (los más explosivos primero)
CREATE INDEX IF NOT EXISTS idx_hidden_gems_explosion_ratio
    ON public.hidden_gems(explosion_ratio DESC);

-- Índice por tamaño de canal (para filtrar por nano/micro/small)
CREATE INDEX IF NOT EXISTS idx_hidden_gems_channel_size
    ON public.hidden_gems(channel_size);

-- Índice por canal (para analizar todos los videos exitosos de un canal)
CREATE INDEX IF NOT EXISTS idx_hidden_gems_channel_id
    ON public.hidden_gems(channel_id);

-- Índice por fecha de descubrimiento (para ver últimos descubrimientos)
CREATE INDEX IF NOT EXISTS idx_hidden_gems_discovered
    ON public.hidden_gems(discovered_at DESC);

-- Índice por views (para ordenar por popularidad absoluta)
CREATE INDEX IF NOT EXISTS idx_hidden_gems_views
    ON public.hidden_gems(view_count DESC);

-- Índice por nicho score (para filtrar solo relevantes)
CREATE INDEX IF NOT EXISTS idx_hidden_gems_nicho
    ON public.hidden_gems(nicho_score DESC);

-- Índice GIN para búsqueda por tags
CREATE INDEX IF NOT EXISTS idx_hidden_gems_tags
    ON public.hidden_gems USING GIN (tags);

-- ================================================================================
-- COMENTARIOS PARA DOCUMENTACIÓN
-- ================================================================================

COMMENT ON TABLE public.hidden_gems IS 'Minas de oro: canales pequeños (<50k subs) con videos explosivos (ratio >100x)';

COMMENT ON COLUMN public.hidden_gems.explosion_ratio IS 'Ratio de explosión: views / (subscribers * 0.05). Ratio >100 = explosivo, >500 = jackpot';
COMMENT ON COLUMN public.hidden_gems.channel_size IS 'nano <1k, micro 1k-10k, small 10k-50k, medium 50k-100k, large 100k-500k, huge >500k';
COMMENT ON COLUMN public.hidden_gems.nicho_score IS 'Relevancia al nicho (0-100). Score >50 = muy relevante';

-- ================================================================================
-- VISTAS ÚTILES PARA ANÁLISIS
-- ================================================================================

-- Vista: Top 50 hidden gems por explosion ratio
CREATE OR REPLACE VIEW v_top_hidden_gems AS
SELECT
    hg.video_id,
    hg.title,
    hg.channel_title,
    hg.channel_subscribers,
    hg.channel_size,
    hg.view_count,
    hg.explosion_ratio,
    hg.nicho_score,
    hg.published_at,
    hg.discovered_at,
    -- Calcular días desde publicación
    EXTRACT(DAY FROM (NOW() - hg.published_at)) AS days_since_published,
    -- Calcular engagement rate
    CASE
        WHEN hg.view_count > 0
        THEN ROUND(((hg.like_count + hg.comment_count)::NUMERIC / hg.view_count::NUMERIC) * 100, 2)
        ELSE 0
    END AS engagement_rate
FROM hidden_gems hg
WHERE hg.nicho_score >= 30  -- Solo relevantes al nicho
ORDER BY hg.explosion_ratio DESC
LIMIT 50;

COMMENT ON VIEW v_top_hidden_gems IS 'Top 50 minas de oro ordenadas por explosion ratio';

-- Vista: Canales nano/micro con múltiples hits
CREATE OR REPLACE VIEW v_hidden_gem_channels AS
SELECT
    hg.channel_id,
    hg.channel_title,
    hg.channel_size,
    hg.channel_subscribers,
    COUNT(*) AS total_hits,
    AVG(hg.explosion_ratio) AS avg_explosion_ratio,
    MAX(hg.explosion_ratio) AS max_explosion_ratio,
    SUM(hg.view_count) AS total_views,
    ARRAY_AGG(hg.video_id ORDER BY hg.explosion_ratio DESC) AS video_ids
FROM hidden_gems hg
WHERE hg.channel_size IN ('nano', 'micro', 'small')  -- Solo canales realmente pequeños
GROUP BY hg.channel_id, hg.channel_title, hg.channel_size, hg.channel_subscribers
HAVING COUNT(*) >= 2  -- Canales con al menos 2 videos exitosos
ORDER BY AVG(hg.explosion_ratio) DESC;

COMMENT ON VIEW v_hidden_gem_channels IS 'Canales pequeños con múltiples videos explosivos (patrón replicable)';

-- ================================================================================
-- FUNCIÓN ÚTIL: Calcular explosion ratio
-- ================================================================================

CREATE OR REPLACE FUNCTION calculate_explosion_ratio(
    p_views BIGINT,
    p_subscribers INTEGER
) RETURNS NUMERIC AS $$
DECLARE
    avg_view_rate NUMERIC := 0.05;  -- 5% de suscriptores ven cada video
    expected_views NUMERIC;
BEGIN
    IF p_subscribers = 0 THEN
        RETURN 0;
    END IF;

    expected_views := p_subscribers * avg_view_rate;

    IF expected_views = 0 THEN
        RETURN 0;
    END IF;

    RETURN ROUND((p_views::NUMERIC / expected_views), 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION calculate_explosion_ratio IS 'Calcula explosion ratio: views / (subs * 0.05). Útil para análisis manual';

-- ================================================================================
-- EXPANDIR video_trending PARA GUARDAR CHANNEL_SUBSCRIBERS
-- ================================================================================

-- Agregar columna channel_subscribers a video_trending (si no existe)
ALTER TABLE public.video_trending
ADD COLUMN IF NOT EXISTS channel_subscribers INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_video_trending_channel_subs
    ON public.video_trending(channel_subscribers);

COMMENT ON COLUMN public.video_trending.channel_subscribers IS 'Suscriptores del canal (para detectar canales pequeños con explosión)';

-- ================================================================================
-- QUERIES DE EJEMPLO (DOCUMENTACIÓN)
-- ================================================================================

-- Ejemplo 1: Encontrar las 10 mayores minas de oro recientes
-- SELECT * FROM v_top_hidden_gems LIMIT 10;

-- Ejemplo 2: Canales nano (<1k subs) con videos >100k views
-- SELECT * FROM hidden_gems
-- WHERE channel_size = 'nano' AND view_count > 100000
-- ORDER BY explosion_ratio DESC;

-- Ejemplo 3: Calcular explosion ratio manualmente
-- SELECT
--     video_id,
--     title,
--     view_count,
--     channel_subscribers,
--     calculate_explosion_ratio(view_count, channel_subscribers) AS explosion_ratio
-- FROM hidden_gems
-- LIMIT 10;

-- Ejemplo 4: Encontrar canales con múltiples hits
-- SELECT * FROM v_hidden_gem_channels LIMIT 10;

-- Ejemplo 5: Análisis de tags más comunes en hidden gems
-- SELECT
--     unnest(tags) AS tag,
--     COUNT(*) AS frequency
-- FROM hidden_gems
-- WHERE nicho_score >= 50
-- GROUP BY tag
-- ORDER BY frequency DESC
-- LIMIT 20;

-- ================================================================================
-- VERIFICACIÓN FINAL
-- ================================================================================

-- Mostrar resumen de la tabla creada
SELECT
    'hidden_gems' AS table_name,
    pg_size_pretty(pg_total_relation_size('public.hidden_gems')) AS size,
    (SELECT COUNT(*) FROM hidden_gems) AS row_count;

-- ================================================================================
-- FIN DE MIGRACIÓN
-- ================================================================================
-- PRÓXIMOS PASOS:
-- 1. Ejecutar esta migración en Supabase SQL Editor
-- 2. Ejecutar detect_hidden_gems.py para poblar la tabla
-- 3. Analizar v_top_hidden_gems para ver las mejores oportunidades
-- 4. Estudiar v_hidden_gem_channels para identificar patrones replicables
-- ================================================================================
