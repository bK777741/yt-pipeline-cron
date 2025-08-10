import os
import pytesseract
from supabase import create_client
from PIL import Image
import requests
from io import BytesIO
import logging
import re

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
BATCH_SIZE = int(os.getenv('BATCH_SIZE_THUMBS', 120))
LANGUAGES = os.getenv('OCR_LANGS', 'spa+eng')
MIN_CONFIDENCE = float(os.getenv('OCR_MIN_CONF', 0.60))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_unprocessed_thumbnails():
    query = supabase.table('v_thumbnail_sources') \
        .select('id', 'thumbnail_url') \
        .is_('processed_ocr', False) \
        .limit(BATCH_SIZE)
    return query.execute().data

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def extract_text(image):
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang=LANGUAGES)
    text = []
    for i in range(len(data['text'])):
        if float(data['conf'][i]) / 100 > MIN_CONFIDENCE:
            text.append(data['text'][i])
    return clean_text(' '.join(text))

def save_text(thumbnail_id, text):
    if not text:
        return
    data = {
        'thumbnail_id': thumbnail_id,
        'ocr_text': text,
        'extracted_at': datetime.utcnow().isoformat()
    }
    supabase.table('video_thumbnail_text').insert(data).execute()
    # Marcar como procesado
    supabase.table('thumbnails').update({'processed_ocr': True}) \
        .eq('id', thumbnail_id).execute()

def main():
    thumbnails = fetch_unprocessed_thumbnails()
    logging.info(f"Processing {len(thumbnails)} thumbnails for OCR")
    
    for thumb in thumbnails:
        try:
            response = requests.get(thumb['thumbnail_url'])
            img = Image.open(BytesIO(response.content))
            text = extract_text(img)
            save_text(thumb['id'], text)
            logging.info(f"Extracted text from thumbnail {thumb['id']}")
        except Exception as e:
            logging.error(f"Error processing thumbnail {thumb['id']}: {str(e)}")

if __name__ == '__main__':
    main()
