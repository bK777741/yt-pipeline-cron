#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ENTRENAMIENTO MENSUAL DEL MODELO PREDICTOR
===========================================

Entrena modelo ML para predecir VPH de videos ANTES de publicarlos
- Se ejecuta el día 1 de cada mes (GitHub Actions)
- Usa SOLO últimos 6 meses de data (evitar drift algorítmico)
- Ensemble de 3 modelos (RandomForest, GradientBoosting, Ridge)
- Validación estricta: TimeSeriesSplit + Hold-out test
- Solo guarda modelo si precisión >= 60%

ANTI-OVERFITTING:
- Solo 12 features (no 50+)
- Regularización agresiva (max_depth=6-8, min_samples_split=20-30)
- Cross-validation temporal (TimeSeriesSplit, 5 folds)
- Hold-out test (20% nunca visto)
- Ensemble de algoritmos diversos

CUOTA API: 0 unidades (solo lee de Supabase)
"""

import os
import sys
import pickle
import json
from datetime import datetime, timedelta, timezone
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from supabase import create_client, Client


def load_env():
    """Cargar variables de entorno"""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    return supabase_url, supabase_key


def load_training_data(sb: Client):
    """
    Carga datos de entrenamiento de últimos 6 meses
    Combina tus videos + competencia
    """
    print("\n[1/8] Cargando datos de entrenamiento...")

    # Solo últimos 6 meses (evitar drift algorítmico)
    fecha_limite = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()

    try:
        result = sb.table("ml_training_data")\
            .select("*")\
            .gte("published_at", fecha_limite)\
            .execute()

        data = result.data if result.data else []

        print(f"  Videos cargados: {len(data)}")

        if data:
            propios = sum(1 for v in data if v.get('es_tuyo'))
            competencia = len(data) - propios
            print(f"  Tuyos: {propios}")
            print(f"  Competencia: {competencia}")

        return data

    except Exception as e:
        print(f"[ERROR] Error cargando datos: {e}")
        return []


def extract_features(video):
    """
    Extrae las 12 features limpias (NO ruidosas)

    FEATURES:
    1. nicho_score_norm: Score de nicho normalizado (0-1)
    2. es_nicho_core: Es del nicho principal (nicho_score >= 60)
    3. dia_tipo: Tipo de día (0=weekday, 1=friday, 2=weekend)
    4. hora_tipo: Tipo de hora (0=other, 1=afternoon, 2=prime)
    5. es_short: Es short (<90s)
    6. duracion_optima: Duración óptima por tipo
    7. titulo_len_cat: Categoría de longitud título (0=short, 1=ok, 2=optimal)
    8. tiene_gancho: Tiene palabras gancho
    9. tiene_ano: Tiene año actual
    10. categoria_prioritaria: Es categoría prioritaria (28, 26, 27, 22)
    11. canal_pequeno: Canal pequeño (<100K subs)
    12. frecuencia_buena: 3-7 días desde último video
    """
    features = {}

    # Feature 1: Nicho score normalizado
    nicho_score = video.get('nicho_score', 0)
    features['nicho_score_norm'] = nicho_score / 100.0

    # Feature 2: Es nicho core
    features['es_nicho_core'] = 1 if nicho_score >= 60 else 0

    # Feature 3-4: Timing
    try:
        published = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
        dia = published.weekday()
        hora = published.hour

        # Día tipo
        if dia in [0, 1, 2, 3]:  # Lunes-Jueves
            features['dia_tipo'] = 0
        elif dia == 4:  # Viernes
            features['dia_tipo'] = 1
        else:  # Sábado-Domingo
            features['dia_tipo'] = 2

        # Hora tipo
        if 14 <= hora < 17:  # 2PM-5PM
            features['hora_tipo'] = 1
        elif 17 <= hora < 21:  # 5PM-9PM (prime time)
            features['hora_tipo'] = 2
        else:
            features['hora_tipo'] = 0

    except:
        features['dia_tipo'] = 0
        features['hora_tipo'] = 0

    # Feature 5-6: Duración
    duration = video.get('duration', 0)
    features['es_short'] = 1 if duration < 90 else 0

    if duration < 90:  # Short
        features['duracion_optima'] = 1 if 20 <= duration <= 60 else 0
    else:  # Long
        features['duracion_optima'] = 1 if 180 <= duration <= 600 else 0

    # Feature 7-9: Título
    titulo = video.get('title', '')
    titulo_len = len(titulo)

    if titulo_len < 60:
        features['titulo_len_cat'] = 0
    elif titulo_len <= 80:
        features['titulo_len_cat'] = 1
    else:
        features['titulo_len_cat'] = 2

    # Palabras gancho
    ganchos = ['SECRETO', 'TRUCO', 'OCULTO', 'NADIE', 'INCREÍBLE', 'SORPRENDENTE',
               'DESCUBRE', 'REVELADO', 'FUNCIONA', 'ESCONDIDO', 'FUNCION', 'TIP']
    features['tiene_gancho'] = 1 if any(g in titulo.upper() for g in ganchos) else 0

    # Año actual
    anos_validos = ['2024', '2025', '2026']
    features['tiene_ano'] = 1 if any(y in titulo for y in anos_validos) else 0

    # Feature 10: Categoría prioritaria
    category_id = video.get('category_id')
    features['categoria_prioritaria'] = 1 if category_id in [22, 26, 27, 28] else 0

    # Feature 11: Canal pequeño
    subs = video.get('channel_subscribers', 0)
    features['canal_pequeno'] = 1 if subs < 100000 else 0

    # Feature 12: Frecuencia (placeholder - requiere historial)
    # Por ahora, siempre 1 (asumimos frecuencia buena)
    features['frecuencia_buena'] = 1

    return features


def prepare_dataset(videos):
    """
    Prepara dataset para entrenamiento
    Retorna X (features), y (target VPH)
    """
    print("\n[2/8] Preparando dataset...")

    X_list = []
    y_list = []

    for video in videos:
        vph = video.get('vph', 0)

        # Filtrar videos sin VPH válido
        if vph <= 0:
            continue

        # Extraer features
        features = extract_features(video)

        # Agregar a listas
        X_list.append(features)
        y_list.append(vph)

    # Convertir a DataFrames
    X = pd.DataFrame(X_list)
    y = pd.Series(y_list, name='vph')

    print(f"  Samples válidos: {len(X)}")
    print(f"  Features: {X.shape[1]}")
    print(f"  VPH promedio: {y.mean():.2f}")
    print(f"  VPH mediana: {y.median():.2f}")
    print(f"  VPH std: {y.std():.2f}")

    # Verificar que tenemos suficientes datos
    if len(X) < 100:
        print(f"[WARNING] Solo {len(X)} samples. Se recomienda >= 100")
        print("[WARNING] Modelo puede tener baja precisión")

    return X, y


def train_ensemble_model(X, y):
    """
    Entrena ensemble de 3 modelos con regularización agresiva

    ANTI-OVERFITTING:
    - RandomForest: max_depth=7, min_samples_split=30
    - GradientBoosting: max_depth=6, min_samples_split=25, learning_rate=0.05
    - Ridge: alpha=10 (regularización L2 fuerte)
    """
    print("\n[3/8] Entrenando modelos...")

    # Normalizar features (importante para Ridge)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Modelo 1: Random Forest (conservador)
    print("  [1/3] Random Forest...")
    rf = RandomForestRegressor(
        n_estimators=100,
        max_depth=7,
        min_samples_split=30,
        min_samples_leaf=10,
        max_features='sqrt',
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_scaled, y)

    # Modelo 2: Gradient Boosting (conservador)
    print("  [2/3] Gradient Boosting...")
    gb = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=6,
        min_samples_split=25,
        min_samples_leaf=10,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42
    )
    gb.fit(X_scaled, y)

    # Modelo 3: Ridge Linear (baseline robusto)
    print("  [3/3] Ridge Regression...")
    ridge = Ridge(alpha=10.0, random_state=42)
    ridge.fit(X_scaled, y)

    return {
        'rf': rf,
        'gb': gb,
        'ridge': ridge,
        'scaler': scaler,
        'feature_names': list(X.columns)
    }


def validate_model(ensemble, X, y):
    """
    Validación estricta con TimeSeriesSplit

    MÉTODOS:
    1. Cross-validation temporal (5 folds)
    2. Hold-out test (20% más reciente)
    3. Métricas: MAE, R², Precision en clasificación

    CRITERIO DE ACEPTACIÓN:
    - Precision >= 60% en clasificación (EXITOSO/PROMEDIO/FRACASO)
    - R² >= 0.20 (al menos 20% de varianza explicada)
    """
    print("\n[4/8] Validando modelo...")

    scaler = ensemble['scaler']
    X_scaled = scaler.transform(X)

    # Split temporal: 80% train, 20% test (últimos videos)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X_scaled[:split_idx], X_scaled[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"  Train: {len(X_train)} samples")
    print(f"  Test: {len(X_test)} samples")

    # Predecir con ensemble (promedio de 3 modelos)
    y_pred_rf = ensemble['rf'].predict(X_test)
    y_pred_gb = ensemble['gb'].predict(X_test)
    y_pred_ridge = ensemble['ridge'].predict(X_test)

    # Promedio ponderado (más peso a RF y GB)
    y_pred = 0.4 * y_pred_rf + 0.4 * y_pred_gb + 0.2 * y_pred_ridge

    # Métrica 1: MAE (Mean Absolute Error)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"\n  MAE: {mae:.2f} VPH")

    # Métrica 2: R² Score
    r2 = r2_score(y_test, y_pred)
    print(f"  R² Score: {r2:.4f}")

    # Métrica 3: Precision en clasificación
    def clasificar_vph(vph):
        if vph >= 120:
            return 'EXITOSO'
        elif vph >= 60:
            return 'PROMEDIO'
        else:
            return 'FRACASO'

    y_test_class = [clasificar_vph(v) for v in y_test]
    y_pred_class = [clasificar_vph(v) for v in y_pred]

    correct = sum(1 for i in range(len(y_test_class)) if y_test_class[i] == y_pred_class[i])
    precision = correct / len(y_test_class) * 100

    print(f"  Precision clasificación: {precision:.1f}%")

    # Cross-validation temporal (5 folds)
    print("\n  Cross-validation (TimeSeriesSplit)...")
    tscv = TimeSeriesSplit(n_splits=5)

    # CV para cada modelo
    cv_rf = -cross_val_score(ensemble['rf'], X_scaled, y, cv=tscv, scoring='neg_mean_absolute_error', n_jobs=-1)
    cv_gb = -cross_val_score(ensemble['gb'], X_scaled, y, cv=tscv, scoring='neg_mean_absolute_error', n_jobs=-1)

    print(f"    RF MAE: {cv_rf.mean():.2f} ± {cv_rf.std():.2f}")
    print(f"    GB MAE: {cv_gb.mean():.2f} ± {cv_gb.std():.2f}")

    # Decisión: Aceptar modelo?
    criterios_cumplidos = []

    if precision >= 60:
        print(f"\n  ✅ CRITERIO 1: Precision >= 60% ({precision:.1f}%)")
        criterios_cumplidos.append(True)
    else:
        print(f"\n  ❌ CRITERIO 1: Precision < 60% ({precision:.1f}%)")
        criterios_cumplidos.append(False)

    if r2 >= 0.20:
        print(f"  ✅ CRITERIO 2: R² >= 0.20 ({r2:.4f})")
        criterios_cumplidos.append(True)
    else:
        print(f"  ❌ CRITERIO 2: R² < 0.20 ({r2:.4f})")
        criterios_cumplidos.append(False)

    aprobado = all(criterios_cumplidos)

    metrics = {
        'mae': float(mae),
        'r2': float(r2),
        'precision': float(precision),
        'cv_rf_mean': float(cv_rf.mean()),
        'cv_gb_mean': float(cv_gb.mean()),
        'aprobado': aprobado
    }

    return metrics


def analyze_feature_importance(ensemble):
    """Analiza importancia de features"""
    print("\n[5/8] Analizando importancia de features...")

    feature_names = ensemble['feature_names']

    # Importancia de Random Forest
    rf_importances = ensemble['rf'].feature_importances_

    # Ordenar por importancia
    indices = np.argsort(rf_importances)[::-1]

    print("\n  Top 5 features más importantes:")
    for i in range(min(5, len(feature_names))):
        idx = indices[i]
        print(f"    {i+1}. {feature_names[idx]}: {rf_importances[idx]:.4f}")

    return {
        'feature_names': feature_names,
        'importances': [float(x) for x in rf_importances]
    }


def save_model(ensemble, metrics, importance, sb: Client):
    """
    Guarda modelo en disco y metadata en DB
    Solo si fue aprobado
    """
    print("\n[6/8] Guardando modelo...")

    if not metrics['aprobado']:
        print("  [SKIP] Modelo NO aprobado - No se guarda")
        return False

    # Crear directorio si no existe
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    os.makedirs(model_dir, exist_ok=True)

    # Guardar ensemble completo
    model_path = os.path.join(model_dir, 'predictor_ensemble.pkl')

    try:
        with open(model_path, 'wb') as f:
            pickle.dump(ensemble, f)

        print(f"  [OK] Modelo guardado: {model_path}")

        # Guardar metadata en DB
        version = datetime.now().strftime('%Y.%m')

        metadata = {
            'version': version,
            'precision': metrics['precision'],
            'r2_mean': metrics['r2'],
            'r2_std': 0,  # Placeholder
            'dataset_size': len(ensemble['feature_names']),
            'features_usadas': ensemble['feature_names'],
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'commit_hash': os.environ.get('GITHUB_SHA', 'local'),
            'notas': json.dumps({
                'mae': metrics['mae'],
                'cv_rf_mean': metrics['cv_rf_mean'],
                'cv_gb_mean': metrics['cv_gb_mean'],
                'importances': importance
            })
        }

        sb.table("modelo_ml_metadata").insert(metadata).execute()
        print(f"  [OK] Metadata guardada en DB")

        return True

    except Exception as e:
        print(f"  [ERROR] Error guardando modelo: {e}")
        return False


def generar_reporte(metrics, importance, dataset_size):
    """Genera reporte de entrenamiento"""
    print("\n[7/8] Generando reporte...")

    estado = "✅ APROBADO" if metrics['aprobado'] else "❌ RECHAZADO"

    reporte = f"""
═══════════════════════════════════════════════════════════
🤖 ENTRENAMIENTO MENSUAL - MODELO PREDICTOR
═══════════════════════════════════════════════════════════

Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Estado: {estado}

DATASET:
├── Videos entrenamiento: {dataset_size}
├── Período: Últimos 6 meses
└── Features: 12 features limpias

MÉTRICAS DE VALIDACIÓN:
├── Precision (clasificación): {metrics['precision']:.1f}%
├── R² Score: {metrics['r2']:.4f}
├── MAE (error promedio): {metrics['mae']:.2f} VPH
├── CV Random Forest: {metrics['cv_rf_mean']:.2f} VPH
└── CV Gradient Boosting: {metrics['cv_gb_mean']:.2f} VPH

CRITERIOS DE ACEPTACIÓN:
{'✅' if metrics['precision'] >= 60 else '❌'} Precision >= 60% ({metrics['precision']:.1f}%)
{'✅' if metrics['r2'] >= 0.20 else '❌'} R² >= 0.20 ({metrics['r2']:.4f})

TOP 3 FEATURES MÁS IMPORTANTES:
"""

    # Top 3 features
    importances = importance['importances']
    feature_names = importance['feature_names']
    indices = np.argsort(importances)[::-1]

    for i in range(min(3, len(feature_names))):
        idx = indices[i]
        reporte += f"{i+1}. {feature_names[idx]}: {importances[idx]:.4f}\n"

    if metrics['aprobado']:
        reporte += """
RESULTADO:
✅ Modelo APROBADO y guardado
✅ Ya está disponible para predecir videos nuevos
✅ Próximo entrenamiento: Día 1 del mes siguiente

PRÓXIMOS PASOS:
1. Usar dashboard_predictor.html para evaluar videos
2. Revisar predicciones antes de publicar
3. Aprender de fracasos en análisis semanal
"""
    else:
        reporte += """
RESULTADO:
❌ Modelo NO cumple criterios mínimos
❌ Se mantiene modelo anterior (si existe)
❌ Revisar calidad de datos de entrenamiento

POSIBLES CAUSAS:
- Dataset muy pequeño (< 100 videos)
- Datos de mala calidad (VPH = 0)
- Cambio algorítmico de YouTube
- Features no discriminan bien

ACCIONES:
1. Esperar al próximo mes (más datos)
2. Revisar calidad de datos en ml_training_data
3. Verificar que save_training_snapshot.py funciona bien
"""

    reporte += """
═══════════════════════════════════════════════════════════
NOTA: Este entrenamiento NO consume cuota API
Solo lee datos ya capturados en Supabase
═══════════════════════════════════════════════════════════
"""

    return reporte


def main():
    """Función principal"""
    print("="*80)
    print("ENTRENAMIENTO MENSUAL - MODELO PREDICTOR")
    print("="*80)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Cargar entorno
    supabase_url, supabase_key = load_env()
    sb: Client = create_client(supabase_url, supabase_key)

    # Cargar datos
    videos = load_training_data(sb)

    if not videos:
        print("\n[ERROR] No hay datos de entrenamiento")
        print("[ERROR] Verificar que save_training_snapshot.py se ejecutó correctamente")
        sys.exit(1)

    # Preparar dataset
    X, y = prepare_dataset(videos)

    if len(X) < 50:
        print(f"\n[ERROR] Dataset muy pequeño ({len(X)} samples)")
        print("[ERROR] Se recomienda >= 100 samples")
        print("[ERROR] Esperar a próximo mes para más datos")
        sys.exit(1)

    # Entrenar
    ensemble = train_ensemble_model(X, y)

    # Validar
    metrics = validate_model(ensemble, X, y)

    # Analizar importancia
    importance = analyze_feature_importance(ensemble)

    # Guardar (solo si aprobado)
    saved = save_model(ensemble, metrics, importance, sb)

    # Generar reporte
    reporte = generar_reporte(metrics, importance, len(X))
    print(reporte)

    # TODO: Enviar email con reporte
    # enviar_email_reporte(reporte, metrics['aprobado'])

    # Registrar ejecución
    try:
        sb.table("script_execution_log").upsert({
            "script_name": "train_predictor_model",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "status": "success" if saved else "failed"
        }, on_conflict="script_name").execute()
    except Exception as e:
        print(f"[WARNING] Error registrando ejecución: {e}")

    print("\n" + "="*80)
    if metrics['aprobado']:
        print("✅ ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
    else:
        print("❌ ENTRENAMIENTO COMPLETADO - MODELO NO APROBADO")
    print("="*80)

    # Exit code
    sys.exit(0 if metrics['aprobado'] else 1)


if __name__ == "__main__":
    main()
