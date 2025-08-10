# YouTube → Supabase → GUI → Base de Datos Local
**Fecha de actualización:** 2025-08-10 17:03 UTC-05:00

## 📌 Descripción General
Este proyecto automatiza la extracción, análisis y almacenamiento de datos de YouTube para optimizar la creación de contenido y la monetización.  
Actualmente se ejecuta mediante **GitHub Actions (cron)** que consultan la **API de YouTube**, procesan los datos y guardan todo en **Supabase**.  
En la siguiente fase, la **GUI** sincronizará de forma **incremental** (sin sobrescribir) hacia una **Base de Datos Local** al momento de abrirse.

---

## 🚀 Funcionalidades Clave
1. **Importación diaria de videos**: título, descripción, hashtags, etiquetas, duración, miniaturas, estado y más.
2. **Análisis de miniaturas** (si está habilitado): color dominante, paleta, brillo, contraste, conteo de rostros, área de texto, **phash** y **saliency**.
3. **Subtítulos**: descarga y almacenamiento por idioma.
4. **Guiones**: conversión de subtítulos a guiones (con **corrección ortográfica** opcional) y estructura básica (gancho, contexto, desarrollo, cierre).
5. **Comentarios**: ingesta de comentarios y respuestas recientes (ventana móvil de 60 días), versión y conciliación de datos.
6. **Sentimiento** en comentarios (positivo, neutro, negativo) con puntaje dimensional.
7. **Métricas diarias** por video (vistas, likes, comentarios).
8. **Analíticas avanzadas**: retención, duración promedio de visualización, minutos vistos, suscriptores ganados.
9. **Monetización**: impresiones, CTR, **CPM**, ingresos estimados, impresiones de anuncios y reproducciones monetizadas.
10. **Tendencias**: videos en tendencia por región e idioma; tendencias de búsqueda (Google Trends).
11. **Horario óptimo de publicación** calculado por día de semana y bloques de hora.
12. **Políticas de YouTube**: descarga periódica de contenidos y detección de cambios.
13. **Mantenimiento/Limpieza**: purga controlada de buffers y backups en Supabase Storage.

---

## ⏱ Horarios de Ejecución (America/Lima)
> Todos los horarios se expresan en hora de Lima (UTC-5).  
> (GitHub Actions corre en UTC; ver sección *Cron* para equivalencias).

- **02:00** → Importar videos del día (`import_daily.py`).
- **02:15** → Importar subtítulos (`import_captions.py`).
- **02:15** → Convertir subtítulos a guiones (`convert_captions_to_script.py`).
- **02:30** → Importar comentarios recientes (`import_recent_comments.py`).
- **02:45** → Conciliar comentarios (`reconcile_comments.py`).
- **03:00** → Analizar sentimiento en comentarios (`fetch_comment_sentiment.py`).
- **04:00** → Actualizar métricas básicas (`maint_metrics.py`).
- **05:00** → Analíticas de retención (`fetch_video_analytics.py`).
- **05:30** → Calcular horario óptimo de publicación (`compute_posting_schedule.py`).
- **06:00** → Analíticas de monetización (`fetch_monetization_metrics.py`).
- **06:30** → Videos en tendencia (`fetch_trending_videos.py`).
- **06:45** → Tendencias de búsqueda (`fetch_search_trends.py`).
- **09:00** (días 1 y 16) → Políticas de YouTube (`fetch_youtube_policies.py`).
- **23:55** → Purga/backup de buffer (`purge_buffer.py`).

---

## 🗂 Tablas principales en Supabase
- `videos`: metadatos completos del video (incluye `hashtags` y `tags`).
- `video_thumbnail_analysis`: análisis de miniaturas por video/URL.
- `captions`: subtítulos por video e idioma.
- `video_scripts`: guiones derivados de subtítulos (hash y versión).
- `comments`: comentarios, versiones, flags de spam, sentimiento.
- `video_statistics`: métricas diarias (vistas, likes, comentarios).
- `video_analytics`: retención y monetización (CPM, CTR, ingresos).
- `video_trending`: videos virales por región/idioma y fecha de corrida.
- `search_trends`: consultas en tendencia por región.
- `posting_schedule`: promedios de vistas a 24h por día/bloque horario.
- `youtube_policies`: contenido y hash de políticas de YouTube.
- `sync_runs`: registro de ejecuciones.
- Índices y RLS activados para rendimiento y seguridad.

---

## 🔐 Seguridad
- **RLS (Row Level Security)** activado en todas las tablas relevantes.
- Escrituración restringida al **service_role** desde GitHub Actions.
- Permisos públicos limitados (solo lectura y/o inserción donde corresponde).
- **GitHub Secrets** para credenciales (YouTube, Supabase, SMTP, etc.).
- **Recomendado**: incluir `.env` en `.gitignore` y usar *dotenv* solo localmente.

---

## 🖥️ Requisitos
- Python 3.12
- Dependencias en `requirements.txt` (incluye `supabase`, `google-api-python-client`, `language-tool-python`, `nltk`, `pytrends`, etc.).
- Tesseract (solo si se habilita OCR de miniaturas).

---

## 🔧 Ejecución local (desarrollo)
```bash
# 1) Clonar y crear entorno
git clone <tu-repo>
cd <tu-repo>
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Configurar variables de entorno (.env, NO subir a Git)
export SUPABASE_URL=...
export SUPABASE_SERVICE_KEY=...
export YT_CLIENT_ID=...
export YT_CLIENT_SECRET=...
export YT_REFRESH_TOKEN=...

# 4) Pruebas de scripts (opcional)
python ./scripts/import_daily.py
```

---

## 🔄 Sincronización incremental hacia Base de Datos Local (GUI)
1. Al abrir la GUI, iniciar un proceso de **pull** por tabla usando *watermarks* (p. ej. `imported_at`, `snapshot_date`, `calculated_at`, `fetched_at`, `last_checked_at`, `checked_at`).  
2. Hacer **upserts** por clave natural:
   - `videos(video_id)`, `captions(video_id, language)`, `video_statistics(video_id, snapshot_date)`, `video_analytics(video_id, snapshot_date)`,
   - `video_trending(video_id, run_date)`, `search_trends(query, run_date, region)`, `posting_schedule(weekday, hour_bucket)`,
   - `youtube_policies(policy_url, content_hash)`, `comments(comment_id)`.
3. Evitar sobrescrituras: **no actualizar** filas cuya versión/hash/fecha local sea más reciente.
4. Manejar borrados lógicos (p. ej., `deleted_at` en `comments`).
5. Registrar `synced_to_gui=true` en Supabase solo al confirmar escritura local.
6. Retentar con **backoff** y logs detallados.

---

## 📝 Licencia y creación de Piloides Aceptados
MIT © 2025
