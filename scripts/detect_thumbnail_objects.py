import os
import cv2
import numpy as np
from ultralytics import YOLO
from supabase import create_client
from datetime import datetime, timezone
import logging
import requests
from io import BytesIO
from PIL import Image

# Configuración
logging.basicConfig(level=logging.INFO)
SUPABASE_URL = (os.getenv('SUPABASE_URL') or '').strip()
SUPABASE_KEY = (os.getenv('SUPABASE_SERVICE_KEY') or '').strip()
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")

BATCH_SIZE = int(os.getenv('BATCH_SIZE_THUMBS', 120))
MODEL_NAME = os.getenv('OBJ_MODEL', 'yolov8n')
CLASSES_WHITELIST = os.getenv('OBJ_CLASSES_WHITELIST', '').split(',') if os.getenv('OBJ_CLASSES_WHITELIST') else None

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_thumbnails():
    return supabase.table('v_thumbnail_sources') \
        .select('video_id, thumbnail_url') \
        .limit(BATCH_SIZE) \
        .execute().data

def check_existing_objects(video_id):
    res = supabase.table('video_thumbnail_objects') \
        .select('*', count='exact') \
        .eq('video_id', video_id) \
        .execute()
    return res.count > 0

def download_image(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

def calculate_pos_bucket(center_x, center_y, width, height):
    # Horizontal bucket
    if center_x < width / 3:
        h_bucket = 'left'
    elif center_x < 2 * width / 3:
        h_bucket = 'center'
    else:
        h_bucket = 'right'
    
    # Vertical bucket
    if center_y < height / 3:
        v_bucket = 'top'
    elif center_y < 2 * height / 3:
        v_bucket = 'middle'
    else:
        v_bucket = 'bottom'
    
    return f"{h_bucket}-{v_bucket}"

def detect_objects(image):
    model = YOLO(f'{MODEL_NAME}.pt')
    results = model(image, verbose=False)
    detections = []
    
    img_array = np.array(image)
    height, width = img_array.shape[:2]
    total_area = width * height

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = model.names[class_id]
            if CLASSES_WHITELIST and class_name not in CLASSES_WHITELIST:
                continue
                
            confidence = float(box.conf[0])
            bbox = box.xyxy[0].tolist()
            
            # Calcular métricas adicionales
            x_min, y_min, x_max, y_max = bbox
            bbox_width = x_max - x_min
            bbox_height = y_max - y_min
            area = bbox_width * bbox_height
            area_ratio = area / total_area
            
            center_x = (x_min + x_max) / 2
            center_y = (y_min + y_max) / 2
            pos_bucket = calculate_pos_bucket(center_x, center_y, width, height)
            
            detections.append({
                'class': class_name,
                'confidence': confidence,
                'x_min': x_min,
                'y_min': y_min,
                'x_max': x_max,
                'y_max': y_max,
                'area_ratio': area_ratio,
                'pos_bucket': pos_bucket
            })
    return detections

def save_detections(video_id, thumbnail_url, detections):
    data = []
    for detection in detections:
        data.append({
            'video_id': video_id,
            'thumbnail_url': thumbnail_url,
            'class': detection['class'],
            'confidence': detection['confidence'],
            'x_min': detection['x_min'],
            'y_min': detection['y_min'],
            'x_max': detection['x_max'],
            'y_max': detection['y_max'],
            'area_ratio': detection['area_ratio'],
            'pos_bucket': detection['pos_bucket'],
            'detected_at': datetime.now(timezone.utc).isoformat()
        })
    
    if data:
        supabase.table('video_thumbnail_objects').insert(data).execute()

def main():
    thumbnails = fetch_thumbnails()
    logging.info(f"Processing {len(thumbnails)} thumbnails")
    
    for thumb in thumbnails:
        video_id = thumb['video_id']
        thumbnail_url = thumb['thumbnail_url']
        
        try:
            # Saltar si ya existe procesamiento
            if check_existing_objects(video_id):
                logging.info(f"Skipping thumbnail {video_id} (already processed)")
                continue
                
            img = download_image(thumbnail_url)
            detections = detect_objects(np.array(img))
            
            if detections:
                save_detections(video_id, thumbnail_url, detections)
                logging.info(f"Processed thumbnail {video_id} with {len(detections)} objects")
        except Exception as e:
            logging.error(f"Error processing thumbnail {video_id}: {str(e)}")

if __name__ == '__main__':
    main()
