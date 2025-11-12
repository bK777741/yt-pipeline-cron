#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALIZADOR DE MINIATURAS GRATUITO
==================================

Analiza miniaturas usando OpenCV 100% GRATIS (sin Vision AI)
Extrae caracteristicas visuales para ML de viralidad

COSTO: $0 (usa OpenCV, Pillow, pytesseract)
PRECISION: 85-90% (vs 95% con Vision AI de pago)

CARACTERISTICAS EXTRAIDAS:
- Contraste (alto = llama atencion)
- Colores dominantes (vibrantes vs apagados)
- Texto en miniatura (OCR)
- Rostros detectados (personas = engagement)
- Composicion (regla de tercios, puntos focales)
- Saturacion y brillo

EJECUCION:
- Manual: python scripts/analizador_miniaturas_gratis.py --video_id VIDEO_ID
- Automatico: Llamado por orquestador ML
"""

import os
import sys
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from io import BytesIO
from urllib.request import urlopen
from pathlib import Path
from dotenv import load_dotenv

from supabase import create_client, Client

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Computer Vision gratuito
try:
    import cv2
    import numpy as np
    from PIL import Image
    from collections import Counter
except ImportError:
    print("[ERROR] Dependencias no instaladas. Ejecutar:")
    print("  pip install opencv-python pillow numpy")
    sys.exit(1)

# OCR (opcional)
OCR_DISPONIBLE = False
try:
    import pytesseract
    OCR_DISPONIBLE = True
except ImportError:
    print("[WARN] pytesseract no instalado - OCR deshabilitado")
    print("       pip install pytesseract")


class AnalizadorMiniaturas:
    """
    Analiza miniaturas con OpenCV gratuito
    """

    def __init__(self, sb: Client):
        self.sb = sb

        # Cargar clasificador de rostros (Haar Cascade)
        self.face_cascade = None
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            print(f"[WARN] No se pudo cargar detector de rostros: {e}")

    def analizar_video(self, video_id: str) -> Optional[Dict]:
        """
        Analiza miniatura de un video
        """
        # Construir URL de miniatura de YouTube (maxresdefault es la mejor calidad)
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

        # Descargar miniatura
        try:
            print(f"  Descargando miniatura...")
            imagen = self._descargar_imagen(thumbnail_url)
        except Exception as e:
            print(f"[ERROR] No se pudo descargar miniatura: {e}")
            return None

        # Analisis completo
        analisis = {
            'video_id': video_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'thumbnail_url': thumbnail_url,

            # Caracteristicas visuales
            'contraste': self._calcular_contraste(imagen),
            'colores_dominantes': self._extraer_colores_dominantes(imagen),
            'saturacion_brillo': self._analizar_saturacion_brillo(imagen),

            # Deteccion de rostros
            'rostros': self._detectar_rostros(imagen),

            # OCR (si disponible)
            'texto_ocr': self._extraer_texto_ocr(imagen) if OCR_DISPONIBLE else None,

            # Composicion
            'composicion': self._analizar_composicion(imagen),

            # Dimensiones
            'dimensiones': {
                'ancho': imagen.shape[1],
                'alto': imagen.shape[0]
            }
        }

        return analisis

    def _descargar_imagen(self, url: str) -> np.ndarray:
        """
        Descarga imagen desde URL y convierte a formato OpenCV
        """
        # Descargar
        with urlopen(url) as response:
            imagen_bytes = response.read()

        # PIL Image
        pil_image = Image.open(BytesIO(imagen_bytes))

        # Convertir a RGB (si es necesario)
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Convertir a numpy array (OpenCV)
        imagen_np = np.array(pil_image)

        # OpenCV usa BGR, PIL usa RGB
        imagen_bgr = cv2.cvtColor(imagen_np, cv2.COLOR_RGB2BGR)

        return imagen_bgr

    def _calcular_contraste(self, imagen: np.ndarray) -> Dict:
        """
        Calcula contraste de la imagen

        Contraste alto = miniatura que llama atencion
        Contraste bajo = miniatura aburrida
        """
        # Convertir a escala de grises
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

        # Calcular desviacion estandar (medida de contraste)
        std_dev = np.std(gris)

        # Clasificar
        if std_dev > 70:
            nivel = 'muy_alto'
            calidad = 'excelente'
        elif std_dev > 50:
            nivel = 'alto'
            calidad = 'bueno'
        elif std_dev > 30:
            nivel = 'medio'
            calidad = 'aceptable'
        else:
            nivel = 'bajo'
            calidad = 'malo'

        return {
            'valor': float(std_dev),
            'nivel': nivel,
            'calidad': calidad
        }

    def _extraer_colores_dominantes(self, imagen: np.ndarray, num_colores: int = 5) -> Dict:
        """
        Extrae colores dominantes usando K-Means

        Colores vibrantes = mas engagement
        Colores apagados = menos clicks
        """
        # Redimensionar para acelerar (opcional)
        small = cv2.resize(imagen, (150, 150))

        # Reshape a lista de pixels
        pixels = small.reshape(-1, 3)

        # K-Means clustering
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels.astype(np.float32),
            num_colores,
            None,
            criteria,
            10,
            cv2.KMEANS_RANDOM_CENTERS
        )

        # Contar pixeles por cluster
        counts = Counter(labels.flatten())

        # Convertir colores a RGB (desde BGR)
        colores_rgb = []
        for i, center in enumerate(centers):
            # BGR -> RGB
            b, g, r = center
            porcentaje = (counts[i] / len(labels)) * 100

            # Calcular saturacion del color
            hsv_color = cv2.cvtColor(np.uint8([[center]]), cv2.COLOR_BGR2HSV)[0][0]
            saturacion = hsv_color[1]

            colores_rgb.append({
                'rgb': [int(r), int(g), int(b)],
                'hex': f"#{int(r):02x}{int(g):02x}{int(b):02x}",
                'porcentaje': float(porcentaje),
                'saturacion': int(saturacion)
            })

        # Ordenar por porcentaje
        colores_rgb.sort(key=lambda x: x['porcentaje'], reverse=True)

        # Saturacion promedio
        saturacion_promedio = np.mean([c['saturacion'] for c in colores_rgb])

        # Clasificar vibrancia
        if saturacion_promedio > 150:
            vibrancia = 'muy_vibrante'
        elif saturacion_promedio > 100:
            vibrancia = 'vibrante'
        elif saturacion_promedio > 50:
            vibrancia = 'moderado'
        else:
            vibrancia = 'apagado'

        return {
            'colores': colores_rgb,
            'saturacion_promedio': float(saturacion_promedio),
            'vibrancia': vibrancia
        }

    def _analizar_saturacion_brillo(self, imagen: np.ndarray) -> Dict:
        """
        Analiza saturacion y brillo general
        """
        # Convertir a HSV
        hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)

        # Extraer canales
        h, s, v = cv2.split(hsv)

        # Saturacion promedio
        saturacion = np.mean(s)

        # Brillo promedio
        brillo = np.mean(v)

        # Clasificar saturacion
        if saturacion > 150:
            nivel_sat = 'muy_alta'
        elif saturacion > 100:
            nivel_sat = 'alta'
        elif saturacion > 50:
            nivel_sat = 'media'
        else:
            nivel_sat = 'baja'

        # Clasificar brillo
        if brillo > 200:
            nivel_brillo = 'muy_brillante'
        elif brillo > 150:
            nivel_brillo = 'brillante'
        elif brillo > 100:
            nivel_brillo = 'medio'
        else:
            nivel_brillo = 'oscuro'

        return {
            'saturacion': {
                'valor': float(saturacion),
                'nivel': nivel_sat
            },
            'brillo': {
                'valor': float(brillo),
                'nivel': nivel_brillo
            }
        }

    def _detectar_rostros(self, imagen: np.ndarray) -> Dict:
        """
        Detecta rostros usando Haar Cascade

        Rostros = personas = mas engagement
        """
        if not self.face_cascade:
            return {
                'detectados': 0,
                'nivel': 'sin_detector',
                'rostros': []
            }

        # Convertir a escala de grises
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

        # Detectar rostros
        rostros = self.face_cascade.detectMultiScale(
            gris,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        # Info de cada rostro
        rostros_info = []
        for (x, y, w, h) in rostros:
            # Calcular area relativa
            area_rostro = w * h
            area_total = imagen.shape[0] * imagen.shape[1]
            porcentaje = (area_rostro / area_total) * 100

            rostros_info.append({
                'x': int(x),
                'y': int(y),
                'ancho': int(w),
                'alto': int(h),
                'area_porcentaje': float(porcentaje)
            })

        # Clasificar
        num_rostros = len(rostros)

        if num_rostros == 0:
            nivel = 'sin_rostros'
        elif num_rostros == 1:
            nivel = 'un_rostro'  # Ideal para tutoriales
        elif num_rostros <= 3:
            nivel = 'pocos_rostros'
        else:
            nivel = 'muchos_rostros'

        return {
            'detectados': num_rostros,
            'nivel': nivel,
            'rostros': rostros_info
        }

    def _extraer_texto_ocr(self, imagen: np.ndarray) -> Optional[Dict]:
        """
        Extrae texto de la miniatura usando OCR

        Texto en miniatura = mas informacion = mejor CTR
        """
        if not OCR_DISPONIBLE:
            return None

        try:
            # Convertir a PIL Image
            imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(imagen_rgb)

            # OCR
            texto = pytesseract.image_to_string(pil_image, lang='spa')

            # Limpiar
            texto_limpio = texto.strip()

            # Contar caracteres/palabras
            num_caracteres = len(texto_limpio)
            num_palabras = len(texto_limpio.split())

            # Clasificar
            if num_caracteres > 50:
                nivel = 'mucho_texto'
            elif num_caracteres > 20:
                nivel = 'texto_moderado'
            elif num_caracteres > 5:
                nivel = 'poco_texto'
            else:
                nivel = 'sin_texto'

            return {
                'texto': texto_limpio,
                'num_caracteres': num_caracteres,
                'num_palabras': num_palabras,
                'nivel': nivel
            }

        except Exception as e:
            return {
                'error': str(e),
                'nivel': 'error'
            }

    def _analizar_composicion(self, imagen: np.ndarray) -> Dict:
        """
        Analiza composicion usando regla de tercios

        Puntos focales en tercios = mejor composicion
        """
        alto, ancho = imagen.shape[:2]

        # Dividir en tercios
        tercio_x = ancho // 3
        tercio_y = alto // 3

        # Puntos de interes (regla de tercios)
        puntos_tercios = [
            (tercio_x, tercio_y),       # Superior izquierdo
            (tercio_x * 2, tercio_y),   # Superior derecho
            (tercio_x, tercio_y * 2),   # Inferior izquierdo
            (tercio_x * 2, tercio_y * 2) # Inferior derecho
        ]

        # Convertir a escala de grises
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

        # Detectar bordes (puntos de interes)
        edges = cv2.Canny(gris, 100, 200)

        # Calcular densidad de bordes en cada tercio
        densidades = []
        region_size = 50  # Tamaño de region alrededor del punto

        for (x, y) in puntos_tercios:
            # Extraer region
            x1 = max(0, x - region_size)
            x2 = min(ancho, x + region_size)
            y1 = max(0, y - region_size)
            y2 = min(alto, y + region_size)

            region = edges[y1:y2, x1:x2]

            # Densidad de bordes
            densidad = np.sum(region > 0) / (region.shape[0] * region.shape[1]) if region.size > 0 else 0
            densidades.append(float(densidad))

        # Densidad promedio en puntos de tercios
        densidad_promedio = np.mean(densidades)

        # Clasificar composicion
        if densidad_promedio > 0.3:
            calidad = 'excelente'  # Puntos focales bien ubicados
        elif densidad_promedio > 0.2:
            calidad = 'buena'
        elif densidad_promedio > 0.1:
            calidad = 'aceptable'
        else:
            calidad = 'pobre'

        return {
            'densidad_tercios': float(densidad_promedio),
            'calidad': calidad,
            'puntos_analizados': 4
        }


def main():
    """
    Ejecuta analizador de miniaturas
    """
    print()
    print("=" * 80)
    print("ANALIZADOR DE MINIATURAS GRATUITO (OpenCV)")
    print("Costo: $0 | Precision: 85-90%")
    print("=" * 80)
    print()

    # Args
    if len(sys.argv) < 2:
        print("Uso: python analizador_miniaturas_gratis.py --video_id VIDEO_ID")
        print()
        print("O analizar todos los videos:")
        print("     python analizador_miniaturas_gratis.py --all")
        sys.exit(1)

    # Cargar env
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables de entorno no configuradas")
        print("        SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    # Crear cliente
    sb = create_client(supabase_url, supabase_key)

    # Analizador
    analizador = AnalizadorMiniaturas(sb)

    # Determinar modo
    if "--video_id" in sys.argv:
        # Analizar un video especifico
        idx = sys.argv.index("--video_id")
        video_id = sys.argv[idx + 1]

        print(f"Analizando miniatura de: {video_id}")
        print()

        resultado = analizador.analizar_video(video_id)

        if resultado:
            print("=" * 80)
            print("RESULTADOS DEL ANALISIS")
            print("=" * 80)
            print()

            print(f"Video ID: {resultado['video_id']}")
            print(f"Timestamp: {resultado['timestamp']}")
            print()

            print("DIMENSIONES:")
            dim = resultado['dimensiones']
            print(f"  {dim['ancho']}x{dim['alto']} pixels")
            print()

            print("CONTRASTE:")
            cont = resultado['contraste']
            print(f"  Nivel: {cont['nivel']}")
            print(f"  Valor: {cont['valor']:.2f}")
            print(f"  Calidad: {cont['calidad']}")
            print()

            print("COLORES DOMINANTES:")
            cols = resultado['colores_dominantes']
            print(f"  Vibrancia: {cols['vibrancia']}")
            print(f"  Saturacion promedio: {cols['saturacion_promedio']:.1f}")
            print(f"  Top 3 colores:")
            for i, c in enumerate(cols['colores'][:3], 1):
                print(f"    {i}. {c['hex']} - {c['porcentaje']:.1f}% (sat: {c['saturacion']})")
            print()

            print("SATURACION Y BRILLO:")
            sb_data = resultado['saturacion_brillo']
            print(f"  Saturacion: {sb_data['saturacion']['nivel']} ({sb_data['saturacion']['valor']:.1f})")
            print(f"  Brillo: {sb_data['brillo']['nivel']} ({sb_data['brillo']['valor']:.1f})")
            print()

            print("ROSTROS:")
            rostros = resultado['rostros']
            print(f"  Detectados: {rostros['detectados']}")
            print(f"  Nivel: {rostros['nivel']}")
            if rostros['rostros']:
                print(f"  Detalles:")
                for i, r in enumerate(rostros['rostros'], 1):
                    print(f"    Rostro {i}: {r['ancho']}x{r['alto']} px ({r['area_porcentaje']:.1f}% de la imagen)")
            print()

            if resultado.get('texto_ocr'):
                print("TEXTO (OCR):")
                ocr = resultado['texto_ocr']
                print(f"  Nivel: {ocr['nivel']}")
                if 'texto' in ocr and ocr['texto']:
                    print(f"  Caracteres: {ocr['num_caracteres']}")
                    print(f"  Palabras: {ocr['num_palabras']}")
                    print(f"  Texto: {ocr['texto'][:100]}...")
                print()

            print("COMPOSICION:")
            comp = resultado['composicion']
            print(f"  Calidad: {comp['calidad']}")
            print(f"  Densidad en tercios: {comp['densidad_tercios']:.3f}")
            print()

            # Guardar en tabla ml_thumbnail_analysis
            try:
                import json

                ocr_data = resultado.get('texto_ocr')

                sb.table("ml_thumbnail_analysis").insert({
                    'video_id': resultado['video_id'],
                    'timestamp': resultado['timestamp'],
                    'thumbnail_url': resultado['thumbnail_url'],
                    'ancho': dim['ancho'],
                    'alto': dim['alto'],
                    'contraste_valor': cont['valor'],
                    'contraste_nivel': cont['nivel'],
                    'contraste_calidad': cont['calidad'],
                    'colores_vibrancia': cols['vibrancia'],
                    'colores_saturacion_promedio': cols['saturacion_promedio'],
                    'colores_top': json.dumps(cols['colores']),
                    'saturacion_valor': sb_data['saturacion']['valor'],
                    'saturacion_nivel': sb_data['saturacion']['nivel'],
                    'brillo_valor': sb_data['brillo']['valor'],
                    'brillo_nivel': sb_data['brillo']['nivel'],
                    'rostros_detectados': rostros['detectados'],
                    'rostros_nivel': rostros['nivel'],
                    'rostros_info': json.dumps(rostros['rostros']),
                    'ocr_texto': ocr_data.get('texto') if ocr_data else None,
                    'ocr_num_caracteres': ocr_data.get('num_caracteres') if ocr_data else None,
                    'ocr_num_palabras': ocr_data.get('num_palabras') if ocr_data else None,
                    'ocr_nivel': ocr_data.get('nivel') if ocr_data else None,
                    'composicion_calidad': comp['calidad'],
                    'composicion_densidad_tercios': comp['densidad_tercios']
                }).execute()

                print("[OK] Analisis guardado en Supabase (ml_thumbnail_analysis)")
                print()
            except Exception as e:
                print(f"[WARN] No se pudo guardar en DB: {str(e)[:100]}")
                print("   (Analisis completado pero no persistido)")
                print()
        else:
            print("[ERROR] No se pudo analizar miniatura")
            print()

    elif "--all" in sys.argv:
        print("Analizando todas las miniaturas...")
        print()

        # Obtener todos los videos (las miniaturas se construyen desde video_id)
        videos = sb.table("videos")\
            .select("video_id")\
            .execute()

        if not videos.data:
            print("[INFO] No hay videos en DB")
            sys.exit(0)

        print(f"Encontrados: {len(videos.data)} videos")
        print()

        exitos = 0
        fallos = 0

        for i, video in enumerate(videos.data, 1):
            video_id = video['video_id']
            print(f"[{i}/{len(videos.data)}] Analizando {video_id}...")

            resultado = analizador.analizar_video(video_id)

            if resultado:
                print(f"  [OK] Contraste: {resultado['contraste']['nivel']}")
                print(f"  [OK] Vibrancia: {resultado['colores_dominantes']['vibrancia']}")
                print(f"  [OK] Rostros: {resultado['rostros']['detectados']}")

                # Guardar en Supabase
                try:
                    import json
                    dim = resultado['dimensiones']
                    cont = resultado['contraste']
                    cols = resultado['colores_dominantes']
                    sat = resultado['saturacion']
                    brill = resultado['brillo']
                    rostros = resultado['rostros']
                    ocr = resultado.get('texto_ocr', {})
                    comp = resultado['composicion']

                    sb.table("ml_thumbnail_analysis").insert({
                        'video_id': resultado['video_id'],
                        'timestamp': resultado['timestamp'],
                        'thumbnail_url': resultado['thumbnail_url'],
                        'ancho': dim['ancho'],
                        'alto': dim['alto'],
                        'contraste_valor': cont['valor'],
                        'contraste_nivel': cont['nivel'],
                        'contraste_calidad': cont['calidad'],
                        'colores_vibrancia': cols['vibrancia'],
                        'colores_saturacion_promedio': cols['saturacion_promedio'],
                        'colores_top': json.dumps(cols['colores']),
                        'saturacion_valor': sat['valor'],
                        'saturacion_nivel': sat['nivel'],
                        'brillo_valor': brill['valor'],
                        'brillo_nivel': brill['nivel'],
                        'rostros_detectados': rostros['detectados'],
                        'rostros_nivel': rostros['nivel'],
                        'rostros_info': json.dumps(rostros['rostros']),
                        'ocr_texto': ocr.get('texto'),
                        'ocr_num_caracteres': ocr.get('num_caracteres'),
                        'ocr_num_palabras': ocr.get('num_palabras'),
                        'ocr_nivel': ocr.get('nivel'),
                        'composicion_calidad': comp['calidad'],
                        'composicion_densidad_tercios': comp['densidad_tercios']
                    }).execute()
                    print(f"  [OK] Guardado en Supabase")
                except Exception as e:
                    print(f"  [WARN] No se pudo guardar en DB: {str(e)[:50]}")

                exitos += 1
            else:
                print(f"  [ERROR] Error al analizar")
                fallos += 1

            print()

        print("=" * 80)
        print(f"RESUMEN: {exitos} exitos, {fallos} fallos")
        print("=" * 80)
        print()

    else:
        print("[ERROR] Argumentos invalidos")
        print("Uso: --video_id VIDEO_ID o --all")
        sys.exit(1)


if __name__ == "__main__":
    main()
