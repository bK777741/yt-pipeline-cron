-- Tabla: gui_training_context
-- Propósito: Almacenar el contexto de entrenamiento del modelo GUI
-- Usado por: scripts/train_gui_model.py

CREATE TABLE IF NOT EXISTS gui_training_context (
    id BIGSERIAL PRIMARY KEY,
    context_type TEXT NOT NULL DEFAULT 'main',
    total_guiones_analizados INTEGER DEFAULT 0,
    fecha_entrenamiento TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    patrones JSONB NOT NULL DEFAULT '{}'::jsonb,
    confianza NUMERIC(5,1) DEFAULT 0.0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para mejorar rendimiento
CREATE INDEX IF NOT EXISTS idx_gui_training_context_type ON gui_training_context(context_type);
CREATE INDEX IF NOT EXISTS idx_gui_training_fecha ON gui_training_context(fecha_entrenamiento DESC);
CREATE INDEX IF NOT EXISTS idx_gui_training_confianza ON gui_training_context(confianza DESC);

-- Comentarios
COMMENT ON TABLE gui_training_context IS 'Contexto de entrenamiento del modelo GUI - CEREBRO 2';
COMMENT ON COLUMN gui_training_context.context_type IS 'Tipo de contexto: main, backup, experimental';
COMMENT ON COLUMN gui_training_context.total_guiones_analizados IS 'Cantidad de guiones usados en el entrenamiento';
COMMENT ON COLUMN gui_training_context.fecha_entrenamiento IS 'Fecha y hora del entrenamiento';
COMMENT ON COLUMN gui_training_context.patrones IS 'Patrones detectados (JSON): estructura, ganchos, estilo, etc';
COMMENT ON COLUMN gui_training_context.confianza IS 'Nivel de confianza del modelo (0-100) basado en cantidad de datos';
COMMENT ON COLUMN gui_training_context.updated_at IS 'Última actualización del registro';
COMMENT ON COLUMN gui_training_context.created_at IS 'Fecha de creación del registro';

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_gui_training_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar updated_at
DROP TRIGGER IF EXISTS trigger_update_gui_training_updated_at ON gui_training_context;
CREATE TRIGGER trigger_update_gui_training_updated_at
    BEFORE UPDATE ON gui_training_context
    FOR EACH ROW
    EXECUTE FUNCTION update_gui_training_updated_at();

-- Verificación
SELECT 'Tabla gui_training_context creada exitosamente' AS status;
