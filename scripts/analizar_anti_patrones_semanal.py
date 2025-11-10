#!/usr/bin/env python3
"""
analizar_anti_patrones_semanal.py
Análisis SEMANAL de anti-patrones (NO re-entrena modelo)

PROPÓSITO:
- Detectar qué videos fracasaron esta semana
- Identificar anti-patrones comunes
- Enviar alerta rápida por email
- Actualizar dashboard con advertencias

DIFERENCIA CON RE-ENTRENAMIENTO MENSUAL:
- Este script: SOLO analiza y alerta (ligero, 1 min)
- Re-entrenamiento: Actualiza modelo ML (pesado, 10 min)

EJECUCIÓN:
- GitHub Actions: Cada domingo 3AM
- Manual: python scripts/analizar_anti_patrones_semanal.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from collections import Counter
from supabase import create_client, Client

def load_env():
    """Cargar variables de entorno"""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("[ERROR] Variables SUPABASE_URL y SUPABASE_SERVICE_KEY requeridas")
        sys.exit(1)

    return supabase_url, supabase_key

def calcular_vph(video):
    """Calcula VPH basado en edad del video"""
    try:
        published = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
        edad_horas = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        vph = video.get('view_count', 0) / max(edad_horas, 1)
        return round(vph, 2)
    except:
        return 0.0

def obtener_videos_semana(sb: Client):
    """Obtiene tus videos de la última semana"""
    fecha_inicio = datetime.now(timezone.utc) - timedelta(days=7)

    try:
        result = sb.table("videos")\
            .select("*")\
            .gte("published_at", fecha_inicio.isoformat())\
            .execute()

        videos = result.data if result.data else []

        # Calcular VPH para cada video
        for video in videos:
            video['vph'] = calcular_vph(video)

        return videos

    except Exception as e:
        print(f"[ERROR] Error obteniendo videos: {e}")
        return []

def clasificar_videos(videos):
    """Clasifica videos en éxitos y fracasos"""
    exitos = []
    promedios = []
    fracasos = []

    for video in videos:
        vph = video.get('vph', 0)

        if vph >= 120:
            exitos.append(video)
        elif vph >= 60:
            promedios.append(video)
        else:
            fracasos.append(video)

    return exitos, promedios, fracasos

def analizar_timing(video):
    """Analiza problemas de timing"""
    problemas = []

    try:
        published = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
        dia = published.weekday()
        hora = published.hour

        # Anti-patrón 1: Lunes/Martes mañana
        if dia in [0, 1] and hora < 12:
            problemas.append({
                'patron': 'Publicar lunes/martes en la mañana',
                'confianza': 'ALTA',
                'razon': 'Bajo engagement inicio de semana + audiencia inactiva mañanas'
            })

        # Anti-patrón 2: Domingo noche
        if dia == 6 and hora >= 20:
            problemas.append({
                'patron': 'Publicar domingo noche',
                'confianza': 'MEDIA',
                'razon': 'Audiencia preparándose para semana laboral'
            })

        # Anti-patrón 3: Madrugada
        if 0 <= hora < 6:
            problemas.append({
                'patron': 'Publicar en madrugada',
                'confianza': 'ALTA',
                'razon': 'Audiencia durmiendo, bajo alcance inicial'
            })

    except:
        pass

    return problemas

def analizar_titulo(video):
    """Analiza problemas de título"""
    problemas = []
    titulo = video.get('title', '')

    # Anti-patrón 1: Sin palabras gancho
    ganchos = ['SECRETO', 'TRUCO', 'OCULTO', 'NADIE', 'INCREÍBLE', 'SORPRENDENTE']
    tiene_gancho = any(g in titulo.upper() for g in ganchos)

    if not tiene_gancho:
        problemas.append({
            'patron': 'Título sin palabras gancho',
            'confianza': 'ALTA',
            'razon': 'Títulos genéricos generan menos curiosidad'
        })

    # Anti-patrón 2: Título muy corto
    if len(titulo) < 60:
        problemas.append({
            'patron': 'Título muy corto (<60 caracteres)',
            'confianza': 'MEDIA',
            'razon': 'Títulos cortos no generan suficiente contexto/curiosidad'
        })

    # Anti-patrón 3: Sin año
    tiene_ano = any(str(y) in titulo for y in [2024, 2025, 2026])
    if not tiene_ano:
        problemas.append({
            'patron': 'Título sin año actual',
            'confianza': 'MEDIA',
            'razon': 'Año indica contenido actualizado, mejora CTR'
        })

    # Anti-patrón 4: Título muy largo
    if len(titulo) > 105:
        problemas.append({
            'patron': 'Título muy largo (>105 caracteres)',
            'confianza': 'BAJA',
            'razon': 'Se trunca en búsquedas móviles'
        })

    return problemas

def analizar_nicho(video):
    """Analiza problemas de nicho"""
    problemas = []
    nicho_score = video.get('nicho_score', 0)

    if nicho_score < 50:
        problemas.append({
            'patron': 'Fuera del nicho principal',
            'confianza': 'ALTA',
            'razon': f'Score de nicho bajo ({nicho_score}/100), audiencia no interesada'
        })

    return problemas

def generar_reporte(exitos, promedios, fracasos, sb: Client):
    """Genera reporte de anti-patrones"""

    # Analizar SOLO fracasos
    anti_patrones_detectados = []

    for video in fracasos:
        video_id = video.get('video_id', 'N/A')
        titulo = video.get('title', 'Sin título')
        vph = video.get('vph', 0)

        # Analizar diferentes aspectos
        problemas_timing = analizar_timing(video)
        problemas_titulo = analizar_titulo(video)
        problemas_nicho = analizar_nicho(video)

        todos_problemas = problemas_timing + problemas_titulo + problemas_nicho

        for problema in todos_problemas:
            anti_patrones_detectados.append({
                'patron': problema['patron'],
                'video': titulo,
                'vph': vph,
                'confianza': problema['confianza'],
                'razon': problema['razon']
            })

    # Contar frecuencia de patrones
    patrones_freq = Counter([ap['patron'] for ap in anti_patrones_detectados])

    # Guardar anti-patrones en DB
    for patron, freq in patrones_freq.items():
        try:
            # Buscar si ya existe este patrón
            existing = sb.table("anti_patrones")\
                .select("*")\
                .eq("patron", patron)\
                .execute()

            if existing.data:
                # Actualizar frecuencia
                sb.table("anti_patrones")\
                    .update({
                        'frecuencia': existing.data[0]['frecuencia'] + freq,
                        'actualizado_at': datetime.now(timezone.utc).isoformat()
                    })\
                    .eq("patron", patron)\
                    .execute()
            else:
                # Insertar nuevo
                ejemplos = [ap for ap in anti_patrones_detectados if ap['patron'] == patron]
                confianza = ejemplos[0]['confianza'] if ejemplos else 'MEDIA'
                vph_promedio = sum(ap['vph'] for ap in ejemplos) / len(ejemplos) if ejemplos else 0

                sb.table("anti_patrones").insert({
                    'patron': patron,
                    'descripcion': ejemplos[0]['razon'] if ejemplos else '',
                    'frecuencia': freq,
                    'confianza': confianza,
                    'impacto_vph_promedio': round(vph_promedio, 2),
                    'ejemplos_video_ids': [ap['video'][:50] for ap in ejemplos[:3]]
                }).execute()

        except Exception as e:
            print(f"[WARNING] Error guardando anti-patrón: {e}")

    # Generar texto del reporte
    reporte = f"""
═══════════════════════════════════════════════════════════
📊 ANÁLISIS SEMANAL - ANTI-PATRONES
═══════════════════════════════════════════════════════════

Fecha: {datetime.now().strftime('%Y-%m-%d')}
Período: Últimos 7 días

RESUMEN:
├── Videos publicados: {len(exitos) + len(promedios) + len(fracasos)}
├── Éxitos (VPH >= 120): {len(exitos)} videos ✅
├── Promedio (VPH 60-120): {len(promedios)} videos 🟡
└── Fracasos (VPH < 60): {len(fracasos)} videos ❌

"""

    if len(fracasos) == 0:
        reporte += """
🎉 ¡EXCELENTE! No hay fracasos esta semana.
Todos tus videos están rindiendo bien.

CONTINÚA ASÍ:
✅ Mantén tu estrategia actual
✅ Replica patrones de éxitos recientes
✅ No cambies lo que funciona

"""
    else:
        reporte += f"""
ANTI-PATRONES DETECTADOS:
(Qué evitar según fracasos de esta semana)

"""
        for patron, count in patrones_freq.most_common(5):
            reporte += f"❌ {patron} ({count} video{'s' if count > 1 else ''})\n"

            ejemplos = [ap for ap in anti_patrones_detectados if ap['patron'] == patron][:2]
            for ej in ejemplos:
                reporte += f"   └─ \"{ej['video'][:50]}...\" → VPH {ej['vph']}\n"
                reporte += f"      Razón: {ej['razon']}\n"

            reporte += "\n"

        reporte += """
RECOMENDACIONES:
✅ Publicar jueves-viernes 5PM-8PM
✅ Usar palabras gancho (SECRETO, TRUCO, OCULTO, NADIE)
✅ Títulos 80-100 caracteres
✅ Incluir año (2025)
✅ Score de nicho >= 60

"""

    reporte += f"""
═══════════════════════════════════════════════════════════
PRÓXIMOS EVENTOS:
- Próximo análisis semanal: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}
- Próximo re-entrenamiento del modelo ML: Día 1 del mes

NOTA: Este análisis NO modifica el modelo ML.
El modelo se actualiza automáticamente el día 1 de cada mes.
═══════════════════════════════════════════════════════════
"""

    return reporte

def main():
    """Función principal"""
    print("="*80)
    print("ANÁLISIS SEMANAL DE ANTI-PATRONES")
    print("="*80)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Cargar entorno
    supabase_url, supabase_key = load_env()
    sb: Client = create_client(supabase_url, supabase_key)

    # Obtener videos de la semana
    print("[1/3] Obteniendo videos de la última semana...")
    videos = obtener_videos_semana(sb)

    if not videos:
        print("[INFO] No hay videos publicados esta semana")
        print("\n[✅] Análisis completado (sin datos)")
        return

    print(f"  Videos encontrados: {len(videos)}")

    # Clasificar
    print("\n[2/3] Clasificando videos...")
    exitos, promedios, fracasos = clasificar_videos(videos)
    print(f"  Éxitos: {len(exitos)}")
    print(f"  Promedio: {len(promedios)}")
    print(f"  Fracasos: {len(fracasos)}")

    # Generar reporte
    print("\n[3/3] Generando reporte...")
    reporte = generar_reporte(exitos, promedios, fracasos, sb)

    print(reporte)

    # TODO: Enviar email (implementar si hay servicio de email configurado)
    # enviar_email_semanal(reporte)

    print("\n" + "="*80)
    print("✅ ANÁLISIS SEMANAL COMPLETADO")
    print("="*80)
    print("\n[IMPORTANTE] Este análisis es informativo")
    print("[IMPORTANTE] NO modifica el modelo ML")
    print("[IMPORTANTE] Modelo se actualiza día 1 de cada mes\n")

if __name__ == "__main__":
    main()
