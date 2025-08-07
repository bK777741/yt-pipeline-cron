#!/usr/bin/env python3
"""
purge_buffer.py
Borra de Supabase todo lo importado hace más de 60 días.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

def load_env():
    load_dotenv()
    supabase_url = os.environ["SUPABASE_URL"].strip()
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return supabase_url, supabase_key

def init_supabase(supabase_url, supabase_key):
    return create_client(supabase_url, supabase_key)

def purge_table(sb: Client, table: str, date_field: str, days: int):
    threshold = datetime.utcnow() - timedelta(days=days)
    sb.table(table).delete().lt(date_field, threshold.isoformat()).execute()

def main():
    supabase_url, supabase_key = load_env()
    sb = init_supabase(supabase_url, supabase_key)

    purge_table(sb, "videos", "imported_at", 60)
    purge_table(sb, "comments", "checked_at", 60)

    print("[purge_buffer] Purga completada (>60 días)")

if __name__ == "__main__":
    main()

