#!/usr/bin/env python3
"""
purge_buffer.py (MODIFICADO)
Ahora incluye backup a Supabase Storage.
"""
import os
import json
import datetime
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

def load_env():
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return supabase_url, supabase_key

def init_supabase(supabase_url, supabase_key):
    return create_client(
        supabase_url, 
        supabase_key,
        options=ClientOptions(storage=ClientOptions.StorageOptions(resumable=False))
    )

def create_backup(sb: Client, table: str, rows):
    if not rows:
        return True
        
    try:
        # Crear bucket si no existe
        try:
            sb.storage.get_bucket("backups")
        except Exception:
            sb.storage.create_bucket("backups", public=False)
        
        # Generar ruta de backup
        today = datetime.date.today().isoformat()
        file_path = f"backups/{table}/{today}/data.ndjson"
        
        # Convertir a NDJSON
        ndjson = "\n".join(json.dumps(row) for row in rows)
        
        # Subir a Storage
        sb.storage.from_("backups").upload(
            file_path,
            ndjson.encode('utf-8'),
            {"content-type": "application/x-ndjson"}
        )
        print(f"Backup creado: {file_path} ({len(rows)} registros)")
        return True
    except Exception as e:
        print(f"Error en backup: {str(e)}")
        return False

def purge_table(sb: Client, table: str, date_field: str, days: int):
    threshold = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    
    # Obtener datos a purgar
    data = sb.table(table).select("*").lt(date_field, threshold.isoformat()).execute()
    
    if not data.data:
        print(f"No hay datos a purgar en {table}")
        return
        
    # Crear backup
    if create_backup(sb, table, data.data):
        # Eliminar si backup fue exitoso
        sb.table(table).delete().lt(date_field, threshold.isoformat()).execute()
        print(f"Purga completada: {table} ({len(data.data)} registros)")
    else:
        print("Purga cancelada por falla en backup")

def main():
    supabase_url, supabase_key = load_env()
    sb = init_supabase(supabase_url, supabase_key)

    purge_table(sb, "videos", "imported_at", 60)
    purge_table(sb, "comments", "checked_at", 60)

    print("[purge_buffer] Proceso completo")

if __name__ == "__main__":
    main()
