#!/usr/bin/env python3
"""
Utilidades para filtrado inteligente por nicho y optimización de cuota YouTube API

Este módulo proporciona funciones para:
- Filtrar videos por relevancia al nicho
- Detectar videos "mina de oro" (crecimiento explosivo)
- Tracking de cuota de YouTube API
- Priorización inteligente de contenido
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Cargar configuración del nicho
CONFIG_PATH = Path(__file__).parent.parent / "config_nicho.json"

def cargar_config() -> Dict:
    """Carga la configuración del nicho"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            print(f"[SUCCESS] ✓ config_nicho.json cargado desde: {CONFIG_PATH}")
            print(f"[SUCCESS] ✓ Keywords oro: {len(config['nicho']['keywords_oro'])}")
            print(f"[SUCCESS] ✓ Keywords excluir: {len(config['nicho']['keywords_excluir'])}")
            return config
    except FileNotFoundError:
        print(f"[ERROR] ✗ config_nicho.json NO encontrado en: {CONFIG_PATH}")
        print(f"[ERROR] ✗ Usando configuracion DEFAULT (ULTRA PERMISIVA)")
        return get_config_default()

def get_config_default() -> Dict:
    """Configuración por defecto si no existe el archivo"""
    return {
        "nicho": {
            "keywords_oro": ["tutorial", "ia", "pc", "tecnologia"],
            "keywords_excluir": ["free fire", "fortnite", "reto"],
            "categorias_youtube_permitidas": [27, 28, 24]
        },
        "deteccion_mina_oro": {
            "metricas_crecimiento": {
                "min_views_per_hour_nuevo": 500,
                "min_likes_ratio": 0.05
            }
        }
    }

CONFIG = cargar_config()

# ============================================================================
# FILTRADO POR RELEVANCIA DE NICHO
# ============================================================================

def calcular_relevancia_nicho(titulo: str, descripcion: str = "",
                               category_id: Optional[int] = None) -> int:
    """
    Calcula la relevancia de un video con el nicho (0-100)

    Args:
        titulo: Título del video
        descripcion: Descripción del video (IGNORADO - solo se usa título)
        category_id: ID de categoría de YouTube

    Returns:
        Score de 0-100 (0 = irrelevante, 100 = muy relevante)
    """
    score = 0
    # FIX 2025-11-07: SOLO usar título, ignorar descripción
    # Las descripciones tienen ruido (links a redes sociales, etc.)
    texto = titulo.lower()

    nicho_config = CONFIG["nicho"]
    keywords_oro = nicho_config.get("keywords_oro", [])
    keywords_alto_valor = nicho_config.get("keywords_alto_valor", [])
    keywords_excluir = nicho_config.get("keywords_excluir", [])
    categorias_permitidas = nicho_config.get("categorias_youtube_permitidas", [])

    # DEBUG: Tracking
    debug_info = {
        "matches_oro": [],
        "matches_alto_valor": [],
        "matches_basura": [],
        "bonus_categoria": 0
    }

    # 1. Keywords de oro (valor: 10 puntos c/u, máx 50)
    # FIX 2025-11-07: Usar word boundary para evitar falsos positivos
    # "ia" NO debe matchear "Shakira", "familia", etc.
    matches_oro = 0
    for keyword in keywords_oro:
        # Buscar palabra completa (word boundary)
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, texto):
            matches_oro += 1
            score += 10
            debug_info["matches_oro"].append(keyword)
    score = min(score, 50)  # Cap en 50 por keywords oro

    # 2. Keywords de alto valor (bonus 15 puntos c/u, máx 30)
    for keyword in keywords_alto_valor:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, texto):
            score += 15
            debug_info["matches_alto_valor"].append(keyword)
    score = min(score, 80)  # Cap temporal en 80

    # 3. Bonus por categoría correcta (20 puntos)
    if category_id and category_id in categorias_permitidas:
        score += 20
        debug_info["bonus_categoria"] = 20

    # 4. Penalización FUERTE por keywords basura (-50 por keyword)
    for basura in keywords_excluir:
        pattern = r'\b' + re.escape(basura.lower()) + r'\b'
        if re.search(pattern, texto):
            score -= 50
            debug_info["matches_basura"].append(basura)

    # 5. Normalizar a rango 0-100
    score_final = max(0, min(100, score))

    # DEBUG: Log scoring detallado para videos con score >= 60 (los sospechosos)
    if not hasattr(calcular_relevancia_nicho, '_debug_count'):
        calcular_relevancia_nicho._debug_count = 0

    if calcular_relevancia_nicho._debug_count < 5 and score_final >= 60:
        print(f"[DEBUG SCORING] titulo='{titulo[:50]}'")
        print(f"  - Keywords oro ({len(debug_info['matches_oro'])}): {debug_info['matches_oro'][:5]}")
        print(f"  - Keywords alto valor ({len(debug_info['matches_alto_valor'])}): {debug_info['matches_alto_valor'][:3]}")
        print(f"  - Keywords basura ({len(debug_info['matches_basura'])}): {debug_info['matches_basura']}")
        print(f"  - Bonus categoria: {debug_info['bonus_categoria']} (cat_id={category_id})")
        print(f"  - Score FINAL: {score_final}")
        calcular_relevancia_nicho._debug_count += 1

    return score_final

def es_video_relevante(titulo: str, descripcion: str = "",
                       category_id: Optional[int] = None,
                       min_score: int = 60) -> Tuple[bool, int]:
    """
    Determina si un video es relevante para el nicho

    Returns:
        (es_relevante, score)
    """
    score = calcular_relevancia_nicho(titulo, descripcion, category_id)
    es_relevante = score >= min_score

    # DEBUG: Log primeros 10 videos evaluados
    if not hasattr(es_video_relevante, '_debug_count'):
        es_video_relevante._debug_count = 0

    if es_video_relevante._debug_count < 10:
        status = "PASS ✓" if es_relevante else "REJECT ✗"
        print(f"[DEBUG NICHO] [{status}] score={score:3d} (min={min_score}) | {titulo[:60]}")
        es_video_relevante._debug_count += 1

    return es_relevante, score

# ============================================================================
# DETECCIÓN DE VIDEOS "MINA DE ORO"
# ============================================================================

def calcular_edad_horas(published_at: str) -> float:
    """
    Calcula las horas transcurridas desde la publicación

    Args:
        published_at: Timestamp ISO 8601 (ej: "2025-10-29T10:30:00Z")
    """
    try:
        if isinstance(published_at, str):
            pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        else:
            pub_date = published_at

        now = datetime.now(pub_date.tzinfo)
        delta = now - pub_date
        return delta.total_seconds() / 3600
    except Exception as e:
        print(f"[ERROR] calcular_edad_horas: {e}")
        return 999999  # Valor alto para evitar falsos positivos

def calcular_views_per_hour(views: int, published_at: str) -> float:
    """Calcula vistas por hora"""
    edad_horas = calcular_edad_horas(published_at)
    if edad_horas > 0:
        return views / edad_horas
    return 0

def calcular_engagement(views: int, likes: int, comments: int) -> Dict[str, float]:
    """Calcula métricas de engagement"""
    if views == 0:
        return {
            "likes_ratio": 0,
            "comments_ratio": 0,
            "engagement_score": 0
        }

    likes_ratio = likes / views
    comments_ratio = comments / views
    engagement_score = (likes_ratio * 0.7) + (comments_ratio * 0.3)

    return {
        "likes_ratio": likes_ratio,
        "comments_ratio": comments_ratio,
        "engagement_score": engagement_score
    }

def es_mina_de_oro(views: int, likes: int, comments: int,
                   published_at: str, duration_seconds: int = 0) -> Tuple[bool, str, int]:
    """
    Detecta si un video es una "mina de oro" (crecimiento explosivo)

    Returns:
        (es_oro, razon, score_prioridad)
    """
    config_deteccion = CONFIG["deteccion_mina_oro"]
    metricas = config_deteccion["metricas_crecimiento"]
    filtros_edad = config_deteccion["filtros_edad"]
    tipos_video = config_deteccion["tipos_video"]

    edad_horas = calcular_edad_horas(published_at)
    edad_dias = edad_horas / 24
    views_per_hour = calcular_views_per_hour(views, published_at)
    engagement = calcular_engagement(views, likes, comments)

    es_short = duration_seconds > 0 and duration_seconds <= tipos_video["short"]["max_duracion"]
    es_largo = duration_seconds > tipos_video["largo"]["min_duracion"]

    # === DETECCIÓN DE MINAS DE ORO ===

    # 1. Video NUEVO con crecimiento EXPLOSIVO (<48h, >500 vph)
    if edad_horas <= filtros_edad["max_age_hours_explosivo"]:
        if views_per_hour >= metricas["min_views_per_hour_nuevo"]:
            score = int(views_per_hour * 2)  # Prioridad MUY ALTA
            return True, "crecimiento_explosivo_nuevo", score

    # 2. Video RECIENTE con MOMENTUM (<7 días, >200 vph, engagement >5%)
    if edad_dias <= filtros_edad["max_age_days_momentum"]:
        if (views_per_hour >= metricas["min_views_per_hour_semana"] and
            engagement["likes_ratio"] >= metricas["min_likes_ratio"]):
            score = int(views_per_hour * 1.5)
            return True, "momentum_fuerte", score

    # 3. SHORT VIRAL (<60s, >10k vistas, <24h)
    if es_short:
        if (views >= tipos_video["short"]["min_views_viral"] and
            edad_horas <= tipos_video["short"]["max_age_hours"]):
            score = int(views / 100)
            return True, "short_viral", score

    # 4. VIDEO LARGO con CALIDAD (>10min, engagement >6%)
    if es_largo:
        if engagement["likes_ratio"] >= tipos_video["largo"]["min_likes_ratio"]:
            score = int(views / 50)
            return True, "video_largo_calidad", score

    # 5. ENGAGEMENT ALTÍSIMO (>1% comments, >8% likes)
    if (engagement["comments_ratio"] >= metricas["min_comments_ratio"] and
        engagement["likes_ratio"] >= metricas["min_engagement_score"]):
        score = int(views / 75)
        return True, "engagement_alto", score

    # No es mina de oro
    return False, "no_califica", 0

# ============================================================================
# PRIORIZACIÓN INTELIGENTE
# ============================================================================

def calcular_score_priorizacion(titulo: str, descripcion: str,
                                 views: int, likes: int, comments: int,
                                 published_at: str, duration_seconds: int = 0,
                                 category_id: Optional[int] = None) -> Tuple[int, Dict]:
    """
    Calcula score final para priorizar qué videos analizar

    Returns:
        (score_total, detalles)
    """
    # 1. Relevancia al nicho
    relevancia = calcular_relevancia_nicho(titulo, descripcion, category_id)

    # 2. Mina de oro
    es_oro, razon_oro, score_oro = es_mina_de_oro(
        views, likes, comments, published_at, duration_seconds
    )

    # 3. Si no es oro O baja relevancia → score 0
    if not es_oro:
        return 0, {"razon": "no_es_mina_oro", "relevancia": relevancia}

    min_relevancia = CONFIG["deteccion_mina_oro"]["filtros_relevancia"]["min_relevancia_para_mina_oro"]
    if relevancia < min_relevancia:
        return 0, {"razon": "baja_relevancia", "relevancia": relevancia}

    # 4. Score final = relevancia × score_oro
    score_total = int((relevancia / 100) * score_oro)

    detalles = {
        "relevancia": relevancia,
        "es_mina_oro": True,
        "razon_oro": razon_oro,
        "score_oro": score_oro,
        "score_total": score_total,
        "views_per_hour": calcular_views_per_hour(views, published_at),
        "edad_horas": calcular_edad_horas(published_at)
    }

    return score_total, detalles

def filtrar_y_priorizar_videos(videos: List[Dict], max_resultados: int = 50) -> List[Dict]:
    """
    Filtra videos por nicho y los prioriza por score

    Args:
        videos: Lista de diccionarios con info de videos
        max_resultados: Máximo número de videos a retornar

    Returns:
        Lista de videos filtrados y priorizados
    """
    videos_con_score = []

    for video in videos:
        score, detalles = calcular_score_priorizacion(
            titulo=video.get("title", ""),
            descripcion=video.get("description", ""),
            views=video.get("view_count", 0),
            likes=video.get("like_count", 0),
            comments=video.get("comment_count", 0),
            published_at=video.get("published_at", ""),
            duration_seconds=video.get("duration_seconds", 0),
            category_id=video.get("category_id")
        )

        if score > 0:  # Solo videos que pasaron el filtro
            video["nicho_score"] = score
            video["nicho_detalles"] = detalles
            videos_con_score.append(video)

    # Ordenar por score descendente
    videos_con_score.sort(key=lambda v: v["nicho_score"], reverse=True)

    # Retornar top N
    return videos_con_score[:max_resultados]

# ============================================================================
# TRACKING DE CUOTA YOUTUBE API
# ============================================================================

def registrar_uso_cuota(operacion: str, unidades: int, supabase_client=None):
    """
    Registra el uso de cuota en la tabla youtube_quota

    Args:
        operacion: Nombre de la operación (ej: "search.list")
        unidades: Unidades consumidas
        supabase_client: Cliente de Supabase (opcional)
    """
    if not supabase_client:
        return

    try:
        from datetime import date
        hoy = date.today().isoformat()

        # Obtener registro de hoy
        result = supabase_client.table("youtube_quota").select("*").eq("date", hoy).execute()

        if result.data:
            # Actualizar existente
            registro = result.data[0]
            nuevo_total = registro["units_used"] + unidades

            operations = registro.get("operations", [])
            operations.append({
                "operacion": operacion,
                "unidades": unidades,
                "timestamp": datetime.now().isoformat()
            })

            supabase_client.table("youtube_quota").update({
                "units_used": nuevo_total,
                "operations": operations
            }).eq("date", hoy).execute()
        else:
            # Crear nuevo
            supabase_client.table("youtube_quota").insert({
                "date": hoy,
                "units_used": unidades,
                "max_quota": 10000,
                "operations": [{
                    "operacion": operacion,
                    "unidades": unidades,
                    "timestamp": datetime.now().isoformat()
                }]
            }).execute()

        print(f"[CUOTA] {operacion}: {unidades} unidades registradas")

    except Exception as e:
        print(f"[WARNING] Error registrando cuota: {e}")

def verificar_cuota_disponible(supabase_client=None) -> Tuple[int, int, float]:
    """
    Verifica la cuota disponible del día

    Returns:
        (cuota_usada, cuota_disponible, porcentaje_uso)
    """
    if not supabase_client:
        return 0, 10000, 0.0

    try:
        from datetime import date
        hoy = date.today().isoformat()

        result = supabase_client.table("youtube_quota").select("*").eq("date", hoy).execute()

        if result.data:
            registro = result.data[0]
            usada = registro["units_used"]
            max_quota = registro.get("max_quota", 10000)
            disponible = max_quota - usada
            porcentaje = (usada / max_quota) * 100

            return usada, disponible, porcentaje
        else:
            return 0, 10000, 0.0

    except Exception as e:
        print(f"[WARNING] Error verificando cuota: {e}")
        return 0, 10000, 0.0

# ============================================================================
# HELPERS PARA CONFIGURACIÓN
# ============================================================================

def get_keywords_nicho() -> List[str]:
    """Retorna todas las keywords del nicho"""
    return CONFIG["nicho"].get("keywords_oro", [])

def get_keywords_excluir() -> List[str]:
    """Retorna keywords a excluir"""
    return CONFIG["nicho"].get("keywords_excluir", [])

def get_limite_cuota_operacion(nombre_script: str) -> int:
    """Retorna el límite de cuota para una operación específica"""
    distribucion = CONFIG["cuota_youtube_api"]["distribucion_diaria"]
    script_config = distribucion.get(nombre_script, {})
    return script_config.get("unidades", 0)

def debe_ejecutarse_hoy(nombre_script: str, sb_client=None) -> bool:
    """
    Determina si un script debe ejecutarse hoy según su frecuencia

    FIX 2025-11-01: Usar watermarks para calcular días transcurridos REALES
    en lugar de día del mes % 3
    """
    distribucion = CONFIG["cuota_youtube_api"]["distribucion_diaria"]
    script_config = distribucion.get(nombre_script, {})
    frecuencia = script_config.get("frecuencia", "diaria")

    if frecuencia == "diaria":
        return True
    elif frecuencia == "cada_3_dias":
        # FIX: Usar watermarks para verificar última ejecución
        if sb_client:
            try:
                result = sb_client.table("script_execution_log") \
                    .select("last_run") \
                    .eq("script_name", nombre_script) \
                    .order("last_run", desc=True) \
                    .limit(1) \
                    .execute()

                if result.data:
                    from datetime import timezone as tz
                    last_run = datetime.fromisoformat(result.data[0]["last_run"].replace('Z', '+00:00'))
                    now_utc = datetime.now(tz.utc)
                    dias_desde_ultima = (now_utc - last_run).days
                    print(f"[DEBUG] {nombre_script}: última ejecución hace {dias_desde_ultima} días")
                    return dias_desde_ultima >= 3
                else:
                    # Primera ejecución
                    return True
            except Exception as e:
                print(f"[WARNING] Error verificando watermark: {e}, ejecutando por defecto")
                return True
        else:
            # Fallback a lógica anterior si no hay cliente Supabase
            # Usar día del año para distribuir mejor
            return (datetime.now().timetuple().tm_yday % 3) == 0
    elif frecuencia == "semanal":
        # Solo lunes
        return datetime.now().weekday() == 0

    return True

# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    print("=== PRUEBA DE FILTRADO POR NICHO ===\n")

    # Video de prueba 1: Relevante
    titulo1 = "Tutorial Completo ChatGPT 2025 - IA Gratis para PC"
    desc1 = "Aprende a usar ChatGPT paso a paso, trucos y configuración"
    relevancia1 = calcular_relevancia_nicho(titulo1, desc1, 28)
    print(f"Video 1: {titulo1}")
    print(f"Relevancia: {relevancia1}/100\n")

    # Video de prueba 2: Irrelevante (gaming)
    titulo2 = "Free Fire Nuevo Reto 24 Horas Challenge"
    desc2 = "Jugando Free Fire toda la noche, épico"
    relevancia2 = calcular_relevancia_nicho(titulo2, desc2, 20)
    print(f"Video 2: {titulo2}")
    print(f"Relevancia: {relevancia2}/100\n")

    # Detección de mina de oro
    print("=== DETECCIÓN MINA DE ORO ===\n")

    es_oro, razon, score = es_mina_de_oro(
        views=50000,
        likes=3000,
        comments=500,
        published_at="2025-10-29T10:00:00Z",
        duration_seconds=45
    )

    print(f"¿Es mina de oro?: {es_oro}")
    print(f"Razón: {razon}")
    print(f"Score: {score}")
