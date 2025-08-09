# YouTube → Supabase pipeline

Cron jobs que importan datos de tu canal de YouTube a una base en Supabase.

## Funcionalidades

- **Import daily videos**: extrae los vídeos publicados hoy en tu canal.
- **Reconcile comments**: sincroniza comentarios nuevos en Supabase.
- **Purge buffer**: limpia datos antiguos de la tabla de buffer.
- **Maintain metrics**: actualiza métricas agregadas.

## Configuración

1. Clona el repositorio:
   ```bash
   git clone https://github.com/bK777741/yt-pipeline-cron.git
   cd yt-pipeline-cron
Crea un entorno virtual e instala dependencias:

bash
Copiar
Editar
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
Crea y configura los secrets en GitHub (Settings → Secrets and variables → Actions):

YT_CLIENT_ID :

YT_CLIENT_SECRET:

YT_REFRESH_TOKEN:

SUPABASE_URL:

SUPABASE_SERVICE_KEY:

DAILY_VIDEO_BATCH:20

CHANNEL_ID:

Ejecución local
bash
Copiar
Editar
# Carga variables de entorno en un .env:
cp .env.txt .env
# Edita .env con tus credenciales.

# Importa vídeos de hoy:
python scripts/import_daily.py
GitHub Actions
El flujo está definido en .github/workflows/cron.yml y corre:

schedule: "0 7 * * *" → Import daily videos (02:00 Lima)

schedule: "30 7 * * *" → Reconcile comments (02:30 Lima)

schedule: "0 8 * * *" → Purge buffer (03:00 Lima)

schedule: "0 9 * * *" → Maintain metrics (04:00 Lima)

También lo puedes lanzar manualmente desde la pestaña Actions → YouTube → Supabase pipeline → Run workflow.

Licencia
MIT © Grupo Destinos Oficial


