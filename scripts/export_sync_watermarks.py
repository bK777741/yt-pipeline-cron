# scripts/export_sync_watermarks.py
import os, base64, json, logging
from supabase import create_client
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

# Hardened initialization to prevent errors from malformed env vars
url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

if not url:
    raise SystemExit("Missing or empty SUPABASE_URL")

if not key:
    raise SystemExit("Missing or empty SUPABASE_SERVICE_KEY")

supabase = create_client(url, key)

# Mapeo corregido de columnas de timestamp por tabla
TIMESTAMP_COLUMNS = {
    'videos': 'imported_at',
    'comments': 'imported_at',
    'video_analytics': 'snapshot_date',   # Columna corregida
    'video_thumbnail_objects': 'detected_at',
    'video_thumbnail_text': 'extracted_at',
    'video_trending_filtered': 'created_at',
    'channel_profile_embeddings': 'created_at'
}

# Tablas temporales para pruebas
TABLES = ["videos", "comments", "video_analytics"]

def get_table_watermark(table):
    timestamp_col = TIMESTAMP_COLUMNS.get(table)
    
    if not timestamp_col:
        logging.warning(f"No timestamp column defined for table: {table}")
        return {
            'max_watermark': None,
            'total_rows': 0
        }
    
    # Obtener máximo timestamp
    max_query = supabase.table(table) \
        .select(timestamp_col) \
        .order(timestamp_col, desc=True) \
        .limit(1) \
        .execute()
    
    max_watermark = max_query.data[0][timestamp_col] if max_query.data else None
    
    # Obtener conteo de filas
    count_query = supabase.table(table) \
        .select('*', count='exact') \
        .execute()
    
    total_rows = count_query.count
    
    return {
        'max_watermark': max_watermark,
        'total_rows': total_rows
    }

def save_watermarks(watermarks):
    data = []
    timestamp = datetime.now(timezone.utc).isoformat()
    
    for table, stats in watermarks.items():
        data.append({
            'table_name': table,
            'max_watermark': stats['max_watermark'],
            'total_rows': stats['total_rows'],
            'calculated_at': timestamp
        })
    
    supabase.table('sync_watermarks').upsert(data).execute()

def main():
    watermarks = {}
    
    for table in TABLES:  # Solo procesar tablas temporales
        try:
            stats = get_table_watermark(table)
            watermarks[table] = stats
            logging.info(f"Processed watermark for {table}")
        except Exception as e:
            logging.error(f"Error processing table {table}: {str(e)}")
    
    save_watermarks(watermarks)
    logging.info(f"Exported watermarks for {len(watermarks)} tables")

if __name__ == '__main__':
    main()
