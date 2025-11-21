#!/usr/bin/env python3
"""
FEEDBACK LOOP - Sistema de Aprendizaje para 7 Cerebros
========================================================
Analiza contenido generado vs performance real
Ejecuta: Semanal (Domingos 03:30 UTC)
Repo: Cuenta 1 (bK777741/yt-pipeline-cron)
"""
import os, sys, json
from datetime import datetime, timedelta
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

def conectar():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERROR] Faltan credenciales Supabase")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def calcular_error_pct(pred, real):
    if not real or not pred or real == 0: return 100.0
    return abs((pred - real) / real) * 100

def calcular_score(ctr_p, ctr_r, ret_p, ret_r, vph_p, vph_r):
    e_ctr = calcular_error_pct(ctr_p, ctr_r) if ctr_r else 50
    e_ret = calcular_error_pct(ret_p, ret_r) if ret_r else 50
    e_vph = calcular_error_pct(vph_p, vph_r) if vph_r else 50

    s_ctr = max(0, 100 - e_ctr)
    s_ret = max(0, 100 - e_ret)
    s_vph = max(0, 100 - e_vph)

    return round(s_ctr * 0.4 + s_ret * 0.4 + s_vph * 0.2, 2)

def main():
    print("="*60)
    print("FEEDBACK LOOP - 7 CEREBROS")
    print(f"Fecha: {datetime.now()}")
    print("="*60)

    sb = conectar()

    # Buscar content_generated publicados
    contents = sb.table("content_generated").select(
        "id, video_id, ctr_predicho, retention_predicho, vph_predicho, "
        "titulo_final, descripcion, hashtags, detonador_usado, published_at"
    ).eq("status", "published").not_.is_("video_id", "null").execute()

    print(f"\n[INFO] {len(contents.data)} videos con contenido generado")

    analizados = 0
    for content in contents.data:
        vid = content["video_id"]

        # Verificar si ya fue analizado hoy
        check = sb.table("feedback_loop_metrics").select("id").eq(
            "content_id", content["id"]
        ).gte("created_at", (datetime.now() - timedelta(days=1)).isoformat()).execute()

        if len(check.data) > 0:
            continue

        # Obtener metricas reales
        stats = sb.table("video_statistics").select(
            "view_count, like_count, comment_count"
        ).eq("video_id", vid).order("date", desc=True).limit(1).execute()

        if not stats.data:
            continue

        stat = stats.data[0]

        analytics = sb.table("video_analytics").select(
            "ctr, average_view_percentage"
        ).eq("video_id", vid).order("date", desc=True).limit(1).execute()

        ctr_r = analytics.data[0].get("ctr") if analytics.data else None
        ret_r = analytics.data[0].get("average_view_percentage") if analytics.data else None
        vph_r = int(stat["view_count"] / 24) if stat["view_count"] else 0

        # Calcular score
        score = calcular_score(
            content.get("ctr_predicho"), ctr_r,
            content.get("retention_predicho"), ret_r,
            content.get("vph_predicho"), vph_r
        )

        # Patrones
        det = content.get("detonador_usado", "")
        pat_ok = {"detonadores_efectivos": [det]} if score >= 70 and det else {}
        pat_bad = {"detonadores_fallidos": [det]} if score < 70 and det else {}

        # Recomendaciones
        recoms = {"usar_mas": [], "evitar": [], "mejorar": []}
        if score >= 80:
            recoms["usar_mas"].append("Repetir estructura - Alta precision")
        elif score < 50:
            recoms["evitar"].append("Evitar estructura - Baja precision")

        if ctr_r and ctr_r < 3:
            recoms["mejorar"].append("Mejorar titulo - CTR bajo")
        if ret_r and ret_r < 30:
            recoms["mejorar"].append("Mejorar guion - Retencion baja")

        # Guardar
        sb.table("feedback_loop_metrics").insert({
            "content_id": content["id"],
            "video_id": vid,
            "ctr_predicho": content.get("ctr_predicho"),
            "retention_predicha": content.get("retention_predicho"),
            "vph_predicho": content.get("vph_predicho"),
            "ctr_real": ctr_r,
            "retention_real": ret_r,
            "vph_real": vph_r,
            "views_real": stat["view_count"],
            "likes_real": stat["like_count"],
            "comments_real": stat["comment_count"],
            "ctr_error_pct": calcular_error_pct(content.get("ctr_predicho"), ctr_r) if ctr_r else None,
            "retention_error_pct": calcular_error_pct(content.get("retention_predicho"), ret_r) if ret_r else None,
            "vph_error_pct": calcular_error_pct(content.get("vph_predicho"), vph_r) if vph_r else None,
            "score_exito": score,
            "patrones_exito": json.dumps(pat_ok),
            "patrones_fracaso": json.dumps(pat_bad),
            "titulo_usado": content.get("titulo_final"),
            "detonadores_usados": json.dumps([det]),
            "recomendaciones": json.dumps(recoms),
            "checkpoint_analizado": "7d",
            "analizado_por": "analizar_feedback_loop.py"
        }).execute()

        analizados += 1
        print(f"[OK] Analizado: {vid[:12]}... | Score: {score}/100")

    print(f"\n{'='*60}")
    print(f"[OK] {analizados} videos analizados")
    print(f"[OK] Feedback Loop completado")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
