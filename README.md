# YouTube → Supabase Pipeline

Este repositorio contiene un pipeline automatizado que, cada día:
1. Importa hasta `DAILY_VIDEO_BATCH` vídeos nuevos de tu canal de YouTube.
2. Guarda esos vídeos en una tabla `videos` de Supabase.
3. Reconcilia comentarios, purga datos y actualiza métricas.

## Cómo empezar

1. Clona este repositorio:
   ```bash
   git clone https://github.com/tu-usuario/yt-pipeline-cron.git
   cd yt-pipeline-cron
