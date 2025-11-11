#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALIZADOR DE CONTINUACION DE SESION
=====================================
🏆 ULTRA SANTO GRIAL 🏆

Analiza si tus videos EXTIENDEN o MATAN sesiones de visualizacion
Usa YouTube Analytics API para metricas de sesion

METRICAS CLAVE:
- sessionStarts: Cuantas sesiones EMPIEZAN en este video
- sessionEnds: Cuantas sesiones TERMINAN en este video
- avgSessionsPerUser: Promedio de videos vistos por sesion

CLASIFICACION:
- 🟢 EXTENSORES: Videos que mantienen al espectador viendo mas
- 🔴 ASESINOS: Videos que hacen que el espectador se vaya
- 🟡 NEUTROS: Videos sin impacto especial

ESTRATEGIA:
1. Identificar videos EXTENSORES → Promocionarlos masivamente
2. Identificar videos ASESINOS → Optimizar o despromocionar
3. Crear red de videos EXTENSORES (efecto telaraña)

EJECUCION:
- Manual: python scripts/analizador_sesion_continuacion.py
- Automatico: Ejecutar semanalmente para actualizar clasificacion

COSTO: $0 (usa YouTube Analytics API - gratis)
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from supabase import create_client, Client

# YouTube Analytics
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
except ImportError:
    print("[ERROR] Dependencias no instaladas. Ejecutar:")
    print("  pip install google-api-python-client google-auth")
    sys.exit(1)


class AnalizadorSesionContinuacion:
    """
    🏆 ULTRA SANTO GRIAL 🏆
    Analiza continuacion de sesiones
    """

    def __init__(self, sb: Client, youtube_analytics):
        self.sb = sb
        self.analytics = youtube_analytics

    def analizar_canal(self, dias_analisis: int = 28) -> Dict:
        """
        Analiza todos los videos del canal para clasificarlos
        """
        print()
        print("=" * 80)
        print("🏆 ULTRA SANTO GRIAL - ANALISIS DE CONTINUACION DE SESION 🏆")
        print("=" * 80)
        print()

        # Fecha de inicio
        fecha_inicio = (datetime.now() - timedelta(days=dias_analisis)).strftime("%Y-%m-%d")
        fecha_fin = datetime.now().strftime("%Y-%m-%d")

        print(f"Periodo de analisis: {fecha_inicio} a {fecha_fin} ({dias_analisis} dias)")
        print()

        # Obtener videos del canal desde Supabase
        videos = self.sb.table("videos")\
            .select("video_id, title")\
            .execute()

        if not videos.data:
            print("[ERROR] No hay videos en la base de datos")
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
                metricas = self._obtener_metricas_sesion(
                    video_id,
                    fecha_inicio,
                    fecha_fin
                )

                if metricas:
                    clasificacion = self._clasificar_video(metricas)

                    resultado = {
                        'video_id': video_id,
                        'title': title,
                        **metricas,
                        **clasificacion
                    }

                    resultados.append(resultado)

                    simbolo = self._get_simbolo_clasificacion(clasificacion['tipo'])
                    print(f"  {simbolo} {clasificacion['tipo']}: Ratio={clasificacion['ratio']:.2f}")
                else:
                    print(f"  ⚠️  Sin datos suficientes")

            except Exception as e:
                print(f"  ❌ Error: {str(e)[:50]}")

            print()

        # Ordenar por ratio (mejores primero)
        resultados.sort(key=lambda x: x.get('ratio', 0), reverse=True)

        # Generar reporte
        reporte = self._generar_reporte(resultados, dias_analisis)

        # Guardar en Supabase (opcional)
        self._guardar_resultados(resultados)

        return reporte

    def analizar_video(self, video_id: str, dias_analisis: int = 28) -> Optional[Dict]:
        """
        Analiza un video especifico
        """
        fecha_inicio = (datetime.now() - timedelta(days=dias_analisis)).strftime("%Y-%m-%d")
        fecha_fin = datetime.now().strftime("%Y-%m-%d")

        metricas = self._obtener_metricas_sesion(video_id, fecha_inicio, fecha_fin)

        if not metricas:
            return None

        clasificacion = self._clasificar_video(metricas)

        return {
            'video_id': video_id,
            **metricas,
            **clasificacion,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _obtener_metricas_sesion(
        self,
        video_id: str,
        fecha_inicio: str,
        fecha_fin: str
    ) -> Optional[Dict]:
        """
        Obtiene metricas de sesion desde YouTube Analytics API
        """
        try:
            # Query a Analytics API
            response = self.analytics.reports().query(
                ids='channel==MINE',
                startDate=fecha_inicio,
                endDate=fecha_fin,
                metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage',
                dimensions='video',
                filters=f'video=={video_id}',
                sort='-views'
            ).execute()

            if 'rows' not in response or not response['rows']:
                return None

            row = response['rows'][0]

            # Extraer metricas basicas
            views = int(row[1])
            minutes_watched = float(row[2])
            avg_view_duration = float(row[3])
            avg_view_percentage = float(row[4])

            # Intentar obtener metricas de sesion
            # NOTA: sessionStarts y sessionEnds requieren permisos especiales
            # Si no estan disponibles, estimamos basandonos en otras metricas

            try:
                session_response = self.analytics.reports().query(
                    ids='channel==MINE',
                    startDate=fecha_inicio,
                    endDate=fecha_fin,
                    metrics='annotationClickThroughRate,annotationCloseRate,cardClickRate,cardTeaserClickRate',
                    dimensions='video',
                    filters=f'video=={video_id}'
                ).execute()

                # Si tenemos datos de clicks, podemos estimar engagement
                if 'rows' in session_response and session_response['rows']:
                    engagement_row = session_response['rows'][0]
                    # Estas metricas indican si el usuario interactua (señal de continuacion)
                    card_click_rate = float(engagement_row[3]) if len(engagement_row) > 3 else 0
                else:
                    card_click_rate = 0

            except Exception:
                card_click_rate = 0

            # ESTIMACION de continuacion de sesion
            # Basado en:
            # 1. Porcentaje de visualizacion (>50% = probable continuacion)
            # 2. Click rate en cards (clicks = continuacion)
            # 3. Duracion de visualizacion promedio

            # Calcular ratio estimado de continuacion
            # Ratio > 1.0 = video extiende sesiones
            # Ratio < 1.0 = video mata sesiones

            ratio_retencion = avg_view_percentage / 50  # Normalizado a 50%
            ratio_engagement = (card_click_rate * 10) if card_click_rate > 0 else 1.0

            # Estimacion final
            # Si retencion es alta Y hay engagement → EXTENSOR
            # Si retencion es baja → ASESINO

            ratio_continuacion = (ratio_retencion * 0.7) + (ratio_engagement * 0.3)

            return {
                'views': views,
                'minutes_watched': minutes_watched,
                'avg_view_duration': avg_view_duration,
                'avg_view_percentage': avg_view_percentage,
                'card_click_rate': card_click_rate,
                'ratio_continuacion_estimado': ratio_continuacion
            }

        except Exception as e:
            print(f"    [ERROR] Analytics API: {str(e)[:50]}")
            return None

    def _clasificar_video(self, metricas: Dict) -> Dict:
        """
        Clasifica video como EXTENSOR, ASESINO o NEUTRO
        """
        ratio = metricas.get('ratio_continuacion_estimado', 1.0)
        retencion = metricas.get('avg_view_percentage', 0)
        card_clicks = metricas.get('card_click_rate', 0)

        # Clasificacion basada en ratio y metricas adicionales
        if ratio >= 1.3 and retencion >= 60:
            tipo = 'EXTENSOR_ELITE'
            accion = 'Promocionar masivamente - Videos de oro'
            prioridad = 1
        elif ratio >= 1.1 and retencion >= 50:
            tipo = 'EXTENSOR'
            accion = 'Promocionar activamente - Buenos videos'
            prioridad = 2
        elif ratio >= 0.9 and ratio < 1.1:
            tipo = 'NEUTRO'
            accion = 'Mantener - Video normal'
            prioridad = 3
        elif ratio >= 0.7 and ratio < 0.9:
            tipo = 'ASESINO_LEVE'
            accion = 'Optimizar titulo/miniatura urgente'
            prioridad = 4
        else:
            tipo = 'ASESINO_CRITICO'
            accion = 'Despromocionar - Video toxico'
            prioridad = 5

        # Calcular confianza de clasificacion
        if metricas['views'] > 1000:
            confianza = 0.95
        elif metricas['views'] > 500:
            confianza = 0.85
        elif metricas['views'] > 100:
            confianza = 0.70
        else:
            confianza = 0.50

        return {
            'tipo': tipo,
            'ratio': float(ratio),
            'accion_recomendada': accion,
            'prioridad': prioridad,
            'confianza': float(confianza)
        }

    def _generar_reporte(self, resultados: List[Dict], dias_analisis: int) -> Dict:
        """
        Genera reporte completo
        """
        # Contar por tipo
        conteo_tipos = {}
        for r in resultados:
            tipo = r.get('tipo', 'DESCONOCIDO')
            conteo_tipos[tipo] = conteo_tipos.get(tipo, 0) + 1

        # Top extensores
        extensores = [r for r in resultados if 'EXTENSOR' in r.get('tipo', '')]
        extensores_elite = [r for r in extensores if r.get('tipo') == 'EXTENSOR_ELITE']

        # Top asesinos
        asesinos = [r for r in resultados if 'ASESINO' in r.get('tipo', '')]
        asesinos_criticos = [r for r in asesinos if r.get('tipo') == 'ASESINO_CRITICO']

        # Videos neutros
        neutros = [r for r in resultados if r.get('tipo') == 'NEUTRO']

        # Imprimir reporte
        print()
        print("=" * 80)
        print("📊 REPORTE COMPLETO")
        print("=" * 80)
        print()

        print(f"Periodo: {dias_analisis} dias")
        print(f"Videos analizados: {len(resultados)}")
        print()

        print("DISTRIBUCION:")
        for tipo, count in sorted(conteo_tipos.items(), key=lambda x: x[1], reverse=True):
            simbolo = self._get_simbolo_clasificacion(tipo)
            porcentaje = (count / len(resultados)) * 100 if resultados else 0
            print(f"  {simbolo} {tipo}: {count} ({porcentaje:.1f}%)")
        print()

        if extensores_elite:
            print("🏆 TOP 5 EXTENSORES ELITE (Videos de ORO):")
            for i, video in enumerate(extensores_elite[:5], 1):
                print(f"  {i}. {video['title'][:60]}")
                print(f"     Ratio: {video['ratio']:.2f} | Retencion: {video['avg_view_percentage']:.1f}%")
            print()

        if asesinos_criticos:
            print("☠️  TOP 5 ASESINOS CRITICOS (Videos TOXICOS):")
            for i, video in enumerate(sorted(asesinos_criticos, key=lambda x: x['ratio'])[:5], 1):
                print(f"  {i}. {video['title'][:60]}")
                print(f"     Ratio: {video['ratio']:.2f} | Retencion: {video['avg_view_percentage']:.1f}%")
                print(f"     ACCION: {video['accion_recomendada']}")
            print()

        # Recomendaciones estrategicas
        print("=" * 80)
        print("🎯 RECOMENDACIONES ESTRATEGICAS")
        print("=" * 80)
        print()

        if extensores_elite:
            print("1. PROMOCION MASIVA:")
            print(f"   Promociona los {len(extensores_elite)} videos ELITE en:")
            print("   - Pantallas finales de TODOS los videos")
            print("   - Videos sugeridos (playlists)")
            print("   - Tarjetas durante reproduccion")
            print()

        if len(asesinos_criticos) > 0:
            print("2. OPTIMIZACION URGENTE:")
            print(f"   Optimiza los {len(asesinos_criticos)} videos ASESINOS:")
            print("   - Cambiar titulo/miniatura")
            print("   - Mejorar gancho inicial (primeros 30 seg)")
            print("   - Agregar cards a videos EXTENSORES")
            print()

        if len(extensores) > 3:
            print("3. EFECTO TELARAÑA:")
            print(f"   Conecta los {len(extensores)} EXTENSORES entre si")
            print("   - Pantallas finales cruzadas")
            print("   - Playlists tematicas")
            print("   - Inyeccion de trafico mutua")
            print()

        return {
            'periodo_dias': dias_analisis,
            'total_videos': len(resultados),
            'distribucion': conteo_tipos,
            'extensores_elite': len(extensores_elite),
            'extensores': len(extensores),
            'neutros': len(neutros),
            'asesinos': len(asesinos),
            'asesinos_criticos': len(asesinos_criticos),
            'top_extensores': extensores_elite[:5],
            'top_asesinos': sorted(asesinos_criticos, key=lambda x: x['ratio'])[:5],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def _guardar_resultados(self, resultados: List[Dict]):
        """
        Guarda resultados en Supabase (tabla session_analysis)
        """
        # TODO: Crear tabla session_analysis en Supabase
        # Por ahora solo imprimimos
        print()
        print("[INFO] Resultados generados (no guardados en DB aun)")
        print("[TODO] Crear tabla 'session_analysis' en Supabase")
        print()

    def _get_simbolo_clasificacion(self, tipo: str) -> str:
        """
        Obtiene simbolo visual segun clasificacion
        """
        simbolos = {
            'EXTENSOR_ELITE': '🏆',
            'EXTENSOR': '🟢',
            'NEUTRO': '🟡',
            'ASESINO_LEVE': '🟠',
            'ASESINO_CRITICO': '🔴'
        }
        return simbolos.get(tipo, '⚪')


def crear_cliente_analytics():
    """
    Crea cliente de YouTube Analytics API
    """
    # Cargar credenciales OAuth
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        print("[ERROR] Credenciales OAuth no configuradas")
        print("        Se requieren:")
        print("        - YOUTUBE_CLIENT_ID")
        print("        - YOUTUBE_CLIENT_SECRET")
        print("        - YOUTUBE_REFRESH_TOKEN")
        sys.exit(1)

    # Crear credenciales
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=['https://www.googleapis.com/auth/yt-analytics.readonly']
    )

    # Crear cliente
    analytics = build('youtubeAnalytics', 'v2', credentials=credentials)

    return analytics


def main():
    """
    Ejecuta analizador de continuacion de sesion
    """
    print()
    print("=" * 80)
    print("🏆 ULTRA SANTO GRIAL 🏆")
    print("Analizador de Continuacion de Sesion")
    print("=" * 80)
    print()

    # Cargar env
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables de entorno no configuradas")
        print("        SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    # Crear clientes
    sb = create_client(supabase_url, supabase_key)

    try:
        analytics = crear_cliente_analytics()
    except Exception as e:
        print(f"[ERROR] No se pudo crear cliente Analytics: {e}")
        sys.exit(1)

    # Analizador
    analizador = AnalizadorSesionContinuacion(sb, analytics)

    # Determinar modo
    if len(sys.argv) > 1 and sys.argv[1] == "--video_id":
        # Analizar video especifico
        video_id = sys.argv[2]

        print(f"Analizando video: {video_id}")
        print()

        resultado = analizador.analizar_video(video_id)

        if resultado:
            simbolo = analizador._get_simbolo_clasificacion(resultado['tipo'])

            print("RESULTADO:")
            print(f"  Clasificacion: {simbolo} {resultado['tipo']}")
            print(f"  Ratio continuacion: {resultado['ratio']:.2f}")
            print(f"  Retencion: {resultado['avg_view_percentage']:.1f}%")
            print(f"  Vistas: {resultado['views']:,}")
            print(f"  Confianza: {resultado['confianza']:.0%}")
            print()
            print(f"  ACCION: {resultado['accion_recomendada']}")
            print()
        else:
            print("[ERROR] No se pudo analizar video")

    else:
        # Analizar canal completo
        dias = 28
        if len(sys.argv) > 1 and sys.argv[1] == "--dias":
            dias = int(sys.argv[2])

        reporte = analizador.analizar_canal(dias_analisis=dias)


if __name__ == "__main__":
    main()
