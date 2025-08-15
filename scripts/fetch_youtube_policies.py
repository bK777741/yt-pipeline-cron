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

# Configuración
MAX_CONTENT_LENGTH = int(os.getenv('POLICY_MAX_CHARS', '12000'))
USER_AGENT = f"Mozilla/5.0 (compatible; PolicyMonitor/1.0; +{os.getenv('CONTACT_EMAIL', '')})"

# Mapa de categorías por ID
ID_MAP = {
    "9288567": "community",
    "72851":   "monetization",
    "1311392": "monetization",
    "6162278": "ad_suitability",
    "2797466": "copyright",
    "2802032": "enforcement",
    "9725604": "updates"
}

def get_content_hash(content: str) -> str:
    """Genera hash SHA-256 del contenido"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def extract_category(url: str) -> str:
    """Extrae categoría de política de la URL usando ID_MAP"""
    m = re.search(r'/answer/(\d+)', url)
    return ID_MAP.get(m.group(1), "community") if m else "community"

def extract_relevant_text(soup: BeautifulSoup, category: str) -> str:
    """Extrae texto relevante de la página con filtro para actualizaciones"""
    # Eliminar elementos no deseados
    for element in soup(['script', 'style', 'footer', 'nav']):
        element.decompose()
    
    current_year = dt.datetime.now().year
    content_parts = []
    
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p']):
        if tag.name.startswith('h'):
            text = tag.get_text().strip()
            if text:
                content_parts.append(f"\n{text}\n")
        else:
            text = tag.get_text().strip()
            if text and len(text) > 30:
                # Filtrar actualizaciones antiguas
                if category == 'updates':
                    year_matches = re.findall(r'\b(20\d{2})\b', text)
                    if year_matches:
                        latest_year = max(int(year) for year in year_matches)
                        if current_year - latest_year > 2:
                            continue
                content_parts.append(text)
    
    full_text = '\n'.join(content_parts)
    return full_text[:MAX_CONTENT_LENGTH]


# ========== Limpieza fuerte de URLs ==========
# elimina todos los ASCII de control (0-31 y 127)
_CTRL_MAP = {**{c: None for c in range(0, 32)}, 127: None}
# espacios “invisibles” (zero-width, NBSP, BOM…)
_ZERO_WIDTH = '\u00a0\u1680\u180e\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u200c\u200d\u200e\u200f\u2028\u2029\u2060\ufeff'
_ZW_RE = re.compile(f"[{re.escape(_ZERO_WIDTH)}]")

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
# ============================================

seeds: list[str] = []

# a) JSON canónico (lee con utf-8-sig por si hay BOM)
json_file = Path(__file__).parent.parent / "policy_urls.json"
if json_file.exists():
    with open(json_file, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
        if isinstance(data, list):
            seeds.extend(str(x) for x in data)

# b) (opcional) variable de entorno
raw_env = os.getenv("POLICY_URLS", "")
if raw_env:
    parts = [p for p in re.split(r"[, \t\r\n]+", raw_env) if p]
    seeds.extend(parts)

# c) limpieza + normalización + deduplicación
seen = set()
POLICY_URLS: list[str] = []
for raw in seeds:
    url = normalize_url(raw)
    if not url or url in seen:
        continue
    seen.add(url)
    POLICY_URLS.append(url)

# Diagnóstico (déjalo activo hasta que pase en verde)
for u in POLICY_URLS:
    _assert_clean_one(u)

# User-Agent estable para evitar bloqueos de HEAD/GET
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

session = requests.Session()
session.headers.update({'User-Agent': UA})

def main():
    supabase: Client = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_KEY']
    )

    for raw in POLICY_URLS:
        # 1ª limpieza/normalización
        url = normalize_url(raw)

        # 2ª limpieza justo antes de pedir (cinturón y tirantes)
        url = sanitize_raw(url)
        _assert_clean_one(url)
        
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            category = extract_category(url)
            content = extract_relevant_text(soup, category)
            content_hash = get_content_hash(content)
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            
            # Verificar si ya existe este hash para esta URL
            existing = supabase.table('youtube_policies') \
                .select('id') \
                .eq('policy_url', url) \
                .eq('content_hash', content_hash) \
                .execute()
            
            if not existing.data:
                # Insertar nuevo registro con cambios
                supabase.table('youtube_policies').insert({
                    'policy_url': url,
                    'category': category,
                    'content_text': content,
                    'content_hash': content_hash,
                    'fetched_at': now,
                    'last_checked_at': now
                }).execute()
                print(f"✅ Actualizada política: {url}")
            else:
                # Actualizar fecha de verificación
                supabase.table('youtube_policies') \
                    .update({'last_checked_at': now}) \
                    .eq('id', existing.data[0]['id']) \
                    .execute()
                print(f"☑️ Política sin cambios: {url}")
            
            # Pausa antibaneo aleatoria
            time.sleep(random.uniform(3, 5))

        except RequestException as e:
            # Reintento tras limpieza extrema por si algo se coló
            url_retry = sanitize_raw(raw)
            _assert_clean_one(url_retry)
            try:
                resp = session.get(url_retry, timeout=30)
                resp.raise_for_status()
                # Si el reintento funciona, continuar con el upsert
                soup = BeautifulSoup(resp.text, 'html.parser')
                category = extract_category(url)
                content = extract_relevant_text(soup, category)
                content_hash = get_content_hash(content)
                now = dt.datetime.now(dt.timezone.utc).isoformat()
                
                # ... (resto de la lógica de upsert) ...
                print(f"✅ Reintento exitoso para {url}")
            except Exception as e2:
                print(f"❌ Error procesando {url}: {e2}")
                continue
        except Exception as e:
            print(f"❌ Error procesando {url}: {e}")
            
if __name__ == "__main__":
    main()
