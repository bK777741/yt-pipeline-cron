#!/usr/bin/env python3
"""
compute_posting_schedule.py
Calcula el mejor horario de publicación basado en vistas en primeras 24h.

ACTUALIZADO: 2025-10-31 - Corrección de datetime.utcnow() deprecado
"""
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

def init_supabase():
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return create_client(supabase_url, supabase_key)

def main():
    sb = init_supabase()
    
    # Calcular fecha límite (últimos 60 días)
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=60)).date()
    
    # Obtener videos de los últimos 60 días con estadísticas
    response = sb.table('videos') \
        .select('video_id, published_at, video_statistics(snapshot_date, view_count)') \
        .gte('published_at', cutoff_date.isoformat()) \
        .execute()
    
    videos = response.data
    if not videos:
        print("[compute_posting_schedule] No hay videos recientes para analizar")
        return

    # Estructura para almacenar resultados
    schedule_data = {}
    
    for video in videos:
        try:
            # Extraer día y hora de publicación
            published_at = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
            weekday = published_at.weekday()  # 0=Lunes, 6=Domingo
            hour_bucket = published_at.hour // 2  # Bloques de 2 horas (0-11)
            
            # Encontrar estadísticas a las 24h
            next_day = (published_at + timedelta(days=1)).date()
            stats = next((s for s in video.get('video_statistics', []) 
                         if s['snapshot_date'] == next_day.isoformat()), None)
            
            if stats and stats.get('view_count'):
                key = (weekday, hour_bucket)
                schedule_data.setdefault(key, []).append(int(stats['view_count']))
        except Exception as e:
            print(f"Error procesando video {video['video_id']}: {str(e)}")
            continue

    # Calcular promedios y preparar datos para upsert
    upsert_data = []
    for (weekday, hour_bucket), views in schedule_data.items():
        avg_views = sum(views) / len(views)
        upsert_data.append({
            'weekday': weekday,
            'hour_bucket': hour_bucket,
            'avg_views_24h': avg_views
        })

    # Actualizar base de datos
    if upsert_data:
        sb.table('posting_schedule').upsert(upsert_data, on_conflict='weekday,hour_bucket').execute()
    
    print(f"[compute_posting_schedule] Horarios actualizados: {len(upsert_data)} registros")

if __name__ == "__main__":
    main()
