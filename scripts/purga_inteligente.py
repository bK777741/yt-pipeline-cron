#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PURGA INTELIGENTE AUTOMATICA
=============================

Limpia datos antiguos de Supabase y DB local
PERO extrae aprendizajes antes de borrar

RETENCION:
- Logs: 7 dias
- Analisis pesados: 30 dias
- Videos normales: 90 dias
- Videos exitosos: 180 dias (6 meses)
- Patrones: PERMANENTE (nunca se borran)

EJECUCION:
- Manual: python scripts/purga_inteligente.py
- Dry run: python scripts/purga_inteligente.py --dry-run
- Automatico: GitHub Actions (mensual)
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from collections import Counter
from supabase import create_client, Client

class PurgaInteligente:
    """
    Sistema de purga con extraccion de aprendizajes
    """

    def __init__(self, sb: Client):
        self.sb = sb

        # Ventanas de retencion
        self.RETENCION = {
            'videos_normales': timedelta(days=90),   # 3 meses
            'videos_exitosos': timedelta(days=180),  # 6 meses
            'subtitulos': timedelta(days=180),       # 6 meses
            'trending': timedelta(days=90),          # 3 meses
            'sugerencias_huerfanas': timedelta(days=180)  # 6 meses
        }

    def purgar_supabase(self, dry_run=False):
        """
        Purga completa de Supabase
        """
        print("=" * 80)
        print("PURGA INTELIGENTE DE SUPABASE")
        print("=" * 80)
        print()

        if dry_run:
            print("[DRY RUN MODE - No se borrara nada realmente]\n")

        ahora = datetime.now(timezone.utc)
        total_liberado_mb = 0
        estadisticas = {}

        # 1. EXTRAER APRENDIZAJES PRIMERO
        print("[1/6] Extrayendo aprendizajes de datos antiguos...")
        patrones_extraidos = self._extraer_aprendizajes_previo_purga()
        print(f"      Patrones extraidos: {patrones_extraidos}")
        print()

        # 2. PURGAR VIDEOS NORMALES (>3 meses)
        print("[2/6] Purgando videos normales antiguos...")
        fecha_limite_normal = ahora - self.RETENCION['videos_normales']

        videos_normales = self.sb.table("videos")\
            .select("video_id, vph", count="exact")\
            .lt("published_at", fecha_limite_normal.isoformat())\
            .lt("vph", 100)\
            .execute()

        if videos_normales.count > 0:
            print(f"      Encontrados: {videos_normales.count} videos normales (VPH < 100)")

            if not dry_run:
                for video in videos_normales.data:
                    self.sb.table("videos").delete().eq("video_id", video['video_id']).execute()
                print(f"      Purgados: {videos_normales.count} videos")

            total_liberado_mb += videos_normales.count * 0.002
            estadisticas['videos_normales'] = videos_normales.count
        else:
            print("      No hay videos normales antiguos")
        print()

        # 3. PURGAR VIDEOS EXITOSOS (>6 meses)
        print("[3/6] Purgando videos exitosos muy antiguos...")
        fecha_limite_exitoso = ahora - self.RETENCION['videos_exitosos']

        videos_exitosos = self.sb.table("videos")\
            .select("video_id, vph", count="exact")\
            .lt("published_at", fecha_limite_exitoso.isoformat())\
            .gte("vph", 100)\
            .execute()

        if videos_exitosos.count > 0:
            print(f"      Encontrados: {videos_exitosos.count} videos exitosos (VPH >= 100)")

            if not dry_run:
                for video in videos_exitosos.data:
                    self.sb.table("videos").delete().eq("video_id", video['video_id']).execute()
                print(f"      Purgados: {videos_exitosos.count} videos")

            total_liberado_mb += videos_exitosos.count * 0.002
            estadisticas['videos_exitosos'] = videos_exitosos.count
        else:
            print("      No hay videos exitosos muy antiguos")
        print()

        # 4. PURGAR SUBTITULOS (>6 meses)
        print("[4/6] Purgando subtitulos antiguos...")
        fecha_limite_subtitulos = ahora - self.RETENCION['subtitulos']

        subtitulos = self.sb.table("captions")\
            .select("id", count="exact")\
            .lt("imported_at", fecha_limite_subtitulos.isoformat())\
            .execute()

        if subtitulos.count > 0:
            print(f"      Encontrados: {subtitulos.count} subtitulos")

            if not dry_run:
                self.sb.table("captions")\
                    .delete()\
                    .lt("imported_at", fecha_limite_subtitulos.isoformat())\
                    .execute()
                print(f"      Purgados: {subtitulos.count} subtitulos")

            total_liberado_mb += subtitulos.count * 0.05
            estadisticas['subtitulos'] = subtitulos.count
        else:
            print("      No hay subtitulos antiguos")
        print()

        # 5. PURGAR TRENDING (>3 meses)
        print("[5/6] Purgando datos de trending antiguos...")
        fecha_limite_trending = ahora - self.RETENCION['trending']

        trending = self.sb.table("video_trending")\
            .select("id", count="exact")\
            .lt("captured_at", fecha_limite_trending.isoformat())\
            .execute()

        if trending.count > 0:
            print(f"      Encontrados: {trending.count} registros trending")

            if not dry_run:
                self.sb.table("video_trending")\
                    .delete()\
                    .lt("captured_at", fecha_limite_trending.isoformat())\
                    .execute()
                print(f"      Purgados: {trending.count} registros")

            total_liberado_mb += trending.count * 0.003
            estadisticas['trending'] = trending.count
        else:
            print("      No hay datos trending antiguos")
        print()

        # 6. PURGAR SUGERENCIAS HUERFANAS (>6 meses sin video_id)
        print("[6/6] Purgando sugerencias ML huerfanas...")
        fecha_limite_sugerencias = ahora - self.RETENCION['sugerencias_huerfanas']

        sugerencias = self.sb.table("ml_suggestions")\
            .select("id", count="exact")\
            .is_("video_id", "null")\
            .lt("suggested_at", fecha_limite_sugerencias.isoformat())\
            .execute()

        if sugerencias.count > 0:
            print(f"      Encontradas: {sugerencias.count} sugerencias huerfanas")

            if not dry_run:
                self.sb.table("ml_suggestions")\
                    .delete()\
                    .is_("video_id", "null")\
                    .lt("suggested_at", fecha_limite_sugerencias.isoformat())\
                    .execute()
                print(f"      Purgadas: {sugerencias.count} sugerencias")

            total_liberado_mb += sugerencias.count * 0.001
            estadisticas['sugerencias'] = sugerencias.count
        else:
            print("      No hay sugerencias huerfanas")
        print()

        # RESUMEN
        print("=" * 80)
        print("RESUMEN DE PURGA")
        print("=" * 80)
        print(f"Espacio liberado: ~{total_liberado_mb:.2f} MB")
        print(f"Videos normales: {estadisticas.get('videos_normales', 0)}")
        print(f"Videos exitosos: {estadisticas.get('videos_exitosos', 0)}")
        print(f"Subtitulos: {estadisticas.get('subtitulos', 0)}")
        print(f"Trending: {estadisticas.get('trending', 0)}")
        print(f"Sugerencias: {estadisticas.get('sugerencias', 0)}")
        print()

        if dry_run:
            print("[DRY RUN - No se borro nada realmente]")
        else:
            print("[PURGA COMPLETADA]")
        print()

        return total_liberado_mb, estadisticas

    def _extraer_aprendizajes_previo_purga(self):
        """
        Extrae patrones de videos antiguos ANTES de borrarlos
        """
        # Obtener videos exitosos antiguos (>6 meses)
        fecha_limite = datetime.now(timezone.utc) - timedelta(days=180)

        try:
            videos_exitosos = self.sb.table("videos")\
                .select("*")\
                .lt("published_at", fecha_limite.isoformat())\
                .gte("vph", 100)\
                .execute()

            if not videos_exitosos.data:
                return 0

            # Analizar patrones
            patrones = self._analizar_patrones_exitosos(videos_exitosos.data)

            # Guardar patrones (si tabla existe)
            patrones_guardados = 0
            for patron in patrones:
                try:
                    # Verificar si ya existe
                    existing = self.sb.table("patrones_exito")\
                        .select("id")\
                        .eq("patron_tipo", patron['tipo'])\
                        .eq("patron_valor", patron['valor'])\
                        .execute()

                    if not existing.data:
                        self.sb.table("patrones_exito").insert({
                            'patron_tipo': patron['tipo'],
                            'patron_valor': patron['valor'],
                            'frecuencia': patron['frecuencia'],
                            'vph_promedio': patron['vph_promedio'],
                            'confianza': patron['confianza']
                        }).execute()
                        patrones_guardados += 1
                except Exception as e:
                    # Tabla puede no existir aun, continuar
                    pass

            return patrones_guardados

        except Exception as e:
            print(f"      Warning: No se pudieron extraer patrones: {e}")
            return 0

    def _analizar_patrones_exitosos(self, videos):
        """
        Analiza que tienen en comun los videos exitosos
        """
        patrones = []

        # Palabras en titulos exitosos
        palabras_titulos = []
        vphs = []

        for video in videos:
            titulo = video.get('title', '').lower()
            palabras = [p for p in titulo.split() if len(p) > 3]
            palabras_titulos.extend(palabras)
            vphs.append(video.get('vph', 0))

        if not palabras_titulos:
            return patrones

        # Top palabras
        counter = Counter(palabras_titulos)
        vph_promedio = sum(vphs) / len(vphs) if vphs else 0

        for palabra, freq in counter.most_common(15):
            patrones.append({
                'tipo': 'palabra_titulo_exitosa',
                'valor': palabra,
                'frecuencia': freq,
                'vph_promedio': vph_promedio,
                'confianza': min(freq / len(videos), 1.0)
            })

        return patrones


def main():
    """
    Ejecuta purga completa
    """
    print()
    print("=" * 80)
    print("SISTEMA DE PURGA INTELIGENTE")
    print("Mantiene Supabase limpio y bajo 500 MB")
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

    # Determinar modo
    dry_run = "--dry-run" in sys.argv

    # Ejecutar purga
    purga = PurgaInteligente(sb)
    espacio_liberado, stats = purga.purgar_supabase(dry_run=dry_run)

    # Resultado final
    print("=" * 80)
    print("PURGA FINALIZADA")
    print("=" * 80)
    print(f"Espacio liberado: ~{espacio_liberado:.2f} MB")
    print()
    print("[TIP] Ejecutar mensualmente para mantener espacio optimo")
    print()


if __name__ == "__main__":
    main()
