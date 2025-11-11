#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMULADOR DE PRE-PUBLICACION
=============================

Predice CTR y retencion ANTES de publicar
Analiza multiples combinaciones de titulos/miniaturas
Recomienda la mejor opcion

VENTAJA: Evita publicar videos destinados a fracasar
COSTO: $0 (usa modelos ML locales)

PROCESO:
1. Ingresar multiples opciones de titulos/miniaturas
2. Analizar cada combinacion con NLP + OpenCV
3. Predecir CTR y retencion usando modelos ML
4. Simular respuesta de diferentes clusters de audiencia
5. Recomendar mejor combinacion

EJECUCION:
- Manual: python scripts/simulador_prepublicacion.py
- Interactivo: Ingresar opciones y obtener predicciones
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from supabase import create_client, Client

# ML gratuito
try:
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import Ridge
    import pickle
except ImportError:
    print("[ERROR] Dependencias no instaladas. Ejecutar:")
    print("  pip install numpy scikit-learn")
    sys.exit(1)


class SimuladorPrePublicacion:
    """
    Simula rendimiento de video ANTES de publicar
    """

    def __init__(self, sb: Client):
        self.sb = sb

        # Cargar config del nicho
        self.config = self._cargar_config_nicho()

        # Cargar modelos ML (si existen)
        self.modelo_ctr = self._cargar_modelo('ctr')
        self.modelo_retencion = self._cargar_modelo('retencion')

        # Cargar benchmarks del canal
        self.benchmarks = self._cargar_benchmarks()

        # Cargar patrones de exito (si existen)
        self.patrones_exito = self._cargar_patrones_exito()

    def simular_combinacion(
        self,
        titulo: str,
        descripcion_miniatura: Dict,  # Caracteristicas de miniatura
        duracion_minutos: float,
        hora_publicacion: Optional[int] = None
    ) -> Dict:
        """
        Simula rendimiento de una combinacion titulo+miniatura
        """
        # Extraer caracteristicas del titulo
        features_titulo = self._extraer_features_titulo(titulo)

        # Combinar todas las caracteristicas
        features = {
            **features_titulo,
            **descripcion_miniatura,
            'duracion_minutos': duracion_minutos,
            'hora_publicacion': hora_publicacion or datetime.now().hour
        }

        # Prediccion de CTR
        ctr_predicho = self._predecir_ctr(features)

        # Prediccion de retencion
        retencion_predicha = self._predecir_retencion(features, duracion_minutos)

        # Prediccion de VPH (basado en CTR y retencion)
        vph_predicho = self._predecir_vph(ctr_predicho, retencion_predicha, features)

        # Score de nicho
        score_nicho = self._calcular_score_nicho(titulo)

        # Similitud con patrones exitosos
        similitud_patrones = self._calcular_similitud_patrones(titulo, features)

        # Simulacion por cluster de audiencia
        simulacion_clusters = self._simular_clusters(features, ctr_predicho, retencion_predicha)

        # Recomendacion final
        recomendacion = self._generar_recomendacion(
            ctr_predicho,
            retencion_predicha,
            vph_predicho,
            score_nicho,
            similitud_patrones
        )

        return {
            'titulo': titulo,
            'timestamp': datetime.now(timezone.utc).isoformat(),

            # Predicciones principales
            'predicciones': {
                'ctr': ctr_predicho,
                'retencion': retencion_predicha,
                'vph': vph_predicho
            },

            # Metricas de nicho
            'score_nicho': score_nicho,
            'similitud_patrones': similitud_patrones,

            # Simulacion por clusters
            'clusters': simulacion_clusters,

            # Recomendacion
            'recomendacion': recomendacion,

            # Features usadas
            'features': features
        }

    def comparar_combinaciones(self, combinaciones: List[Dict]) -> Dict:
        """
        Compara multiples combinaciones y rankea
        """
        resultados = []

        print()
        print("=" * 80)
        print("SIMULANDO COMBINACIONES...")
        print("=" * 80)
        print()

        for i, combo in enumerate(combinaciones, 1):
            print(f"[{i}/{len(combinaciones)}] Analizando: {combo['titulo'][:50]}...")

            resultado = self.simular_combinacion(
                titulo=combo['titulo'],
                descripcion_miniatura=combo.get('miniatura', {}),
                duracion_minutos=combo.get('duracion_minutos', 10)
            )

            resultados.append(resultado)

        # Ordenar por score compuesto
        resultados.sort(
            key=lambda x: (
                x['predicciones']['vph'] * 0.5 +
                x['predicciones']['ctr'] * 100 * 0.3 +
                x['predicciones']['retencion'] * 0.2
            ),
            reverse=True
        )

        print()
        print("=" * 80)
        print("RANKING DE COMBINACIONES")
        print("=" * 80)
        print()

        for i, res in enumerate(resultados, 1):
            pred = res['predicciones']
            rec = res['recomendacion']

            print(f"#{i}. {res['titulo'][:60]}")
            print(f"    VPH predicho: {pred['vph']:.1f}")
            print(f"    CTR predicho: {pred['ctr']:.2%}")
            print(f"    Retención: {pred['retencion']:.1f}%")
            print(f"    Recomendación: {rec['decision']} ({rec['confianza']:.0%})")
            print()

        # Mejor combinacion
        mejor = resultados[0]

        return {
            'mejor_combinacion': mejor,
            'todas_combinaciones': resultados,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _extraer_features_titulo(self, titulo: str) -> Dict:
        """
        Extrae caracteristicas del titulo
        """
        palabras = titulo.lower().split()

        # Longitud
        num_caracteres = len(titulo)
        num_palabras = len(palabras)

        # Palabras en mayusculas (enfasis)
        palabras_mayus = sum(1 for p in titulo.split() if p.isupper())

        # Numeros (tips, listas)
        tiene_numeros = any(c.isdigit() for c in titulo)

        # Signos de exclamacion/interrogacion
        tiene_exclamacion = '!' in titulo or '¡' in titulo
        tiene_pregunta = '?' in titulo or '¿' in titulo

        # Emojis (aproximado)
        tiene_emoji = any(ord(c) > 127 for c in titulo)

        # Palabras clave del nicho
        keywords_nicho = self.config.get('keywords_oro', {})
        score_nicho = sum(
            keywords_nicho.get(palabra, 0)
            for palabra in palabras
        )

        return {
            'titulo_num_caracteres': num_caracteres,
            'titulo_num_palabras': num_palabras,
            'titulo_palabras_mayus': palabras_mayus,
            'titulo_tiene_numeros': 1 if tiene_numeros else 0,
            'titulo_tiene_exclamacion': 1 if tiene_exclamacion else 0,
            'titulo_tiene_pregunta': 1 if tiene_pregunta else 0,
            'titulo_tiene_emoji': 1 if tiene_emoji else 0,
            'titulo_score_nicho': score_nicho
        }

    def _predecir_ctr(self, features: Dict) -> float:
        """
        Predice CTR usando modelo ML (o heuristica si no hay modelo)
        """
        if self.modelo_ctr:
            # Usar modelo entrenado
            try:
                X = self._features_dict_to_array(features, 'ctr')
                ctr = self.modelo_ctr.predict([X])[0]
                return max(0.0, min(1.0, ctr))  # Clamp entre 0-1
            except Exception as e:
                print(f"[WARN] Error al usar modelo CTR: {e}")

        # Heuristica simple (baseline)
        ctr_base = 0.04  # 4% baseline

        # Ajustar por caracteristicas
        multiplicador = 1.0

        # Titulo corto = mejor
        if features.get('titulo_num_caracteres', 0) < 50:
            multiplicador *= 1.2

        # Titulo con pregunta = mejor
        if features.get('titulo_tiene_pregunta', 0) == 1:
            multiplicador *= 1.15

        # Titulo con numero = mejor
        if features.get('titulo_tiene_numeros', 0) == 1:
            multiplicador *= 1.1

        # Alto score nicho = mejor
        score_nicho = features.get('titulo_score_nicho', 0)
        if score_nicho > 50:
            multiplicador *= 1.3
        elif score_nicho > 30:
            multiplicador *= 1.15

        # Contraste miniatura alto = mejor
        contraste = features.get('contraste_valor', 50)
        if contraste > 70:
            multiplicador *= 1.2
        elif contraste > 50:
            multiplicador *= 1.1

        # Rostros en miniatura = mejor
        num_rostros = features.get('rostros_detectados', 0)
        if num_rostros == 1:
            multiplicador *= 1.15  # Ideal para tutoriales

        ctr_predicho = ctr_base * multiplicador

        return min(ctr_predicho, 0.20)  # Cap al 20%

    def _predecir_retencion(self, features: Dict, duracion_minutos: float) -> float:
        """
        Predice retencion promedio
        """
        if self.modelo_retencion:
            # Usar modelo entrenado
            try:
                X = self._features_dict_to_array(features, 'retencion')
                retencion = self.modelo_retencion.predict([X])[0]
                return max(0.0, min(100.0, retencion))
            except Exception as e:
                print(f"[WARN] Error al usar modelo retencion: {e}")

        # Heuristica simple
        retencion_base = 45.0  # 45% baseline

        # Ajustar por duracion (videos mas cortos = mejor retencion)
        if duracion_minutos < 3:
            multiplicador = 1.3
        elif duracion_minutos < 5:
            multiplicador = 1.2
        elif duracion_minutos < 10:
            multiplicador = 1.1
        elif duracion_minutos < 15:
            multiplicador = 1.0
        else:
            multiplicador = 0.9

        # Score de nicho alto = mejor retencion
        score_nicho = features.get('titulo_score_nicho', 0)
        if score_nicho > 50:
            multiplicador *= 1.1

        retencion_predicha = retencion_base * multiplicador

        return min(retencion_predicha, 90.0)  # Cap al 90%

    def _predecir_vph(self, ctr: float, retencion: float, features: Dict) -> float:
        """
        Predice VPH basado en CTR y retencion
        """
        # Formula aproximada: VPH correlaciona con CTR * retencion
        # Normalizado por benchmarks del canal

        # CTR y retencion como factores
        factor_ctr = ctr / 0.05  # Normalizado a 5% CTR promedio
        factor_retencion = retencion / 50  # Normalizado a 50% retencion promedio

        # VPH base del canal (promedio historico)
        vph_base = self.benchmarks.get('vph_promedio', 50)

        # Calcular VPH predicho
        vph_predicho = vph_base * factor_ctr * factor_retencion

        # Ajustar por hora de publicacion
        hora = features.get('hora_publicacion', 12)
        if 18 <= hora <= 22:  # Hora pico
            vph_predicho *= 1.2
        elif 6 <= hora <= 9:  # Mañana
            vph_predicho *= 1.1

        return max(vph_predicho, 1.0)  # Minimo 1 VPH

    def _calcular_score_nicho(self, titulo: str) -> int:
        """
        Calcula score de nicho del titulo
        """
        palabras = titulo.lower().split()
        keywords_oro = self.config.get('keywords_oro', {})

        score = sum(
            keywords_oro.get(palabra, 0)
            for palabra in palabras
        )

        return score

    def _calcular_similitud_patrones(self, titulo: str, features: Dict) -> Dict:
        """
        Calcula similitud con patrones exitosos
        """
        if not self.patrones_exito:
            return {
                'similitud': 0.0,
                'patrones_coincidentes': []
            }

        palabras_titulo = set(titulo.lower().split())

        patrones_coincidentes = []
        score_total = 0

        for patron in self.patrones_exito:
            if patron['patron_tipo'] == 'palabra_titulo_exitosa':
                if patron['patron_valor'] in palabras_titulo:
                    patrones_coincidentes.append({
                        'patron': patron['patron_valor'],
                        'vph_promedio': patron.get('vph_promedio', 0),
                        'confianza': patron.get('confianza', 0)
                    })
                    score_total += patron.get('confianza', 0)

        similitud = score_total / len(palabras_titulo) if palabras_titulo else 0

        return {
            'similitud': float(similitud),
            'patrones_coincidentes': patrones_coincidentes
        }

    def _simular_clusters(
        self,
        features: Dict,
        ctr_base: float,
        retencion_base: float
    ) -> Dict:
        """
        Simula respuesta de diferentes clusters de audiencia
        """
        # Definir clusters tipicos
        clusters = {
            'principiantes': {
                'descripcion': 'Usuarios nuevos del nicho',
                'porcentaje_audiencia': 40,
                'preferencias': {
                    'titulo_simple': True,
                    'duracion_corta': True
                }
            },
            'intermedios': {
                'descripcion': 'Usuarios con conocimiento medio',
                'porcentaje_audiencia': 45,
                'preferencias': {
                    'titulo_descriptivo': True,
                    'duracion_media': True
                }
            },
            'avanzados': {
                'descripcion': 'Expertos del nicho',
                'porcentaje_audiencia': 15,
                'preferencias': {
                    'titulo_tecnico': True,
                    'duracion_larga': True
                }
            }
        }

        resultados_clusters = {}

        for cluster_id, cluster_data in clusters.items():
            # Ajustar CTR y retencion segun preferencias del cluster
            ctr_ajustado = ctr_base
            retencion_ajustada = retencion_base

            # Aplicar preferencias
            if cluster_data['preferencias'].get('titulo_simple'):
                if features.get('titulo_num_palabras', 0) < 8:
                    ctr_ajustado *= 1.1
                    retencion_ajustada *= 1.05

            if cluster_data['preferencias'].get('duracion_corta'):
                if features.get('duracion_minutos', 0) < 5:
                    retencion_ajustada *= 1.15

            resultados_clusters[cluster_id] = {
                'descripcion': cluster_data['descripcion'],
                'porcentaje_audiencia': cluster_data['porcentaje_audiencia'],
                'ctr_esperado': float(ctr_ajustado),
                'retencion_esperada': float(retencion_ajustada)
            }

        return resultados_clusters

    def _generar_recomendacion(
        self,
        ctr: float,
        retencion: float,
        vph: float,
        score_nicho: int,
        similitud_patrones: Dict
    ) -> Dict:
        """
        Genera recomendacion final
        """
        # Umbrales
        CTR_MIN = 0.03
        RETENCION_MIN = 40
        VPH_MIN = 30
        SCORE_NICHO_MIN = 30

        # Evaluar
        problemas = []
        advertencias = []

        if ctr < CTR_MIN:
            problemas.append(f"CTR muy bajo ({ctr:.2%} < {CTR_MIN:.2%})")

        if retencion < RETENCION_MIN:
            problemas.append(f"Retencion baja ({retencion:.1f}% < {RETENCION_MIN}%)")

        if vph < VPH_MIN:
            advertencias.append(f"VPH bajo ({vph:.1f} < {VPH_MIN})")

        if score_nicho < SCORE_NICHO_MIN:
            problemas.append(f"Score de nicho bajo ({score_nicho} < {SCORE_NICHO_MIN})")

        # Decision
        if problemas:
            decision = 'NO_PUBLICAR'
            confianza = 0.8
            mensaje = "Alto riesgo de fracaso. Mejorar antes de publicar."
        elif advertencias:
            decision = 'PUBLICAR_CON_PRECAUCION'
            confianza = 0.6
            mensaje = "Rendimiento esperado: medio. Considerar mejoras."
        else:
            decision = 'PUBLICAR'
            confianza = 0.9
            mensaje = "Buenas probabilidades de exito."

        return {
            'decision': decision,
            'confianza': float(confianza),
            'mensaje': mensaje,
            'problemas': problemas,
            'advertencias': advertencias
        }

    def _features_dict_to_array(self, features: Dict, modelo_tipo: str) -> np.ndarray:
        """
        Convierte dict de features a array numpy para modelo
        """
        # Orden de features (debe coincidir con entrenamiento)
        feature_names = [
            'titulo_num_caracteres',
            'titulo_num_palabras',
            'titulo_score_nicho',
            'duracion_minutos',
            'hora_publicacion',
            'contraste_valor',
            'rostros_detectados'
        ]

        return np.array([features.get(f, 0) for f in feature_names])

    def _cargar_config_nicho(self) -> Dict:
        """
        Carga configuracion del nicho
        """
        config_path = os.path.join(
            os.path.dirname(__file__),
            '../config_nicho.json'
        )

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] No se pudo cargar config_nicho.json: {e}")
            return {}

    def _cargar_modelo(self, tipo: str) -> Optional[object]:
        """
        Carga modelo ML entrenado (si existe)
        """
        modelo_path = os.path.join(
            os.path.dirname(__file__),
            f'../modelos/modelo_{tipo}.pkl'
        )

        if not os.path.exists(modelo_path):
            return None

        try:
            with open(modelo_path, 'rb') as f:
                modelo = pickle.load(f)
            print(f"[INFO] Modelo {tipo} cargado")
            return modelo
        except Exception as e:
            print(f"[WARN] No se pudo cargar modelo {tipo}: {e}")
            return None

    def _cargar_benchmarks(self) -> Dict:
        """
        Carga benchmarks del canal desde Supabase
        """
        try:
            # Obtener promedio de VPH del canal
            videos = self.sb.table("videos")\
                .select("vph")\
                .gte("vph", 0)\
                .execute()

            if videos.data:
                vphs = [v['vph'] for v in videos.data if v.get('vph')]
                vph_promedio = sum(vphs) / len(vphs) if vphs else 50
            else:
                vph_promedio = 50  # Default

            return {
                'vph_promedio': vph_promedio
            }
        except Exception as e:
            print(f"[WARN] No se pudieron cargar benchmarks: {e}")
            return {'vph_promedio': 50}

    def _cargar_patrones_exito(self) -> List[Dict]:
        """
        Carga patrones de exito desde Supabase
        """
        try:
            patrones = self.sb.table("patrones_exito")\
                .select("*")\
                .order("confianza", desc=True)\
                .limit(50)\
                .execute()

            return patrones.data if patrones.data else []
        except Exception as e:
            print(f"[WARN] No se pudieron cargar patrones: {e}")
            return []


def main():
    """
    Ejecuta simulador interactivo
    """
    print()
    print("=" * 80)
    print("SIMULADOR DE PRE-PUBLICACION")
    print("Predice CTR y retencion ANTES de publicar")
    print("=" * 80)
    print()

    # Cargar env
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables de entorno no configuradas")
        print("        SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    # Crear cliente
    sb = create_client(supabase_url, supabase_key)

    # Simulador
    simulador = SimuladorPrePublicacion(sb)

    # Modo interactivo
    print("Ingresa multiples combinaciones para comparar")
    print("(deja titulo vacio para terminar)")
    print()

    combinaciones = []

    while True:
        print(f"Combinacion #{len(combinaciones) + 1}:")
        titulo = input("  Titulo: ").strip()

        if not titulo:
            break

        duracion = input("  Duracion (minutos) [10]: ").strip()
        duracion = float(duracion) if duracion else 10.0

        # Descripcion miniatura (simplificado)
        print("  Miniatura:")
        contraste = input("    Contraste (0-100) [60]: ").strip()
        contraste = float(contraste) if contraste else 60.0

        rostros = input("    Rostros detectados [1]: ").strip()
        rostros = int(rostros) if rostros else 1

        combinaciones.append({
            'titulo': titulo,
            'duracion_minutos': duracion,
            'miniatura': {
                'contraste_valor': contraste,
                'rostros_detectados': rostros
            }
        })

        print()

    if not combinaciones:
        print("[INFO] No se ingresaron combinaciones")
        sys.exit(0)

    # Comparar
    resultado = simulador.comparar_combinaciones(combinaciones)

    # Recomendacion final
    mejor = resultado['mejor_combinacion']

    print("=" * 80)
    print("RECOMENDACION FINAL")
    print("=" * 80)
    print()

    print(f"Mejor opcion: {mejor['titulo']}")
    print()

    pred = mejor['predicciones']
    print(f"Predicciones:")
    print(f"  CTR: {pred['ctr']:.2%}")
    print(f"  Retencion: {pred['retencion']:.1f}%")
    print(f"  VPH: {pred['vph']:.1f}")
    print()

    rec = mejor['recomendacion']
    print(f"Decision: {rec['decision']}")
    print(f"Confianza: {rec['confianza']:.0%}")
    print(f"Mensaje: {rec['mensaje']}")
    print()

    if rec['problemas']:
        print("Problemas:")
        for p in rec['problemas']:
            print(f"  ❌ {p}")
        print()

    if rec['advertencias']:
        print("Advertencias:")
        for a in rec['advertencias']:
            print(f"  ⚠️  {a}")
        print()


if __name__ == "__main__":
    main()
