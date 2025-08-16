import os
import re
import hashlib
import time
import random
import datetime as dt
from urllib.parse import urlparse
import json
import urllib.parse
from urllib.parse import urlsplit, urlunsplit, quote
from pathlib import Path
import requests
from requests import RequestException
from bs4 import BeautifulSoup
from supabase import create_client, Client
from datetime import datetime, timezone

# --- pega esto en fetch_youtube_policies.py ---
import hashlib
import datetime as dt

TABLE = "youtube_policies"

def now_utc_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

def save_policy(supabase, url: str, category: str, content_text: str):
    content_text = (content_text or "").strip()
    h = hash_text(content_text)
    now = now_utc_iso()

    print(f"[SAVE] Upsert → {url} (cat={category}, chars={len(content_text)})")

    try:
        existing = supabase.table(TABLE).select("id, content_hash").eq("policy_url", url).limit(1).execute()
    except Exception as e:
        print(f"❌ SELECT error {url}: {e}")
        return

    if existing.data:
        row = existing.data[0]
        if row["content_hash"] == h:
            try:
                res = supabase.table(TABLE).update({"last_checked_at": now}).eq("id", row["id"]).execute()
                if getattr(res, "error", None):
                    print(f"❌ update last_checked_at ERROR {url}: {res.error}")
                else:
                    print(f"☑️ Sin cambios (last_checked_at) {url}")
            except Exception as e:
                print(f"❌ update last_checked_at EXCEPTION {url}: {e}")
            return

        payload = {
            "category": category,
            "content_text": content_text,
            "content_hash": h,
            "fetched_at": now,
            "last_checked_at": now,
        }
        try:
            res = supabase.table(TABLE).update(payload).eq("id", row["id"]).execute()
            if getattr(res, "error", None):
                print(f"❌ update ERROR {url}: {res.error}")
            else:
                print(f"🔁 Actualizada {url}")
        except Exception as e:
            print(f"❌ update EXCEPTION {url}: {e}")
        return

    payload = {
        "policy_url": url,
        "category": category,
        "content_text": content_text,
        "content_hash": h,
        "fetched_at": now,
        "last_checked_at": now,
    }
    try:
        res = supabase.table(TABLE).upsert(payload, on_conflict="policy_url").execute()
        if getattr(res, "error", None):
            print(f"❌ upsert ERROR {url}: {res.error}")
        else:
            print(f"➕ Insertada {url}")
    except Exception as e:
        print(f"❌ upsert EXCEPTION {url}: {e}")

def load_policy_urls():
    import os, json, re, pathlib
    p = pathlib.Path("scripts/policy_urls.json")
    if p.exists():
        return [u.strip() for u in json.loads(p.read_text(encoding="utf-8")) if isinstance(u, str) and u.strip()]
    raw = os.getenv("POLICY_URLS", "")
    return [s.strip() for s in re.split(r"[\s,]+", raw) if s.strip()]

def _clean_base_url(raw: str) -> str:
    # Quita CR/LF y espacios, remueve barras finales, añade https:// si falta
    base = (raw or "").strip().rstrip("/")
    if base and not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base

SUPABASE_URL = _clean_base_url(os.environ.get("SUPABASE_URL", ""))
SUPABASE_SERVICE_KEY = (os.environ.get("SUPABASE_SERVICE_KEY", "")).strip()

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL vacío después de limpiar; revisa el secreto.")
if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY vacío; revisa el secreto.")

# (Opcional) imprime el host para depurar (GitHub oculta la URL completa)
try:
    host = SUPABASE_URL.split("://", 1)[1].split("/", 1)[0]
    print(f"[DEBUG] Supabase host: {host}")
except Exception:
    pass

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ========== Limpieza fuerte de URLs ==========
# elimina todos los ASCII de control (0-31 y 127)
_CTRL_MAP = {**{c: None for c in range(0, 32)}, 127: None}
# espacios “invisibles” (zero-width, NBSP, BOM…)
_ZERO_WIDTH = '\u00a0\u1680\u180e\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u200c\u200d\u200e\u200f\u2028\u2029\u2060\ufeff'
_ZW_RE = re.compile(f"[{re.escape(_ZERO_WIDTH)}]")

def _strip_controls(s: str) -> str:
    # elimina \n \r \t … y DEL
    return s.translate(_CTRL_MAP)

def sanitize_raw(u: str | None) -> str:
    """Limpieza AGRESIVA: quita controles, zero-width y TODO whitespace (incluye \n)."""
    if not u:
        return ""
    # quita zero-width
    u = _ZW_RE.sub("", u)
    # quita \r \n \t explícitos
    u = u.replace("\r", "").replace("\n", "").replace("\t", "")
    # elimina cualquier whitespace restante (incluye varios Unicode)
    u = "".join(u.split())
    # elimina ASCII de control
    u = u.translate(_CTRL_MAP)
    return u.strip()

def normalize_url(u: str | None) -> str | None:
    """Normaliza y asegura https + hl=es"""
    u = sanitize_raw(u)
    if not u:
        return None
    if u.startswith("http://"):
        u = "https://" + u[7:]
    elif not u.startswith("https://"):
        u = "https://" + u

    p = urlsplit(u)
    path  = quote(p.path, safe="/%:@")
    query = p.query or "hl=es"
    query = quote(query, safe="=&:%,@/?")
    frag  = quote(p.fragment, safe="=&:%,@/?")
    return urlunsplit(("https", p.netloc, path, query, frag))

def _assert_clean_one(u: str):
    """Imprime diagnóstico si queda algún control char."""
    bad = [f"{i}:{ord(ch)}" for i, ch in enumerate(u) if ord(ch) < 32 or ord(ch) == 127]
    if bad:
        print(f"[DBG] control chars -> {bad}  URL={repr(u)}")

def scrub_controls(s: str) -> str:
    # elimina \r \n y cualquier control ASCII; además, aplana a una sola línea
    s = s.replace("\r", "").replace("\n", "")
    s = "".join(ch for ch in s if 32 <= ord(ch) <= 126 or ch in "/:?&=%._-#")
    return s

# ============================================

# User-Agent estable para evitar bloqueos de HEAD/GET
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

session = requests.Session()
session.headers.update({'User-Agent': UA})

def main():
    urls = load_policy_urls()
    print(f"[MAIN] {len(urls)} URLs a procesar")

    pre = supabase.table("youtube_policies").select("id", count="exact").execute()
    print("COUNT BEFORE:", pre.count)

    for raw in urls:
        url = normalize_url(raw) or ""
        url = scrub_controls(url)
        url = url.splitlines()[0].strip()
        print("[URL]", repr(url), [ord(c) for c in url if ord(c) < 32])
        
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            category = extract_category(url)
            content_text = extract_relevant_text(soup, category)

            save_policy(supabase, url=url, category=category, content_text=content_text)
            
            # Pausa antibaneo aleatoria
            time.sleep(random.uniform(3, 5))

        except RequestException as e:
            print(f"❌ Error procesando {url}: {e}")
            
    post = supabase.table("youtube_policies").select("id", count="exact").execute()
    print("COUNT AFTER:", post.count)
    print("[MAIN] DONE")

if __name__ == "__main__":
    main()
