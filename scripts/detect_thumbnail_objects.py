import os
import cv2
import numpy as np
from ultralytics import YOLO
from supabase import create_client
from datetime import datetime
import logging
import requests
from io import BytesIO
from PIL import Image

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
BATCH_SIZE = int(os.getenv('BATCH_SIZE_THUMBS', 120))
MODEL_NAME = os.getenv('OBJ_MODEL', 'yolov8n')
CLASSES_WHITELIST = os.getenv('OBJ_CLASSES_WHITELIST', '').split(',') if os.getenv('OBJ_CLASSES_WHITELIST') else None
MAX_WORKERS = int(os.getenv('MAX_THUMB_WORKERS', 2))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_unprocessed_thumbnails():
    query = supabase.table('v_thumbnail_sources') \
        .select('id', 'thumbnail_url') \
        .is_('processed_objects', False) \
        .limit(BATCH_SIZE)
    return query.execute().data

def download_image(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

def detect_objects(image):
    model = YOLO(f'{MODEL_NAME}.pt')
    results = model(image, verbose=False)
    detections = []
    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            if CLASSES_WHITELIST and class_name not in CLASSES_WHITELIST:
                continue
            confidence = float(box.conf[0])
            bbox = box.xyxy[0].tolist()
            detections.append({
                'class': class_name,
                'confidence': confidence,
                'bbox': bbox
            })
    return detections

def save_detections(thumbnail_id, detections):
    for detection in detections:
        data = {
            'thumbnail_id': thumbnail_id,
            'object_class': detection['class'],
            'confidence': detection['confidence'],
            'x_min': detection['bbox'][0],
            'y_min': detection['bbox'][1],
            'x_max': detection['bbox'][2],
            'y_max': detection['bbox'][3],
            'detected_at': datetime.utcnow().isoformat()
        }
        supabase.table('video_thumbnail_objects').insert(data).execute()
    # Marcar como procesado
    supabase.table('thumbnails').update({'processed_objects': True}) \
        .eq('id', thumbnail_id).execute()

def main():
    thumbnails = fetch_unprocessed_thumbnails()
    logging.info(f"Processing {len(thumbnails)} thumbnails")
    
    for thumb in thumbnails:
        try:
            img = download_image(thumb['thumbnail_url'])
            detections = detect_objects(np.array(img))
            if detections:
                save_detections(thumb['id'], detections)
                logging.info(f"Processed thumbnail {thumb['id']} with {len(detections)} objects")
        except Exception as e:
            logging.error(f"Error processing thumbnail {thumb['id']}: {str(e)}")

if __name__ == '__main__':
    main()
