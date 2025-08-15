import os
import re
import hashlib
import time
import random
import datetime as dt
from urllib.parse import urlparse
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Configuración
MAX_CONTENT_LENGTH = int(os.getenv('POLICY_MAX_CHARS', '12000'))
USER_AGENT = f"Mozilla/5.0 (compatible; PolicyMonitor/1.0; +{os.getenv('CONTACT_EMAIL', '')})"
POLICY_URLS = os.getenv('POLICY_URLS', '').split(',')

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


# ============= Leer y normalizar POLICY_URLS (manteniendo SIEMPRE los 7) =============
RAW = os.getenv("POLICY_URLS", "[]")

try:
    seeds = json.loads(RAW)  # esperamos una lista JSON
except json.JSONDecodeError:
    # fallback por si alguien envió texto separado por comas
    seeds = [u.strip() for u in RAW.split(",") if u.strip()]

def normalize(u: str) -> str | None:
    """
    Normaliza:
      - obliga a https://support.google.com/youtube/...
      - añade hl=en si falta
      - conserva /youtube/answer/<id>
    """
    u = u.strip()
    if not u:
        return None

    p = urllib.parse.urlsplit(u)

    # esquema y dominio
    if p.scheme not in {"http", "https"}:
        return None
    if p.netloc != "support.google.com":
        return None

    # sólo rutas /youtube/
    if not p.path.startswith("/youtube/"):
        return None

    # añade hl=en si no está
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    if not any(k == "hl" for k, _ in q):
        q.append(("hl", "en"))
    new_query = urllib.parse.urlencode(q)

    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, new_query, p.fragment))

# normalizamos, quitamos None y duplicados, manteniendo orden
POLICY_URLS = list(
    dict.fromkeys(
        filter(None, (normalize(u) for u in seeds))
    )
)

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
            headers = {'User-Agent': UA}
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
