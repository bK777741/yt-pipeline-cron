-- ==============================================================================
-- TABLAS PARA SISTEMA ML DE VIRALIDAD
-- ==============================================================================
-- Creado: 2025-11-11
-- Proposito: Almacenar resultados de analisis ML de texto, miniatura, sesion,
--            pasarelas y hijacking
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. ANALISIS DE TEXTO (NLP)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_text_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Caracteristicas basicas
  longitud_caracteres INT,
  longitud_palabras INT,

  -- Tema principal
  tema_principal TEXT,
  tema_confianza FLOAT,
  top_keywords JSONB, -- Array de {termino, score}

  -- Ritmo narrativo
  ritmo_tipo TEXT, -- 'muy_variado', 'variado', 'moderado', 'monotono'
  ritmo_variacion FLOAT,
  ritmo_longitud_promedio FLOAT,
  ritmo_num_oraciones INT,

  -- Hooks emocionales
  hooks_total INT,
  hooks_intensidad FLOAT,
  hooks_nivel TEXT, -- 'muy_alto', 'alto', 'medio', 'bajo', 'sin_hooks'
  hooks_por_categoria JSONB, -- {categoria: count}

  -- Sentimiento
  sentimiento_tipo TEXT, -- 'positivo', 'negativo', 'neutro'
  sentimiento_polaridad FLOAT,
  sentimiento_subjetividad FLOAT,

  -- Keywords del nicho
  nicho_score_total INT,
  nicho_densidad FLOAT,
  nicho_keywords_detectadas JSONB,
  nicho_num_keywords INT,

  -- Diversidad lexical
  diversidad_tipo TEXT, -- 'muy_alta', 'alta', 'media', 'baja'
  diversidad_valor FLOAT,
  diversidad_palabras_unicas INT,
  diversidad_palabras_totales INT,

  CONSTRAINT fk_video FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ml_text_video_id ON ml_text_analysis(video_id);
CREATE INDEX IF NOT EXISTS idx_ml_text_timestamp ON ml_text_analysis(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ml_text_tema ON ml_text_analysis(tema_principal);

COMMENT ON TABLE ml_text_analysis IS 'Analisis NLP de subtitulos (analizador_texto_gratis.py)';

-- ------------------------------------------------------------------------------
-- 2. ANALISIS DE MINIATURA (OpenCV)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_thumbnail_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  thumbnail_url TEXT,

  -- Dimensiones
  ancho INT,
  alto INT,

  -- Contraste
  contraste_valor FLOAT,
  contraste_nivel TEXT, -- 'muy_alto', 'alto', 'medio', 'bajo'
  contraste_calidad TEXT, -- 'excelente', 'bueno', 'aceptable', 'malo'

  -- Colores dominantes
  colores_vibrancia TEXT, -- 'muy_vibrante', 'vibrante', 'moderado', 'apagado'
  colores_saturacion_promedio FLOAT,
  colores_top JSONB, -- Array de {rgb, hex, porcentaje, saturacion}

  -- Saturacion y brillo
  saturacion_valor FLOAT,
  saturacion_nivel TEXT,
  brillo_valor FLOAT,
  brillo_nivel TEXT,

  -- Rostros detectados
  rostros_detectados INT,
  rostros_nivel TEXT, -- 'sin_rostros', 'un_rostro', 'pocos_rostros', 'muchos_rostros'
  rostros_info JSONB, -- Array de {x, y, ancho, alto, area_porcentaje}

  -- Texto OCR (opcional)
  ocr_texto TEXT,
  ocr_num_caracteres INT,
  ocr_num_palabras INT,
  ocr_nivel TEXT,

  -- Composicion
  composicion_calidad TEXT, -- 'excelente', 'buena', 'aceptable', 'pobre'
  composicion_densidad_tercios FLOAT,

  CONSTRAINT fk_video_thumbnail FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ml_thumbnail_video_id ON ml_thumbnail_analysis(video_id);
CREATE INDEX IF NOT EXISTS idx_ml_thumbnail_timestamp ON ml_thumbnail_analysis(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ml_thumbnail_contraste ON ml_thumbnail_analysis(contraste_nivel);

COMMENT ON TABLE ml_thumbnail_analysis IS 'Analisis visual de miniaturas (analizador_miniaturas_gratis.py)';

-- ------------------------------------------------------------------------------
-- 3. ANALISIS DE CONTINUACION DE SESION
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Metricas de sesion
  views INT,
  minutes_watched FLOAT,
  avg_view_duration FLOAT,
  avg_view_percentage FLOAT,
  card_click_rate FLOAT,

  -- Clasificacion
  tipo TEXT NOT NULL, -- 'EXTENSOR_ELITE', 'EXTENSOR', 'NEUTRO', 'ASESINO_LEVE', 'ASESINO_CRITICO'
  ratio FLOAT NOT NULL, -- Ratio de continuacion (>1 = extensor, <1 = asesino)
  accion_recomendada TEXT,
  prioridad INT, -- 1 (mas urgente) a 5 (menos urgente)
  confianza FLOAT, -- 0-1

  -- Periodo de analisis
  fecha_inicio DATE,
  fecha_fin DATE,
  dias_analisis INT,

  CONSTRAINT fk_video_session FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_video_id ON session_analysis(video_id);
CREATE INDEX IF NOT EXISTS idx_session_tipo ON session_analysis(tipo);
CREATE INDEX IF NOT EXISTS idx_session_ratio ON session_analysis(ratio DESC);
CREATE INDEX IF NOT EXISTS idx_session_timestamp ON session_analysis(timestamp DESC);

COMMENT ON TABLE session_analysis IS 'Clasificacion EXTENSORES/ASESINOS (analizador_sesion_continuacion.py)';
COMMENT ON COLUMN session_analysis.tipo IS 'EXTENSOR_ELITE: Ratio >= 1.3 y Ret >= 60% | EXTENSOR: Ratio >= 1.1 y Ret >= 50% | NEUTRO: Ratio 0.9-1.1 | ASESINO_LEVE: Ratio 0.7-0.9 | ASESINO_CRITICO: Ratio < 0.7';

-- ------------------------------------------------------------------------------
-- 4. ANALISIS DE VIDEOS PASARELA
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gateway_videos_analysis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Clasificacion
  es_pasarela BOOLEAN NOT NULL,
  nivel TEXT, -- 'PASARELA_ELITE', 'PASARELA', 'NO_PASARELA'
  pasarela_score FLOAT NOT NULL, -- 0-100

  -- Componentes del score
  score_trafico_busqueda FLOAT,
  score_trafico_browse FLOAT,
  score_query_fundamental FLOAT,
  score_simplicidad_titulo FLOAT,
  score_nicho FLOAT,

  -- Metricas de trafico
  total_views INT,
  busqueda_pct FLOAT, -- % de trafico desde busqueda
  browse_pct FLOAT, -- % de trafico desde browse
  suggested_pct FLOAT, -- % de trafico desde sugeridos
  trafico_raw JSONB, -- {fuente: views}

  -- Recomendacion
  accion_recomendada TEXT,

  -- Periodo de analisis
  fecha_inicio DATE,
  fecha_fin DATE,
  dias_analisis INT,

  CONSTRAINT fk_video_gateway FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gateway_video_id ON gateway_videos_analysis(video_id);
CREATE INDEX IF NOT EXISTS idx_gateway_nivel ON gateway_videos_analysis(nivel);
CREATE INDEX IF NOT EXISTS idx_gateway_score ON gateway_videos_analysis(pasarela_score DESC);
CREATE INDEX IF NOT EXISTS idx_gateway_timestamp ON gateway_videos_analysis(timestamp DESC);

COMMENT ON TABLE gateway_videos_analysis IS 'Videos que sirven como puntos de entrada al nicho (detector_videos_pasarela.py)';
COMMENT ON COLUMN gateway_videos_analysis.pasarela_score IS 'Score 0-100: >= 80 ELITE, >= 60 PASARELA, < 60 NO_PASARELA';

-- ------------------------------------------------------------------------------
-- 5. OPORTUNIDADES DE HIJACKING
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hijacking_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Video viral de competencia
  video_viral_id TEXT NOT NULL,
  video_viral_titulo TEXT NOT NULL,
  video_viral_canal TEXT,
  video_viral_vph FLOAT,
  video_viral_views INT,
  video_viral_published_at TIMESTAMP WITH TIME ZONE,

  -- Analisis del viral
  tipo_contenido TEXT, -- 'tutorial', 'tips', 'comparacion', 'explicacion', 'desconocido'
  gaps_detectados TEXT[], -- Array de gaps: 'contenido_avanzado', 'mas_tips', etc
  es_viral BOOLEAN,

  -- Idea de hijacking
  tipo_hijacking TEXT NOT NULL, -- 'extension', 'comparacion', 'profundizacion', 'correccion', 'alternativa'
  titulo_sugerido TEXT NOT NULL,
  estrategia TEXT,
  gap_cubierto TEXT,
  potencial_trafico FLOAT, -- VPH esperado de nuestro video hijack

  -- Estado
  estado TEXT DEFAULT 'pendiente', -- 'pendiente', 'en_produccion', 'publicado', 'descartado'
  video_creado_id TEXT, -- ID del video que creamos (si se implementa)

  CONSTRAINT fk_video_creado FOREIGN KEY (video_creado_id) REFERENCES videos(video_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_hijacking_timestamp ON hijacking_opportunities(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_hijacking_estado ON hijacking_opportunities(estado);
CREATE INDEX IF NOT EXISTS idx_hijacking_potencial ON hijacking_opportunities(potencial_trafico DESC);
CREATE INDEX IF NOT EXISTS idx_hijacking_tipo ON hijacking_opportunities(tipo_hijacking);

COMMENT ON TABLE hijacking_opportunities IS 'Oportunidades de capturar trafico de videos virales (sistema_robo_sesiones.py)';
COMMENT ON COLUMN hijacking_opportunities.potencial_trafico IS 'VPH esperado si creamos el video hijack (basado en VPH del viral)';

-- ------------------------------------------------------------------------------
-- TRIGGERS PARA ACTUALIZAR timestamps
-- ------------------------------------------------------------------------------

-- Trigger para ml_text_analysis
CREATE OR REPLACE FUNCTION update_ml_text_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.timestamp = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_ml_text_timestamp
BEFORE UPDATE ON ml_text_analysis
FOR EACH ROW
EXECUTE FUNCTION update_ml_text_timestamp();

-- Trigger para ml_thumbnail_analysis
CREATE OR REPLACE FUNCTION update_ml_thumbnail_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.timestamp = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_ml_thumbnail_timestamp
BEFORE UPDATE ON ml_thumbnail_analysis
FOR EACH ROW
EXECUTE FUNCTION update_ml_thumbnail_timestamp();

-- Trigger para session_analysis
CREATE OR REPLACE FUNCTION update_session_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.timestamp = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_session_timestamp
BEFORE UPDATE ON session_analysis
FOR EACH ROW
EXECUTE FUNCTION update_session_timestamp();

-- Trigger para gateway_videos_analysis
CREATE OR REPLACE FUNCTION update_gateway_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.timestamp = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_gateway_timestamp
BEFORE UPDATE ON gateway_videos_analysis
FOR EACH ROW
EXECUTE FUNCTION update_gateway_timestamp();

-- Trigger para hijacking_opportunities
CREATE OR REPLACE FUNCTION update_hijacking_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.timestamp = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_hijacking_timestamp
BEFORE UPDATE ON hijacking_opportunities
FOR EACH ROW
EXECUTE FUNCTION update_hijacking_timestamp();

-- ==============================================================================
-- FIN DEL SCRIPT
-- ==============================================================================
