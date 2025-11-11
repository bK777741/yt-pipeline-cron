-- Tabla de patrones de exito (PERMANENTE - nunca se borra)
-- Almacena aprendizajes extraidos de videos antiguos antes de purgarlos

CREATE TABLE IF NOT EXISTS patrones_exito (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patron_tipo TEXT NOT NULL,
  patron_valor TEXT NOT NULL,
  frecuencia INT NOT NULL DEFAULT 1,
  vph_promedio FLOAT,
  confianza FLOAT,
  extraido_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  actualizado_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patrones_tipo ON patrones_exito(patron_tipo);
CREATE INDEX IF NOT EXISTS idx_patrones_confianza ON patrones_exito(confianza DESC);
CREATE INDEX IF NOT EXISTS idx_patrones_vph ON patrones_exito(vph_promedio DESC);

-- Constraint para evitar duplicados
CREATE UNIQUE INDEX IF NOT EXISTS idx_patrones_unico
ON patrones_exito(patron_tipo, patron_valor);

-- Comentarios
COMMENT ON TABLE patrones_exito IS 'Patrones de exito extraidos de videos antiguos (PERMANENTE)';
COMMENT ON COLUMN patrones_exito.patron_tipo IS 'Tipo: palabra_titulo_exitosa, timing_optimo, etc';
COMMENT ON COLUMN patrones_exito.patron_valor IS 'Valor del patron: chatgpt, jueves_6pm, etc';
COMMENT ON COLUMN patrones_exito.frecuencia IS 'Numero de veces que aparecio en videos exitosos';
COMMENT ON COLUMN patrones_exito.vph_promedio IS 'VPH promedio de videos con este patron';
COMMENT ON COLUMN patrones_exito.confianza IS 'Nivel de confianza del patron (0-1)';
