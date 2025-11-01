-- ============================================================================
-- TABLA: script_execution_log
-- Propósito: Registrar última ejecución de cada script para watermarks
-- Uso: Sistema de frecuencias personalizadas (cada_3_dias, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.script_execution_log (
    script_name TEXT PRIMARY KEY,
    last_run TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'success',
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_script_execution_log_last_run
    ON public.script_execution_log(last_run DESC);

CREATE INDEX IF NOT EXISTS idx_script_execution_log_status
    ON public.script_execution_log(status);

-- ============================================================================
-- COMENTARIOS
-- ============================================================================

COMMENT ON TABLE public.script_execution_log IS
'Registro de ejecuciones de scripts para sistema de watermarks y frecuencias personalizadas';

COMMENT ON COLUMN public.script_execution_log.script_name IS
'Nombre único del script (PK). Ejemplos: import_captions, fetch_trending_videos';

COMMENT ON COLUMN public.script_execution_log.last_run IS
'Timestamp de la última ejecución exitosa del script';

COMMENT ON COLUMN public.script_execution_log.status IS
'Estado de la última ejecución: success, error, skipped';

COMMENT ON COLUMN public.script_execution_log.details IS
'Detalles adicionales de la ejecución (JSON). Ej: videos procesados, errores, etc.';

-- ============================================================================
-- DATOS INICIALES (OPCIONAL)
-- ============================================================================

-- Insertar registro inicial para import_captions si no existe
INSERT INTO public.script_execution_log (script_name, last_run, status)
VALUES ('import_captions', NOW() - INTERVAL '4 days', 'success')
ON CONFLICT (script_name) DO NOTHING;

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================

-- Verificar que la tabla se creó correctamente
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'script_execution_log'
ORDER BY ordinal_position;

-- ============================================================================
-- EJEMPLO DE USO
-- ============================================================================

-- Consultar última ejecución de un script
-- SELECT * FROM script_execution_log WHERE script_name = 'import_captions';

-- Registrar nueva ejecución (UPSERT)
-- INSERT INTO script_execution_log (script_name, last_run, status)
-- VALUES ('import_captions', NOW(), 'success')
-- ON CONFLICT (script_name)
-- DO UPDATE SET
--     last_run = EXCLUDED.last_run,
--     status = EXCLUDED.status,
--     updated_at = NOW();
