#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE ROBO DE SESIONES (HIJACKING)
========================================

Detecta videos virales de competencia y crea videos "secuestradores"
para capturar trafico de sugeridos

CONCEPTO:
Un usuario ve video viral de competencia → YouTube sugiere tu video
→ Usuario hace click → Robas su sesion

PROCESO:
1. Detectar videos virales del nicho (alto VPH)
2. Analizar que preguntas dejan sin responder
3. Generar ideas de videos "complementarios"
4. Optimizar titulo para aparecer en sugeridos
5. Crear miniatura que llame atencion junto al viral

TIPOS DE HIJACKING:
- 🔄 EXTENSION: "Parte 2", "Mas trucos", "Lo que no te dijeron"
- 🆚 COMPARACION: "X vs Y", "Mejor alternativa a X"
- 🔍 PROFUNDIZACION: "Explicacion detallada de X"
- ⚠️  CORRECCION: "Errores de X", "La verdad sobre X"
- 💡 ALTERNATIVA: "Como hacer X mas facil"

VENTAJA: Trafico de calidad (usuarios ya interesados en el tema)

EJECUCION:
- Manual: python scripts/sistema_robo_sesiones.py
- Automatico: Ejecutar semanalmente para nuevas oportunidades

COSTO: $0 (usa datos de Supabase + YouTube Data API)
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from collections import defaultdict

from supabase import create_client, Client

# YouTube Data API (para buscar videos de competencia)
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
except ImportError:
    print("[ERROR] Dependencias no instaladas. Ejecutar:")
    print("  pip install google-api-python-client google-auth")
    sys.exit(1)


class SistemaRoboSesiones:
    """
    Sistema de hijacking de sesiones
    """

    def __init__(self, sb: Client, youtube_data):
        self.sb = sb
        self.youtube = youtube_data

        # Cargar config del nicho
        self.config = self._cargar_config_nicho()

        # Keywords del nicho
        self.keywords_nicho = list(self.config.get('keywords_oro', {}).keys())[:10]

        # Plantillas de hijacking
        self.PLANTILLAS_HIJACKING = {
            'extension': [
                "Parte 2: {topic}",
                "Mas trucos de {topic}",
                "Lo que no te dijeron sobre {topic}",
                "{topic} - Nivel avanzado",
                "Continua aprendiendo {topic}"
            ],
            'comparacion': [
                "{topic} vs {alternative}",
                "Mejor alternativa a {topic}",
                "{topic} o {alternative}? La verdad",
                "Comparativa completa: {topic}"
            ],
            'profundizacion': [
                "Explicacion detallada de {topic}",
                "Todo sobre {topic}",
                "{topic} explicado paso a paso",
                "Guia completa de {topic}"
            ],
            'correccion': [
                "Errores comunes con {topic}",
                "La verdad sobre {topic}",
                "Lo que esta mal en {topic}",
                "{topic} - Evita estos errores"
            ],
            'alternativa': [
                "Como hacer {topic} mas facil",
                "Metodo rapido para {topic}",
                "{topic} sin complicaciones",
                "Atajo para {topic}"
            ]
        }

    def detectar_oportunidades(self, max_resultados: int = 20) -> Dict:
        """
        Detecta videos virales para hijackear
        """
        print()
        print("=" * 80)
        print("🎯 SISTEMA DE ROBO DE SESIONES")
        print("Detecta oportunidades de hijacking")
        print("=" * 80)
        print()

        oportunidades = []

        # Buscar videos virales por cada keyword del nicho
        for keyword in self.keywords_nicho[:5]:  # Top 5 keywords
            print(f"Buscando videos virales de: {keyword}")

            videos_virales = self._buscar_videos_virales(keyword, max_videos=10)

            for video in videos_virales:
                # Analizar video viral
                analisis = self._analizar_video_viral(video)

                # Generar ideas de hijacking
                ideas = self._generar_ideas_hijacking(video, analisis)

                if ideas:
                    oportunidades.append({
                        'video_viral': video,
                        'analisis': analisis,
                        'ideas_hijacking': ideas
                    })

                    print(f"  ✓ {video['title'][:50]}")
                    print(f"    VPH: {analisis.get('vph', 0):.1f} | Ideas: {len(ideas)}")

            print()

        # Ordenar por potencial (VPH del video viral)
        oportunidades.sort(
            key=lambda x: x['analisis'].get('vph', 0),
            reverse=True
        )

        # Generar reporte
        reporte = self._generar_reporte_oportunidades(oportunidades)

        # Guardar
        self._guardar_oportunidades(oportunidades)

        return reporte

    def _buscar_videos_virales(self, keyword: str, max_videos: int = 10) -> List[Dict]:
        """
        Busca videos virales del nicho usando YouTube Data API
        """
        try:
            # Buscar videos publicados en ultimos 30 dias
            fecha_desde = (datetime.now() - timedelta(days=30)).isoformat() + 'Z'

            # Search
            search_response = self.youtube.search().list(
                q=keyword,
                part='snippet',
                type='video',
                maxResults=max_videos,
                publishedAfter=fecha_desde,
                order='viewCount',  # Ordenar por vistas
                relevanceLanguage='es',
                regionCode='US'
            ).execute()

            videos = []

            for item in search_response.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']

                # Obtener estadisticas
                stats_response = self.youtube.videos().list(
                    part='statistics,contentDetails',
                    id=video_id
                ).execute()

                if not stats_response['items']:
                    continue

                stats = stats_response['items'][0]['statistics']
                content = stats_response['items'][0]['contentDetails']

                # Calcular VPH
                view_count = int(stats.get('viewCount', 0))
                published_at = datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00'))
                edad_horas = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
                vph = view_count / edad_horas if edad_horas > 0 else 0

                # Filtrar solo virales (VPH > 25)
                if vph < 25:
                    continue

                # Parsear duracion
                duration_str = content['duration']
                duracion_segundos = self._parse_duration(duration_str)

                videos.append({
                    'video_id': video_id,
                    'title': snippet['title'],
                    'channel_id': snippet['channelId'],
                    'channel_title': snippet['channelTitle'],
                    'published_at': snippet['publishedAt'],
                    'view_count': view_count,
                    'vph': vph,
                    'duracion_segundos': duracion_segundos,
                    'thumbnail_url': snippet['thumbnails']['high']['url']
                })

            return videos

        except Exception as e:
            print(f"  [ERROR] Busqueda falló: {str(e)[:50]}")
            return []

    def _analizar_video_viral(self, video: Dict) -> Dict:
        """
        Analiza un video viral para identificar gaps
        """
        titulo = video['title'].lower()

        # Detectar tipo de contenido
        tipo_contenido = 'desconocido'

        if any(word in titulo for word in ['tutorial', 'como', 'guia']):
            tipo_contenido = 'tutorial'
        elif any(word in titulo for word in ['trucos', 'tips', 'secretos']):
            tipo_contenido = 'tips'
        elif any(word in titulo for word in ['vs', 'comparacion', 'diferencia']):
            tipo_contenido = 'comparacion'
        elif any(word in titulo for word in ['que es', 'explicacion']):
            tipo_contenido = 'explicacion'

        # Detectar gaps (que falta)
        gaps = []

        # Si es tutorial basico → falta avanzado
        if 'principiantes' in titulo or 'basico' in titulo:
            gaps.append('contenido_avanzado')

        # Si es tips → falta mas tips
        if tipo_contenido == 'tips':
            gaps.append('mas_tips')

        # Si es corto → falta profundizacion
        if video['duracion_segundos'] < 180:  # <3 min
            gaps.append('version_detallada')

        # Si es viral → puede tener errores
        if video['vph'] > 100:
            gaps.append('correccion_errores')

        return {
            'vph': video['vph'],
            'tipo_contenido': tipo_contenido,
            'gaps_detectados': gaps,
            'duracion_segundos': video['duracion_segundos'],
            'es_viral': video['vph'] > 50
        }

    def _generar_ideas_hijacking(self, video: Dict, analisis: Dict) -> List[Dict]:
        """
        Genera ideas de videos hijacking
        """
        ideas = []
        titulo_viral = video['title']

        # Extraer tema principal
        topic = self._extraer_tema(titulo_viral)

        # Generar ideas segun gaps detectados
        for gap in analisis['gaps_detectados']:
            if gap == 'contenido_avanzado':
                # Extension
                for plantilla in self.PLANTILLAS_HIJACKING['extension']:
                    titulo_hijack = plantilla.format(topic=topic)
                    ideas.append({
                        'tipo': 'extension',
                        'titulo_sugerido': titulo_hijack,
                        'estrategia': 'Aparecer en sugeridos como continuacion',
                        'gap_cubierto': gap
                    })

            elif gap == 'mas_tips':
                # Mas tips
                ideas.append({
                    'tipo': 'extension',
                    'titulo_sugerido': f"Mas trucos de {topic}",
                    'estrategia': 'Capturar usuarios que quieren mas',
                    'gap_cubierto': gap
                })

            elif gap == 'version_detallada':
                # Profundizacion
                for plantilla in self.PLANTILLAS_HIJACKING['profundizacion']:
                    titulo_hijack = plantilla.format(topic=topic)
                    ideas.append({
                        'tipo': 'profundizacion',
                        'titulo_sugerido': titulo_hijack,
                        'estrategia': 'Capturar usuarios que quieren mas detalle',
                        'gap_cubierto': gap
                    })

            elif gap == 'correccion_errores':
                # Correccion
                for plantilla in self.PLANTILLAS_HIJACKING['correccion']:
                    titulo_hijack = plantilla.format(topic=topic)
                    ideas.append({
                        'tipo': 'correccion',
                        'titulo_sugerido': titulo_hijack,
                        'estrategia': 'Controversy/curiosidad',
                        'gap_cubierto': gap
                    })

        # Limitar a top 3 ideas por video
        ideas = ideas[:3]

        # Agregar metadata
        for idea in ideas:
            idea['video_viral_id'] = video['video_id']
            idea['video_viral_titulo'] = video['title']
            idea['video_viral_vph'] = video['vph']
            idea['potencial_trafico'] = self._calcular_potencial_trafico(video, idea)

        return ideas

    def _extraer_tema(self, titulo: str) -> str:
        """
        Extrae tema principal del titulo
        """
        # Limpiar titulo
        titulo_limpio = titulo.lower()

        # Remover palabras comunes
        palabras_remover = [
            'como', 'tutorial', 'guia', 'trucos', 'tips',
            'secretos', 'que es', 'para', 'principiantes'
        ]

        for palabra in palabras_remover:
            titulo_limpio = titulo_limpio.replace(palabra, '')

        # Extraer keywords del nicho presentes
        keywords_presentes = []
        for keyword in self.keywords_nicho:
            if keyword.lower() in titulo_limpio:
                keywords_presentes.append(keyword)

        # Si hay keyword del nicho, usar esa
        if keywords_presentes:
            return keywords_presentes[0]

        # Si no, usar primera palabra significativa
        palabras = titulo_limpio.split()
        palabras_significativas = [p for p in palabras if len(p) > 3]

        if palabras_significativas:
            return palabras_significativas[0]

        return 'tema'

    def _calcular_potencial_trafico(self, video_viral: Dict, idea: Dict) -> float:
        """
        Calcula potencial de trafico de la idea hijacking
        """
        # Basado en VPH del video viral
        vph_viral = video_viral['vph']

        # Porcentaje de trafico que podriamos capturar
        # Extension/profundizacion = 15-20%
        # Correccion = 10-15%
        # Alternativa = 5-10%

        tipo = idea['tipo']

        if tipo == 'extension':
            porcentaje_captura = 0.175
        elif tipo == 'profundizacion':
            porcentaje_captura = 0.15
        elif tipo == 'correccion':
            porcentaje_captura = 0.125
        else:
            porcentaje_captura = 0.075

        # VPH potencial de nuestro video hijack
        vph_potencial = vph_viral * porcentaje_captura

        return float(vph_potencial)

    def _generar_reporte_oportunidades(self, oportunidades: List[Dict]) -> Dict:
        """
        Genera reporte de oportunidades
        """
        print()
        print("=" * 80)
        print("📊 REPORTE DE OPORTUNIDADES DE HIJACKING")
        print("=" * 80)
        print()

        print(f"Oportunidades detectadas: {len(oportunidades)}")
        print()

        if not oportunidades:
            print("[INFO] No se encontraron oportunidades")
            return {}

        # Top 10 oportunidades
        print("🏆 TOP 10 OPORTUNIDADES:")
        print()

        for i, op in enumerate(oportunidades[:10], 1):
            video_viral = op['video_viral']
            ideas = op['ideas_hijacking']

            print(f"{i}. VIDEO VIRAL:")
            print(f"   Titulo: {video_viral['title'][:60]}")
            print(f"   Canal: {video_viral['channel_title']}")
            print(f"   VPH: {video_viral['vph']:.1f}")
            print(f"   Vistas: {video_viral['view_count']:,}")
            print()

            print(f"   IDEAS DE HIJACKING ({len(ideas)}):")
            for j, idea in enumerate(ideas, 1):
                print(f"     {j}. [{idea['tipo'].upper()}] {idea['titulo_sugerido']}")
                print(f"        VPH potencial: {idea['potencial_trafico']:.1f}")
                print(f"        Estrategia: {idea['estrategia']}")
            print()

        # Resumen por tipo
        tipos_count = defaultdict(int)
        for op in oportunidades:
            for idea in op['ideas_hijacking']:
                tipos_count[idea['tipo']] += 1

        print("DISTRIBUCION POR TIPO:")
        for tipo, count in sorted(tipos_count.items(), key=lambda x: x[1], reverse=True):
            print(f"  {tipo}: {count} ideas")
        print()

        # Recomendaciones
        print("=" * 80)
        print("🎯 RECOMENDACIONES")
        print("=" * 80)
        print()

        if oportunidades:
            top_op = oportunidades[0]
            top_idea = top_op['ideas_hijacking'][0]

            print("1. PRIORIDAD MAXIMA:")
            print(f"   Video viral: {top_op['video_viral']['title'][:60]}")
            print(f"   VPH: {top_op['video_viral']['vph']:.1f}")
            print()
            print(f"   CREAR VIDEO:")
            print(f"   Titulo: \"{top_idea['titulo_sugerido']}\"")
            print(f"   Tipo: {top_idea['tipo']}")
            print(f"   VPH esperado: {top_idea['potencial_trafico']:.1f}")
            print()

        print("2. OPTIMIZACION:")
        print("   - Titulo similar pero NO copia (evitar copyright)")
        print("   - Miniatura contrastante (destacar junto al viral)")
        print("   - Primeros 30 seg: Hook potente")
        print("   - Tags: Copiar tags del video viral")
        print()

        print("3. ESTRATEGIA DE PUBLICACION:")
        print("   - Publicar mientras el viral esta activo")
        print("   - Agregar video viral a playlist")
        print("   - Mencionar video viral en descripcion")
        print()

        return {
            'total_oportunidades': len(oportunidades),
            'top_oportunidades': oportunidades[:10],
            'tipos_distribucion': dict(tipos_count),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _guardar_oportunidades(self, oportunidades: List[Dict]):
        """
        Guarda oportunidades en Supabase
        """
        # TODO: Crear tabla hijacking_opportunities
        print()
        print("[INFO] Oportunidades generadas (no guardadas en DB aun)")
        print("[TODO] Crear tabla 'hijacking_opportunities' en Supabase")
        print()

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parsea duracion ISO 8601 a segundos
        """
        # Formato: PT#H#M#S
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)

        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

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


def crear_cliente_youtube():
    """
    Crea cliente de YouTube Data API
    """
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        print("[ERROR] Credenciales OAuth no configuradas")
        sys.exit(1)

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=['https://www.googleapis.com/auth/youtube.force-ssl']
    )

    youtube = build('youtube', 'v3', credentials=credentials)
    return youtube


def main():
    """
    Ejecuta sistema de robo de sesiones
    """
    print()
    print("=" * 80)
    print("🎯 SISTEMA DE ROBO DE SESIONES (HIJACKING)")
    print("Detecta videos virales para hijackear")
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
        youtube = crear_cliente_youtube()
    except Exception as e:
        print(f"[ERROR] No se pudo crear cliente YouTube: {e}")
        sys.exit(1)

    # Sistema
    sistema = SistemaRoboSesiones(sb, youtube)

    # Detectar oportunidades
    reporte = sistema.detectar_oportunidades(max_resultados=20)


if __name__ == "__main__":
    main()
