-- ============================================================================
-- VISTA: v_thumbnail_sources
-- Propósito: Devolver videos con thumbnails que NO han sido procesados
-- ============================================================================

CREATE OR REPLACE VIEW v_thumbnail_sources AS
SELECT
    v.video_id,
    COALESCE(
        v.thumbnail_maxres,
        v.thumbnail_standard,
        v.thumbnail_high,
        v.thumbnail_medium,
        v.thumbnail_default
    ) AS thumbnail_url
FROM videos v
WHERE
    -- Video tiene al menos un thumbnail
    (v.thumbnail_maxres IS NOT NULL
     OR v.thumbnail_standard IS NOT NULL
     OR v.thumbnail_high IS NOT NULL
     OR v.thumbnail_medium IS NOT NULL
     OR v.thumbnail_default IS NOT NULL)

    -- Y NO ha sido procesado todavía para detección de objetos
    AND NOT EXISTS (
        SELECT 1
        FROM video_thumbnail_objects vto
        WHERE vto.video_id = v.video_id
    );

-- ============================================================================
-- COMENTARIO
-- ============================================================================
COMMENT ON VIEW v_thumbnail_sources IS
'Vista que devuelve videos con thumbnails pendientes de procesar (sin objects ni OCR)';
