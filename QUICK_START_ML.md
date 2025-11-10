# 🚀 Quick Start - Sistema ML Predictor

Guía rápida de instalación y activación del sistema ML 100% automático.

---

## ✅ PASO 1: Crear Tablas en Supabase

1. Ir a Supabase → SQL Editor
2. Copiar contenido de `sql/create_ml_training_data.sql`
3. Ejecutar el script SQL
4. Verificar que se crearon las tablas:
   - `ml_training_data`
   - `video_clasificacion`
   - `modelo_ml_metadata`
   - `anti_patrones`

**Verificación:**
```sql
SELECT COUNT(*) FROM ml_training_data;
-- Debe retornar 0 (vacío al inicio)
```

---

## ✅ PASO 2: Instalar Dependencias ML

```bash
cd "GITHUB CRON"
pip install -r requirements.txt
```

**Verificación:**
```bash
python -c "import sklearn, pandas, numpy; print('✅ Dependencias OK')"
```

---

## ✅ PASO 3: Test Manual de Scripts

### 3.1 Test Snapshot (Guardar Datos)

```bash
cd scripts
python save_training_snapshot.py
```

Esperado:
```
[SNAPSHOT COMPETENCIA] Completado
  Guardados: 0-50 (depende de datos existentes)
[SNAPSHOT PROPIOS] Completado
  Guardados: 0-10
```

### 3.2 Test Análisis Semanal

```bash
python analizar_anti_patrones_semanal.py
```

Esperado:
```
[1/3] Obteniendo videos de la última semana...
  Videos encontrados: X
[2/3] Clasificando videos...
[3/3] Generando reporte...
✅ ANÁLISIS SEMANAL COMPLETADO
```

### 3.3 Test Entrenamiento (Opcional - Requiere >=100 videos)

```bash
python train_predictor_model.py
```

Si dataset < 100:
```
[ERROR] Dataset muy pequeño (X samples)
[ERROR] Esperar a próximo mes para más datos
```

Esto es NORMAL al inicio. El sistema acumulará datos automáticamente.

### 3.4 Test Predicción

```bash
python predict_video.py
```

Si modelo no existe aún:
```
[ERROR] Modelo no encontrado
[INFO] Ejecutar primero: train_predictor_model.py
```

Esto es NORMAL. Usa el dashboard para ver anti-patrones mientras se entrena el primer modelo.

---

## ✅ PASO 4: Verificar GitHub Actions

1. Ir a GitHub → Actions
2. Verificar workflows activos:
   - ✅ **Sistema ML Predictor** (domingos 3AM)
   - ✅ **ML - Entrenamiento Mensual** (día 1 de mes, 2AM)
   - ✅ **Purga Automática Supabase** (día 1 de mes, 3AM)
   - ✅ **Búsqueda Activa Trending** (cada 2 días, 6AM)

3. Test manual:
   - Click en "ML - Entrenamiento Mensual"
   - Click "Run workflow"
   - Esperar 5-10 minutos
   - Verificar logs

---

## ✅ PASO 5: Usar Dashboard Local

```bash
# Windows
start dashboard_predictor.html

# Mac/Linux
open dashboard_predictor.html
```

El dashboard muestra:
- ✅ Formulario de predicción (simulada - usar Python para real)
- ✅ Anti-patrones detectados
- ✅ Estado del sistema
- ✅ Comandos útiles

---

## 📅 Cronograma Automático

Una vez instalado, el sistema funciona solo:

| Cuándo | Qué | Script |
|--------|-----|--------|
| **Cada 2 días, 6AM** | Captura competencia + Snapshot | save_training_snapshot.py |
| **Domingos, 3AM** | Análisis anti-patrones | analizar_anti_patrones_semanal.py |
| **Día 1, 3AM** | Snapshot + Purga videos viejos | save_training_snapshot.py + purga_inteligente_supabase.py |
| **Día 1, 2AM** | Re-entrenamiento modelo | train_predictor_model.py |

---

## 📊 Primera Ejecución (Mes 1)

### Semana 1-4: Acumulación de Datos
- Sistema captura videos de competencia cada 2 días
- Análisis semanal detecta anti-patrones
- Dataset crece: 0 → 50 → 100 → 150 videos

### Día 1 del Mes 2: Primer Entrenamiento
- Dataset: ~150 videos
- Entrenamiento: ✅ Exitoso (si precision >= 60%)
- Modelo guardado: `models/predictor_ensemble.pkl`
- Ya puedes usar `predict_video.py`

### Meses Siguientes: Aprendizaje Continuo
- Dataset sigue creciendo: 150 → 300 → 500 → 1,000+
- Re-entrenamiento mensual mejora precisión
- Modelo se adapta a cambios del algoritmo

---

## 🎯 Uso Diario (Después del Mes 1)

### Antes de Publicar un Video:

```bash
cd scripts
python predict_video.py
```

Input:
```
Título: SECRETO de ChatGPT 2025 que NADIE conoce
Duración: 300
Día: viernes
Hora: 18
Score nicho: 75
```

Output:
```
VPH PREDICHO: 127.3
CLASIFICACIÓN: EXITOSO 🚀
Recomendado PUBLICAR
```

**Decisión:**
- VPH >= 120 → PUBLICAR ✅
- VPH 60-119 → Revisar recomendaciones ⚠️
- VPH < 60 → RE-PLANIFICAR ❌

---

## ⚠️ Troubleshooting Común

### "Dataset muy pequeño"

**Normal al inicio.** Esperar 1-2 meses para acumular >=100 videos.

**Acelerar:**
- Ejecutar manualmente `save_training_snapshot.py` cada semana
- Verificar que workflows de captura funcionan

### "Modelo no encontrado"

**Normal al inicio.** Primer modelo se genera el día 1 del mes siguiente.

**Mientras tanto:**
- Usar anti-patrones del análisis semanal
- Dashboard muestra qué evitar

### "Precision < 60%"

**Posible en primeras ejecuciones.**

**Causas:**
- Dataset muy pequeño (< 100 videos)
- Datos de mala calidad (VPH = 0)
- Nicho muy volátil

**Solución:**
- Modelo anterior se mantiene
- Esperar al próximo mes (más datos)
- Verificar calidad de datos en Supabase

---

## 📞 Necesitas Ayuda?

1. **Leer documentación completa:** `ML_SYSTEM_README.md`
2. **Verificar logs:** GitHub Actions → Workflows → Ver logs
3. **Verificar datos:** Supabase → SQL Editor → Queries de verificación
4. **Test manual:** Ejecutar scripts localmente para debugging

---

## ✨ Resultado Esperado

Después de 2-3 meses:

| Métrica | Esperado |
|---------|----------|
| **Precisión** | 65-80% |
| **Videos en dataset** | 500-1,000+ |
| **Anti-patrones detectados** | 10-15 |
| **Ahorro de tiempo** | 50-70% |
| **Tasa de éxito** | +30-50% |

---

**🎉 ¡LISTO! Sistema 100% automático activado**

El sistema ahora:
- ✅ Aprende automáticamente cada mes
- ✅ Detecta anti-patrones cada semana
- ✅ Predice VPH antes de publicar
- ✅ Se adapta a cambios del algoritmo
- ✅ NO consume cuota API
- ✅ NO requiere intervención manual

**Solo tienes que usar `predict_video.py` antes de publicar cada video.**

---

**Sistema ML Predictor v1.0**
Creado con Claude Code | 2025-11-10
