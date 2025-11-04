-- ================================================================================
-- MIGRACIÓN COMPLETA: SISTEMA DE INTELIGENCIA YOUTUBE
-- Fecha: 2025-11-04
-- Versión: 3.0.0
-- Propósito: Conocer YouTube al milímetro para dejar de improvisar
-- ================================================================================

-- ================================================================================
-- PARTE 1: EXPANDIR video_analytics (CONSOLIDACIÓN COMPLETA)
-- ================================================================================

-- Agregar columnas faltantes para analytics completos
ALTER TABLE public.video_analytics
ADD COLUMN IF NOT EXISTS subscribers_lost INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS shares INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS card_impressions BIGINT DEFAULT 0,
ADD COLUMN IF NOT EXISTS card_clicks INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS card_click_rate NUMERIC(5,3) DEFAULT 0,
ADD COLUMN IF NOT EXISTS traffic_sources JSONB;

-- Comentarios para documentación
COMMENT ON COLUMN public.video_analytics.subscribers_lost IS 'Suscriptores perdidos por este video';
COMMENT ON COLUMN public.video_analytics.shares IS 'Veces que se compartió el video';
COMMENT ON COLUMN public.video_analytics.card_impressions IS 'Impresiones de cards en el video';
COMMENT ON COLUMN public.video_analytics.card_clicks IS 'Clicks en cards del video';
COMMENT ON COLUMN public.video_analytics.card_click_rate IS 'CTR de cards (porcentaje)';
COMMENT ON COLUMN public.video_analytics.traffic_sources IS 'Fuentes de tráfico en formato JSON: [{source_type, views, watch_time_minutes}]';

-- ================================================================================
-- PARTE 2: NUEVA TABLA - video_metadata_extended
-- Propósito: Capturar TAGS, HASHTAGS y metadata completa (TU vs COMPETENCIA)
-- ================================================================================

CREATE TABLE IF NOT EXISTS public.video_metadata_extended (
    video_id TEXT PRIMARY KEY,

    -- TAGS Y HASHTAGS (CRÍTICO PARA SEO)
    tags TEXT[],
    hashtags TEXT[],
    tag_count INTEGER DEFAULT 0,
    hashtag_count INTEGER DEFAULT 0,

    -- DESCRIPCIÓN ESTRUCTURADA
    description_length INTEGER,
    has_timestamps BOOLEAN DEFAULT FALSE,
    timestamps JSONB,  -- [{"time": "0:00", "label": "Intro"}, ...]
    external_links TEXT[],
    external_link_count INTEGER DEFAULT 0,

    -- IDIOMAS Y LOCALIZACIÓN
    default_language TEXT,
    audio_language TEXT,
    available_captions TEXT[],  -- ["es", "en", "pt"]
    caption_count INTEGER DEFAULT 0,

    -- METADATA ADICIONAL
    category_id INTEGER,
    category_name TEXT,  -- "Science & Technology", "Education", etc
    is_made_for_kids BOOLEAN DEFAULT FALSE,
    has_custom_thumbnail BOOLEAN DEFAULT FALSE,

    -- OWNERSHIP (para diferenciar propios vs competencia)
    is_own_video BOOLEAN DEFAULT FALSE,  -- TRUE si es tuyo, FALSE si es competencia

    -- TRACKING
    captured_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_video_metadata_tags
    ON public.video_metadata_extended USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_video_metadata_hashtags
    ON public.video_metadata_extended USING GIN (hashtags);

CREATE INDEX IF NOT EXISTS idx_video_metadata_category
    ON public.video_metadata_extended(category_id);

CREATE INDEX IF NOT EXISTS idx_video_metadata_ownership
    ON public.video_metadata_extended(is_own_video);

COMMENT ON TABLE public.video_metadata_extended IS 'Metadata extendida de videos (propios y competencia): tags, hashtags, timestamps, idiomas';

-- ================================================================================
-- PARTE 3: NUEVA TABLA - ab_test_experiments
-- Propósito: Tracking de experimentos A/B de títulos y thumbnails
-- ================================================================================

CREATE TABLE IF NOT EXISTS public.ab_test_experiments (
    experiment_id SERIAL PRIMARY KEY,
    video_id TEXT NOT NULL,
    experiment_type TEXT NOT NULL CHECK (experiment_type IN ('title', 'thumbnail', 'both')),

    -- VARIANTES (hasta 3)
    variant_1_content TEXT,
    variant_2_content TEXT,
    variant_3_content TEXT,

    -- PATRONES DETECTADOS
    variant_1_pattern TEXT,  -- "number_pattern", "question_pattern", etc
    variant_2_pattern TEXT,
    variant_3_pattern TEXT,

    -- MÉTRICAS POR VARIANTE
    variant_1_impressions BIGINT DEFAULT 0,
    variant_1_clicks BIGINT DEFAULT 0,
    variant_1_ctr NUMERIC(5,3) DEFAULT 0,

    variant_2_impressions BIGINT DEFAULT 0,
    variant_2_clicks BIGINT DEFAULT 0,
    variant_2_ctr NUMERIC(5,3) DEFAULT 0,

    variant_3_impressions BIGINT DEFAULT 0,
    variant_3_clicks BIGINT DEFAULT 0,
    variant_3_ctr NUMERIC(5,3) DEFAULT 0,

    -- RESULTADO DEL TEST
    winning_variant INTEGER CHECK (winning_variant IN (1, 2, 3)),
    winning_ctr NUMERIC(5,3),
    confidence_level NUMERIC(5,2),  -- 95%, 90%, etc

    -- STATUS Y TRACKING
    status TEXT DEFAULT 'running' CHECK (status IN ('draft', 'running', 'completed', 'inconclusive', 'cancelled')),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    test_duration_hours INTEGER,
    sample_size INTEGER,

    -- METADATA
    created_at TIMESTAMP DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_ab_test_video
    ON public.ab_test_experiments(video_id);

CREATE INDEX IF NOT EXISTS idx_ab_test_status
    ON public.ab_test_experiments(status);

CREATE INDEX IF NOT EXISTS idx_ab_test_type
    ON public.ab_test_experiments(experiment_type);

COMMENT ON TABLE public.ab_test_experiments IS 'Experimentos A/B de títulos y thumbnails (feature de YouTube 2024+)';

-- ================================================================================
-- PARTE 4: NUEVA TABLA - ab_test_learnings
-- Propósito: Aprendizaje automático de patrones ganadores
-- ================================================================================

CREATE TABLE IF NOT EXISTS public.ab_test_learnings (
    learning_id SERIAL PRIMARY KEY,

    -- PATRÓN IDENTIFICADO
    pattern_type TEXT NOT NULL,  -- "title_with_numbers", "thumbnail_with_face", etc
    pattern_category TEXT,  -- "title" o "thumbnail"
    pattern_description TEXT,

    -- PERFORMANCE AGREGADO
    total_tests INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate NUMERIC(5,2) DEFAULT 0,  -- Porcentaje

    avg_ctr NUMERIC(5,3) DEFAULT 0,
    avg_ctr_improvement NUMERIC(5,2) DEFAULT 0,  -- % mejora vs baseline

    -- EJEMPLOS
    best_examples JSONB,  -- [{"content": "7 trucos...", "ctr": 12.5, "video_id": "abc"}]
    worst_examples JSONB,

    -- RECOMENDACIÓN
    recommendation TEXT,  -- "Usa siempre números en títulos para CTR +40%"
    confidence_level TEXT CHECK (confidence_level IN ('high', 'medium', 'low')),

    -- TRACKING
    last_updated TIMESTAMP DEFAULT NOW(),
    sample_size INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ab_learnings_pattern
    ON public.ab_test_learnings(pattern_type);

CREATE INDEX IF NOT EXISTS idx_ab_learnings_winrate
    ON public.ab_test_learnings(win_rate DESC);

COMMENT ON TABLE public.ab_test_learnings IS 'Patrones aprendidos de tests A/B - Qué funciona y qué no';

-- ================================================================================
-- PARTE 5: NUEVA TABLA - performance_patterns
-- Propósito: Análisis de patrones de éxito/fracaso en tus videos
-- ================================================================================

CREATE TABLE IF NOT EXISTS public.performance_patterns (
    pattern_id SERIAL PRIMARY KEY,
    video_id TEXT NOT NULL,

    -- TÍTULO
    title_length INTEGER,
    title_pattern TEXT,
    has_numbers BOOLEAN DEFAULT FALSE,
    has_year BOOLEAN DEFAULT FALSE,
    has_free_word BOOLEAN DEFAULT FALSE,
    has_emojis BOOLEAN DEFAULT FALSE,
    power_words TEXT[],  -- ["gratis", "secreto", "oculto"]

    -- THUMBNAIL
    thumbnail_has_face BOOLEAN DEFAULT FALSE,
    thumbnail_has_text BOOLEAN DEFAULT FALSE,
    thumbnail_text_size TEXT,  -- "large", "medium", "small"
    thumbnail_dominant_colors TEXT[],
    thumbnail_contrast_level TEXT,  -- "high", "medium", "low"

    -- DESCRIPCIÓN
    description_length INTEGER,
    keyword_in_first_150 BOOLEAN DEFAULT FALSE,
    has_cta BOOLEAN DEFAULT FALSE,
    has_timestamps BOOLEAN DEFAULT FALSE,

    -- TAGS
    tag_count INTEGER DEFAULT 0,
    main_tags TEXT[],

    -- PERFORMANCE (desde video_analytics)
    ctr_percentage NUMERIC(5,3),
    avg_view_percentage NUMERIC(5,2),
    engagement_rate NUMERIC(5,3),  -- (likes+comments+shares)/views

    -- CLASIFICACIÓN
    performance_tier TEXT CHECK (performance_tier IN ('top10', 'top25', 'average', 'bottom25', 'bottom10')),

    -- TRACKING
    analyzed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_performance_video
    ON public.performance_patterns(video_id);

CREATE INDEX IF NOT EXISTS idx_performance_tier
    ON public.performance_patterns(performance_tier);

CREATE INDEX IF NOT EXISTS idx_performance_ctr
    ON public.performance_patterns(ctr_percentage DESC);

COMMENT ON TABLE public.performance_patterns IS 'Patrones de performance: qué elementos correlacionan con éxito/fracaso';

-- ================================================================================
-- PARTE 6: NUEVA TABLA - smart_recommendations
-- Propósito: Recomendaciones accionables para próximos videos
-- ================================================================================

CREATE TABLE IF NOT EXISTS public.smart_recommendations (
    recommendation_id SERIAL PRIMARY KEY,
    generated_date DATE DEFAULT CURRENT_DATE,

    -- TÍTULO RECOMENDADO
    recommended_title TEXT,
    recommended_title_pattern TEXT,
    title_reasoning TEXT,  -- "Basado en patrón 'number_list' con 75% win rate"

    -- DESCRIPCIÓN RECOMENDADA
    recommended_description TEXT,
    recommended_hashtags TEXT[],
    description_reasoning TEXT,

    -- TAGS RECOMENDADOS
    recommended_tags TEXT[],
    tags_reasoning TEXT,  -- "Estos tags generan CTR +35% en tu nicho"

    -- ESTRUCTURA DE VIDEO
    recommended_intro_seconds INTEGER,
    recommended_total_duration INTEGER,
    recommended_cta_moments INTEGER[],  -- [120, 290] = minuto 2:00 y 4:50
    structure_reasoning TEXT,

    -- THUMBNAIL RECOMENDADO
    recommended_thumbnail_elements JSONB,  -- {has_face: true, text: "GRATIS", colors: ["yellow", "black"]}
    thumbnail_reasoning TEXT,

    -- TIMING Y TEMA
    recommended_publish_day TEXT,
    recommended_publish_time TIME,
    recommended_topic TEXT,
    timing_reasoning TEXT,

    -- PERFORMANCE ESPERADO
    estimated_ctr NUMERIC(5,3),
    estimated_avg_view_percentage NUMERIC(5,2),
    estimated_engagement_rate NUMERIC(5,3),
    estimated_cpm NUMERIC(6,2),
    estimated_views_30days INTEGER,
    estimated_revenue_30days NUMERIC(8,2),

    -- CONFIANZA
    confidence_score NUMERIC(5,2),  -- 0-100
    based_on_sample_size INTEGER,

    -- TRACKING
    generated_at TIMESTAMP DEFAULT NOW(),
    applied_to_video_id TEXT,  -- Si se usó la recomendación
    actual_performance JSONB  -- Comparación recomendado vs real
);

CREATE INDEX IF NOT EXISTS idx_recommendations_date
    ON public.smart_recommendations(generated_date DESC);

CREATE INDEX IF NOT EXISTS idx_recommendations_applied
    ON public.smart_recommendations(applied_to_video_id);

COMMENT ON TABLE public.smart_recommendations IS 'Recomendaciones semanales generadas por IA basadas en todos los datos históricos';

-- ================================================================================
-- PARTE 7: EXPANDIR video_trending (agregar tags y hashtags de competencia)
-- ================================================================================

ALTER TABLE public.video_trending
ADD COLUMN IF NOT EXISTS tags TEXT[],
ADD COLUMN IF NOT EXISTS hashtags TEXT[],
ADD COLUMN IF NOT EXISTS default_language TEXT,
ADD COLUMN IF NOT EXISTS has_captions BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS caption_languages TEXT[];

-- Índices para búsquedas por tags de competencia
CREATE INDEX IF NOT EXISTS idx_video_trending_tags
    ON public.video_trending USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_video_trending_hashtags
    ON public.video_trending USING GIN (hashtags);

COMMENT ON COLUMN public.video_trending.tags IS 'Tags usados por competencia (ORO para aprender SEO)';
COMMENT ON COLUMN public.video_trending.hashtags IS 'Hashtags usados por competencia';

-- ================================================================================
-- PARTE 8: RENOMBRAR TABLA youtube_policies → youtube_updates
-- ================================================================================

-- Verificar si existe youtube_policies antes de renombrar
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'youtube_policies') THEN
        ALTER TABLE public.youtube_policies RENAME TO youtube_updates;
        COMMENT ON TABLE public.youtube_updates IS 'Políticas Y nuevas features de YouTube (A/B testing, algoritmo, etc)';
    END IF;
END $$;

-- ================================================================================
-- PARTE 9: FUNCIONES ÚTILES PARA ANÁLISIS
-- ================================================================================

-- Función para calcular engagement rate
CREATE OR REPLACE FUNCTION calculate_engagement_rate(
    p_likes INTEGER,
    p_comments INTEGER,
    p_shares INTEGER,
    p_views BIGINT
) RETURNS NUMERIC AS $$
BEGIN
    IF p_views = 0 THEN
        RETURN 0;
    END IF;
    RETURN ROUND(((p_likes + p_comments + p_shares)::NUMERIC / p_views::NUMERIC) * 100, 3);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Función para extraer hashtags de descripción
CREATE OR REPLACE FUNCTION extract_hashtags(p_text TEXT)
RETURNS TEXT[] AS $$
DECLARE
    hashtags TEXT[];
BEGIN
    SELECT array_agg(DISTINCT match[1])
    INTO hashtags
    FROM regexp_matches(p_text, '#([a-zA-Z0-9_áéíóúñ]+)', 'g') AS match;

    RETURN COALESCE(hashtags, ARRAY[]::TEXT[]);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ================================================================================
-- PARTE 10: VISTAS ÚTILES PARA ANÁLISIS RÁPIDO
-- ================================================================================

-- Vista: Top performers (tus videos top 10%)
CREATE OR REPLACE VIEW v_top_performers AS
SELECT
    v.video_id,
    v.title,
    va.average_view_percentage,
    va.subscribers_gained,
    va.playback_based_cpm,
    calculate_engagement_rate(va.likes, va.comments_count, va.shares, va.views) as engagement_rate,
    pp.title_pattern,
    pp.thumbnail_has_face,
    vme.tags,
    vme.hashtags
FROM videos v
JOIN video_analytics va ON v.video_id = va.video_id
LEFT JOIN performance_patterns pp ON v.video_id = pp.video_id
LEFT JOIN video_metadata_extended vme ON v.video_id = vme.video_id
WHERE va.average_view_percentage >= (
    SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY average_view_percentage)
    FROM video_analytics
)
ORDER BY va.average_view_percentage DESC;

COMMENT ON VIEW v_top_performers IS 'Tus videos top 10% (para aprender qué funciona)';

-- Vista: Competencia viral (videos trending con mejor performance)
CREATE OR REPLACE VIEW v_viral_competitors AS
SELECT
    vt.video_id,
    vt.title,
    vt.channel_title,
    vt.view_count,
    vt.vph,
    vt.engagement,
    vt.score,
    vt.tags,
    vt.hashtags,
    vt.published_at
FROM video_trending vt
WHERE vt.score >= 70
    AND vt.vph >= 100
ORDER BY vt.score DESC, vt.vph DESC
LIMIT 50;

COMMENT ON VIEW v_viral_competitors IS 'Competencia viral del nicho (para aprender y replicar)';

-- ================================================================================
-- VERIFICACIÓN FINAL
-- ================================================================================

-- Mostrar resumen de tablas creadas/modificadas
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN (
        'video_analytics',
        'video_metadata_extended',
        'ab_test_experiments',
        'ab_test_learnings',
        'performance_patterns',
        'smart_recommendations',
        'video_trending',
        'youtube_updates'
    )
ORDER BY tablename;

-- ================================================================================
-- FIN DE MIGRACIÓN
-- ================================================================================
-- RESULTADO ESPERADO:
-- ✅ 4 tablas nuevas creadas
-- ✅ 2 tablas existentes expandidas (video_analytics, video_trending)
-- ✅ 1 tabla renombrada (youtube_policies → youtube_updates)
-- ✅ 2 funciones útiles
-- ✅ 2 vistas para análisis rápido
--
-- PRÓXIMOS PASOS:
-- 1. Ejecutar esta migración en Supabase SQL Editor
-- 2. Ejecutar scripts consolidados (unified_analytics.py, etc)
-- 3. Empezar a capturar datos completos
-- ================================================================================
