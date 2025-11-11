-- Tabla 1: Sugerencias del modelo
CREATE TABLE IF NOT EXISTS ml_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT,
  suggestion_type TEXT NOT NULL,
  original_suggestion TEXT NOT NULL,
  final_version TEXT,
  was_modified BOOLEAN DEFAULT FALSE,
  modification_type TEXT,
  changes_summary JSONB,
  model_version TEXT NOT NULL,
  model_confidence FLOAT,
  predicted_vph FLOAT,
  suggested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  published_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_suggestions_video_id ON ml_suggestions(video_id);
CREATE INDEX IF NOT EXISTS idx_ml_suggestions_type ON ml_suggestions(suggestion_type);
CREATE INDEX IF NOT EXISTS idx_ml_suggestions_modified ON ml_suggestions(was_modified);
CREATE INDEX IF NOT EXISTS idx_ml_suggestions_suggested_at ON ml_suggestions(suggested_at DESC);

-- Tabla 2: Feedback de resultados
CREATE TABLE IF NOT EXISTS ml_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  suggestion_id UUID NOT NULL REFERENCES ml_suggestions(id),
  video_id TEXT NOT NULL,
  views_24h INT,
  views_7d INT,
  views_30d INT,
  likes INT,
  comments INT,
  shares INT,
  ctr_percent FLOAT,
  avg_view_duration_seconds INT,
  retention_percent FLOAT,
  vph_24h FLOAT,
  vph_7d FLOAT,
  engagement_score FLOAT,
  performance_score FLOAT,
  vs_channel_average_percent FLOAT,
  vs_predicted_vph_percent FLOAT,
  result_quality TEXT,
  measured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_feedback_suggestion_id ON ml_feedback(suggestion_id);
CREATE INDEX IF NOT EXISTS idx_ml_feedback_video_id ON ml_feedback(video_id);
CREATE INDEX IF NOT EXISTS idx_ml_feedback_quality ON ml_feedback(result_quality);

-- Tabla 3: Versiones de modelos
CREATE TABLE IF NOT EXISTS ml_model_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_name TEXT NOT NULL,
  version TEXT NOT NULL,
  trained_at TIMESTAMP WITH TIME ZONE NOT NULL,
  dataset_size INT NOT NULL,
  training_duration_seconds INT,
  features JSONB,
  hyperparameters JSONB,
  metrics JSONB NOT NULL,
  human_modifications_learned INT DEFAULT 0,
  acceptance_rate FLOAT,
  improvement_rate FLOAT,
  is_active BOOLEAN DEFAULT TRUE,
  replaced_by TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ml_model_versions_name ON ml_model_versions(model_name);
CREATE INDEX IF NOT EXISTS idx_ml_model_versions_version ON ml_model_versions(version);
CREATE INDEX IF NOT EXISTS idx_ml_model_versions_active ON ml_model_versions(is_active);
CREATE INDEX IF NOT EXISTS idx_ml_model_versions_trained_at ON ml_model_versions(trained_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ml_model_versions_active_unique
ON ml_model_versions(model_name) WHERE is_active = TRUE;
