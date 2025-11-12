#!/usr/bin/env python3
"""
Monitor de Metricas de Videos + Aprendizaje Automatico
Trackea metricas en checkpoints: 1h, 6h, 24h, 48h, 72h
Obtiene CTR desde YouTube Analytics API
Aprende de metricas reales (Stage 2 Learning)
Envia alertas cuando CTR < 5%
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def get_youtube_analytics_service():
    """Crea servicio de YouTube Analytics API con OAuth"""
    try:
        creds = Credentials(
            token=None,
            refresh_token=os.getenv("YT_REFRESH_TOKEN"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("YT_CLIENT_ID"),
            client_secret=os.getenv("YT_CLIENT_SECRET"),
            scopes=['https://www.googleapis.com/auth/yt-analytics.readonly']
        )

        # Refresh token si es necesario
        if creds.expired or not creds.valid:
            creds.refresh(Request())

        return build('youtubeAnalytics', 'v2', credentials=creds)
    except Exception as e:
        print(f"[ERROR] No se pudo crear servicio Analytics: {e}")
        return None

def get_video_ctr(video_id, published_date):
    """
    Obtiene CTR del video desde YouTube Analytics API
    CONSUMO API: 0 unidades (Analytics API tiene cuota separada de 50,000/dia)
    """
    try:
        analytics = get_youtube_analytics_service()
        if not analytics:
            print(f"[WARN] Analytics API no disponible para {video_id}")
            return None

        # Fechas para el query (desde publicacion hasta hoy)
        start_date = published_date.strftime('%Y-%m-%d')
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Query Analytics API
        response = analytics.reports().query(
            ids='channel==MINE',
            startDate=start_date,
            endDate=end_date,
            metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,cardClickRate',
            dimensions='video',
            filters=f'video=={video_id}'
        ).execute()

        if response.get('rows'):
            # cardClickRate es el CTR de thumbnails/titulos
            ctr = response['rows'][0][5] if len(response['rows'][0]) > 5 else None
            print(f"[CTR] {video_id}: {ctr}%")
            return ctr

        print(f"[WARN] No hay datos de CTR para {video_id}")
        return None

    except Exception as e:
        print(f"[ERROR] Error obteniendo CTR: {e}")
        return None

def send_email(subject, body):
    """Envia email usando SMTP"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg['From'] = os.getenv("SMTP_USER")
        msg['To'] = os.getenv("NOTIFICATION_EMAIL")
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
            server.send_message(msg)

        print(f"[EMAIL] {subject}")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo enviar email: {e}")
        return False

def save_learning_data(sb, video, ctr, vph, views, checkpoint):
    """
    Guarda datos de aprendizaje en user_preferences (Stage 2 Learning)
    Aprende de metricas reales de YouTube
    """
    try:
        # Clasificar titulo basado en metricas
        if ctr is not None and ctr >= 8.0:
            # CTR >= 8% = EXCELENTE (título ganador)
            user_action = 'approved'
            reason = f'ctr_excelente_{ctr:.1f}%'
        elif ctr is not None and ctr >= 5.0:
            # CTR 5-8% = BUENO (título aceptable)
            user_action = 'approved'
            reason = f'ctr_bueno_{ctr:.1f}%'
        elif ctr is not None and ctr < 5.0:
            # CTR < 5% = MALO (título rechazado)
            user_action = 'rejected'
            reason = f'ctr_bajo_{ctr:.1f}%'
        elif vph >= 100:
            # Sin CTR pero VPH alto = titulo probablemente bueno
            user_action = 'approved'
            reason = f'vph_alto_{vph}'
        elif vph < 25:
            # VPH bajo = titulo probablemente malo
            user_action = 'rejected'
            reason = f'vph_bajo_{vph}'
        else:
            # Neutro, no guardar
            return None

        # Guardar en user_preferences
        sb.table("user_preferences").insert({
            "content_type": "titulo",
            "original_content": video['title_original'],
            "user_action": user_action,
            "metadata": {
                "ctr": ctr,
                "vph": vph,
                "views": views,
                "checkpoint": checkpoint,
                "reason": reason,
                "video_id": video['video_id'],
                "published_at": video['published_at'],
                "learning_source": "stage2_metrics"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        print(f"[LEARNING] {user_action.upper()}: '{video['title_original'][:50]}...' ({reason})")
        return user_action

    except Exception as e:
        print(f"[ERROR] Error guardando learning data: {e}")
        return None

def generate_new_title_variants(original_title, sb):
    """
    Genera nuevas variantes de titulo usando Gemini
    CONSUMO API: ~500 tokens (input) + ~200 tokens (output) = 0.0007 unidades Gemini
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        prompt = f"""Genera 3 variantes MEJORADAS de este título de YouTube que tiene CTR bajo (<5%):

Título original: "{original_title}"

REQUISITOS:
1. Variante A (Curiosidad): Usa curiosidad, misterio, "secreto", "oculto"
2. Variante B (Beneficio): Promete beneficio claro, "cómo", resultado específico
3. Variante C (Urgencia): Usa urgencia, "AHORA", "YA", números

Formato de respuesta (EXACTO):
A: [título variante A]
B: [título variante B]
C: [título variante C]"""

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Parsear respuesta
        variants = {}
        for line in text.split('\n'):
            if line.startswith('A:'):
                variants['variant_a'] = line.replace('A:', '').strip()
            elif line.startswith('B:'):
                variants['variant_b'] = line.replace('B:', '').strip()
            elif line.startswith('C:'):
                variants['variant_c'] = line.replace('C:', '').strip()

        return variants if len(variants) == 3 else {
            'variant_a': f"DESCUBRE: {original_title}",
            'variant_b': f"Cómo {original_title.lower()} (Tutorial PASO a PASO)",
            'variant_c': f"{original_title} - ¡HAZLO AHORA!"
        }

    except Exception as e:
        print(f"[ERROR] Error generando variantes: {e}")
        # Fallback a variantes simples
        return {
            'variant_a': f"El SECRETO de {original_title}",
            'variant_b': f"Cómo {original_title.lower()} FÁCIL",
            'variant_c': f"{original_title} - TUTORIAL 2025"
        }

def send_alert_email(video, ctr, vph, views, new_variants):
    """Envia email de ALERTA cuando CTR < 5%"""
    subject = f"🚨 ALERTA: CTR BAJO ({ctr:.1f}%) - {video['title_original'][:40]}..."

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <div style="background: #dc2626; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h2 style="margin: 0;">🚨 ALERTA: CTR CRÍTICO</h2>
            <p style="font-size: 18px; margin: 10px 0 0 0;">Es necesario CAMBIAR el título AHORA</p>
        </div>

        <h3 style="color: #dc2626;">Título Actual (RECHAZADO):</h3>
        <p style="background: #fee2e2; padding: 15px; border-radius: 5px; border-left: 4px solid #dc2626;">
            {video['title_original']}
        </p>

        <h3 style="color: #ea580c;">Métricas Actuales:</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <tr style="background: #fee2e2;">
                <td style="padding: 10px; border: 1px solid #fca5a5;"><strong>CTR</strong></td>
                <td style="padding: 10px; border: 1px solid #fca5a5; color: #dc2626; font-weight: bold;">{ctr:.1f}% (< 5% es CRÍTICO)</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>VPH</strong></td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{vph:,}</td>
            </tr>
            <tr style="background: #f3f4f6;">
                <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Vistas</strong></td>
                <td style="padding: 10px; border: 1px solid #e5e7eb;">{views:,}</td>
            </tr>
        </table>

        <h3 style="color: #16a34a;">Nuevos Títulos Sugeridos (A/B Testing):</h3>
        <ul style="list-style: none; padding: 0;">
            <li style="margin: 10px 0; padding: 15px; background: #fef3c7; border-radius: 5px; border-left: 4px solid #f59e0b;">
                <strong>Variante A (Curiosidad):</strong><br>
                <span style="font-size: 16px;">{new_variants['variant_a']}</span>
            </li>
            <li style="margin: 10px 0; padding: 15px; background: #dbeafe; border-radius: 5px; border-left: 4px solid #3b82f6;">
                <strong>Variante B (Beneficio):</strong><br>
                <span style="font-size: 16px;">{new_variants['variant_b']}</span>
            </li>
            <li style="margin: 10px 0; padding: 15px; background: #fce7f3; border-radius: 5px; border-left: 4px solid #ec4899;">
                <strong>Variante C (Urgencia):</strong><br>
                <span style="font-size: 16px;">{new_variants['variant_c']}</span>
            </li>
        </ul>

        <div style="background: #dcfce7; padding: 15px; border-left: 4px solid #16a34a; margin-top: 20px;">
            <p style="margin: 0;"><strong>ACCIÓN RECOMENDADA:</strong></p>
            <p style="margin: 5px 0 0 0;">Cambia el título del video en YouTube Studio con una de las variantes sugeridas AHORA para mejorar el CTR.</p>
        </div>

        <hr style="margin: 30px 0;">
        <p style="color: #6b7280; font-size: 12px;">
            Video ID: {video['video_id']}<br>
            Sistema de Aprendizaje Automático - Stage 2<br>
            Los Cerebros han aprendido que este estilo de título NO funciona
        </p>
    </body>
    </html>
    """

    send_email(subject, body)

def monitor_videos():
    """Monitorea videos en checkpoints especificos"""
    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )

    # Obtener videos en monitoreo
    videos = sb.table("video_monitoring")\
        .select("*")\
        .eq("status", "monitoring")\
        .execute()

    print(f"[INFO] Videos en monitoreo: {len(videos.data)}")

    now = datetime.now(timezone.utc)

    for video in videos.data:
        published = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
        hours_since = (now - published).total_seconds() / 3600

        # Determinar checkpoint
        checkpoint = None
        checkpoint_name = None

        if 0.9 <= hours_since < 1.1:
            checkpoint = "checkpoint_1h"
            checkpoint_name = "1 Hora"
        elif 5.9 <= hours_since < 6.1:
            checkpoint = "checkpoint_6h"
            checkpoint_name = "6 Horas"
        elif 23.9 <= hours_since < 24.1:
            checkpoint = "checkpoint_24h"
            checkpoint_name = "24 Horas"
        elif 47.9 <= hours_since < 48.1:
            checkpoint = "checkpoint_48h"
            checkpoint_name = "48 Horas"
        elif 71.9 <= hours_since < 72.1:
            checkpoint = "checkpoint_72h"
            checkpoint_name = "72 Horas"

        if checkpoint:
            # Verificar si ya se envio notificacion para este checkpoint
            notifications = json.loads(video.get('notifications_sent', '{}') or '{}')
            if checkpoint in notifications:
                print(f"[SKIP] {checkpoint_name} ya notificado para {video['title_original'][:50]}")
                continue

            print(f"\n[{checkpoint_name}] {video['title_original'][:50]}...")

            # Obtener metricas actuales del video
            video_data = sb.table("videos")\
                .select("view_count, like_count, comment_count")\
                .eq("video_id", video['video_id'])\
                .single()\
                .execute()

            views = video_data.data.get('view_count', 0)
            likes = video_data.data.get('like_count', 0)
            comments = video_data.data.get('comment_count', 0)

            # Calcular VPH
            vph = int(views / hours_since) if hours_since > 0 else 0

            # Obtener CTR desde YouTube Analytics API (solo en checkpoint 24h, 48h, 72h)
            ctr = None
            if checkpoint in ["checkpoint_24h", "checkpoint_48h", "checkpoint_72h"]:
                published_date = datetime.fromisoformat(video['published_at'].replace('Z', '+00:00'))
                ctr = get_video_ctr(video['video_id'], published_date)

            # Guardar metricas en JSONB
            current_metrics = json.loads(video.get('metrics', '{}') or '{}')
            current_metrics[checkpoint] = {
                'timestamp': now.isoformat(),
                'views': views,
                'likes': likes,
                'comments': comments,
                'vph': vph,
                'ctr': ctr,
                'hours_since': round(hours_since, 1)
            }

            # Actualizar notificaciones enviadas
            notifications[checkpoint] = now.isoformat()

            # Actualizar en base de datos
            sb.table("video_monitoring").update({
                'metrics': json.dumps(current_metrics),
                'notifications_sent': json.dumps(notifications),
                'last_check_at': now.isoformat(),
                'monitoring_stage': checkpoint
            }).eq('video_id', video['video_id']).execute()

            # Evaluar performance (con CTR si está disponible)
            if checkpoint == "checkpoint_1h":
                nivel = "EXCELENTE" if vph >= 100 else "BUENO" if vph >= 50 else "NORMAL" if vph >= 25 else "BAJO"
                color = "#10b981" if vph >= 50 else "#f59e0b" if vph >= 25 else "#ef4444"
            elif checkpoint == "checkpoint_24h":
                # En 24h usamos CTR como métrica principal
                if ctr is not None:
                    nivel = "VIRAL" if ctr >= 10.0 else "EXCELENTE" if ctr >= 8.0 else "BUENO" if ctr >= 5.0 else "CRÍTICO"
                    color = "#10b981" if ctr >= 8.0 else "#f59e0b" if ctr >= 5.0 else "#ef4444"
                else:
                    nivel = "VIRAL" if vph >= 50 else "BUENO" if vph >= 25 else "NORMAL" if vph >= 10 else "BAJO"
                    color = "#10b981" if vph >= 25 else "#f59e0b" if vph >= 10 else "#ef4444"
            else:
                nivel = "BUENO" if vph >= 20 else "NORMAL" if vph >= 10 else "BAJO"
                color = "#10b981" if vph >= 20 else "#f59e0b" if vph >= 10 else "#ef4444"

            # STAGE 2 LEARNING: Guardar en user_preferences
            save_learning_data(sb, video, ctr, vph, views, checkpoint)

            # ALERTA CRÍTICA: Si CTR < 5% en checkpoint 24h, enviar alerta con nuevas variantes
            if checkpoint == "checkpoint_24h" and ctr is not None and ctr < 5.0:
                print(f"[ALERT] CTR CRÍTICO: {ctr:.1f}% - Generando nuevos títulos...")
                new_variants = generate_new_title_variants(video['title_original'], sb)
                send_alert_email(video, ctr, vph, views, new_variants)

                # Guardar variantes sugeridas en monitoring
                sb.table("video_monitoring").update({
                    'alert_sent_at': now.isoformat(),
                    'suggested_titles': json.dumps(new_variants)
                }).eq('video_id', video['video_id']).execute()

            # Enviar notificacion normal
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2 style="color: #2563eb;">Reporte {checkpoint_name}</h2>
                <p><strong>Video:</strong></p>
                <p style="background: #f3f4f6; padding: 10px; border-radius: 5px;">{video['title_original']}</p>

                <div style="background: {color}; color: white; padding: 15px; border-radius: 10px; margin: 20px 0;">
                    <h3 style="margin: 0;">Performance: {nivel}</h3>
                    <p style="font-size: 24px; margin: 5px 0;"><strong>{vph:,} VPH</strong></p>
                </div>

                <h3 style="color: #16a34a;">Metricas Actuales:</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    {"<tr style='background: " + ("#dcfce7" if ctr and ctr >= 8.0 else "#fee2e2" if ctr and ctr < 5.0 else "#f3f4f6") + ";'><td style='padding: 10px; border: 1px solid #e5e7eb;'><strong>CTR (Click-Through Rate)</strong></td><td style='padding: 10px; border: 1px solid #e5e7eb; font-weight: bold; color: " + ("#16a34a" if ctr and ctr >= 8.0 else "#dc2626" if ctr and ctr < 5.0 else "#6b7280") + ";'>" + f"{ctr:.1f}%" + (" ✅ EXCELENTE" if ctr >= 8.0 else " ⚠️ CRÍTICO" if ctr < 5.0 else " ✓ OK") + "</td></tr>" if ctr is not None else ""}
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Vistas</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{views:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>VPH (Vistas por Hora)</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{vph:,}</td>
                    </tr>
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Likes</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{likes:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Comentarios</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{comments:,}</td>
                    </tr>
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Tiempo desde publicacion</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{hours_since:.1f} horas</td>
                    </tr>
                </table>

                <hr style="margin: 30px 0;">
                <p style="color: #6b7280; font-size: 12px;">
                    Video ID: {video['video_id']}<br>
                    Checkpoint: {checkpoint_name}<br>
                    Proximo reporte en el siguiente checkpoint
                </p>
            </body>
            </html>
            """

            send_email(
                f"[{checkpoint_name}] {video['title_original'][:50]} - {vph} VPH ({nivel})",
                email_body
            )

            print(f"  Vistas: {views:,} | Likes: {likes:,} | VPH: {vph:,} | {nivel}")

            # Si es checkpoint_72h, marcar como completado
            if checkpoint == "checkpoint_72h":
                sb.table("video_monitoring").update({
                    'status': 'completed',
                    'completed_at': now.isoformat()
                }).eq('video_id', video['video_id']).execute()
                print(f"  [COMPLETADO] Monitoreo finalizado")

if __name__ == "__main__":
    monitor_videos()
