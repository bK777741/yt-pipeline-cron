#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DETECTOR DE VIDEOS PASARELA
============================

Identifica videos que sirven como PUNTOS DE ENTRADA al nicho
Analiza trafico de busqueda y fuentes externas

VIDEO PASARELA = Video que:
1. Trae nuevo trafico desde busqueda/browse
2. Tiene alto % de trafico externo
3. Responde queries fundamentales del nicho
4. Inicia sesiones (alto sessionStarts)
5. Es primer contacto con el canal

ESTRATEGIA:
1. Identificar queries fundamentales del nicho
2. Crear videos optimizados para esas busquedas
3. Diseñar estructura para maximizar continuacion de sesion
4. Conectar pasarelas con videos EXTENSORES

EJEMPLO:
- Pasarela: "Que es ChatGPT" (1K busquedas/mes)
- Extension: "10 trucos de ChatGPT" (video EXTENSOR)
- Red: Usuario entra → ve pasarela → continua a extensores

EJECUCION:
- Manual: python scripts/detector_videos_pasarela.py
- Automatico: Ejecutar mensualmente para actualizar

COSTO: $0 (usa YouTube Analytics API - gratis)
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

from supabase import create_client, Client

# Cargar variables de entorno desde .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# YouTube Analytics
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
except ImportError:
    print("[ERROR] Dependencias no instaladas. Ejecutar:")
    print("  pip install google-api-python-client google-auth")
    sys.exit(1)


class DetectorVideosPasarela:
    """
    Detecta videos que sirven como puntos de entrada
    """

    def __init__(self, sb: Client, youtube_analytics):
        self.sb = sb
        self.analytics = youtube_analytics

        # Cargar config del nicho
        self.config = self._cargar_config_nicho()

        # Queries fundamentales del nicho (a buscar)
        self.queries_fundamentales = self._generar_queries_fundamentales()

    def analizar_canal(self, dias_analisis: int = 28) -> Dict:
        """
        Analiza canal completo para identificar videos pasarela
        """
        print()
        print("=" * 80)
        print("[PASARELA] DETECTOR DE VIDEOS PASARELA")
        print("Identifica puntos de entrada al nicho")
        print("=" * 80)
        print()

        fecha_inicio = (datetime.now() - timedelta(days=dias_analisis)).strftime("%Y-%m-%d")
        fecha_fin = datetime.now().strftime("%Y-%m-%d")

        print(f"Periodo: {fecha_inicio} a {fecha_fin} ({dias_analisis} dias)")
        print()

        # Obtener videos del canal
        videos = self.sb.table("videos")\
            .select("video_id, title")\
            .execute()

        if not videos.data:
            print("[ERROR] No hay videos en DB")
            return {}

        print(f"Analizando {len(videos.data)} videos...")
        print()

        # Analizar cada video
        resultados = []

        for i, video in enumerate(videos.data, 1):
            video_id = video['video_id']
            title = video['title']

            print(f"[{i}/{len(videos.data)}] {title[:50]}...")

            try:
                analisis = self._analizar_video_pasarela(
                    video_id,
                    title,
                    fecha_inicio,
                    fecha_fin
                )

                if analisis:
                    resultados.append(analisis)

                    if analisis['es_pasarela']:
                        print(f"  [PASARELA] PASARELA: Score={analisis['pasarela_score']:.1f}")
                    else:
                        print(f"  ⚪ Normal: Score={analisis['pasarela_score']:.1f}")
                else:
                    print(f"  [WARN]  Sin datos")

            except Exception as e:
                print(f"  [ERROR] Error: {str(e)[:50]}")

            print()

        # Ordenar por score de pasarela
        resultados.sort(key=lambda x: x.get('pasarela_score', 0), reverse=True)

        # Generar reporte
        reporte = self._generar_reporte(resultados, dias_analisis)

        # Guardar resultados
        self._guardar_resultados(resultados)

        return reporte

    def _analizar_video_pasarela(
        self,
        video_id: str,
        title: str,
        fecha_inicio: str,
        fecha_fin: str
    ) -> Optional[Dict]:
        """
        Analiza si un video es pasarela
        """
        # Obtener metricas de trafico
        metricas_trafico = self._obtener_metricas_trafico(
            video_id,
            fecha_inicio,
            fecha_fin
        )

        if not metricas_trafico:
            return None

        # Calcular score de pasarela
        score_componentes = {
            # 1. Trafico desde busqueda (mas importante)
            'trafico_busqueda': self._calcular_score_busqueda(metricas_trafico),

            # 2. Trafico desde browse/suggested (usuarios nuevos)
            'trafico_browse': self._calcular_score_browse(metricas_trafico),

            # 3. Query fundamental (titulo responde pregunta basica)
            'query_fundamental': self._calcular_score_query_fundamental(title),

            # 4. Simplicidad del titulo (pasarelas son simples)
            'simplicidad_titulo': self._calcular_score_simplicidad(title),

            # 5. Nicho score (debe ser del nicho)
            'nicho_score': self._calcular_score_nicho(title)
        }

        # Score total (ponderado)
        pasarela_score = (
            score_componentes['trafico_busqueda'] * 0.35 +
            score_componentes['trafico_browse'] * 0.25 +
            score_componentes['query_fundamental'] * 0.20 +
            score_componentes['simplicidad_titulo'] * 0.10 +
            score_componentes['nicho_score'] * 0.10
        )

        # Clasificar
        es_pasarela = pasarela_score >= 60  # Umbral: 60/100

        # Nivel de pasarela
        if pasarela_score >= 80:
            nivel = 'PASARELA_ELITE'
            accion = 'Optimizar al maximo - Entrada principal'
        elif pasarela_score >= 60:
            nivel = 'PASARELA'
            accion = 'Potenciar - Buena entrada'
        else:
            nivel = 'NO_PASARELA'
            accion = 'Continuar como video normal'

        return {
            'video_id': video_id,
            'title': title,
            'es_pasarela': es_pasarela,
            'nivel': nivel,
            'pasarela_score': float(pasarela_score),
            'score_componentes': score_componentes,
            'metricas_trafico': metricas_trafico,
            'accion_recomendada': accion,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _obtener_metricas_trafico(
        self,
        video_id: str,
        fecha_inicio: str,
        fecha_fin: str
    ) -> Optional[Dict]:
        """
        Obtiene metricas de fuentes de trafico desde Analytics API
        """
        try:
            # Query por fuente de trafico
            response = self.analytics.reports().query(
                ids='channel==MINE',
                startDate=fecha_inicio,
                endDate=fecha_fin,
                metrics='views',
                dimensions='insightTrafficSourceType',
                filters=f'video=={video_id}',
                sort='-views'
            ).execute()

            if 'rows' not in response:
                return None

            # Procesar fuentes de trafico
            trafico = {}
            total_views = 0

            for row in response['rows']:
                fuente = row[0]
                views = int(row[1])
                trafico[fuente] = views
                total_views += views

            # Calcular porcentajes
            trafico_pct = {}
            for fuente, views in trafico.items():
                trafico_pct[fuente] = (views / total_views) * 100 if total_views > 0 else 0

            # Fuentes clave para pasarelas
            busqueda = trafico_pct.get('YT_SEARCH', 0) + trafico_pct.get('EXT_URL', 0)
            browse = trafico_pct.get('BROWSE', 0)
            suggested = trafico_pct.get('RELATED_VIDEO', 0)

            return {
                'total_views': total_views,
                'trafico_raw': trafico,
                'trafico_pct': trafico_pct,
                'busqueda_pct': float(busqueda),
                'browse_pct': float(browse),
                'suggested_pct': float(suggested)
            }

        except Exception as e:
            print(f"    [ERROR] Analytics API trafico: {str(e)[:50]}")
            return None

    def _calcular_score_busqueda(self, metricas: Dict) -> float:
        """
        Score basado en trafico de busqueda
        """
        busqueda_pct = metricas.get('busqueda_pct', 0)

        # Pasarelas ideales tienen >40% de busqueda
        if busqueda_pct >= 50:
            return 100
        elif busqueda_pct >= 40:
            return 90
        elif busqueda_pct >= 30:
            return 70
        elif busqueda_pct >= 20:
            return 50
        elif busqueda_pct >= 10:
            return 30
        else:
            return 10

    def _calcular_score_browse(self, metricas: Dict) -> float:
        """
        Score basado en trafico de browse
        """
        browse_pct = metricas.get('browse_pct', 0)

        # Browse indica usuarios explorando (nuevos)
        if browse_pct >= 30:
            return 100
        elif browse_pct >= 20:
            return 80
        elif browse_pct >= 10:
            return 60
        elif browse_pct >= 5:
            return 40
        else:
            return 20

    def _calcular_score_query_fundamental(self, titulo: str) -> float:
        """
        Score basado en si responde query fundamental
        """
        titulo_lower = titulo.lower()

        # Palabras que indican query fundamental
        palabras_fundamentales = [
            'que es', 'como', 'tutorial', 'guia', 'principiantes',
            'basico', 'introduccion', 'empezar', 'aprender',
            'para que sirve', 'explicacion', 'paso a paso'
        ]

        # Contar coincidencias
        coincidencias = sum(1 for palabra in palabras_fundamentales if palabra in titulo_lower)

        # Score
        if coincidencias >= 2:
            return 100
        elif coincidencias == 1:
            return 70
        else:
            return 30

    def _calcular_score_simplicidad(self, titulo: str) -> float:
        """
        Score basado en simplicidad del titulo
        Pasarelas deben ser simples (no tecnicas)
        """
        palabras = titulo.split()
        num_palabras = len(palabras)

        # Titulos simples = 5-10 palabras
        if 5 <= num_palabras <= 10:
            simplicidad = 100
        elif 4 <= num_palabras <= 12:
            simplicidad = 80
        elif num_palabras <= 15:
            simplicidad = 60
        else:
            simplicidad = 40

        # Penalizar tecnicismos
        palabras_tecnicas = ['api', 'algoritmo', 'avanzado', 'experto', 'complejo']
        tiene_tecnicismo = any(t in titulo.lower() for t in palabras_tecnicas)

        if tiene_tecnicismo:
            simplicidad *= 0.5

        return float(simplicidad)

    def _calcular_score_nicho(self, titulo: str) -> float:
        """
        Score de nicho del titulo
        """
        palabras = titulo.lower().split()
        keywords_oro = self.config.get('keywords_oro', {})

        score = sum(keywords_oro.get(palabra, 0) for palabra in palabras)

        # Normalizar a 0-100
        if score >= 50:
            return 100
        elif score >= 30:
            return 80
        elif score >= 20:
            return 60
        elif score >= 10:
            return 40
        else:
            return 20

    def _generar_queries_fundamentales(self) -> List[str]:
        """
        Genera lista de queries fundamentales del nicho
        """
        keywords_oro = self.config.get('keywords_oro', {})

        # Top keywords del nicho
        top_keywords = sorted(
            keywords_oro.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Generar queries fundamentales
        queries = []

        for keyword, _ in top_keywords:
            queries.extend([
                f"que es {keyword}",
                f"como usar {keyword}",
                f"tutorial {keyword}",
                f"{keyword} para principiantes",
                f"como funciona {keyword}"
            ])

        return queries

    def _generar_reporte(self, resultados: List[Dict], dias_analisis: int) -> Dict:
        """
        Genera reporte completo
        """
        # Filtrar pasarelas
        pasarelas = [r for r in resultados if r['es_pasarela']]
        pasarelas_elite = [r for r in pasarelas if r['nivel'] == 'PASARELA_ELITE']
        no_pasarelas = [r for r in resultados if not r['es_pasarela']]

        print()
        print("=" * 80)
        print("[STATS] REPORTE DE PASARELAS")
        print("=" * 80)
        print()

        print(f"Periodo: {dias_analisis} dias")
        print(f"Videos analizados: {len(resultados)}")
        print()

        print("DISTRIBUCION:")
        print(f"  [PASARELA] Pasarelas ELITE: {len(pasarelas_elite)}")
        print(f"  [PASARELA] Pasarelas normales: {len(pasarelas) - len(pasarelas_elite)}")
        print(f"  ⚪ No pasarelas: {len(no_pasarelas)}")
        print()

        if pasarelas_elite:
            print("[TOP] TOP PASARELAS ELITE:")
            for i, video in enumerate(pasarelas_elite[:5], 1):
                print(f"  {i}. {video['title'][:60]}")
                print(f"     Score: {video['pasarela_score']:.1f}")
                met = video['metricas_trafico']
                print(f"     Busqueda: {met['busqueda_pct']:.1f}% | Browse: {met['browse_pct']:.1f}%")
                print(f"     Vistas: {met['total_views']:,}")
            print()

        if pasarelas:
            print("[TARGET] QUERIES FALTANTES (Oportunidades):")
            print()
            print("  Queries fundamentales sin video pasarela:")

            # Identificar queries fundamentales sin video
            queries_cubiertas = []
            for video in pasarelas:
                titulo = video['title'].lower()
                for query in self.queries_fundamentales:
                    if any(word in titulo for word in query.split()):
                        queries_cubiertas.append(query)

            queries_faltantes = [
                q for q in self.queries_fundamentales[:20]
                if q not in queries_cubiertas
            ]

            for i, query in enumerate(queries_faltantes[:10], 1):
                print(f"  {i}. \"{query}\"")
            print()

        # Recomendaciones
        print("=" * 80)
        print("[TARGET] RECOMENDACIONES ESTRATEGICAS")
        print("=" * 80)
        print()

        if pasarelas_elite:
            print("1. OPTIMIZAR PASARELAS ELITE:")
            print(f"   - {len(pasarelas_elite)} videos son entradas principales")
            print("   - Optimizar titulo/miniatura al maximo")
            print("   - Agregar cards a videos EXTENSORES en seg 30")
            print("   - Pantalla final: Top 3 videos EXTENSORES")
            print()

        if queries_faltantes:
            print("2. CREAR NUEVAS PASARELAS:")
            print(f"   - Faltan {len(queries_faltantes)} queries fundamentales")
            print("   - Priorizar:")
            for q in queries_faltantes[:5]:
                print(f"     • \"{q}\"")
            print()

        if len(pasarelas) > 3:
            print("3. RED DE PASARELAS:")
            print(f"   - Conectar {len(pasarelas)} pasarelas con videos EXTENSORES")
            print("   - Diseñar flujo: Pasarela → Extensor → Profundizacion")
            print("   - Maximizar sesiones de 3+ videos")
            print()

        return {
            'periodo_dias': dias_analisis,
            'total_videos': len(resultados),
            'pasarelas_elite': len(pasarelas_elite),
            'pasarelas': len(pasarelas),
            'no_pasarelas': len(no_pasarelas),
            'top_pasarelas': pasarelas_elite[:5],
            'queries_faltantes': queries_faltantes[:10],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _guardar_resultados(self, resultados: List[Dict]):
        """
        Guarda resultados en Supabase
        """
        # TODO: Crear tabla gateway_videos_analysis
        print()
        print("[INFO] Resultados generados (no guardados en DB aun)")
        print("[TODO] Crear tabla 'gateway_videos_analysis' en Supabase")
        print()

    def _cargar_config_nicho(self) -> Dict:
        """
        Carga config del nicho
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


def crear_cliente_analytics():
    """
    Crea cliente de YouTube Analytics API
    """
    client_id = os.environ.get("YT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YT_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YT_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        print("[ERROR] Credenciales OAuth no configuradas")
        sys.exit(1)

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=['https://www.googleapis.com/auth/yt-analytics.readonly']
    )

    analytics = build('youtubeAnalytics', 'v2', credentials=credentials)
    return analytics


def main():
    """
    Ejecuta detector de videos pasarela
    """
    print()
    print("=" * 80)
    print("[PASARELA] DETECTOR DE VIDEOS PASARELA")
    print("Identifica puntos de entrada al nicho")
    print("=" * 80)
    print()

    # Cargar env
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables de entorno no configuradas")
        sys.exit(1)

    # Crear clientes
    sb = create_client(supabase_url, supabase_key)

    try:
        analytics = crear_cliente_analytics()
    except Exception as e:
        print(f"[ERROR] No se pudo crear cliente Analytics: {e}")
        sys.exit(1)

    # Detector
    detector = DetectorVideosPasarela(sb, analytics)

    # Ejecutar analisis
    dias = 28
    if len(sys.argv) > 1 and sys.argv[1] == "--dias":
        dias = int(sys.argv[2])

    reporte = detector.analizar_canal(dias_analisis=dias)


if __name__ == "__main__":
    main()
