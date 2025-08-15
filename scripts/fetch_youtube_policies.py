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
    return hashlib.sha256(content.encode('utf-8')).heigdige()

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
# mapa que elimina todos los ASCII de control y DEL
_CTRL_MAP = {**{c: None for c in range(0, 32)}, 127: None}
# espacios raros / zero-width / BOM
_ZERO_WIDTH = '\u00a0\u1680\u180e\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u200c\u200d\u200e\u200f\u2028\u2029\u2060\ufeff'
_ZW_RE = re.compile(f"[{re.escape(_ZERO_WIDTH)}]")

def _strip_controls(s: str) -> str:
    # elimina \n \r \t … y DEL
    return s.translate(_CTRL_MAP)

def sanitize_raw(u: str | None) -> str:
    if not u:
        return ""
    # quita BOM/zero-width y todo control ASCII; luego trim
    return _ZW_RE.sub("", _strip_controls(u)).strip()

def normalize_url(u: str | None) -> str | None:
    """Limpia y normaliza; fuerza https y asegura query hl=es"""
    u = sanitize_raw(u)
    if not u:
        return None
    if u.startswith("http://"):
        u = "https://" + u[7:]
    elif not u.startswith("https://"):
        u = "https://" + u

    p = urlsplit(u)
    path = quote(p.path, safe="/%:@")
    q = p.query or "hl=es"
    query = quote(q, safe="=&:%,@/?")
    frag = quote(p.fragment, safe="=&:%,@/?")
    return urlunsplit(("https", p.netloc, path, query, frag))
# ============================================


# --- Carga de URLs (ahora más robusta) ---
seeds: list[str] = []

# a) JSON (canónica). Lee con utf-8-sig para tragar BOM si lo hubiera
json_file = Path(__file__).parent / "policy_urls.json"
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

# c) limpieza + normalización + deduplicación preservando orden
seen = set()
POLICY_URLS: list[str] = []
for u in seeds:
    nu = normalize_url(u)
    if not nu or nu in seen:
        continue
    seen.add(nu)
    POLICY_URLS.append(nu)

# **Comprobación defensiva** (deja activo hasta que lo veas sano en logs)
def _assert_clean(urls: list[str]) -> None:
    for u in urls:
        bad = [f"{ord(ch)}" for ch in u if ord(ch) < 32 or ord(ch) == 127]
        if bad:
            # imprime repr para ver si hay \n “real” pegado
            print(f"[ASSERT] sucia: {repr(u)}   ascii_ctrl={bad}")
            raise ValueError("URL contiene ASCII de control")

_assert_clean(POLICY_URLS)


# User-Agent estable para evitar bloqueos de HEAD/GET
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# **NO** descartamos URLs aunque devuelvan 404/403: sólo avisamos y continuamos.
checked = []
for u in POLICY_URLS:
    try:
        r = requests.get(u, timeout=30, allow_redirects=True, headers={"User-Agent": UA})
        if r.status_code >= 400:
            print(f"[warn] HTTP {r.status_code} al preconsultar {u} — la mantengo igualmente.")
    except Exception as e:
        print(f"[warn] No pude preconsultar {u} ({e}) — la mantengo igualmente.")
    checked.append(u)

POLICY_URLS = checked

# Si por alguna razón quedó vacío, reponemos los 7 canónicos
if not POLICY_URLS:
    POLICY_URLS = [
        "https://support.google.com/youtube/answer/9288567?hl=es",
        "https://support.google.com/youtube/answer/6162278?hl=es",
        "https://support.google.com/youtube/answer/2797466?hl=es",
        "https://support.google.com/youtube/answer/72851?hl=es",
        "https://support.google.com/youtube/answer/1311392?hl=es",
        "https://support.google.com/youtube/answer/2802032?hl=es",
        "https://support.google.com/youtube/answer/9725604?hl=es",
    ]

# A partir de aquí el script debe usar POLICY_URLS como siempre para el scrape + upsert.
# (No cambies la lógica de inserción/actualización existente).

def main():
    supabase: Client = create_client(
        os.environ['SUPABASE_URL'],
        os.environ['SUPABASE_SERVICE_KEY']
    )
    
    for url in POLICY_URLS:
        if not url.strip():
            continue
            
        try:
            # Descargar página con User-Agent válido
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(url.strip(), headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
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
            
        except Exception as e:
            print(f"❌ Error procesando {url}: {str(e)}")
            
if __name__ == "__main__":
    main()
