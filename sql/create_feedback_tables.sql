-- ============================================================================
-- SISTEMA DE FEEDBACK LOOP - APRENDIZAJE CONTINUO
-- ============================================================================
--
-- OBJETIVO: Permitir que los modelos aprendan de las modificaciones humanas
--
-- FLUJO:
-- 1. Modelo sugiere algo → guarda en ml_suggestions
-- 2. Usuario modifica (o acepta) → marca en ml_suggestions
-- 3. Video se publica → métricas van a ml_feedback
-- 4. Modelo re-entrena aprendiendo de las modificaciones exitosas
-- ============================================================================

-- TABLA 1: Sugerencias del modelo
-- ============================================================================
CREATE TABLE IF NOT EXISTS ml_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identificación
  video_id TEXT,  -- NULL si aún no se publicó
  suggestion_type TEXT NOT NULL,  -- 'title', 'script', 'thumbnail', 'tags'

  -- Contenido
  original_suggestion TEXT NOT NULL,  -- Lo que el modelo sugirió
  final_version TEXT,  -- Lo que TÚ publicaste (puede ser igual o modificado)

  -- Estado de modificación
  was_modified BOOLEAN DEFAULT FALSE,  -- ¿Modificaste la sugerencia?
  modification_type TEXT,  -- 'accepted', 'minor_edit', 'major_rewrite', 'rejected'

  -- Análisis de cambios
  changes_summary JSONB,  -- Qué cambió exactamente
  -- Ejemplo: {"added_words": ["OCULTO"], "removed_words": ["SECRETO"], "length_change": +5}

  -- Metadata del modelo
  model_version TEXT NOT NULL,  -- v2.0, v2.1, etc.
  model_confidence FLOAT,  -- Confianza del modelo (0-1)
  predicted_vph FLOAT,  -- VPH predicho por el modelo

  -- Timestamps
  suggested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  published_at TIMESTAMP WITH TIME ZONE,

  -- Índices para búsqueda rápida
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para búsqueda eficiente
CREATE INDEX IF NOT EXISTS idx_ml_suggestions_video_id ON ml_suggestions(video_id);
CREATE INDEX IF NOT EXISTS idx_ml_suggestions_type ON ml_suggestions(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_ml_suggestions_modified ON ml_suggestions(was_modified);
CREATE INDEX IF NOT EXISTS idx_ml_suggestions_suggested_at ON ml_suggestions(suggested_at DESC);

-- TABLA 2: Feedback de resultados reales
-- ============================================================================
CREATE TABLE IF NOT EXISTS ml_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Referencia a la sugerencia
  suggestion_id UUID NOT NULL REFERENCES ml_suggestions(id),
  video_id TEXT NOT NULL,

  -- Métricas reales (después de publicar)
  views_24h INT,
  views_7d INT,
  views_30d INT,

  likes INT,
  comments INT,
  shares INT,

  ctr_percent FLOAT,  -- Click-through rate
  avg_view_duration_seconds INT,
  retention_percent FLOAT,

  vph_24h FLOAT,  -- Views per hour (primeras 24h)
  vph_7d FLOAT,   -- VPH promedio 7 días

  -- Score de performance
  engagement_score FLOAT,  -- Calculado: (likes + comments*2 + shares*3) / views
  performance_score FLOAT,  -- Score global de performance

  -- Comparación con benchmark
  vs_channel_average_percent FLOAT,  -- +30% mejor que tu promedio
  vs_predicted_vph_percent FLOAT,    -- +50% mejor que lo predicho

  -- Clasificación de resultado
  result_quality TEXT,  -- 'excellent', 'good', 'average', 'poor'

  -- Timestamps
  measured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ml_feedback_suggestion_id ON ml_feedback(suggestion_id);
CREATE INDEX IF NOT EXISTS idx_ml_feedback_video_id ON ml_feedback(video_id);
CREATE INDEX IF NOT EXISTS idx_ml_feedback_quality ON ml_feedback(result_quality);

-- TABLA 3: Versiones y métricas de modelos
-- ============================================================================
CREATE TABLE IF NOT EXISTS ml_model_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identificación
  model_name TEXT NOT NULL,  -- 'predictor', 'gui_evaluator'
  version TEXT NOT NULL,  -- v2.0, v2.1, v3.0

  -- Metadata del entrenamiento
  trained_at TIMESTAMP WITH TIME ZONE NOT NULL,
  dataset_size INT NOT NULL,  -- Número de ejemplos usados
  training_duration_seconds INT,

  -- Features del modelo
  features JSONB,  -- Lista de features usadas
  hyperparameters JSONB,  -- Configuración del modelo

  -- Métricas de rendimiento
  metrics JSONB NOT NULL,
  -- Ejemplo: {"mae": 45.2, "r2": 0.78, "accuracy": 0.82}

  -- Feedback learning stats
  human_modifications_learned INT DEFAULT 0,  -- Cuántas modificaciones humanas incorporó
  acceptance_rate FLOAT,  -- % de sugerencias aceptadas sin modificar
  improvement_rate FLOAT,  -- % de mejora vs versión anterior

  -- Estado
  is_active BOOLEAN DEFAULT TRUE,  -- ¿Es la versión activa?
  replaced_by TEXT,  -- Versión que lo reemplazó

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ml_model_versions_name ON ml_model_versions(model_name);
CREATE INDEX IF NOT EXISTS idx_ml_model_versions_version ON ml_model_versions(version);
CREATE INDEX IF NOT EXISTS idx_ml_model_versions_active ON ml_model_versions(is_active);
CREATE INDEX IF NOT EXISTS idx_ml_model_versions_trained_at ON ml_model_versions(trained_at DESC);

-- Constraint: Solo una versión activa por modelo
CREATE UNIQUE INDEX IF NOT EXISTS idx_ml_model_versions_active_unique
ON ml_model_versions(model_name) WHERE is_active = TRUE;

-- ============================================================================
-- COMENTARIOS SOBRE EL SISTEMA
-- ============================================================================

COMMENT ON TABLE ml_suggestions IS
'Guarda todas las sugerencias del modelo para aprender de modificaciones humanas';

COMMENT ON TABLE ml_feedback IS
'Métricas reales de videos para evaluar si las sugerencias/modificaciones funcionaron';

COMMENT ON TABLE ml_model_versions IS
'Tracking de versiones de modelos y sus métricas de rendimiento';

COMMENT ON COLUMN ml_suggestions.was_modified IS
'TRUE = Usuario modificó la sugerencia. FALSE = Aceptó tal cual (modelo perfecto)';

COMMENT ON COLUMN ml_feedback.vs_predicted_vph_percent IS
'Diferencia entre VPH real vs predicho. >0 = mejor de lo esperado';

COMMENT ON COLUMN ml_model_versions.acceptance_rate IS
'% de sugerencias aceptadas sin modificar. Meta: 100% (modelo perfecto)';
