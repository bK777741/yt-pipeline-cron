#!/usr/bin/env python3
"""
Monitor de Metricas de Videos
Trackea metricas en checkpoints: 1h, 6h, 24h, 48h, 72h
Envia notificaciones EMAIL con el progreso
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
import json

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

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

            # Guardar metricas en JSONB
            current_metrics = json.loads(video.get('metrics', '{}') or '{}')
            current_metrics[checkpoint] = {
                'timestamp': now.isoformat(),
                'views': views,
                'likes': likes,
                'comments': comments,
                'vph': vph,
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

            # Evaluar performance
            if checkpoint == "checkpoint_1h":
                nivel = "EXCELENTE" if vph >= 100 else "BUENO" if vph >= 50 else "NORMAL" if vph >= 25 else "BAJO"
                color = "#10b981" if vph >= 50 else "#f59e0b" if vph >= 25 else "#ef4444"
            elif checkpoint == "checkpoint_24h":
                nivel = "VIRAL" if vph >= 50 else "BUENO" if vph >= 25 else "NORMAL" if vph >= 10 else "BAJO"
                color = "#10b981" if vph >= 25 else "#f59e0b" if vph >= 10 else "#ef4444"
            else:
                nivel = "BUENO" if vph >= 20 else "NORMAL" if vph >= 10 else "BAJO"
                color = "#10b981" if vph >= 20 else "#f59e0b" if vph >= 10 else "#ef4444"

            # Enviar notificacion
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
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Vistas</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{views:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Likes</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{likes:,}</td>
                    </tr>
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Comentarios</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{comments:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>Tiempo desde publicacion</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{hours_since:.1f} horas</td>
                    </tr>
                    <tr style="background: #f3f4f6;">
                        <td style="padding: 10px; border: 1px solid #e5e7eb;"><strong>VPH (Vistas por Hora)</strong></td>
                        <td style="padding: 10px; border: 1px solid #e5e7eb;">{vph:,}</td>
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
