# YouTube → Supabase → GUI → Base de Datos Local
**Fecha de actualización:** 2025-08-10

## 📌 Descripción General
Este proyecto automatiza la extracción, análisis y almacenamiento de datos de YouTube para optimizar la creación de contenido y la monetización.  
Actualmente, se ejecuta mediante **cron jobs en GitHub Actions** que conectan con la **API de YouTube**, procesan los datos y los guardan en **Supabase**.  
En una fase futura, toda la información se sincronizará automáticamente con una **Base de Datos Local** al abrir la GUI.

---

## 🚀 Funcionalidades Clave
1. **Importación diaria de videos** con título, descripción, hashtags, etiquetas, duración y miniatura.
2. **Análisis de miniaturas**: color dominante, paleta, brillo, contraste, detección de rostros, OCR para texto, phash.
3. **Extracción de comentarios** y respuestas recientes (últimos 60 días), con filtrado de spam y análisis de sentimiento (positivo, negativo, neutro).
4. **Importación de subtítulos** para posible uso en análisis de guiones.
5. **Actualización de métricas** diarias (vistas, likes, comentarios).
6. **Analíticas de monetización**: impresiones, CTR, CPM, ingresos estimados, reproducciones monetizadas.
7. **Analíticas de retención**: minutos vistos, duración promedio de visualización, retención de audiencia, suscriptores ganados.
8. **Detección de tendencias** de búsqueda y videos virales relevantes para el nicho del canal.
9. **Registro de políticas de YouTube**, detectando cambios y actualizando la base.
10. **Cálculo de horarios óptimos** para publicar nuevos videos.
11. **Limpieza automática de datos antiguos** (con backup en Supabase Storage).

---

## ⏱ Horarios de Ejecución (Lima)
- **02:00** → Importar videos del día (`import_daily.py`).
- **02:30** → Sincronizar comentarios (`reconcile_comments.py`).
- **03:00** → Purga de buffer y backup (`purge_buffer.py`).
- **04:00** → Actualizar métricas (`maint_metrics.py`).

---

## 🛠 Estructura de Datos en Supabase
Las tablas principales incluyen:
- **videos** → Datos completos de cada video.
- **comments** → Comentarios y análisis de sentimiento/spam.
- **captions** → Subtítulos.
- **video_statistics** → Métricas diarias.
- **video_analytics** → Analíticas de retención y monetización.
- **video_trending** → Videos virales filtrados por nicho.
- **search_trends** → Tendencias de búsqueda.
- **posting_schedule** → Mejores horarios para publicar.
- **youtube_policies** → Políticas y actualizaciones de YouTube.
- **video_thumbnail_analysis** → Análisis de miniaturas.

---

## 🔒 Seguridad
- **RLS (Row Level Security)** activado en todas las tablas.
- Acceso de escritura limitado al **service_role**.
- El **anon key** solo puede insertar y leer en `video_trending`.
- Recomendación: asegurar que el archivo `.env` esté en `.gitignore` para evitar exposición de credenciales.

---

## 📈 Flujo del Proyecto
1. **GitHub Actions** ejecuta scripts que consultan la API de YouTube.
2. Los datos se procesan y se guardan en **Supabase**.
3. En la próxima fase, la **GUI** descargará datos de Supabase a la **Base de Datos Local** de forma incremental, evitando sobrescrituras.

---

## 📂 Instalación Local
```bash
# Clonar el repositorio
git clone <tu-repositorio>
cd <tu-repositorio>

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate    # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar credenciales en .env
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
YT_CLIENT_ID=...
YT_CLIENT_SECRET=...
YT_REFRESH_TOKEN=...
```

---

## 📜 Licencia
MIT © 2025  
Desarrollado por PILOIDE
