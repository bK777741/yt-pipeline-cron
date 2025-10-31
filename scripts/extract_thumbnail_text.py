import os
import pytesseract
from supabase import create_client
from PIL import Image
import requests
from io import BytesIO
import logging
import re
import numpy as np
from datetime import datetime, timezone

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').strip()
SUPABASE_KEY = (os.getenv('SUPABASE_SERVICE_KEY') or '').strip()
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")

BATCH_SIZE = int(os.getenv('BATCH_SIZE_THUMBS', 120))
LANGUAGES = os.getenv('OCR_LANGS', 'spa+eng')
MIN_CONFIDENCE = float(os.getenv('OCR_MIN_CONF', 0.60))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_thumbnails():
    return supabase.table('v_thumbnail_sources') \
        .select('video_id, thumbnail_url') \
        .limit(BATCH_SIZE) \
        .execute().data

def check_existing_text(video_id):
    res = supabase.table('video_thumbnail_text') \
        .select('*', count='exact') \
        .eq('video_id', video_id) \
        .execute()
    return res.count > 0

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def calculate_upper_ratio(data, height):
    upper_count = 0
    total = 0
    
    for i in range(len(data['text'])):
        conf = float(data['conf'][i]) / 100
        if conf < MIN_CONFIDENCE or not data['text'][i].strip():
            continue
            
        # Calcular centro vertical
        y_center = data['top'][i] + data['height'][i] / 2
        
        # Verificar si está en el tercio superior
        if y_center < height / 3:
            upper_count += 1
        total += 1
    
    return upper_count / total if total > 0 else 0.0

def extract_text(image):
    img_array = np.array(image)
    height = img_array.shape[0]
    
    data = pytesseract.image_to_data(
        image, 
        output_type=pytesseract.Output.DICT, 
        lang=LANGUAGES
    )
    
    # Filtrar elementos válidos
    valid_indices = []
    words = []
    confidences = []
    
    for i in range(len(data['text'])):
        conf = float(data['conf'][i]) / 100
        text = data['text'][i].strip()
        
        if conf >= MIN_CONFIDENCE and text:
            valid_indices.append(i)
            words.append(text)
            confidences.append(conf)
    
    # Calcular métricas
    text_full = clean_text(' '.join(words))
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    word_count = len(words)
    upper_ratio = calculate_upper_ratio(data, height)
    
    # Preparar bloques
    blocks = []
    for i in valid_indices:
        blocks.append({
            'text': data['text'][i],
            'confidence': float(data['conf'][i]) / 100,
            'x': data['left'][i],
            'y': data['top'][i],
            'width': data['width'][i],
            'height': data['height'][i]
        })
    
    return {
        'text_full': text_full,
        'ocr_confidence_avg': avg_confidence,
        'word_count': word_count,
        'upper_ratio': upper_ratio,
        'lang': LANGUAGES,
        'blocks': blocks
    }

def save_text(video_id, thumbnail_url, text_data):
    data = {
        'video_id': video_id,
        'thumbnail_url': thumbnail_url,
        'text_full': text_data['text_full'],
        'ocr_confidence_avg': text_data['ocr_confidence_avg'],
        'word_count': text_data['word_count'],
        'upper_ratio': text_data['upper_ratio'],
        'lang': text_data['lang'],
        'blocks': text_data['blocks'],
        'extracted_at': datetime.now(timezone.utc).isoformat()
    }
    
    supabase.table('video_thumbnail_text').insert(data).execute()

def main():
    thumbnails = fetch_thumbnails()
    logging.info(f"Processing {len(thumbnails)} thumbnails for OCR")
    
    for thumb in thumbnails:
        video_id = thumb['video_id']
        thumbnail_url = thumb['thumbnail_url']
        
        try:
            # Saltar si ya existe texto
            if check_existing_text(video_id):
                logging.info(f"Skipping thumbnail {video_id} (text already extracted)")
                continue
                
            response = requests.get(thumbnail_url)
            img = Image.open(BytesIO(response.content))
            text_data = extract_text(img)
            
            if text_data['text_full']:
                save_text(video_id, thumbnail_url, text_data)
                logging.info(f"Extracted text from thumbnail {video_id}")
        except Exception as e:
            logging.error(f"Error processing thumbnail {video_id}: {str(e)}")

if __name__ == '__main__':
    main()
