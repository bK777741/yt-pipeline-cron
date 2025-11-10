# 🤖 Sistema ML Predictor de YouTube

Sistema de Machine Learning 100% automático para predecir el rendimiento (VPH) de videos ANTES de publicarlos.

## 📋 Tabla de Contenidos

- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [Componentes](#componentes)
- [Flujo de Datos](#flujo-de-datos)
- [Instalación](#instalación)
- [Uso](#uso)
- [Automatización](#automatización)
- [Métricas y Validación](#métricas-y-validación)
- [Anti-Patrones](#anti-patrones)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Arquitectura del Sistema

### Estrategia Híbrida

El sistema usa un enfoque híbrido de dos niveles:

1. **SEMANAL** (Domingos 3AM):
   - Análisis ligero de anti-patrones
   - Detecta qué falló en videos de la semana
   - **NO** re-entrena el modelo
   - Tiempo: ~1 minuto
   - Cuota API: 0 unidades

2. **MENSUAL** (Día 1 de cada mes):
   - Snapshot de datos antes de purgar
   - Re-entrenamiento completo del modelo
   - Validación estricta (Precision >= 60%, R² >= 0.20)
   - Tiempo: ~10 minutos
   - Cuota API: 0 unidades

### ¿Por Qué Híbrido?

| Aspecto | Solo Semanal | Solo Mensual | **Híbrido** |
|---------|--------------|--------------|-------------|
| Alertas rápidas | ✅ | ❌ | ✅ |
| Evita overfitting | ❌ | ✅ | ✅ |
| Adapta a cambios | ⚠️ | ⚠️ | ✅ |
| Consumo recursos | Bajo | Medio | Óptimo |

---

## 📦 Componentes

### 1. Base de Datos (Supabase)

#### Tablas ML

```sql
-- Datos de entrenamiento (NUNCA se purgan)
ml_training_data
├── video_id (PK)
├── es_tuyo (boolean) -- TRUE = tu canal, FALSE = competencia
├── title, duration, category_id, channel_subscribers
├── vph (target principal)
├── nicho_score
└── snapshot_date

-- Metadata de modelos entrenados
modelo_ml_metadata
├── id (PK)
├── version (ej: "2025.01")
├── precision, r2_mean, dataset_size
├── features_usadas
└── trained_at

-- Anti-patrones detectados
anti_patrones
├── id (PK)
├── patron (ej: "Publicar lunes mañana")
├── frecuencia (cuántas veces detectado)
├── confianza (BAJA/MEDIA/ALTA)
└── impacto_vph_promedio
```

#### Crear Tablas

```bash
cd sql
psql $SUPABASE_URL -f create_ml_training_data.sql
```

### 2. Scripts Python

```
scripts/
├── save_training_snapshot.py     # Guarda datos antes de purgar
├── train_predictor_model.py      # Entrenamiento mensual
├── analizar_anti_patrones_semanal.py  # Análisis semanal
├── predict_video.py              # Predicción individual
└── nicho_utils.py                # Utilidades compartidas
```

### 3. Modelos ML

```
models/
└── predictor_ensemble.pkl        # Ensemble de 3 modelos
    ├── Random Forest (40% peso)
    ├── Gradient Boosting (40% peso)
    └── Ridge Regression (20% peso)
```

### 4. Workflows GitHub Actions

```
.github/workflows/
├── ml_system.yml                 # Análisis semanal
├── ml_monthly_training.yml       # Entrenamiento mensual
├── purga_automatica_supabase.yml # Con snapshot integrado
└── search_trending_every_2days.yml  # Con snapshot integrado
```

### 5. Dashboard Local

```
dashboard_predictor.html          # Interfaz web local
```

---

## 🔄 Flujo de Datos

### 1. Captura de Datos

```
fetch_shorts_search.py ──┐
fetch_explosive_longs.py ─┤
fetch_trending_videos.py ─┼──> Supabase Tables
maint_metrics.py ─────────┘     (video_shorts_search,
                                 video_explosive_longs,
                                 video_trending)
```

### 2. Snapshot Pre-Purga

```
Cada 2 días (antes de purgar):
┌─────────────────────────────────────┐
│ save_training_snapshot.py           │
│ ┌─────────────────────────────────┐ │
│ │ Videos 23-30 días (competencia) │ │
│ │ Videos 173-180 días (tuyos)     │ │
│ └─────────────────────────────────┘ │
│               ↓                     │
│      ml_training_data (permanente) │
└─────────────────────────────────────┘
            ↓
   purga_trending_30dias.py
   (elimina videos >30 días)
```

### 3. Entrenamiento Mensual

```
Día 1 de cada mes:
┌──────────────────────────────────────┐
│ train_predictor_model.py             │
│ ┌──────────────────────────────────┐ │
│ │ 1. Load últimos 6 meses          │ │
│ │ 2. Extract 12 features           │ │
│ │ 3. Train ensemble (RF+GB+Ridge)  │ │
│ │ 4. Validate (TimeSeriesSplit)    │ │
│ │ 5. Check: Precision >= 60%?      │ │
│ │    └─ SÍ: Guardar modelo         │ │
│ │    └─ NO: Mantener anterior      │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
            ↓
   predictor_ensemble.pkl
   (commit a GitHub)
```

### 4. Análisis Semanal

```
Cada domingo 3AM:
┌──────────────────────────────────────┐
│ analizar_anti_patrones_semanal.py    │
│ ┌──────────────────────────────────┐ │
│ │ 1. Get videos últimos 7 días     │ │
│ │ 2. Clasificar (ÉXITO/PROMEDIO/   │ │
│ │    FRACASO) por VPH              │ │
│ │ 3. Analizar solo FRACASOS:       │ │
│ │    - Timing (día/hora)           │ │
│ │    - Título (gancho, año, etc.)  │ │
│ │    - Nicho (score)               │ │
│ │ 4. Save to anti_patrones table   │ │
│ │ 5. Generate report (email)       │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### 5. Predicción

```
Usuario:
┌──────────────────────────────────────┐
│ python predict_video.py              │
│ ┌──────────────────────────────────┐ │
│ │ Input: título, duración, timing  │ │
│ │   ↓                              │ │
│ │ Extract 12 features              │ │
│ │   ↓                              │ │
│ │ Load predictor_ensemble.pkl      │ │
│ │   ↓                              │ │
│ │ Predict VPH                      │ │
│ │   ↓                              │ │
│ │ Classify: EXITOSO/PROMEDIO/      │ │
│ │           FRACASO                │ │
│ │   ↓                              │ │
│ │ Generate recommendations         │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

---

## 🚀 Instalación

### 1. Dependencias Python

```bash
pip install -r requirements.txt

# Dependencias ML adicionales:
pip install scikit-learn==1.3.0
pip install pandas numpy
```

### 2. Crear Tablas en Supabase

```bash
cd sql
# Copiar contenido de create_ml_training_data.sql
# Ejecutar en Supabase SQL Editor
```

O usando CLI:

```bash
psql $SUPABASE_URL -f create_ml_training_data.sql
```

### 3. Verificar GitHub Secrets

Asegurar que existen:

```
SUPABASE_URL
SUPABASE_SERVICE_KEY
YT_REFRESH_TOKEN
YT_CLIENT_ID
YT_CLIENT_SECRET
```

### 4. Test Manual

```bash
cd scripts

# Test 1: Snapshot
python save_training_snapshot.py

# Test 2: Análisis semanal (requiere videos de última semana)
python analizar_anti_patrones_semanal.py

# Test 3: Entrenamiento (requiere >= 100 videos en ml_training_data)
python train_predictor_model.py

# Test 4: Predicción
python predict_video.py
```

---

## 💻 Uso

### Predicción Individual (CLI)

#### Modo Interactivo

```bash
cd scripts
python predict_video.py
```

Te pedirá:
- Título del video
- Duración (segundos)
- Día de publicación
- Hora de publicación
- Score de nicho (opcional, default: 70)

#### Modo Argumentos

```bash
python predict_video.py \
  --titulo "SECRETO de ChatGPT 2025 que NADIE conoce" \
  --duracion 300 \
  --dia viernes \
  --hora 18 \
  --nicho-score 75
```

Salida:

```
==================================================
PREDICCIÓN
==================================================

Título: SECRETO de ChatGPT 2025 que NADIE conoce
Duración: 300s (5m 0s)
Timing: Viernes a las 18:00

VPH PREDICHO: 127.3
CLASIFICACIÓN: EXITOSO 🚀

🎉 ¡Excelente! Este video tiene alto potencial
   Recomendado PUBLICAR

==================================================
RECOMENDACIONES
==================================================
✅ Video cumple con todas las mejores prácticas
==================================================
```

### Dashboard Web Local

Abre en navegador:

```bash
# En Windows
start dashboard_predictor.html

# En Mac/Linux
open dashboard_predictor.html
```

**IMPORTANTE**: El dashboard usa predicciones simuladas. Para predicciones REALES del modelo entrenado, usa `predict_video.py`.

---

## ⚙️ Automatización

### Cronograma Completo

| Frecuencia | Workflow | Script | Hora | Descripción |
|------------|----------|--------|------|-------------|
| **Cada 2 días** | search_trending_every_2days.yml | save_training_snapshot.py | 6AM | Snapshot competencia antes de purgar |
| **Cada 2 días** | search_trending_every_2days.yml | purga_trending_30dias.py | 6AM | Purga videos trending >30 días |
| **Domingos** | ml_system.yml | analizar_anti_patrones_semanal.py | 3AM | Análisis de anti-patrones |
| **Día 1 mes** | purga_automatica_supabase.yml | save_training_snapshot.py | 3AM | Snapshot videos propios antes de purgar |
| **Día 1 mes** | purga_automatica_supabase.yml | purga_inteligente_supabase.py | 3AM | Purga videos propios >180 días |
| **Día 1 mes** | ml_monthly_training.yml | train_predictor_model.py | 2AM | Re-entrenamiento modelo ML |

### Flujo Mensual Completo

```
Día 28-30: Snapshot de competencia (cada 2 días)
    ↓
Día 1, 3AM: Snapshot de videos propios
    ↓
Día 1, 3AM: Purga inteligente (elimina >180 días)
    ↓
Día 1, 2AM: Entrenamiento modelo ML
    ↓
Día 1, 2AM: Commit modelo a GitHub
```

### Triggers Manuales

Todos los workflows se pueden ejecutar manualmente:

1. Ir a GitHub → Actions
2. Seleccionar workflow
3. Click "Run workflow"
4. Seleccionar opciones (si aplica)

---

## 📊 Métricas y Validación

### Features Usadas (12 Total)

El modelo usa solo 12 features limpias para evitar overfitting:

| # | Feature | Tipo | Descripción |
|---|---------|------|-------------|
| 1 | `nicho_score_norm` | Continua | Score de nicho normalizado (0-1) |
| 2 | `es_nicho_core` | Binaria | Score >= 60 |
| 3 | `dia_tipo` | Categórica | 0=weekday, 1=viernes, 2=weekend |
| 4 | `hora_tipo` | Categórica | 0=other, 1=afternoon(14-17h), 2=prime(17-21h) |
| 5 | `es_short` | Binaria | Duración < 90s |
| 6 | `duracion_optima` | Binaria | 20-60s (short) o 180-600s (long) |
| 7 | `titulo_len_cat` | Categórica | 0=<60, 1=60-80, 2=>80 chars |
| 8 | `tiene_gancho` | Binaria | Contiene SECRETO/TRUCO/OCULTO/etc |
| 9 | `tiene_ano` | Binaria | Contiene 2024/2025/2026 |
| 10 | `categoria_prioritaria` | Binaria | Es categoría 22/26/27/28 |
| 11 | `canal_pequeno` | Binaria | Suscriptores < 100K |
| 12 | `frecuencia_buena` | Binaria | 3-7 días desde último video |

### Modelos del Ensemble

#### 1. Random Forest
```python
RandomForestRegressor(
    n_estimators=100,
    max_depth=7,              # Limita profundidad (anti-overfitting)
    min_samples_split=30,     # Mínimo 30 samples por split
    min_samples_leaf=10,
    max_features='sqrt',      # Solo sqrt(12) ≈ 3-4 features por árbol
    random_state=42
)
```

#### 2. Gradient Boosting
```python
GradientBoostingRegressor(
    n_estimators=100,
    max_depth=6,              # Más conservador que RF
    min_samples_split=25,
    learning_rate=0.05,       # Aprendizaje lento (anti-overfitting)
    subsample=0.8,            # Bootstrap 80% (variabilidad)
    random_state=42
)
```

#### 3. Ridge Regression
```python
Ridge(
    alpha=10.0,               # Regularización L2 fuerte
    random_state=42
)
```

### Validación

#### 1. TimeSeriesSplit Cross-Validation

```
Fold 1: [Train ──────────] [Test]
Fold 2: [Train ────────────────] [Test]
Fold 3: [Train ──────────────────────] [Test]
Fold 4: [Train ────────────────────────────] [Test]
Fold 5: [Train ──────────────────────────────────] [Test]
```

- 5 folds temporales (NO aleatorios)
- Respeta orden cronológico
- Evita data leakage

#### 2. Hold-out Test Set

- 80% Train + 20% Test
- Test = Videos más recientes (últimos en tiempo)
- NUNCA vistos durante entrenamiento

#### 3. Criterios de Aceptación

Modelo se guarda SOLO si cumple:

| Criterio | Umbral | Descripción |
|----------|--------|-------------|
| **Precision** | >= 60% | Clasificación correcta EXITOSO/PROMEDIO/FRACASO |
| **R² Score** | >= 0.20 | Al menos 20% de varianza explicada |
| **MAE** | Razonable | Error absoluto medio en VPH |

Si NO cumple:
- Modelo NO se guarda
- Se mantiene modelo anterior
- Email de alerta enviado
- Esperar al próximo mes (más datos)

### Clasificación de VPH

| Clase | VPH | Acción |
|-------|-----|--------|
| **EXITOSO** 🚀 | >= 120 | PUBLICAR |
| **PROMEDIO** 🟡 | 60-119 | Revisar recomendaciones |
| **FRACASO** ❌ | < 60 | RE-PLANIFICAR |

---

## ⚠️ Anti-Patrones

El sistema detecta automáticamente 10+ anti-patrones comunes:

### Timing

| Anti-Patrón | Confianza | Impacto |
|-------------|-----------|---------|
| Publicar lunes/martes mañana | ALTA | Muy Negativo |
| Publicar domingo noche | MEDIA | Negativo |
| Publicar madrugada (0-6AM) | ALTA | Muy Negativo |

### Título

| Anti-Patrón | Confianza | Impacto |
|-------------|-----------|---------|
| Sin palabras gancho | ALTA | Muy Negativo |
| Título muy corto (<60 chars) | MEDIA | Negativo |
| Sin año actual | MEDIA | Negativo |
| Título muy largo (>105 chars) | BAJA | Leve Negativo |

### Nicho

| Anti-Patrón | Confianza | Impacto |
|-------------|-----------|---------|
| Fuera del nicho principal (score <50) | ALTA | Muy Negativo |

### Cómo se Detectan

1. Cada domingo, analiza videos de últimos 7 días
2. Clasifica por VPH: EXITOSO/PROMEDIO/FRACASO
3. Analiza SOLO fracasos (VPH < 60)
4. Busca patrones comunes
5. Guarda en tabla `anti_patrones`
6. Genera reporte y email

### Ver Anti-Patrones

```sql
-- En Supabase SQL Editor
SELECT
    patron,
    frecuencia,
    confianza,
    impacto_vph_promedio,
    actualizado_at
FROM anti_patrones
ORDER BY frecuencia DESC
LIMIT 10;
```

---

## 🔧 Troubleshooting

### Error: "Modelo no encontrado"

```
[ERROR] Modelo no encontrado
[ERROR] Ruta: GITHUB CRON/models/predictor_ensemble.pkl
```

**Solución:**
1. Entrenar modelo manualmente:
   ```bash
   cd scripts
   python train_predictor_model.py
   ```

2. Verificar que modelo fue aprobado:
   - Precision >= 60%?
   - Dataset >= 100 videos?

3. Si modelo no cumple criterios:
   - Esperar más datos (próximo mes)
   - Verificar calidad de datos en `ml_training_data`

### Error: "Dataset muy pequeño"

```
[ERROR] Dataset muy pequeño (42 samples)
[ERROR] Se recomienda >= 100 samples
```

**Solución:**
1. Verificar que `save_training_snapshot.py` se ejecuta:
   ```bash
   python save_training_snapshot.py
   ```

2. Verificar datos en Supabase:
   ```sql
   SELECT COUNT(*) FROM ml_training_data;
   ```

3. Esperar a que se acumulen más snapshots (cada 2 días + mensual)

4. Mientras tanto, usar dashboard para ver anti-patrones semanales

### Error: "Precisión muy baja (< 60%)"

```
❌ CRITERIO 1: Precision < 60% (42.3%)
```

**Causas comunes:**
1. Dataset muy pequeño
2. Datos de mala calidad (VPH = 0)
3. Cambio algorítmico de YouTube
4. Nicho muy volátil

**Solución:**
1. Verificar calidad de datos:
   ```sql
   SELECT
       AVG(vph) as vph_promedio,
       COUNT(CASE WHEN vph = 0 THEN 1 END) as ceros,
       COUNT(*) as total
   FROM ml_training_data;
   ```

2. Si muchos ceros, revisar scripts de captura

3. Esperar al próximo mes (más datos = mejor modelo)

4. Modelo anterior se mantiene activo

### Error: GitHub Actions falla al commit modelo

```
ERROR: Permission denied (publickey)
```

**Solución:**
1. Verificar que workflow tiene permisos:
   ```yaml
   permissions:
     contents: write
   ```

2. Verificar token en checkout:
   ```yaml
   - uses: actions/checkout@v4
     with:
       token: ${{ secrets.GITHUB_TOKEN }}
   ```

### Snapshot no guarda datos

```
[INFO] Videos sin captions: 0
```

**Verificar:**
1. ¿Hay videos en ventana de 23-30 días?
   ```sql
   SELECT COUNT(*)
   FROM video_shorts_search
   WHERE published_at >= NOW() - INTERVAL '30 days'
     AND published_at < NOW() - INTERVAL '23 days';
   ```

2. ¿Ya existen en ml_training_data?
   ```sql
   SELECT COUNT(*) FROM ml_training_data;
   ```

3. Si ventana vacía: Normal, esperar a que videos lleguen a esa edad

---

## 📈 Mejoras Futuras

### Fase 1 (Actual) ✅
- [x] Sistema básico de predicción
- [x] 12 features limpias
- [x] Ensemble de 3 modelos
- [x] Validación temporal
- [x] Anti-patrones semanales
- [x] 100% automático

### Fase 2 (Próxima)
- [ ] Detección de drift algorítmico
- [ ] Modelo específico por tipo (shorts vs longs)
- [ ] Features de thumbnail (OCR + embeddings)
- [ ] Análisis de sentimiento de títulos
- [ ] Predicción de retención

### Fase 3 (Avanzada)
- [ ] Transfer learning con BERT/GPT
- [ ] Predicción de monetización
- [ ] Recomendaciones de edición
- [ ] A/B testing automatizado

---

## 📝 Notas Importantes

### Cuota API
- **Snapshot**: 0 unidades (solo lee Supabase)
- **Entrenamiento**: 0 unidades (solo lee Supabase)
- **Análisis semanal**: 0 unidades (solo lee Supabase)
- **Predicción**: 0 unidades (modelo local)

**TOTAL: 0 unidades API consumidas** ✅

### Almacenamiento
- `ml_training_data`: ~2KB por video
- 1,000 videos = 2 MB
- 10,000 videos = 20 MB
- Crecimiento: ~700 videos/mes = 1.4 MB/mes

**Plan Free (500 MB): Suficiente para ~250K videos** ✅

### Privacidad
- Todos los datos en tu Supabase privado
- Modelo entrenado localmente (GitHub Actions)
- NO se envía nada a servicios externos
- Predicciones 100% offline

---

## 🎯 Resultado Esperado

Con este sistema 100% automático:

1. **Análisis Continuo**:
   - Anti-patrones detectados cada semana
   - Alertas tempranas de problemas

2. **Predicciones Confiables**:
   - Precisión 65-80% esperada
   - Evita publicar videos con alto riesgo de fracaso
   - Optimiza timing y formato

3. **Aprendizaje Continuo**:
   - Modelo se actualiza cada mes
   - Se adapta a cambios del algoritmo de YouTube
   - Aprende de tus éxitos Y fracasos

4. **Ahorro de Tiempo**:
   - NO más videos que fracasan
   - Focus en contenido que funciona
   - Mejora continua automática

---

## 📞 Soporte

Si encuentras problemas:

1. Revisar logs de GitHub Actions
2. Verificar tabla `modelo_ml_metadata` en Supabase
3. Ejecutar scripts manualmente para debugging
4. Revisar esta documentación (Troubleshooting)

---

**🤖 Sistema ML Predictor v1.0**
Creado con Claude Code | Última actualización: 2025-11-10
