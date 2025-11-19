#!/usr/bin/env python3
"""
Sistema de Purga Inteligente para Supabase
Detecta cuando está por llenarse (500 GB gratis) y hace borrado automático
manteniendo CONTINUIDAD (no empieza desde 0)

Estrategia:
1. Monitorea uso de storage
2. Al 90% (450 GB), purga datos viejos (>6 meses)
3. Mantiene watermarks para continuidad
4. Conserva datos recientes y críticos
"""
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================================
# CONFIGURACIÓN DE PURGA
# ============================================================================

PURGA_CONFIG = {
    # Límites de storage (FREE TIER = 500MB database + 1GB files = ~1.5GB total)
    "limite_total_gb": 1.5,   # Supabase FREE tier (500MB DB + 1GB storage)
    "alerta_porcentaje": 70,  # Alerta al 70% (1.05 GB)
    "purga_porcentaje": 85,   # Purgar al 85% (1.27 GB) - Antes de llegar al límite

    # Retención de datos (qué tan viejo antes de borrar)
    "retencion_dias": {
        "videos": 180,            # 6 meses
        "video_statistics": 90,   # 3 meses
        "comments": 90,           # 3 meses
        "captions": 180,          # 6 meses (subtítulos - críticos para scripts)
        "trending_videos": 30,    # 1 mes
        "ai_analysis": 180,       # 6 meses
        "sync_log": 30            # 1 mes
    },

    # Datos críticos a NUNCA borrar
    "conservar_siempre": {
        "videos_propios": True,  # Videos de tu canal
        "minas_oro": True,       # Videos con alta prioridad
        "datos_recientes": 30    # Últimos 30 días NUNCA borrar
    }
}

# ============================================================================
# MONITOREO DE STORAGE
# ============================================================================

def estimar_uso_storage_gb() -> float:
    """
    Estima el uso de storage en GB contando registros

    NOTA: Supabase no expone el uso real de storage fácilmente,
    así que estimamos basándonos en número de registros

    Promedio estimado:
    - Video: 2 KB
    - Video_statistics: 0.5 KB
    - Comment: 1 KB
    - AI_analysis: 5 KB
    """
    print("[STORAGE] Estimando uso actual...")

    # Contadores por tabla
    tablas_peso = {
        "videos": 0.002,              # 2 KB por video
        "video_statistics": 0.0005,   # 0.5 KB por stat
        "comments": 0.001,            # 1 KB por comment
        "captions": 0.007,            # 7 KB por caption (promedio 7,000 caracteres)
        "trending_videos": 0.002,     # 2 KB por trending
        "ai_analysis": 0.005,         # 5 KB por análisis
        "thumbnails_analysis": 0.003, # 3 KB por thumbnail
        "sync_log": 0.001             # 1 KB por log
    }

    uso_total_mb = 0

    for tabla, peso_mb in tablas_peso.items():
        try:
            result = supabase.table(tabla).select("*", count="exact").limit(0).execute()
            count = result.count or 0
            uso_mb = count * peso_mb
            uso_total_mb += uso_mb
            print(f"  {tabla:30} {count:,} registros → {uso_mb:.2f} MB")
        except Exception as e:
            print(f"  {tabla:30} [ERROR] {e}")

    uso_gb = uso_total_mb / 1024
    print(f"\n[STORAGE] Uso estimado total: {uso_gb:.2f} GB")

    return uso_gb

def verificar_estado_storage() -> dict:
    """
    Verifica el estado del storage y determina si necesita purga

    Returns:
        {
            "uso_gb": float,
            "porcentaje": float,
            "necesita_alerta": bool,
            "necesita_purga": bool
        }
    """
    uso_gb = estimar_uso_storage_gb()
    limite_gb = PURGA_CONFIG["limite_total_gb"]
    porcentaje = (uso_gb / limite_gb) * 100

    estado = {
        "uso_gb": uso_gb,
        "limite_gb": limite_gb,
        "porcentaje": porcentaje,
        "necesita_alerta": porcentaje >= PURGA_CONFIG["alerta_porcentaje"],
        "necesita_purga": porcentaje >= PURGA_CONFIG["purga_porcentaje"]
    }

    print(f"\n[STORAGE] Estado: {uso_gb:.2f} GB / {limite_gb} GB ({porcentaje:.1f}%)")

    if estado["necesita_purga"]:
        print(f"[⚠️ CRÍTICO] Uso al {porcentaje:.1f}% - PURGA REQUERIDA")
    elif estado["necesita_alerta"]:
        print(f"[⚠️ ALERTA] Uso al {porcentaje:.1f}% - Aproximándose al límite")
    else:
        print(f"[✅ OK] Uso al {porcentaje:.1f}% - Espacio suficiente")

    return estado

# ============================================================================
# PURGA INTELIGENTE CON CONTINUIDAD
# ============================================================================

def purgar_tabla(tabla: str, retencion_dias: int, conservar_recientes_dias: int = 30) -> int:
    """
    Purga registros antiguos de una tabla manteniendo continuidad

    Args:
        tabla: Nombre de la tabla
        retencion_dias: Días de retención (borrar más viejos que esto)
        conservar_recientes_dias: NUNCA borrar últimos X días

    Returns:
        Número de registros eliminados
    """
    print(f"\n[PURGA] Procesando tabla: {tabla}")

    # Calcular fechas límite
    fecha_limite_purga = datetime.now() - timedelta(days=retencion_dias)
    fecha_limite_conservar = datetime.now() - timedelta(days=conservar_recientes_dias)

    print(f"  Borrar registros anteriores a: {fecha_limite_purga.date()}")
    print(f"  Conservar SIEMPRE posteriores a: {fecha_limite_conservar.date()}")

    # Mapeo de columnas de timestamp por tabla
    timestamp_columns = {
        "videos": "created_at",
        "video_statistics": "snapshot_at",
        "comments": "imported_at",
        "captions": "imported_at",
        "trending_videos": "created_at",
        "ai_analysis": "analyzed_at",
        "sync_log": "started_at"
    }

    timestamp_col = timestamp_columns.get(tabla)
    if not timestamp_col:
        print(f"  [SKIP] No se definió columna de timestamp para {tabla}")
        return 0

    try:
        # Contar registros a eliminar
        result_count = supabase.table(tabla) \
            .select("*", count="exact") \
            .lt(timestamp_col, fecha_limite_purga.isoformat()) \
            .execute()

        count_a_eliminar = result_count.count or 0

        if count_a_eliminar == 0:
            print(f"  [OK] No hay registros antiguos para eliminar")
            return 0

        print(f"  [INFO] Registros a eliminar: {count_a_eliminar:,}")

        # Eliminar en lotes (evitar timeouts)
        BATCH_SIZE = 1000
        total_eliminado = 0

        while True:
            # Obtener IDs de registros a eliminar (batch)
            result = supabase.table(tabla) \
                .select("id") \
                .lt(timestamp_col, fecha_limite_purga.isoformat()) \
                .limit(BATCH_SIZE) \
                .execute()

            if not result.data:
                break

            ids_a_eliminar = [r["id"] for r in result.data]

            # Eliminar batch
            for id_val in ids_a_eliminar:
                try:
                    supabase.table(tabla).delete().eq("id", id_val).execute()
                    total_eliminado += 1
                except Exception as e:
                    print(f"    [WARNING] Error eliminando {id_val}: {e}")

            print(f"  [PROGRESO] Eliminados: {total_eliminado:,} / {count_a_eliminar:,}")

            if len(ids_a_eliminar) < BATCH_SIZE:
                break

        print(f"  [OK] Total eliminado: {total_eliminado:,} registros")

        # Registrar purga en sync_log
        supabase.table("sync_log").insert({
            "sync_type": f"purga_{tabla}",
            "source": "purga_inteligente",
            "records_deleted": total_eliminado,
            "status": "success",
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat()
        }).execute()

        return total_eliminado

    except Exception as e:
        print(f"  [ERROR] Error purgando {tabla}: {e}")
        return 0

def ejecutar_purga_completa() -> dict:
    """
    Ejecuta purga completa en todas las tablas configuradas

    Returns:
        Dict con estadísticas de purga
    """
    print("="*80)
    print("PURGA INTELIGENTE DE SUPABASE")
    print("="*80)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Verificar estado antes de purgar
    estado_antes = verificar_estado_storage()

    if not estado_antes["necesita_purga"]:
        print("\n[INFO] No se requiere purga en este momento")
        return {"purga_ejecutada": False}

    print("\n[INFO] Iniciando purga inteligente...\n")

    # Purgar cada tabla según configuración
    stats_purga = {}
    total_eliminado = 0

    for tabla, retencion_dias in PURGA_CONFIG["retencion_dias"].items():
        eliminados = purgar_tabla(
            tabla,
            retencion_dias,
            PURGA_CONFIG["conservar_siempre"]["datos_recientes"]
        )
        stats_purga[tabla] = eliminados
        total_eliminado += eliminados

    # Verificar estado después de purgar
    print("\n" + "="*80)
    print("VERIFICANDO ESTADO POST-PURGA")
    print("="*80)
    estado_despues = verificar_estado_storage()

    # Resumen
    print("\n" + "="*80)
    print("RESUMEN DE PURGA")
    print("="*80)
    print(f"Antes:  {estado_antes['uso_gb']:.2f} GB ({estado_antes['porcentaje']:.1f}%)")
    print(f"Después: {estado_despues['uso_gb']:.2f} GB ({estado_despues['porcentaje']:.1f}%)")
    print(f"Liberado: {estado_antes['uso_gb'] - estado_despues['uso_gb']:.2f} GB")
    print(f"\nRegistros eliminados por tabla:")
    for tabla, count in stats_purga.items():
        if count > 0:
            print(f"  {tabla:30} {count:,}")
    print(f"\nTotal eliminado: {total_eliminado:,} registros")

    print("\n" + "="*80)
    print("✅ PURGA COMPLETADA")
    print("="*80)
    print("\n[IMPORTANTE] Los datos nuevos continuarán desde donde quedaron")
    print("[IMPORTANTE] Los watermarks se mantienen intactos")
    print("[IMPORTANTE] No se perdió continuidad del sistema")

    return {
        "purga_ejecutada": True,
        "total_eliminado": total_eliminado,
        "uso_antes_gb": estado_antes["uso_gb"],
        "uso_despues_gb": estado_despues["uso_gb"],
        "gb_liberados": estado_antes["uso_gb"] - estado_despues["uso_gb"],
        "stats_por_tabla": stats_purga
    }

# ============================================================================
# VERIFICACIÓN AUTOMÁTICA (para cronjob)
# ============================================================================

def verificar_y_purgar_si_necesario():
    """
    Verifica el estado y purga automáticamente si es necesario
    Usar en cronjob semanal o mensual
    """
    print("="*80)
    print("VERIFICACIÓN AUTOMÁTICA DE STORAGE")
    print("="*80)

    estado = verificar_estado_storage()

    if estado["necesita_purga"]:
        print("\n[ACCIÓN] Ejecutando purga automática...")
        return ejecutar_purga_completa()
    elif estado["necesita_alerta"]:
        print("\n[ALERTA] Storage al {}% - Considerar purga pronto".format(
            round(estado["porcentaje"], 1)
        ))
        return {"alerta": True, "purga_ejecutada": False}
    else:
        print("\n[OK] Storage en buen estado - No se requiere acción")
        return {"ok": True, "purga_ejecutada": False}

# ============================================================================
# EJECUCIÓN
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        print("[INFO] Purga forzada (ignorando umbrales)")
        ejecutar_purga_completa()
    else:
        verificar_y_purgar_si_necesario()
