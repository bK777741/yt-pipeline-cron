# Proyecto GitHub → Supabase - Auditoría Completa

Este documento es una versión extendida y detallada del `README.md`, incluyendo el flujo de datos, scripts, estructuras, y relaciones entre GitHub y Supabase, como referencia técnica oficial del proyecto.

---

## 🔄 Descripción General

Este proyecto automatiza el proceso de extracción, análisis, transformación y almacenamiento de datos desde la API de YouTube hacia una base de datos Supabase.

Se utiliza para:

* Análisis de tendencias y competencia
* Generación de guiones de videos
* Detección de objetos y texto en miniaturas
* Perfilamiento de canales y nichos
* Calculo de horarios de publicación óptimos
* Exportación de políticas de monetización

---

## 📊 Estructura del Proyecto (por Bloques)

### ✅ Bloque 1 - Fundacional

| Archivo                                  | Descripción                                                        |
| ---------------------------------------- | ------------------------------------------------------------------ |
| `README.md`                              | Documentación general (esta versión la extiende)                   |
| `requirements.txt`                       | Lista de dependencias necesarias (Supabase, NLP, Visíon, ML, etc.) |
| `cron.yml`, `fetch_youtube_policies.yml` | Tareas programadas automáticas para ejecución periódica            |

#### Scripts principales

| Script                          | Función                                             | Tabla destino                       |
| ------------------------------- | --------------------------------------------------- | ----------------------------------- |
| `build_channel_profile.py`      | Embeddings de videos y clustering                   | `channel_profile_embeddings`        |
| `build_niche_profile.py`        | Generación de vector de nicho (TF-IDF + Embeddings) | Supabase Storage (modelo `nv.json`) |
| `compute_posting_schedule.py`   | Calcula mejor horario de publicación                | `posting_schedule`                  |
| `convert_captions_to_script.py` | Transforma subtítulos en guiones estructurados      | `video_scripts`                     |
| `detect_thumbnail_objects.py`   | Detección con YOLOv8                                | `video_thumbnail_objects`           |
| `export_sync_watermarks.py`     | Exporta últimos timestamps de sincronización        | `sync_watermarks`                   |

---

### 🔢 Bloque 2 - Extracción y sincronización

| Script                          | Función                    | Tabla destino          |
| ------------------------------- | -------------------------- | ---------------------- |
| `extract_thumbnail_text.py`     | OCR de miniaturas          | `video_thumbnail_text` |
| `fetch_comment_sentiment.py`    | Sentimiento de comentarios | `comments` (update)    |
| `fetch_monetization_metrics.py` | Métricas de monetización   | `monetization_metrics` |
| `fetch_search_trends.py`        | Tendencias de búsqueda     | `search_trends`        |
| `fetch_trending_videos.py`      | Videos en tendencia        | `video_trending`       |
| `fetch_video_analytics.py`      | Métricas de rendimiento    | `video_analytics`      |
| `fetch_youtube_policies.py`     | Políticas de YouTube       | `youtube_policies`     |
| `import_captions.py`            | Subtítulos                 | `captions`             |
| `import_daily.py`               | Videos diarios del canal   | `videos`               |
| `import_recent_comments.py`     | Comentarios recientes      | `comments`             |

---

### 🚀 Bloque 3 - Procesamiento y mantenimiento

| Script                           | Función                                          | Tabla destino                         |
| -------------------------------- | ------------------------------------------------ | ------------------------------------- |
| `maint_metrics.py`               | Métricas de mantenimiento (snapshot)             | `video_statistics`                    |
| `purge_buffer.py`                | Elimina registros antiguos con backup en Storage | Varios + `Storage`                    |
| `reconcile_comments.py`          | Reconciliación y limpieza de comentarios         | `comments`                            |
| `refine_trending_with_niche.py`  | Filtrado de trending según el perfil del canal   | `video_trending_filtered`             |
| `scan_competencia_auto_nicho.py` | Exploración de competencia/nicho                 | `video_trending_filtered`, `Storage`  |
| `policy_urls.json`               | Reglas de políticas para validación              | Usado por `fetch_youtube_policies.py` |

---

## 🚪 Variables de entorno necesarias

* `SUPABASE_URL`
* `SUPABASE_SERVICE_KEY`
* `YT_API_KEY` o `YT_REFRESH_TOKEN`
* `STORAGE_BUCKET`

---

## 📊 Tablas en Supabase utilizadas

| Tabla                        | Propósito                                 |
| ---------------------------- | ----------------------------------------- |
| `videos`                     | Videos extraídos del canal                |
| `comments`                   | Comentarios importados y sentimentados    |
| `video_analytics`            | Estadísticas detalladas de videos         |
| `video_scripts`              | Guiones generados desde subtítulos        |
| `video_trending`             | Videos tendencia candidatos               |
| `video_trending_filtered`    | Videos tendencia filtrados por nicho      |
| `channel_profile_embeddings` | Embeddings de canal                       |
| `niche_profile_embeddings`   | Embeddings del nicho                      |
| `captions`                   | Subtítulos crudos                         |
| `video_thumbnail_objects`    | Objetos detectados en miniaturas          |
| `video_thumbnail_text`       | Texto detectado en miniaturas (OCR)       |
| `monetization_metrics`       | Estimaciones monetarias                   |
| `search_trends`              | Palabras clave en tendencia               |
| `sync_watermarks`            | Timestamps de última sync por tabla       |
| `youtube_policies`           | Listado y validación de políticas YouTube |
| `posting_schedule`           | Horarios sugeridos de publicación         |
| `video_statistics`           | Historico diario por video                |

---

## 🚀 Integración GitHub Actions (cron)

El archivo `cron.yml` define la ejecución automatizada de scripts vía GitHub Actions.
Asegúrate de que:

* Los secretos (`SUPABASE_URL`, etc.) estén bien cargados en GitHub.
* El scheduler esté activo según la zona horaria deseada.
* Cada job tenga su script correctamente configurado.

---

## 🔧 Recomendaciones Finales

1. ✅ Verifica los `cron.yml` y que cada script se ejecute periódicamente.
2. 🔢 Asegura que las variables de entorno estén disponibles en todos los entornos (GitHub, local, etc.)
3. 📈 Revisa la tabla `sync_watermarks` para monitorear si los scripts están alimentando datos.
4. 🏙️ Usa `Storage` para respaldos si haces limpieza masiva (`purge_buffer.py`).
5. ⚖️ Revisa logs en Supabase y GitHub para cualquier script que no refleje datos.

---

## 📙 Licencia oficial a Piloides Aceptados


