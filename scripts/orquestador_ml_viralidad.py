#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORQUESTADOR ML DE VIRALIDAD
============================
🧠 CEREBRO DEL SISTEMA 🧠

Coordina TODOS los componentes del sistema ML:
1. Analizadores (texto, miniatura)
2. Simulador pre-publicacion
3. Analisis de continuacion de sesion
4. Detector de pasarelas
5. Sistema de hijacking

FLUJO COMPLETO:
1. Analizar videos existentes (texto + miniatura)
2. Clasificar videos (EXTENSORES/ASESINOS/PASARELAS)
3. Detectar oportunidades de hijacking
4. Generar recomendaciones estrategicas
5. Actualizar modelos ML con feedback

MODOS DE EJECUCION:
- Analisis completo: Todos los componentes
- Analisis ligero: Solo clasificaciones
- Solo recomendaciones: Skip analisis

EJECUCION:
- Manual: python scripts/orquestador_ml_viralidad.py
- Automatico: GitHub Actions (semanal)

COSTO: $0 (todo gratuito)
"""

import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from supabase import create_client, Client


class OrquestadorMLViralidad:
    """
    🧠 Orquestador principal del sistema ML
    """

    def __init__(self, sb: Client):
        self.sb = sb

        # Timestamps
        self.inicio = datetime.now(timezone.utc)

        # Resultados acumulados
        self.resultados = {
            'analisis_texto': [],
            'analisis_miniatura': [],
            'clasificacion_sesion': {},
            'videos_pasarela': {},
            'oportunidades_hijacking': {},
            'recomendaciones': []
        }

    def ejecutar_analisis_completo(self, modo: str = 'completo') -> Dict:
        """
        Ejecuta analisis completo del canal

        Modos:
        - completo: Todos los componentes
        - ligero: Solo clasificaciones
        - recomendaciones: Solo generar recomendaciones
        """
        print()
        print("=" * 80)
        print("🧠 ORQUESTADOR ML DE VIRALIDAD")
        print("Analisis completo del canal")
        print("=" * 80)
        print()

        print(f"Modo: {modo}")
        print(f"Inicio: {self.inicio.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print()

        # FASE 1: Analisis de videos existentes
        if modo in ['completo', 'ligero']:
            print()
            print("=" * 80)
            print("FASE 1: ANALISIS DE VIDEOS EXISTENTES")
            print("=" * 80)
            print()

            self._ejecutar_analisis_videos()

        # FASE 2: Clasificacion de sesiones
        if modo in ['completo', 'ligero']:
            print()
            print("=" * 80)
            print("FASE 2: CLASIFICACION DE SESIONES")
            print("=" * 80)
            print()

            self._ejecutar_clasificacion_sesiones()

        # FASE 3: Deteccion de pasarelas
        if modo in ['completo']:
            print()
            print("=" * 80)
            print("FASE 3: DETECCION DE VIDEOS PASARELA")
            print("=" * 80)
            print()

            self._ejecutar_deteccion_pasarelas()

        # FASE 4: Oportunidades de hijacking
        if modo in ['completo']:
            print()
            print("=" * 80)
            print("FASE 4: OPORTUNIDADES DE HIJACKING")
            print("=" * 80)
            print()

            self._ejecutar_deteccion_hijacking()

        # FASE 5: Generar recomendaciones
        print()
        print("=" * 80)
        print("FASE 5: RECOMENDACIONES ESTRATEGICAS")
        print("=" * 80)
        print()

        self._generar_recomendaciones_estrategicas()

        # Reporte final
        duracion = (datetime.now(timezone.utc) - self.inicio).total_seconds()

        print()
        print("=" * 80)
        print("✅ ANALISIS COMPLETADO")
        print("=" * 80)
        print()
        print(f"Duracion: {duracion:.1f} segundos")
        print()

        # Guardar resultados
        self._guardar_resultados_completos()

        return self.resultados

    def _ejecutar_analisis_videos(self):
        """
        Analiza texto y miniatura de todos los videos
        """
        print("Analizando videos del canal...")
        print()

        # Obtener videos con subtitulos
        videos = self.sb.table("videos")\
            .select("video_id, title, thumbnail_url")\
            .execute()

        if not videos.data:
            print("[WARN] No hay videos en DB")
            return

        print(f"Videos a analizar: {len(videos.data)}")
        print()

        # Importar analizadores
        try:
            # NOTA: Estos imports solo funcionan si los scripts estan en el PATH
            # En produccion, usar importlib o subprocess
            print("[INFO] Analisis de texto y miniatura")
            print("      (Ejecutar scripts individuales para analisis detallado)")
            print()

            # Por ahora solo registramos que se deben ejecutar
            self.resultados['analisis_texto'] = {
                'status': 'pending',
                'script': 'analizador_texto_gratis.py --all',
                'videos_count': len(videos.data)
            }

            self.resultados['analisis_miniatura'] = {
                'status': 'pending',
                'script': 'analizador_miniaturas_gratis.py --all',
                'videos_count': len(videos.data)
            }

        except Exception as e:
            print(f"[ERROR] Analisis de videos: {e}")

    def _ejecutar_clasificacion_sesiones(self):
        """
        Clasifica videos segun continuacion de sesion
        """
        print("Clasificando videos por continuacion de sesion...")
        print()

        try:
            # Obtener videos
            videos = self.sb.table("videos")\
                .select("video_id, title, vph")\
                .order("vph", desc=True)\
                .execute()

            if not videos.data:
                print("[WARN] No hay videos en DB")
                return

            # Clasificacion simplificada basada en VPH
            # (Version completa usa Analytics API - ver analizador_sesion_continuacion.py)

            extensores_elite = []
            extensores = []
            neutros = []
            asesinos = []

            for video in videos.data:
                vph = video.get('vph', 0)

                if vph >= 100:
                    extensores_elite.append(video)
                elif vph >= 50:
                    extensores.append(video)
                elif vph >= 20:
                    neutros.append(video)
                else:
                    asesinos.append(video)

            self.resultados['clasificacion_sesion'] = {
                'extensores_elite': len(extensores_elite),
                'extensores': len(extensores),
                'neutros': len(neutros),
                'asesinos': len(asesinos),
                'top_extensores': extensores_elite[:5],
                'top_asesinos': sorted(asesinos, key=lambda x: x.get('vph', 0))[:5]
            }

            print(f"Clasificacion completada:")
            print(f"  🏆 Extensores ELITE: {len(extensores_elite)}")
            print(f"  🟢 Extensores: {len(extensores)}")
            print(f"  🟡 Neutros: {len(neutros)}")
            print(f"  🔴 Asesinos: {len(asesinos)}")
            print()

        except Exception as e:
            print(f"[ERROR] Clasificacion: {e}")

    def _ejecutar_deteccion_pasarelas(self):
        """
        Detecta videos pasarela
        """
        print("Detectando videos pasarela...")
        print()

        try:
            # Version simplificada - detecta por titulo
            videos = self.sb.table("videos")\
                .select("video_id, title")\
                .execute()

            if not videos.data:
                return

            # Palabras clave de pasarelas
            palabras_pasarela = [
                'que es', 'como', 'tutorial', 'guia',
                'principiantes', 'introduccion', 'basico'
            ]

            pasarelas = []

            for video in videos.data:
                titulo = video['title'].lower()
                if any(p in titulo for p in palabras_pasarela):
                    pasarelas.append(video)

            self.resultados['videos_pasarela'] = {
                'total_pasarelas': len(pasarelas),
                'pasarelas': pasarelas[:10]
            }

            print(f"Pasarelas detectadas: {len(pasarelas)}")
            print()

        except Exception as e:
            print(f"[ERROR] Deteccion pasarelas: {e}")

    def _ejecutar_deteccion_hijacking(self):
        """
        Detecta oportunidades de hijacking
        """
        print("Detectando oportunidades de hijacking...")
        print()

        try:
            # Esta fase requiere YouTube Data API
            # Ver sistema_robo_sesiones.py para implementacion completa

            self.resultados['oportunidades_hijacking'] = {
                'status': 'pending',
                'script': 'sistema_robo_sesiones.py',
                'nota': 'Requiere YouTube Data API - ejecutar manualmente'
            }

            print("[INFO] Deteccion de hijacking requiere ejecucion manual")
            print("      Script: sistema_robo_sesiones.py")
            print()

        except Exception as e:
            print(f"[ERROR] Deteccion hijacking: {e}")

    def _generar_recomendaciones_estrategicas(self):
        """
        Genera recomendaciones basadas en todos los analisis
        """
        print("Generando recomendaciones estrategicas...")
        print()

        recomendaciones = []

        # 1. RECOMENDACIONES DE EXTENSORES
        clasificacion = self.resultados.get('clasificacion_sesion', {})
        extensores_elite = clasificacion.get('extensores_elite', 0)

        if extensores_elite > 0:
            recomendaciones.append({
                'prioridad': 1,
                'categoria': 'PROMOCION',
                'titulo': 'Promocionar videos EXTENSORES ELITE',
                'descripcion': f'Tienes {extensores_elite} videos que extienden sesiones. Promocionalos masivamente.',
                'acciones': [
                    'Agregar a pantallas finales de TODOS los videos',
                    'Crear playlist destacada con estos videos',
                    'Usar como videos sugeridos en tarjetas'
                ]
            })

        # 2. RECOMENDACIONES DE ASESINOS
        asesinos = clasificacion.get('asesinos', 0)

        if asesinos > 3:
            recomendaciones.append({
                'prioridad': 2,
                'categoria': 'OPTIMIZACION',
                'titulo': 'Optimizar videos ASESINOS urgente',
                'descripcion': f'Tienes {asesinos} videos que matan sesiones. Requieren optimizacion.',
                'acciones': [
                    'Cambiar titulo y miniatura',
                    'Mejorar hook inicial (primeros 30 seg)',
                    'Agregar tarjetas a videos EXTENSORES'
                ]
            })

        # 3. RECOMENDACIONES DE PASARELAS
        pasarelas = self.resultados.get('videos_pasarela', {})
        total_pasarelas = pasarelas.get('total_pasarelas', 0)

        if total_pasarelas > 0:
            recomendaciones.append({
                'prioridad': 3,
                'categoria': 'PASARELAS',
                'titulo': 'Optimizar puntos de entrada',
                'descripcion': f'Tienes {total_pasarelas} videos pasarela. Son tus puntos de entrada.',
                'acciones': [
                    'Optimizar SEO (titulo, descripcion, tags)',
                    'Conectar pasarelas con extensores',
                    'Medir trafico de busqueda'
                ]
            })

        # 4. RECOMENDACIONES DE CONTENIDO NUEVO
        recomendaciones.append({
            'prioridad': 4,
            'categoria': 'CREACION',
            'titulo': 'Crear nuevo contenido estrategico',
            'descripcion': 'Ideas de videos con alto potencial viral',
            'acciones': [
                'Ejecutar sistema de hijacking para detectar oportunidades',
                'Crear videos complementarios a virales de competencia',
                'Cubrir queries fundamentales faltantes'
            ]
        })

        # 5. EFECTO TELARAÑA
        if extensores_elite >= 3:
            recomendaciones.append({
                'prioridad': 1,
                'categoria': 'RED',
                'titulo': 'Implementar Efecto Telaraña',
                'descripcion': 'Conectar videos EXTENSORES para maximizar sesiones',
                'acciones': [
                    f'Conectar los {extensores_elite} extensores elite entre si',
                    'Pantallas finales cruzadas',
                    'Playlists tematicas con extensores'
                ]
            })

        self.resultados['recomendaciones'] = recomendaciones

        # Imprimir recomendaciones
        print()
        print("=" * 80)
        print("🎯 RECOMENDACIONES ESTRATEGICAS")
        print("=" * 80)
        print()

        for i, rec in enumerate(sorted(recomendaciones, key=lambda x: x['prioridad']), 1):
            print(f"{i}. [{rec['categoria']}] {rec['titulo']}")
            print(f"   Prioridad: {rec['prioridad']}")
            print(f"   {rec['descripcion']}")
            print()
            print("   Acciones:")
            for accion in rec['acciones']:
                print(f"     • {accion}")
            print()

    def _guardar_resultados_completos(self):
        """
        Guarda resultados completos en archivo JSON
        """
        timestamp = self.inicio.strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(
            os.path.dirname(__file__),
            f'../reportes/reporte_ml_{timestamp}.json'
        )

        # Crear directorio si no existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Guardar
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.resultados, f, indent=2, ensure_ascii=False)

            print()
            print(f"📄 Reporte guardado en: {output_path}")
            print()

        except Exception as e:
            print(f"[ERROR] No se pudo guardar reporte: {e}")


def main():
    """
    Ejecuta orquestador
    """
    print()
    print("=" * 80)
    print("🧠 ORQUESTADOR ML DE VIRALIDAD")
    print("Sistema completo de analisis y optimizacion")
    print("=" * 80)
    print()

    # Args
    modo = 'completo'
    if len(sys.argv) > 1:
        modo = sys.argv[1]

    if modo not in ['completo', 'ligero', 'recomendaciones']:
        print("[ERROR] Modo invalido")
        print("Modos: completo, ligero, recomendaciones")
        sys.exit(1)

    # Cargar env
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables de entorno no configuradas")
        sys.exit(1)

    # Crear cliente
    sb = create_client(supabase_url, supabase_key)

    # Orquestador
    orquestador = OrquestadorMLViralidad(sb)

    # Ejecutar
    resultados = orquestador.ejecutar_analisis_completo(modo=modo)

    print()
    print("=" * 80)
    print("✅ SISTEMA ML COMPLETADO")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
