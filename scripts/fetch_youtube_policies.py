import os
import re
import hashlib
import time
import random
import datetime as dt
from urllib.parse import urlparse
import json
import urllib.parse
from urllib.parse import urlsplit, urlunsplit, quote # Añadido urlsplit y urlunsplit
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


# ======= Limpieza fuerte de URLs (control/BOM/zero-width) =======
# Todos los ASCII de control + DEL
_CONTROL_ASCII = ''.join(chr(c) for c in list(range(0, 32)) + [127])
# Espacios raros / zero-width / BOM
_ZERO_WIDTH = '\u00a0\u1680\u180e\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u200c\u200d\u200e\u200f\u2028\u2029\u2060\ufeff'
_SANITIZER = re.compile(f"[{re.escape(_CONTROL_ASCII + _ZERO_WIDTH)}]")

def sanitize_raw(u: str) -> str:
    """Elimina por completo saltos de línea, BOM y zero-width; además hace strip()."""
    if u is None:
        return ""
    return _SANITIZER.sub("", u).strip()

def normalize_url(u: str) -> str | None:
    """Normaliza la URL ya saneada; siempre devuelve https + query hl=es."""
    u = sanitize_raw(u)
    if not u:
        return None

    # Asegura https
    if u.startswith("http://"):
        u = "https://" + u[7:]
    elif not u.startswith("https://"):
        u = "https://" + u

    # Parse y rehace sin caracteres prohibidos en path/query/fragment
    parts = urlsplit(u)
    path = quote(parts.path, safe="/%:@")
    query = quote(parts.query or "hl=es", safe="=&:%,@/?")
    frag  = quote(parts.fragment, safe="=&:%,@/?")
    return urlunsplit(("https", parts.netloc, path, query, frag))
# ================================================================

# --- Carga de URLs (ahora más robusta) ---
seeds: list[str] = []

# 1) JSON (fuente canónica). Lee con 'utf-8-sig' para comer BOM si lo hubiera.
json_file = Path(__file__).parent / "policy_urls.json"
if json_file.exists():
    with open(json_file, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
        if isinstance(data, list):
            seeds.extend(str(x) for x in data)

# 2) (Opcional) VARIABLE DE ENTORNO, por si acaso alguien la deja puesta.
raw_env = os.getenv("POLICY_URLS", "")
if raw_env:
    # Acepta coma, salto de línea o cualquier whitespace como separador
    parts = [p for p in re.split(r"[, \t\r\n]+", raw_env) if p]
    seeds.extend(parts)

# 3) Saneado fuerte + normalizado + deduplicado preservando orden
seen = set()
POLICY_URLS: list[str] = []
for u in seeds:
    u_norm = normalize_url(u)  # <--- usa SIEMPRE normalize_url (que ya limpia '\n')
    if not u_norm or u_norm in seen:
        continue
    seen.add(u_norm)
    POLICY_URLS.append(u_norm)

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
        "https://support.google.com/youtube/answer/9288567?hl=en",
        "https://support.google.com/youtube/answer/6162278?hl=en",
        "https://support.google.com/youtube/answer/2797466?hl=en",
        "https://support.google.com/youtube/answer/72851?hl=en",
        "https://support.google.com/youtube/answer/1311392?hl=en",
        "https://support.google.com/youtube/answer/2802032?hl=en",
        "https://support.google.com/youtube/answer/9725604?hl=en",
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
