import os
import re
import hashlib
import time
import datetime as dt
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Configuración
MAX_CONTENT_LENGTH = int(os.getenv('POLICY_MAX_CHARS', '12000'))
USER_AGENT = f"Mozilla/5.0 (compatible; PolicyMonitor/1.0; +{os.getenv('CONTACT_EMAIL', '')})"
POLICY_URLS = os.getenv('POLICY_URLS', '').split(',')

def get_content_hash(content: str) -> str:
    """Genera hash SHA-256 del contenido"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def extract_category(url: str) -> str:
    """Extrae categoría de política de la URL"""
    categories = {
        'community': 'community',
        'monetization': 'monetization',
        'ad_suitability': 'ad_suitability',
        'copyright': 'copyright',
        'enforcement': 'enforcement',
        'updates': 'updates'
    }
    
    path = urlparse(url).path.lower()
    for key in categories:
        if key in path:
            return categories[key]
    return 'other'

def extract_relevant_text(soup: BeautifulSoup) -> str:
    """Extrae texto relevante de la página"""
    # Eliminar elementos no deseados
    for element in soup(['script', 'style', 'footer', 'nav']):
        element.decompose()
    
    # Extraer encabezados y párrafos principales
    content_parts = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p']):
        if tag.name.startswith('h'):
            content_parts.append(f"\n{tag.get_text().strip()}\n")
        else:
            text = tag.get_text().strip()
            if text and len(text) > 30:  # Filtrar párrafos cortos
                content_parts.append(text)
    
    full_text = '\n'.join(content_parts)
    return full_text[:MAX_CONTENT_LENGTH]

def is_content_old(soup: BeautifulSoup) -> bool:
    """Verifica si el contenido es mayor a 2 años"""
    current_year = dt.datetime.now().year
    text = soup.get_text()
    
    # Buscar años en el texto (ej: 2022, 2023)
    year_matches = re.findall(r'\b(20\d{2})\b', text)
    if year_matches:
        latest_year = max(int(year) for year in year_matches)
        return current_year - latest_year > 2
    
    return False

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
            
            # Verificar antigüedad
            if is_content_old(soup):
                print(f"⚠️ Contenido viejo en {url}, omitiendo...")
                continue
                
            # Procesar contenido
            content = extract_relevant_text(soup)
            content_hash = get_content_hash(content)
            category = extract_category(url)
            
            # Verificar si ya existe este hash para esta URL
            existing = supabase.table('youtube_policies') \
                .select('id') \
                .eq('policy_url', url) \
                .eq('content_hash', content_hash) \
                .execute()
            
            if not existing.data:
                # Insertar nuevo registro si hay cambios
                supabase.table('youtube_policies').insert({
                    'policy_url': url,
                    'category': category,
                    'content_text': content,
                    'content_hash': content_hash
                }).execute()
                print(f"✅ Actualizada política: {url}")
            else:
                # Actualizar fecha de verificación
                supabase.table('youtube_policies') \
                    .update({'last_checked_at': dt.datetime.now().isoformat()}) \
                    .eq('id', existing.data[0]['id']) \
                    .execute()
                print(f"☑️ Política sin cambios: {url}")
            
            # Pausa antibaneo
            time.sleep(4)
            
        except Exception as e:
            print(f"❌ Error procesando {url}: {str(e)}")
            
if __name__ == "__main__":
    main()
