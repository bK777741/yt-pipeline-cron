#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREDICTOR DE VPH PARA VIDEOS NUEVOS
====================================

Script para predecir VPH ANTES de publicar un video
Usa el modelo entrenado mensualmente

USO:
    python predict_video.py --titulo "..." --duracion 300 --dia viernes --hora 18

O interactivo:
    python predict_video.py

SALIDA:
    - VPH predicho
    - Clasificación (EXITOSO/PROMEDIO/FRACASO)
    - Recomendaciones
"""

import os
import sys
import pickle
import argparse
from datetime import datetime
import pandas as pd


def load_model():
    """Carga el modelo entrenado"""
    model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'predictor_ensemble.pkl')

    if not os.path.exists(model_path):
        print("[ERROR] Modelo no encontrado")
        print(f"[ERROR] Ruta: {model_path}")
        print("[INFO] Ejecutar primero: train_predictor_model.py")
        sys.exit(1)

    with open(model_path, 'rb') as f:
        ensemble = pickle.load(f)

    return ensemble


def extract_features_from_input(titulo, duracion, dia, hora, nicho_score=70, category_id=28, subs=50000):
    """
    Extrae las 12 features a partir de input del usuario

    Args:
        titulo (str): Título del video
        duracion (int): Duración en segundos
        dia (str): Día de publicación (lunes, martes, ..., domingo)
        hora (int): Hora de publicación (0-23)
        nicho_score (int): Score de nicho (0-100)
        category_id (int): Categoría de YouTube
        subs (int): Suscriptores del canal
    """
    features = {}

    # Feature 1: Nicho score normalizado
    features['nicho_score_norm'] = nicho_score / 100.0

    # Feature 2: Es nicho core
    features['es_nicho_core'] = 1 if nicho_score >= 60 else 0

    # Feature 3: Día tipo
    dias_map = {
        'lunes': 0, 'martes': 0, 'miercoles': 0, 'miércoles': 0, 'jueves': 0,
        'viernes': 1,
        'sabado': 2, 'sábado': 2, 'domingo': 2
    }
    features['dia_tipo'] = dias_map.get(dia.lower(), 0)

    # Feature 4: Hora tipo
    if 14 <= hora < 17:
        features['hora_tipo'] = 1
    elif 17 <= hora < 21:
        features['hora_tipo'] = 2
    else:
        features['hora_tipo'] = 0

    # Feature 5: Es short
    features['es_short'] = 1 if duracion < 90 else 0

    # Feature 6: Duración óptima
    if duracion < 90:
        features['duracion_optima'] = 1 if 20 <= duracion <= 60 else 0
    else:
        features['duracion_optima'] = 1 if 180 <= duracion <= 600 else 0

    # Feature 7: Longitud título
    titulo_len = len(titulo)
    if titulo_len < 60:
        features['titulo_len_cat'] = 0
    elif titulo_len <= 80:
        features['titulo_len_cat'] = 1
    else:
        features['titulo_len_cat'] = 2

    # Feature 8: Tiene gancho
    ganchos = ['SECRETO', 'TRUCO', 'OCULTO', 'NADIE', 'INCREÍBLE', 'SORPRENDENTE',
               'DESCUBRE', 'REVELADO', 'FUNCIONA', 'ESCONDIDO', 'FUNCION', 'TIP']
    features['tiene_gancho'] = 1 if any(g in titulo.upper() for g in ganchos) else 0

    # Feature 9: Tiene año
    anos_validos = ['2024', '2025', '2026']
    features['tiene_ano'] = 1 if any(y in titulo for y in anos_validos) else 0

    # Feature 10: Categoría prioritaria
    features['categoria_prioritaria'] = 1 if category_id in [22, 26, 27, 28] else 0

    # Feature 11: Canal pequeño
    features['canal_pequeno'] = 1 if subs < 100000 else 0

    # Feature 12: Frecuencia buena
    features['frecuencia_buena'] = 1

    return features


def predict_vph(ensemble, features):
    """Predice VPH usando el ensemble"""
    # Convertir a DataFrame
    X = pd.DataFrame([features])

    # Ordenar columnas según el modelo
    X = X[ensemble['feature_names']]

    # Normalizar
    X_scaled = ensemble['scaler'].transform(X)

    # Predecir con cada modelo
    pred_rf = ensemble['rf'].predict(X_scaled)[0]
    pred_gb = ensemble['gb'].predict(X_scaled)[0]
    pred_ridge = ensemble['ridge'].predict(X_scaled)[0]

    # Promedio ponderado
    vph_pred = 0.4 * pred_rf + 0.4 * pred_gb + 0.2 * pred_ridge

    return max(0, vph_pred)  # No puede ser negativo


def clasificar_vph(vph):
    """Clasifica VPH en categorías"""
    if vph >= 120:
        return 'EXITOSO', '[EXITO]'
    elif vph >= 60:
        return 'PROMEDIO', '[OK]'
    else:
        return 'FRACASO', '[BAJO]'


def generar_recomendaciones(features, titulo, duracion, dia, hora):
    """Genera recomendaciones para mejorar el video"""
    recomendaciones = []

    # Título
    if not features['tiene_gancho']:
        recomendaciones.append("[!] Agregar palabra gancho (SECRETO, TRUCO, OCULTO, etc.)")

    if not features['tiene_ano']:
        recomendaciones.append("[!] Incluir año actual (2025) en título")

    if features['titulo_len_cat'] == 0:
        recomendaciones.append("[!] Título muy corto. Usar 80-100 caracteres")

    # Timing
    if features['dia_tipo'] == 0:
        recomendaciones.append("[!] Mejor día: Viernes o fin de semana")

    if features['hora_tipo'] == 0:
        recomendaciones.append("[!] Mejor hora: 5PM-9PM (prime time)")

    # Duración
    if not features['duracion_optima']:
        if duracion < 90:
            recomendaciones.append("[!] Short óptimo: 20-60 segundos")
        else:
            recomendaciones.append("[!] Long óptimo: 3-10 minutos")

    # Nicho
    if not features['es_nicho_core']:
        recomendaciones.append("[!] Video fuera del nicho principal (score < 60)")

    if not recomendaciones:
        recomendaciones.append("[OK] Video cumple con todas las mejores prácticas")

    return recomendaciones


def interactive_mode():
    """Modo interactivo para input manual"""
    print("="*80)
    print("PREDICTOR DE VPH - MODO INTERACTIVO")
    print("="*80)
    print()

    # Solicitar inputs
    titulo = input("Título del video: ").strip()
    duracion = int(input("Duración (segundos): ").strip())

    print("\nDía de publicación:")
    print("  1. Lunes-Jueves")
    print("  2. Viernes")
    print("  3. Sábado-Domingo")
    dia_opt = input("Opción (1-3): ").strip()
    dia_map = {'1': 'lunes', '2': 'viernes', '3': 'sabado'}
    dia = dia_map.get(dia_opt, 'viernes')

    hora = int(input("Hora de publicación (0-23): ").strip())

    nicho_score = input("Score de nicho (0-100) [default: 70]: ").strip()
    nicho_score = int(nicho_score) if nicho_score else 70

    return titulo, duracion, dia, hora, nicho_score


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Predice VPH de un video antes de publicarlo')
    parser.add_argument('--titulo', type=str, help='Título del video')
    parser.add_argument('--duracion', type=int, help='Duración en segundos')
    parser.add_argument('--dia', type=str, help='Día (lunes, viernes, sabado, etc.)')
    parser.add_argument('--hora', type=int, help='Hora de publicación (0-23)')
    parser.add_argument('--nicho-score', type=int, default=70, help='Score de nicho (0-100)')
    parser.add_argument('--category-id', type=int, default=28, help='Categoría de YouTube')
    parser.add_argument('--subs', type=int, default=50000, help='Suscriptores del canal')

    args = parser.parse_args()

    # Si no hay argumentos, modo interactivo
    if not args.titulo:
        titulo, duracion, dia, hora, nicho_score = interactive_mode()
        category_id = 28
        subs = 50000
    else:
        titulo = args.titulo
        duracion = args.duracion
        dia = args.dia
        hora = args.hora
        nicho_score = args.nicho_score
        category_id = args.category_id
        subs = args.subs

    # Cargar modelo
    print("\n[INFO] Cargando modelo...")
    ensemble = load_model()
    print("[OK] Modelo cargado\n")

    # Extraer features
    features = extract_features_from_input(titulo, duracion, dia, hora, nicho_score, category_id, subs)

    # Predecir
    vph_pred = predict_vph(ensemble, features)
    clasificacion, emoji = clasificar_vph(vph_pred)

    # Recomendaciones
    recomendaciones = generar_recomendaciones(features, titulo, duracion, dia, hora)

    # Mostrar resultados
    print("="*80)
    print("PREDICCIÓN")
    print("="*80)
    print(f"\nTítulo: {titulo}")
    print(f"Duración: {duracion}s ({duracion//60}m {duracion%60}s)")
    print(f"Timing: {dia.capitalize()} a las {hora}:00")
    print()
    print(f"VPH PREDICHO: {vph_pred:.1f}")
    print(f"CLASIFICACIÓN: {clasificacion} {emoji}")
    print()

    if clasificacion == 'EXITOSO':
        print("[EXITO] ¡Excelente! Este video tiene alto potencial")
        print("   Recomendado PUBLICAR")
    elif clasificacion == 'PROMEDIO':
        print("[OK] Video aceptable, pero puede mejorar")
        print("   Considera optimizar según recomendaciones")
    else:
        print("[!] ADVERTENCIA: Alto riesgo de fracaso")
        print("   Recomendado RE-PLANIFICAR antes de publicar")

    print()
    print("="*80)
    print("RECOMENDACIONES")
    print("="*80)
    for rec in recomendaciones:
        print(rec)

    print()
    print("="*80)


if __name__ == "__main__":
    main()
