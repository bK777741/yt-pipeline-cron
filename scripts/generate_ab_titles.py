#!/usr/bin/env python3
"""
Generador ML de 3 títulos A/B
Analiza top videos del canal y genera variaciones optimizadas
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
import re

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def generate_ab_titles(original_title: str, sb_client) -> dict:
    """
    Genera 3 variaciones de título basadas en patrones exitosos

    Estrategias:
    A) Curiosidad/Gap - "Descubre el secreto de..."
    B) Beneficio/Número - "5 formas de..."
    C) Urgencia/Novedad - "Nuevo método 2025..."
    """

    # Analizar top 20 videos con mejor CTR
    top_videos = sb_client.table("videos")\
        .select("title")\
        .order("view_count", desc=True)\
        .limit(20)\
        .execute()

    # Extraer palabras clave del título original
    keywords = extract_keywords(original_title)

    # Generar variaciones
    variant_a = generate_curiosity_variant(keywords, original_title)
    variant_b = generate_benefit_variant(keywords, original_title)
    variant_c = generate_urgency_variant(keywords, original_title)

    return {
        "original": original_title,
        "variant_a": variant_a,
        "variant_b": variant_b,
        "variant_c": variant_c
    }

def extract_keywords(title: str) -> list:
    """Extrae keywords principales del título"""
    # Remover palabras comunes
    stop_words = ['el', 'la', 'de', 'en', 'y', 'a', 'para', 'como', 'con']
    words = re.findall(r'\w+', title.lower())
    return [w for w in words if w not in stop_words and len(w) > 3][:3]

def generate_curiosity_variant(keywords: list, original: str) -> str:
    """Genera variante de curiosidad"""
    templates = [
        f"Descubre el secreto de {' '.join(keywords[:2])}",
        f"Lo que NADIE te dice sobre {' '.join(keywords[:2])}",
        f"El truco oculto de {' '.join(keywords[:1])} que cambió todo"
    ]
    return templates[0][:100]  # Max 100 chars

def generate_benefit_variant(keywords: list, original: str) -> str:
    """Genera variante de beneficio directo"""
    templates = [
        f"5 formas de {' '.join(keywords[:2])} (la #3 es increíble)",
        f"Cómo {' '.join(keywords[:2])} en 2025 (paso a paso)",
        f"{keywords[0].capitalize()}: La guía definitiva 2025"
    ]
    return templates[0][:100]

def generate_urgency_variant(keywords: list, original: str) -> str:
    """Genera variante de urgencia"""
    templates = [
        f"NUEVO método de {' '.join(keywords[:2])} (2025)",
        f"Esto cambia TODO sobre {' '.join(keywords[:1])}",
        f"{keywords[0].capitalize()} 2025: Lo que necesitas saber YA"
    ]
    return templates[0][:100]

def main():
    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )

    if len(sys.argv) < 2:
        print("Uso: python generate_ab_titles.py 'Título Original'")
        sys.exit(1)

    original_title = sys.argv[1]
    variants = generate_ab_titles(original_title, sb)

    print(f"Original: {variants['original']}")
    print(f"Variante A (Curiosidad): {variants['variant_a']}")
    print(f"Variante B (Beneficio): {variants['variant_b']}")
    print(f"Variante C (Urgencia): {variants['variant_c']}")

if __name__ == "__main__":
    main()
