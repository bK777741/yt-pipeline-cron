# SISTEMA DE FEEDBACK LOOP - APRENDIZAJE CONTINUO
## El "Trío Perfecto" de Machine Learning

---

## 🎯 OBJETIVO

Crear un sistema donde los modelos de IA **aprenden continuamente** de las modificaciones humanas, mejorando hasta que **no sea necesario modificar nada**.

### Meta Final
```
Hoy:      80% de sugerencias modificadas
3 meses:  50% de sugerencias modificadas
6 meses:  20% de sugerencias modificadas
META:      0% de sugerencias modificadas = MODELO PERFECTO
```

---

## 🔄 EL TRIO PERFECTO

```
┌──────────────────────┐
│  1. MODELO SUGIERE   │
│                      │  El modelo predice título, guion, etc.
│  "Truco SECRETO      │  basado en datos históricos
│   de WhatsApp"       │
└──────────┬───────────┘
           │
           ↓
┌──────────────────────┐
│  2. HUMANO EVALÚA    │
│                      │  Usuario decide:
│  ✓ ACEPTO (perfecto) │  - Aceptar tal cual → Modelo acertó
│  ✗ MODIFICO          │  - Modificar → Aprender de la modificación
│    "El Truco OCULTO" │
└──────────┬───────────┘
           │
           ↓
┌──────────────────────┐
│  3. RESULTADO ENSEÑA │
│                      │  Métricas reales confirman:
│  50K views          │  - Si el modelo acertó
│  85% retención      │  - Si la modificación mejoró
│  VPH: 625           │  - Qué cambios funcionan
└──────────┬───────────┘
           │
           ↓
      APRENDIZAJE
```

---

## 📊 ARQUITECTURA

### Tablas en Supabase

#### 1. `ml_suggestions`
Guarda todas las sugerencias del modelo

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | ID único |
| `video_id` | TEXT | ID del video (NULL hasta publicar) |
| `suggestion_type` | TEXT | 'title', 'script', 'thumbnail', 'tags' |
| `original_suggestion` | TEXT | Lo que el modelo sugirió |
| `final_version` | TEXT | Lo que TÚ publicaste |
| `was_modified` | BOOLEAN | ¿Modificaste la sugerencia? |
| `model_version` | TEXT | v2.0, v2.1, etc. |
| `predicted_vph` | FLOAT | VPH predicho |
| `suggested_at` | TIMESTAMP | Cuándo se sugirió |

#### 2. `ml_feedback`
Métricas reales de resultados

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | ID único |
| `suggestion_id` | UUID | Ref a ml_suggestions |
| `video_id` | TEXT | ID del video |
| `views_24h` | INT | Views en 24h |
| `vph_24h` | FLOAT | Views per hour |
| `retention_percent` | FLOAT | Retención promedio |
| `vs_channel_average_percent` | FLOAT | vs promedio del canal |
| `result_quality` | TEXT | 'excellent', 'good', 'average', 'poor' |

#### 3. `ml_model_versions`
Tracking de versiones de modelos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | ID único |
| `model_name` | TEXT | 'predictor', 'gui_evaluator' |
| `version` | TEXT | v2.0, v2.1, v3.0 |
| `acceptance_rate` | FLOAT | % sugerencias aceptadas sin modificar |
| `trained_at` | TIMESTAMP | Cuándo se entrenó |

---

## 🚀 FLUJO COMPLETO

### Paso 1: Modelo hace sugerencia

```python
from ml_suggestion_tracker import SuggestionTracker

tracker = SuggestionTracker(supabase_client)

# Modelo predice título
suggestion_id = tracker.record_suggestion(
    suggestion_type="title",
    original_suggestion="Truco SECRETO de WhatsApp",
    model_version="v2.0",
    model_confidence=0.85,
    predicted_vph=150.0
)
```

**Resultado**: Sugerencia guardada en `ml_suggestions`

---

### Paso 2: Usuario publica (con o sin modificación)

#### Caso A: Aceptado sin modificar (MODELO PERFECTO)

```python
tracker.record_publication(
    suggestion_id=suggestion_id,
    video_id="abc123",
    final_version="Truco SECRETO de WhatsApp",  # Igual
    was_modified=False  # ← ACEPTADO
)
```

**Significado**: El modelo acertó completamente. +1 punto de confianza.

---

#### Caso B: Modificado (APRENDER)

```python
tracker.record_publication(
    suggestion_id=suggestion_id,
    video_id="abc123",
    final_version="El Truco OCULTO de WhatsApp que cambió mi vida",
    was_modified=True,  # ← MODIFICADO
    modification_type="major_rewrite",
    changes={
        "added_words": ["OCULTO", "cambió", "vida"],
        "removed_words": ["SECRETO"],
        "length_change": +25
    }
)
```

**Significado**: El modelo debe aprender de este cambio.

---

### Paso 3: Métricas reales (24h después)

```python
tracker.record_feedback(
    suggestion_id=suggestion_id,
    video_id="abc123",
    views_24h=15000,
    likes=850,
    comments=120,
    retention_percent=75.5,
    vph_24h=625.0,
    vs_channel_average_percent=87.5  # +87.5% mejor que promedio ✅
)
```

**Análisis automático**:
- VPH predicho: 150
- VPH real: 625
- Mejora: **+316%** 🚀

**Conclusión**: La modificación humana fue EXITOSA. El modelo debe:
- Aumentar peso de "OCULTO"
- Reducir peso de "SECRETO"
- Preferir títulos más largos y descriptivos

---

### Paso 4: Aprendizaje automático (cada 7 días)

```bash
# Ejecutado automáticamente por GitHub Actions
python scripts/ml_feedback_learner.py
```

**Proceso**:
1. Analiza todas las sugerencias vs resultados
2. Identifica modificaciones exitosas
3. Extrae patrones (palabras que funcionan, estructuras, etc.)
4. Actualiza pesos del modelo
5. Re-entrena incorporando feedback humano

**Resultado**:
```
[REPORTE DE APRENDIZAJE]
Tasa de Aceptación: 45% (era 30% hace 1 mes)

Modificaciones exitosas: 15
Patrones aprendidos:
  - "OCULTO" funciona +120% mejor que "SECRETO"
  - Títulos con 8-12 palabras → +45% CTR
  - Mencionar beneficio en título → +67% retention

Modelo actualizado: v2.1
```

---

## 📈 MÉTRICAS CLAVE

### Tasa de Aceptación (Acceptance Rate)

```
Acceptance Rate = (Sugerencias aceptadas sin modificar / Total sugerencias) × 100
```

**Interpretación**:
- 0-20%: Modelo muy impreciso
- 21-40%: Modelo aprendiendo
- 41-60%: Modelo competente
- 61-80%: Modelo confiable
- 81-100%: **Modelo perfecto** ✨

### Mejora por Modificación

```
Mejora = ((VPH real - VPH predicho) / VPH predicho) × 100
```

**Interpretación**:
- Positivo: Modificación humana mejoró resultado
- Cero: Modelo tenía razón
- Negativo: Modelo era mejor (no debiste modificar)

---

## 🔧 INSTALACIÓN

### 1. Crear tablas en Supabase

```bash
# Opción A: Desde dashboard
# 1. Ve a https://supabase.com/dashboard
# 2. Tu proyecto → SQL Editor
# 3. Copia contenido de: sql/create_feedback_tables.sql
# 4. Ejecuta (RUN)

# Opción B: Desde CLI
psql $DATABASE_URL -f sql/create_feedback_tables.sql
```

### 2. Instalar dependencias (ya incluidas)

```bash
pip install supabase
```

### 3. Configurar GitHub Actions

El sistema ya está configurado para ejecutarse automáticamente:
- `ml_feedback_learner.py`: Cada 7 días
- Workflow: `.github/workflows/ml_feedback_weekly.yml`

---

## 💡 EJEMPLOS DE USO

### Ejemplo 1: Modelo acertó (no modificas)

```
Modelo: "Cómo recuperar archivos borrados GRATIS"
Tú:     [ACEPTAS TAL CUAL] ✓

Resultado: 25K views, 80% retention
Análisis: Modelo perfecto, +1 confianza
```

### Ejemplo 2: Modificación exitosa (aprendes)

```
Modelo: "Tutorial de WhatsApp Web"
Tú:     "El TRUCO de WhatsApp Web que NADIE conoce" ✏️

Resultado: 60K views, 85% retention
Análisis: Tu versión +240% mejor → Aprender de ti
```

### Ejemplo 3: Modelo tenía razón (no debiste modificar)

```
Modelo: "Activa Windows 11 GRATIS (Legal)"
Tú:     "Como activar Windows 11" ✏️

Resultado: 3K views, 45% retention
Análisis: Versión original era mejor → Reforzar modelo
```

---

## 📊 DASHBOARD DE PROGRESO

### Consulta SQL para ver tu progreso

```sql
SELECT
  DATE(suggested_at) as fecha,
  COUNT(*) as total_sugerencias,
  SUM(CASE WHEN was_modified = FALSE THEN 1 ELSE 0 END) as aceptadas,
  ROUND(
    SUM(CASE WHEN was_modified = FALSE THEN 1 ELSE 0 END)::numeric /
    COUNT(*)::numeric * 100,
    1
  ) as tasa_aceptacion_percent
FROM ml_suggestions
WHERE suggested_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(suggested_at)
ORDER BY fecha DESC;
```

**Resultado esperado**:
```
 fecha       | total | aceptadas | tasa_aceptacion
-------------+-------+-----------+-----------------
 2025-11-11  |   10  |     4     |      40.0%
 2025-11-10  |   12  |     3     |      25.0%
 2025-11-09  |    8  |     2     |      25.0%
```

---

## 🎓 FILOSOFÍA DEL SISTEMA

> "El mejor modelo es aquel que ya no necesita ser modificado"

Este sistema implementa **Reinforcement Learning from Human Feedback (RLHF)**, el mismo principio que usa ChatGPT.

**Ciclo virtuoso**:
1. Modelo aprende de datos históricos
2. Usuario corrige/mejora sugerencias
3. Modelo aprende de las correcciones
4. Sugerencias mejoran cada vez más
5. Usuario modifica menos y menos
6. **Meta**: Usuario nunca necesita modificar = Modelo perfecto

---

## 📞 SOPORTE

**Archivos clave**:
- `sql/create_feedback_tables.sql` - Esquema de BD
- `scripts/ml_suggestion_tracker.py` - Helper para trackear
- `scripts/ml_feedback_learner.py` - Sistema de aprendizaje

**Documentación**:
- Este archivo: `docs/SISTEMA_FEEDBACK_LOOP.md`
- Modelo predictor: `scripts/train_predictor_model.py`
- Modelo GUI: `scripts/gui/train_gui_model.py`

---

**Versión**: 1.0
**Fecha**: 2025-11-11
**Autor**: Sistema de ML con Feedback Humano
