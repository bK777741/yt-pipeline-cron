#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Purge buffer robusto con:
- Paginación (evita timeouts).
- Subida idempotente a Supabase Storage (upsert).
- Reintentos exponenciales en operaciones de red.
- Exit 0 en casos benignos (sin filas a purgar).
"""

import os
import json
import io
import time
import datetime as dt
from typing import List, Dict, Any, Optional, Tuple, Callable

from supabase import create_client, Client

# Import tolerante del StorageException (cambia entre versiones de supabase-py)
try:
    # supabase-py >= 2.4 aprox.
    from supabase.storage.errors import StorageException            # type: ignore
except Exception:
    try:
        # Algunos builds exponen la excepción aquí
        from supabase.lib.storage.types import StorageException     # type: ignore
    except Exception:
        # Si no existe en tu versión, usa Exception genérica
        class StorageException(Exception):
            pass

# Defaults; permite override por ENV si quieres
RETENTION_DAYS_VIDEOS = int(os.getenv("RETENTION_DAYS_VIDEOS", "60"))
RETENTION_DAYS_COMMENTS = int(os.getenv("RETENTION_DAYS_COMMENTS", "60"))
BUCKET_NAME = "buffer_backups"
PAGE_SIZE = 1000            # filas por página
MAX_RETRIES = 3             # reintentos en red
RETRY_BASE_SLEEP = 1.5      # segundos


def _now_utc():
    return dt.datetime.now(dt.timezone.utc)


def _cutoff(days: int) -> str:
    return (_now_utc() - dt.timedelta(days=days)).isoformat()


def _get_env() -> Tuple[str, str]:
    url = os.environ["SUPABASE_URL"].strip().rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"].strip()
    return url, key


def _sb() -> Client:
    url, key = _get_env()
    return create_client(url, key)


def _retry(fn: Callable[[], Any], what: str):
    last = None
    for i in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            sleep = RETRY_BASE_SLEEP * (2 ** (i - 1))
            print(f"[purge_buffer] {what} fallo intento {i}/{MAX_RETRIES}: {e} -> retry en {sleep:.1f}s")
            time.sleep(sleep)
    raise last


def ensure_bucket(sb) -> None:
    def _work():
        buckets = sb.storage.list_buckets()
        if not any(b.name == BUCKET_NAME for b in buckets):
            # CORREGIDO: Se crea el bucket sin el argumento 'public' para evitar TypeError
            sb.storage.create_bucket(BUCKET_NAME)
            print(f"[purge_buffer] Bucket '{BUCKET_NAME}' creado.")
        else:
            print(f"[purge_buffer] Bucket '{BUCKET_NAME}' OK.")
    _retry(_work, "ensure_bucket")


def fetch_rows_paged(sb, table: str, ts_col: str, days: int) -> List[Dict[str, Any]]:
    cutoff = _cutoff(days)
    all_rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        def _page():
            # count="exact" sólo para logging; no es crítico
            res = sb.table(table).select("*").lte(ts_col, cutoff)\
                    .range(offset, offset + PAGE_SIZE - 1).execute()
            return res.data or []

        rows = _retry(_page, f"select {table} page offset={offset}")
        if not rows:
            break
        all_rows.extend(rows)
        print(f"[purge_buffer] {table}: pagina offset={offset} -> {len(rows)} filas")
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    print(f"[purge_buffer] {table}: total {len(all_rows)} filas <= cutoff {cutoff}")
    return all_rows


def to_jsonl(rows: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    for r in rows:
        buf.write(json.dumps(r, ensure_ascii=False) + "\n")
    return buf.getvalue().encode("utf-8")


def upload_backup(sb, path: str, payload: bytes) -> None:
    def _work():
        # upsert=True evita colisiones si se repite el nombre
        sb.storage.from_(BUCKET_NAME).upload(
            path=path,
            file=payload,
            file_options={"contentType": "application/json"},
            upsert=True
        )
        print(f"[purge_buffer] Backup subido: {path}")
    try:
        _retry(_work, f"upload {path}")
    except (StorageException, Exception) as e:
        raise RuntimeError(f"Fallo subiendo backup '{path}': {e}") from e


def delete_rows(sb, table: str, ids: List[Any], id_col="id") -> int:
    if not ids:
        print(f"[purge_buffer] {table}: no hay IDs que eliminar.")
        return 0

    def _work():
        # Nota: supabase v2 no devuelve count por defecto en delete.
        # Usamos len(data) como proxy.
        res = sb.table(table).delete().in_(id_col, ids).execute()
        return len(res.data or [])

    deleted = _retry(_work, f"delete {table}")
    print(f"[purge_buffer] {table}: {deleted} filas eliminadas.")
    return deleted


def purge_table(sb, table: str, ts_col: str, days: int, id_col="id") -> None:
    rows = fetch_rows_paged(sb, table, ts_col, days)
    if not rows:
        print(f"[purge_buffer] {table}: nada para purgar.")
        return

    date_prefix = _now_utc().strftime("%Y/%m/%d")
    path = f"{table}/{date_prefix}/{table}-{_now_utc().strftime('%Y%m%d-%H%M%S')}.jsonl"
    payload = to_jsonl(rows)

    upload_backup(sb, path, payload)

    ids = [r.get(id_col) for r in rows if r.get(id_col) is not None]
    delete_rows(sb, table, ids, id_col=id_col)


def main():
    try:
        sb = _sb()
        ensure_bucket(sb)

        purge_table(sb, "videos",   "imported_at", RETENTION_DAYS_VIDEOS,   id_col="id")
        purge_table(sb, "comments", "checked_at",  RETENTION_DAYS_COMMENTS, id_col="id")

        print("[purge_buffer] Proceso completo ✅")
        raise SystemExit(0)
    except KeyError as e:
        print(f"[purge_buffer] Variables de entorno faltantes: {e}")
        raise SystemExit(1)
    except Exception as e:
        print(f"[purge_buffer] ERROR no recuperable: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
