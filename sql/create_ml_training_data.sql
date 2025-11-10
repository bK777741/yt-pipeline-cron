-- ============================================================================
-- TABLA: ml_training_data
-- Propósito: Almacenar snapshot de videos para entrenamiento ML
-- Nunca se purga - Histórico permanente para el modelo
-- ============================================================================

CREATE TABLE IF NOT EXISTS ml_training_data (
    id SERIAL PRIMARY KEY,

    -- Identificación
    video_id TEXT NOT NULL,
    es_tuyo BOOLEAN DEFAULT FALSE,  -- TRUE = tu canal, FALSE = competencia

    -- Metadata (para features)
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    duration INTEGER,  -- segundos
    category_id INTEGER,
    channel_id TEXT,
    channel_subscribers INTEGER DEFAULT 0,

    -- Thumbnail features (JSON compacto)
    thumbnail_url TEXT,
    thumbnail_text TEXT,
    thumbnail_has_text BOOLEAN DEFAULT FALSE,

    -- Métricas finales (targets)
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,

    -- Métricas calculadas
    vph DECIMAL(10,2),  -- Views por hora
    ctr DECIMAL(5,2),   -- Click-through rate (si disponible)
    average_view_percentage DECIMAL(5,2),  -- Retención promedio

    -- Score de nicho
    nicho_score INTEGER DEFAULT 0,

    -- Metadata de snapshot
    snapshot_date TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraint: Un video solo se guarda una vez
    UNIQUE(video_id)
);

-- Índices para consultas rápidas
CREATE INDEX IF NOT EXISTS idx_ml_training_published ON ml_training_data(published_at);
CREATE INDEX IF NOT EXISTS idx_ml_training_es_tuyo ON ml_training_data(es_tuyo);
CREATE INDEX IF NOT EXISTS idx_ml_training_snapshot ON ml_training_data(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_ml_training_vph ON ml_training_data(vph);

-- Comentarios
COMMENT ON TABLE ml_training_data IS 'Histórico de videos para entrenamiento ML - NUNCA se purga';
COMMENT ON COLUMN ml_training_data.es_tuyo IS 'TRUE si es video del canal principal, FALSE si es competencia';
COMMENT ON COLUMN ml_training_data.vph IS 'Views por hora - Métrica principal de viralidad';
COMMENT ON COLUMN ml_training_data.nicho_score IS 'Score 0-100 calculado con config_nicho.json';

-- ============================================================================
-- TABLA: video_clasificacion
-- Propósito: Clasificar videos en ÉXITO/PROMEDIO/FRACASO
-- ============================================================================

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

CREATE INDEX IF NOT EXISTS idx_video_clasificacion_clase ON video_clasificacion(clasificacion);
CREATE INDEX IF NOT EXISTS idx_video_clasificacion_score ON video_clasificacion(score);

-- ============================================================================
-- TABLA: modelo_ml_metadata
-- Propósito: Guardar metadata de cada modelo entrenado
-- ============================================================================

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

CREATE INDEX IF NOT EXISTS idx_modelo_ml_trained ON modelo_ml_metadata(trained_at);

COMMENT ON TABLE modelo_ml_metadata IS 'Historial de modelos ML entrenados';

-- ============================================================================
-- TABLA: anti_patrones
-- Propósito: Guardar anti-patrones detectados semanalmente
-- ============================================================================

CREATE TABLE IF NOT EXISTS anti_patrones (
    id SERIAL PRIMARY KEY,
    patron TEXT NOT NULL,
    descripcion TEXT,
    frecuencia INTEGER DEFAULT 1,  -- Cuántas veces se ha detectado
    confianza TEXT CHECK (confianza IN ('BAJA', 'MEDIA', 'ALTA')),
    impacto_vph_promedio DECIMAL(10,2),  -- VPH promedio cuando ocurre este anti-patrón
    ejemplos_video_ids TEXT[],
    detectado_at TIMESTAMPTZ DEFAULT NOW(),
    actualizado_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anti_patrones_confianza ON anti_patrones(confianza);
CREATE INDEX IF NOT EXISTS idx_anti_patrones_actualizado ON anti_patrones(actualizado_at);

COMMENT ON TABLE anti_patrones IS 'Anti-patrones detectados por análisis semanal';

-- ============================================================================
-- Vista útil: Resumen de dataset ML
-- ============================================================================

CREATE OR REPLACE VIEW ml_dataset_summary AS
SELECT
    COUNT(*) as total_videos,
    COUNT(CASE WHEN es_tuyo THEN 1 END) as videos_propios,
    COUNT(CASE WHEN NOT es_tuyo THEN 1 END) as videos_competencia,
    AVG(vph) as vph_promedio,
    MIN(published_at) as fecha_mas_antigua,
    MAX(published_at) as fecha_mas_reciente,
    AVG(nicho_score) as nicho_score_promedio
FROM ml_training_data;

COMMENT ON VIEW ml_dataset_summary IS 'Resumen rápido del dataset para ML';

-- ============================================================================
-- Fin del script
-- ============================================================================
