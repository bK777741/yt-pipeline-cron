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
    """
    Carga URLs de políticas Y páginas de nuevas features de YouTube.
    FIX 2025-11-04: Expandido para monitorear features como A/B testing de títulos/thumbnails
    """
    import os, json, re, pathlib
    p = pathlib.Path("scripts/policy_urls.json")

    # URLs base de políticas
    base_urls = []
    if p.exists():
        base_urls = [u.strip() for u in json.loads(p.read_text(encoding="utf-8")) if isinstance(u, str) and u.strip()]
    else:
        raw = os.getenv("POLICY_URLS", "")
        base_urls = [s.strip() for s in re.split(r"[\s,]+", raw) if s.strip()]

    # NUEVO: URLs de features y actualizaciones
    feature_urls = [
        # A/B Testing de títulos y thumbnails
        "https://support.google.com/youtube/answer/12563084?hl=es",  # Test & Compare

        # Creator Studio updates
        "https://support.google.com/youtube/answer/9012010?hl=es",   # YouTube Studio features

        # Algoritmo y recomendaciones
        "https://support.google.com/youtube/answer/7239739?hl=es",   # How search works
        "https://support.google.com/youtube/answer/6002784?hl=es",   # Recommendation system

        # Monetización updates
        "https://support.google.com/youtube/answer/72857?hl=es",     # Advertiser-friendly content
        "https://support.google.com/youtube/answer/9598778?hl=es",   # Shorts monetization

        # Analytics updates
        "https://support.google.com/youtube/answer/9002587?hl=es",   # YouTube Analytics
    ]

    return base_urls + feature_urls

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

def _int_from_env(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)).strip())
        return max(0, v)
    except Exception:
        return default

# Tamaño máximo de texto a guardar (se alinea con tu env del workflow)
POLICY_MAX_CHARS: int = _int_from_env("POLICY_MAX_CHARS", 12000)
# Alias por compatibilidad con código viejo que use MAX_CONTENT_LENGTH
MAX_CONTENT_LENGTH: int = POLICY_MAX_CHARS

def extract_relevant_text(soup, category: str, max_len: int | None = None) -> str:
    """
    Devuelve el texto relevante recortado a max_len. No asume que exista ningún
    global fuera: toma POLICY_MAX_CHARS por defecto si max_len es None.
    """
    if max_len is None:
        max_len = POLICY_MAX_CHARS

    # --- tu lógica de extracción actual (ejemplos) ---
    # 1) intenta seleccionar el cuerpo principal
    nodes = []
    main = soup.select_one("main") or soup.select_one("article")
    if main:
        nodes.append(main.get_text(" ", strip=True))

    # 2) fallback: todo el documento sin scripts/estilos
    if not nodes:
        for s in soup(["script", "style", "noscript"]):
            s.extract()
        nodes.append(soup.get_text(" ", strip=True))

    full_text = " ".join(x for x in nodes if x).strip()
    return full_text[:max_len] if full_text else ""


# ========== PARCHE CATEGORÍA (idempotente) ==========
# Si extract_category no existe en este módulo, la definimos aquí mismo.
try:
    extract_category  # type: ignore
except NameError:
    import re as _re
    _ID_TO_CATEGORY = {
        "9288567": "community_guidelines",
        "6162278": "copyright",
        "2797466": "monetization",
        "72851":   "policies_overview",
        "1311392": "privacy_and_safety",
        "2802032": "metadata_policies",
        "9725604": "advertiser_friendly",
    }
    def extract_category(url: str) -> str:
        if not url:
            return "youtube_policy"
        m = _re.search(r"/answer/(\d+)", url)
        return _ID_TO_CATEGORY.get(m.group(1) if m else None, "youtube_policy")
    print("[DEBUG] extract_category activado en este archivo")
# =====================================================

# User-Agent estable para evitar bloqueos de HEAD/GET
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

session = requests.Session()
session.headers.update({'User-Agent': UA})

def main():
    urls = load_policy_urls()
    print(f"[MAIN] {len(urls)} URLs a procesar")
    print(f"[CFG] POLICY_MAX_CHARS={POLICY_MAX_CHARS}")


    pre = supabase.table("youtube_policies").select("id", count="exact").execute()
    print("COUNT BEFORE:", pre.count)

    for raw in urls:
        url = normalize_url(raw) or ""
        url = scrub_controls(url)
        url = url.splitlines()[0].strip()
        
        try:
            category = extract_category(url)
        except Exception:
            import re as _re
            _m = _re.search(r"/answer/(\d+)", url)
            _id = _m.group(1) if _m else None
            category = {
                "9288567":"community_guidelines",
                "6162278":"copyright",
                "2797466":"monetization",
                "72851":"policies_overview",
                "1311392":"privacy_and_safety",
                "2802032":"metadata_policies",
                "9725604":"advertiser_friendly",
            }.get(_id, "youtube_policy")
            print("[WARN] extract_category faltó en runtime; usando fallback para", url)

        print(f"[URL] {url} -> category={category}")
        print("[URL]", repr(url), [ord(c) for c in url if ord(c) < 32])
        
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            # La categoría ya está definida arriba.
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
