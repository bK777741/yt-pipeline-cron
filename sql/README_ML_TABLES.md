# TABLAS DE MACHINE LEARNING

## 📋 INSTALACIÓN

### **Paso 1: Crear Tablas en Supabase**

```bash
# Opción A: Dashboard de Supabase
1. Ir a https://supabase.com/dashboard
2. Seleccionar proyecto
3. Ir a SQL Editor
4. Copiar contenido de: sql/create_ml_analysis_tables.sql
5. Ejecutar (RUN)

# Opción B: psql (CLI)
psql $DATABASE_URL -f sql/create_ml_analysis_tables.sql
```

---

## 📊 TABLAS CREADAS

### **1. ml_text_analysis**
**Propósito:** Almacena análisis NLP de subtítulos

**Columnas principales:**
- `video_id` - ID del video (FK a `videos`)
- `tema_principal` - Tema extraído con TF-IDF
- `ritmo_tipo` - Tipo de ritmo narrativo
- `hooks_total` - Cantidad de hooks emocionales
- `sentimiento_tipo` - Positivo/negativo/neutro
- `nicho_score_total` - Score de keywords del nicho
- `diversidad_valor` - Diversidad léxical (0-1)

**Script generador:** `scripts/analizador_texto_gratis.py`

**Ejemplo de consulta:**
```sql
-- Videos con mejor ritmo narrativo
SELECT video_id, tema_principal, ritmo_tipo, ritmo_variacion
FROM ml_text_analysis
WHERE ritmo_tipo IN ('muy_variado', 'variado')
ORDER BY ritmo_variacion DESC
LIMIT 10;
```

---

### **2. ml_thumbnail_analysis**
**Propósito:** Almacena análisis visual de miniaturas

**Columnas principales:**
- `video_id` - ID del video (FK a `videos`)
- `contraste_nivel` - Nivel de contraste (muy_alto/alto/medio/bajo)
- `colores_vibrancia` - Vibrancia de colores
- `rostros_detectados` - Cantidad de rostros
- `composicion_calidad` - Calidad de composición

**Script generador:** `scripts/analizador_miniaturas_gratis.py`

**Ejemplo de consulta:**
```sql
-- Miniaturas con mejor contraste y rostros
SELECT video_id, contraste_nivel, rostros_detectados, composicion_calidad
FROM ml_thumbnail_analysis
WHERE contraste_nivel = 'muy_alto'
  AND rostros_detectados = 1
ORDER BY timestamp DESC
LIMIT 10;
```

---

### **3. session_analysis**
**Propósito:** Clasificación EXTENSORES/ASESINOS

**Columnas principales:**
- `video_id` - ID del video (FK a `videos`)
- `tipo` - EXTENSOR_ELITE/EXTENSOR/NEUTRO/ASESINO_LEVE/ASESINO_CRITICO
- `ratio` - Ratio de continuación (>1 = extensor, <1 = asesino)
- `avg_view_percentage` - Retención promedio
- `accion_recomendada` - Qué hacer con el video

**Script generador:** `scripts/analizador_sesion_continuacion.py`

**Ejemplo de consulta:**
```sql
-- Top 10 videos EXTENSORES
SELECT video_id, tipo, ratio, avg_view_percentage, accion_recomendada
FROM session_analysis
WHERE tipo IN ('EXTENSOR_ELITE', 'EXTENSOR')
ORDER BY ratio DESC
LIMIT 10;

-- Videos ASESINOS que requieren optimización
SELECT video_id, tipo, ratio, accion_recomendada
FROM session_analysis
WHERE tipo IN ('ASESINO_CRITICO', 'ASESINO_LEVE')
ORDER BY ratio ASC
LIMIT 10;
```

---

### **4. gateway_videos_analysis**
**Propósito:** Identifica videos pasarela (puntos de entrada)

**Columnas principales:**
- `video_id` - ID del video (FK a `videos`)
- `es_pasarela` - Boolean
- `nivel` - PASARELA_ELITE/PASARELA/NO_PASARELA
- `pasarela_score` - Score 0-100
- `busqueda_pct` - % de tráfico desde búsqueda
- `browse_pct` - % de tráfico desde browse

**Script generador:** `scripts/detector_videos_pasarela.py`

**Ejemplo de consulta:**
```sql
-- Videos pasarela con más tráfico de búsqueda
SELECT video_id, nivel, pasarela_score, busqueda_pct, total_views
FROM gateway_videos_analysis
WHERE es_pasarela = true
ORDER BY busqueda_pct DESC
LIMIT 10;
```

---

### **5. hijacking_opportunities**
**Propósito:** Oportunidades de capturar tráfico viral

**Columnas principales:**
- `video_viral_id` - ID del video viral de competencia
- `video_viral_titulo` - Título del viral
- `video_viral_vph` - VPH del viral
- `tipo_hijacking` - extension/comparacion/profundizacion/correccion
- `titulo_sugerido` - Título para nuestro video hijack
- `potencial_trafico` - VPH esperado
- `estado` - pendiente/en_produccion/publicado/descartado

**Script generador:** `scripts/sistema_robo_sesiones.py`

**Ejemplo de consulta:**
```sql
-- Top oportunidades de hijacking pendientes
SELECT
  video_viral_titulo,
  video_viral_vph,
  tipo_hijacking,
  titulo_sugerido,
  potencial_trafico,
  estrategia
FROM hijacking_opportunities
WHERE estado = 'pendiente'
ORDER BY potencial_trafico DESC
LIMIT 10;

-- Marcar como en producción
UPDATE hijacking_opportunities
SET estado = 'en_produccion'
WHERE id = 'xxx-xxx-xxx';
```

---

## 🔗 RELACIONES

```
videos (tabla existente)
  ├── ml_text_analysis (1:N)
  ├── ml_thumbnail_analysis (1:N)
  ├── session_analysis (1:N)
  └── gateway_videos_analysis (1:N)

hijacking_opportunities
  └── video_creado_id → videos (N:1, opcional)
```

---

## 🚀 QUERIES ÚTILES

### **Dashboard de Videos Óptimos**
```sql
-- Videos con análisis completo (texto + miniatura + sesión)
SELECT
  v.video_id,
  v.title,
  v.vph,
  t.tema_principal,
  t.hooks_nivel,
  m.contraste_nivel,
  m.rostros_detectados,
  s.tipo AS clasificacion_sesion,
  s.ratio,
  g.es_pasarela
FROM videos v
LEFT JOIN ml_text_analysis t ON v.video_id = t.video_id
LEFT JOIN ml_thumbnail_analysis m ON v.video_id = m.video_id
LEFT JOIN session_analysis s ON v.video_id = s.video_id
LEFT JOIN gateway_videos_analysis g ON v.video_id = g.video_id
WHERE v.vph >= 50
ORDER BY v.vph DESC
LIMIT 20;
```

### **Videos para Promocionar (EXTENSORES con buen análisis)**
```sql
SELECT
  v.video_id,
  v.title,
  s.tipo,
  s.ratio,
  t.hooks_nivel,
  m.contraste_nivel
FROM videos v
JOIN session_analysis s ON v.video_id = s.video_id
LEFT JOIN ml_text_analysis t ON v.video_id = t.video_id
LEFT JOIN ml_thumbnail_analysis m ON v.video_id = m.video_id
WHERE s.tipo IN ('EXTENSOR_ELITE', 'EXTENSOR')
  AND t.hooks_nivel IN ('muy_alto', 'alto')
  AND m.contraste_nivel IN ('muy_alto', 'alto')
ORDER BY s.ratio DESC;
```

### **Videos para Optimizar (ASESINOS)**
```sql
SELECT
  v.video_id,
  v.title,
  s.tipo,
  s.ratio,
  s.accion_recomendada,
  t.nicho_score_total,
  m.contraste_nivel
FROM videos v
JOIN session_analysis s ON v.video_id = s.video_id
LEFT JOIN ml_text_analysis t ON v.video_id = t.video_id
LEFT JOIN ml_thumbnail_analysis m ON v.video_id = m.video_id
WHERE s.tipo IN ('ASESINO_CRITICO', 'ASESINO_LEVE')
ORDER BY s.ratio ASC;
```

---

## 🔧 MANTENIMIENTO

### **Limpiar análisis antiguos**
```sql
-- Borrar análisis de videos eliminados (por cascada ya se hace automático)

-- Borrar análisis duplicados (mantener solo el más reciente)
DELETE FROM ml_text_analysis
WHERE id IN (
  SELECT id FROM (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY timestamp DESC) AS rn
    FROM ml_text_analysis
  ) t
  WHERE rn > 1
);
```

### **Verificar integridad**
```sql
-- Videos sin análisis de texto
SELECT v.video_id, v.title
FROM videos v
LEFT JOIN ml_text_analysis t ON v.video_id = t.video_id
WHERE t.id IS NULL;

-- Videos sin análisis de miniatura
SELECT v.video_id, v.title
FROM videos v
LEFT JOIN ml_thumbnail_analysis m ON v.video_id = m.video_id
WHERE m.id IS NULL;
```

---

## 📈 ESTADÍSTICAS

```sql
-- Resumen de análisis por tipo
SELECT
  'Texto' AS tipo,
  COUNT(*) AS total_analisis,
  COUNT(DISTINCT video_id) AS videos_unicos
FROM ml_text_analysis

UNION ALL

SELECT
  'Miniatura' AS tipo,
  COUNT(*) AS total_analisis,
  COUNT(DISTINCT video_id) AS videos_unicos
FROM ml_thumbnail_analysis

UNION ALL

SELECT
  'Sesión' AS tipo,
  COUNT(*) AS total_analisis,
  COUNT(DISTINCT video_id) AS videos_unicos
FROM session_analysis;
```

---

**Versión:** 1.0
**Fecha:** 2025-11-11
**Sistema:** Tablas ML de Viralidad
