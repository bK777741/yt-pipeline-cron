#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purge buffer con backup seguro a Supabase Storage.
- Crea bucket 'buffer_backups' si no existe (privado).
- Exporta registros > N días a JSONL (carpeta por fecha).
- Sólo purga si el backup fue exitoso.
- Salida 0 en casos benignos (sin filas a purgar).
"""

import os
import json
import io
import datetime as dt
from typing import List, Dict, Any

from supabase import create_client
from supabase.lib.client_options import ClientOptions
from supabase._sync.storage.client import StorageException  # v2

RETENTION_DAYS_VIDEOS = 60
RETENTION_DAYS_COMMENTS = 60
BUCKET_NAME = "buffer_backups"


def _now_utc():
    return dt.datetime.now(dt.timezone.utc)


def load_env():
    url = os.environ["SUPABASE_URL"].strip().rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return url, key


def init_client(url: str, key: str):
    return create_client(
        url, key,
        options=ClientOptions(postgrest_client_timeout=60_000,
                              storage_client_timeout=60_000)
    )


def ensure_bucket(sb) -> None:
    try:
        buckets = sb.storage.list_buckets()
        if not any(b.name == BUCKET_NAME for b in buckets):
            # bucket privado
            sb.storage.create_bucket(BUCKET_NAME, public=False)
            print(f"[purge_buffer] Bucket '{BUCKET_NAME}' creado.")
        else:
            print(f"[purge_buffer] Bucket '{BUCKET_NAME}' OK.")
    except Exception as e:
        raise RuntimeError(f"No se pudo asegurar el bucket: {e}") from e


def fetch_rows(sb, table: str, ts_col: str, days: int) -> List[Dict[str, Any]]:
    cutoff = (_now_utc() - dt.timedelta(days=days)).isoformat()
    # IMPORTANTE: usar RPC con filtro <= para PostgREST si tu columna es timestamptz
    # Aquí usamos el query builder de supabase-py v2
    res = sb.table(table).select("*").lte(ts_col, cutoff).execute()
    rows = res.data or []
    print(f"[purge_buffer] {table}: {len(rows)} filas > {days} días.")
    return rows


def to_jsonl(rows: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    for r in rows:
        buf.write(json.dumps(r, ensure_ascii=False) + "\n")
    return buf.getvalue().encode("utf-8")


def upload_backup(sb, path: str, payload: bytes) -> None:
    try:
        sb.storage.from_(BUCKET_NAME).upload(
            path=path,
            file=payload,
            file_options={"contentType": "application/json"}
        )
        print(f"[purge_buffer] Backup subido: {path}")
    except StorageException as e:
        # Si ya existe, versionar con sufijo
        if getattr(e, "status_code", None) == 409:
            ts = _now_utc().strftime("%H%M%S")
            alt = path.replace(".jsonl", f"_{ts}.jsonl")
            sb.storage.from_(BUCKET_NAME).upload(
                path=alt,
                file=payload,
                file_options={"contentType": "application/json"}
            )
            print(f"[purge_buffer] Backup existente, guardado como: {alt}")
        else:
            raise
    except Exception as e:
        raise RuntimeError(f"Fallo subiendo backup '{path}': {e}") from e


def delete_rows(sb, table: str, ids: List[Any], id_col="id") -> int:
    if not ids:
        return 0
    res = sb.table(table).delete().in_(id_col, ids).execute()
    count = res.count or 0
    print(f"[purge_buffer] {table}: {count} filas eliminadas.")
    return count


def purge_table(sb, table: str, ts_col: str, days: int, id_col="id") -> None:
    rows = fetch_rows(sb, table, ts_col, days)
    if not rows:
        print(f"[purge_buffer] {table}: nada para purgar.")
        return

    date_prefix = _now_utc().strftime("%Y/%m/%d")
    path = f"{table}/{date_prefix}/{table}-{_now_utc().strftime('%Y%m%d-%H%M%S')}.jsonl"
    payload = to_jsonl(rows)

    # 1) backup
    upload_backup(sb, path, payload)

    # 2) purge (sólo si backup OK)
    ids = [r.get(id_col) for r in rows if r.get(id_col) is not None]
    delete_rows(sb, table, ids, id_col=id_col)


def main():
    try:
        url, key = load_env()
        sb = init_client(url, key)
        ensure_bucket(sb)

        # Ajusta id_col si tus tablas usan otra PK
        purge_table(sb, "videos", "imported_at", RETENTION_DAYS_VIDEOS, id_col="id")
        purge_table(sb, "comments", "checked_at", RETENTION_DAYS_COMMENTS, id_col="id")

        print("[purge_buffer] Proceso completo ✅")
    except KeyError as e:
        print(f"[purge_buffer] Variables de entorno faltantes: {e}")
        # fallo real: debe marcarse rojo
        raise SystemExit(1)
    except Exception as e:
        print(f"[purge_buffer] ERROR no recuperable: {e}")
        # fallo real: debe marcarse rojo
        raise SystemExit(1)


if __name__ == "__main__":
    main()
