#!/usr/bin/env python3
"""
Convierte subtítulos en guiones estructurados.
"""
import os
import re
import json
import hashlib
import logging
from datetime import datetime, timezone
import unidecode
import language_tool_python
from supabase import create_client, Client

# Configuración básica de logging
logging.basicConfig(level=logging.INFO, format='[convert_captions] %(message)s')
logger = logging.getLogger()

def load_env():
    return {
        "supabase_url": os.environ["SUPABASE_URL"].strip(),
        "supabase_key": os.environ["SUPABASE_SERVICE_KEY"].strip(),
        "lang": os.getenv("SCRIPT_LANG", "es"),
        "max_per_run": int(os.getenv("SCRIPT_MAX_PER_RUN", "20")),
        "ortho_enabled": os.getenv("SCRIPT_ORTHO_ENABLED", "true").lower() == "true",
        "dry_run": os.getenv("SCRIPT_DRY_RUN", "false").lower() == "true"
    }

def init_supabase(url: str, key: str) -> Client:
    return create_client(url, key)

def fetch_videos(sb: Client, lang: str, max_videos: int):
    query = sb.table("captions") \
        .select("video_id, caption_text") \
        .eq("language", lang) \
        .is_("processed_at", None) \
        .order("imported_at", desc=True) \
        .limit(max_videos)
    return query.execute().data

def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def correct_spelling(text: str, lang: str) -> str:
    try:
        tool = language_tool_python.LanguageTool(lang)
        corrected = tool.correct(text)
        tool.close()
        return corrected
    except Exception as e:
        logger.warning(f"Error en corrección ortográfica: {e}")
        return text

def clean_caption(text: str) -> str:
    # Eliminar timestamps (ej: [00:00:00])
    text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', text)
    # Eliminar notas técnicas ([música], ...)
    text = re.sub(r'\[.*?\]', '', text)
    # Eliminar numeración de líneas
    text = re.sub(r'^\d+\s*', '', text, flags=re.MULTILINE)
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def segment_paragraphs(text: str) -> list:
    # Segmentar en párrafos naturales
    segments = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in segments if s.strip()]

def structure_script(paragraphs: list) -> dict:
    # Estructura mínima del guión
    hook = paragraphs[0] if paragraphs else ""
    context = " ".join(paragraphs[1:2]) if len(paragraphs) > 1 else ""
    development = " ".join(paragraphs[2:-1]) if len(paragraphs) > 3 else ""
    closure = paragraphs[-1] if len(paragraphs) > 1 else ""
    
    return {
        "hook": hook,
        "context": context,
        "development": development,
        "closure": closure
    }

def generate_extras(paragraphs: list) -> dict:
    # Generar hooks alternativos (primeras 3 oraciones)
    alt_hooks = paragraphs[:3] if len(paragraphs) >= 3 else paragraphs
    
    # Resumen (primer + último párrafo)
    summary = f"{paragraphs[0]} [...] {paragraphs[-1]}" if len(paragraphs) > 1 else paragraphs[0]
    
    # Frases destacables (oraciones > 15 palabras)
    highlights = [p for p in paragraphs if len(p.split()) > 15][:6]
    
    # Palabras clave (palabras frecuentes > 5 letras)
    word_counts = {}
    for p in paragraphs:
        for word in re.findall(r'\w{5,}', unidecode.unidecode(p.lower())):
            word_counts[word] = word_counts.get(word, 0) + 1
    keywords = sorted(word_counts, key=word_counts.get, reverse=True)[:10]
    
    return {
        "alt_hooks": alt_hooks,
        "summary": summary,
        "highlights": highlights,
        "keywords": keywords
    }

def process_video(video: dict, lang: str, ortho_enabled: bool) -> dict:
    raw_text = video["caption_text"]
    caption_hash = compute_hash(raw_text)
    
    # Paso 1: Corrección ortográfica
    text = correct_spelling(raw_text, lang) if ortho_enabled else raw_text
    
    # Paso 2: Limpieza
    clean_text = clean_caption(text)
    
    # Paso 3: Segmentación
    paragraphs = segment_paragraphs(clean_text)
    
    # Paso 4: Estructuración
    script = structure_script(paragraphs)
    
    # Paso 5: Extras
    extras = generate_extras(paragraphs)
    
    return {
        "video_id": video["video_id"],
        "caption_hash": caption_hash,
        "script": script,
        "extras": extras
    }

def save_script(sb: Client, video_id: str, script_data: dict, dry_run: bool):
    if dry_run:
        logger.info(f"(dry-run) Guion guardado para {video_id}")
        return
    
    sb.table("video_scripts").upsert({
        "video_id": video_id,
        "caption_hash": script_data["caption_hash"],
        "script_data": script_data["script"],
        "extras": script_data["extras"],
        "processed_at": datetime.now(timezone.utc).isoformat()
    }).execute()

def generate_report(processed: list, skipped: list, errors: list) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report = f"# Reporte de Guiones - {date_str}\n\n"
    report += f"- Procesados: {len(processed)}\n"
    report += f"- Omitidos: {len(skipped)}\n"
    report += f"- Errores: {len(errors)}\n\n"
    
    if processed:
        report += "## Videos procesados:\n"
        for p in processed:
            report += f"- {p['video_id']} ({p['duration']:.2f}s)\n"
    
    if errors:
        report += "\n## Errores:\n"
        for e in errors:
            report += f"- {e['video_id']}: {e['error']}\n"
    
    return report

def main():
    config = load_env()
    logger.info(f"Iniciando con config: {config}")
    
    try:
        sb = init_supabase(config["supabase_url"], config["supabase_key"])
        videos = fetch_videos(sb, config["lang"], config["max_per_run"])
    except Exception as e:
        logger.error(f"Error crítico: {e}")
        return  # Exit sin fallar el pipeline

    processed, skipped, errors = [], [], []
    
    for video in videos:
        try:
            result = process_video(video, config["lang"], config["ortho_enabled"])
            save_script(sb, video["video_id"], result, config["dry_run"])
            processed.append({
                "video_id": video["video_id"],
                "duration": len(video["caption_text"]) / 1000  # Tiempo aproximado
            })
        except Exception as e:
            errors.append({"video_id": video["video_id"], "error": str(e)})
            logger.error(f"Error procesando {video['video_id']}: {e}")

    # Generar reporte
    report_content = generate_report(processed, skipped, errors)
    report_filename = f"scripts_report_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
    with open(report_filename, "w") as f:
        f.write(report_content)
    
    logger.info(f"Finalizado. Procesados: {len(processed)}, Errores: {len(errors)}")

if __name__ == "__main__":
    main()
