import os
from supabase import create_client
import logging
from datetime import datetime

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

TABLES = [
    'videos', 'comments', 'metrics', 
    'video_thumbnail_objects', 'video_thumbnail_text',
    'video_trending_filtered'
]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_watermarks():
    watermarks = {}
    for table in TABLES:
        try:
            # Obtener máxima fecha de actualización y conteo
            max_date = supabase.rpc(f'get_max_updated_at', {'table_name': table}).execute().data
            count = supabase.table(table).select('count', count=True).execute().count
            
            watermarks[table] = {
                'last_updated': max_date[0]['max'] if max_date else None,
                'total_rows': count
            }
        except Exception as e:
            logging.error(f"Error processing table {table}: {str(e)}")
    return watermarks

def save_watermarks(watermarks):
    data = []
    for table, stats in watermarks.items():
        data.append({
            'table_name': table,
            'last_updated': stats['last_updated'],
            'total_rows': stats['total_rows'],
            'exported_at': datetime.utcnow().isoformat()
        })
    supabase.table('sync_watermarks').upsert(data).execute()

def main():
    watermarks = get_watermarks()
    save_watermarks(watermarks)
    logging.info(f"Exported watermarks for {len(watermarks)} tables")

if __name__ == '__main__':
    main()
