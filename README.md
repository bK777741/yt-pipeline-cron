# Proyecto de Automatización y Análisis para YouTube

---

## 🚀 Visión General

Este proyecto es un sistema automatizado para la extracción, análisis, transformación y almacenamiento de datos desde la API de YouTube. Está diseñado para funcionar de manera autónoma mediante tareas programadas (cron jobs), interactuando con una base de datos en Supabase para la persistencia y análisis de datos.

El núcleo del sistema se encarga de tareas como:

*   Análisis de tendencias y de la competencia.
*   Generación de perfiles de nicho y de canal mediante embeddings y NLP.
*   Cálculo de horarios de publicación óptimos.
*   Procesamiento de subtítulos, texto y objetos en miniaturas.
*   Sincronización de métricas de canal, videos y monetización.

---

## 📋 Requisitos Previos

*   Python 3.10+
*   Una cuenta de Supabase con un proyecto creado.
*   Credenciales de la API de Google (OAuth 2.0) con acceso a la API de YouTube.

---

## ⚙️ Instalación y Configuración

Sigue estos pasos para configurar el proyecto en tu entorno local.

### 1. Clona el Repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_DIRECTORIO>
```

### 2. Instala las Dependencias

Se recomienda usar un entorno virtual.

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
python -m pip install -r requirements.txt
```

### 3. Configura las Variables de Entorno

Este es el paso más importante. El proyecto utiliza un archivo `.env.local` para gestionar todas las claves de API y secretos.

Crea un archivo llamado `.env.local` dentro del directorio `credentials/`.

```
touch credentials/.env.local
```

Abre el archivo y pega el siguiente contenido, reemplazando los valores `...` con tus propias credenciales:

```ini
# Credenciales de Supabase
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
STORAGE_BUCKET=...

# Credenciales de Google Cloud / YouTube API (OAuth 2.0)
# Obtenidas desde la consola de Google Cloud
CLIENT_ID=...
CLIENT_SECRET=...
REFRESH_TOKEN=...

# (Opcional) API Key de YouTube para tareas que no requieren OAuth
YT_API_KEY=...
```

### 4. Valida tu Configuración

Una vez que hayas configurado tu archivo `.env.local`, puedes usar los scripts de validación para asegurarte de que todo está en orden.

*   **En Windows:**
    Simplemente ejecuta el archivo `COMPROBADOR GENERAL QUE FUNCIONA_env.bat`. Este script cargará las variables y probará la conexión con la API de Google automáticamente.

*   **En macOS / Linux:**
    Ejecuta los siguientes comandos en orden:

    ```bash
    # 1. Valida que las variables de entorno de Google existen
    python scripts/check_env.py

    # 2. Prueba el refresco del token de acceso
    python scripts/refresh_token.py
    ```

Si todo es correcto, verás mensajes de `OK` y un nuevo token de acceso al final.

---

## 🤖 Automatización con GitHub Actions

El repositorio está configurado para ejecutar scripts automáticamente mediante GitHub Actions.

### Workflows Principales

1.  **`cron.yml`**: Orquesta la ejecución de la mayoría de los scripts de análisis y sincronización de datos con Supabase.
2.  **`refresh_token.yml`**: Se ejecuta diariamente para probar el proceso de refresco del token de OAuth de YouTube, asegurando que las credenciales siguen siendo válidas. Su principal función es de monitoreo.

### Configuración de Secretos en GitHub

Para que los workflows funcionen, debes configurar los siguientes "secrets" en la configuración de tu repositorio en GitHub (`Settings > Secrets and variables > Actions`):

*   `SUPABASE_URL`
*   `SUPABASE_SERVICE_KEY`
*   `YT_CLIENT_ID`
*   `YT_CLIENT_SECRET`
*   `YT_REFRESH_TOKEN`
*   `YT_API_KEY` (si es necesario)

---

## 🧰 Descripción de Scripts

A continuación se detallan los scripts principales y su función dentro del ecosistema.

### Scripts Fundacionales y de Autenticación

| Script                | Función                                                                 |
| --------------------- | ----------------------------------------------------------------------- |
| `check_env.py`        | Verifica que las variables de entorno de Google estén cargadas.         |
| `refresh_token.py`    | Usa el `REFRESH_TOKEN` para obtener un nuevo `access_token` de Google.  |

### Scripts de Análisis y Perfilamiento

| Script                          | Función                                                        |
| ------------------------------- | -------------------------------------------------------------- |
| `build_channel_profile.py`      | Crea embeddings de videos y realiza clustering.                |
| `build_niche_profile.py`        | Genera un vector de nicho (TF-IDF + Embeddings).               |
| `compute_posting_schedule.py`   | Calcula el mejor horario de publicación basado en métricas.    |
| `convert_captions_to_script.py` | Transforma subtítulos de videos en guiones estructurados.       |
| `detect_thumbnail_objects.py`   | Detecta objetos en miniaturas usando un modelo YOLOv8.         |
| `extract_thumbnail_text.py`     | Extrae texto de miniaturas mediante OCR.                       |
| `refine_trending_with_niche.py` | Filtra videos en tendencia según el perfil del canal.          |
| `scan_competencia_auto_nicho.py`| Explora canales de la competencia para análisis de nicho.      |

### Scripts de Extracción y Sincronización

| Script                          | Función                                                        |
| ------------------------------- | -------------------------------------------------------------- |
| `fetch_comment_sentiment.py`    | Analiza y asigna un sentimiento a los comentarios de videos.   |
| `fetch_monetization_metrics.py` | Obtiene métricas de monetización estimadas.                    |
| `fetch_search_trends.py`        | Captura tendencias de búsqueda relacionadas con el nicho.      |
| `fetch_trending_videos.py`      | Obtiene la lista de videos en tendencia de YouTube.            |
| `fetch_video_analytics.py`      | Extrae métricas detalladas de rendimiento de los videos.       |
| `fetch_youtube_policies.py`     | Descarga y valida las políticas de la comunidad de YouTube.    |
| `import_captions.py`            | Importa los subtítulos de los videos.                          |
| `import_daily.py`               | Importa los videos más recientes del canal.                    |
| `import_recent_comments.py`     | Importa los comentarios más recientes.                         |

### Scripts de Mantenimiento

| Script                      | Función                                                              |
| --------------------------- | -------------------------------------------------------------------- |
| `maint_metrics.py`          | Genera snapshots diarios de estadísticas de videos.                  |
| `purge_buffer.py`           | Elimina registros antiguos, con opción de backup en Supabase Storage.|
| `reconcile_comments.py`     | Realiza tareas de limpieza y reconciliación en los comentarios.    |
| `export_sync_watermarks.py` | Exporta los timestamps de la última sincronización de cada tabla.    |

---

## 🗃️ Arquitectura de Datos (Supabase)

El proyecto utiliza varias tablas en Supabase para almacenar los datos procesados. La tabla `sync_watermarks` es especialmente importante, ya que registra la última vez que cada script se ejecutó y sincronizó datos, permitiendo un procesamiento incremental.

---

## 📙 Licencia

Licencia oficial a Piloides Aceptados.