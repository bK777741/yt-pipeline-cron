#!/usr/bin/env python3
"""
Detector de Videos Nuevos + Notificación Email
Detecta videos publicados en últimas 24h y envía notificación con títulos A/B
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def send_email(subject, body):
    """Envía email usando SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv("SMTP_USER")
        msg['To'] = os.getenv("NOTIFICATION_EMAIL")
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
            server.send_message(msg)

        print("[EMAIL] Notificacion enviada exitosamente")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo enviar email: {e}")
        return False

def detect_new_videos():
    """Detecta videos nuevos y genera titulos A/B"""
    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY")
    )

    # Buscar videos de ultimas 24 horas
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    new_videos = sb.table("videos")\
        .select("video_id, title, published_at")\
        .gte("published_at", yesterday)\
        .execute()

    print(f"[INFO] Buscando videos desde {yesterday}")
    print(f"[INFO] Videos encontrados: {len(new_videos.data)}")

    videos_procesados = 0

    for video in new_videos.data:
        # Verificar si ya esta en monitoreo
        existing = sb.table("video_monitoring")\
            .select("id")\
            .eq("video_id", video['video_id'])\
            .execute()

        if not existing.data:
            # NUEVO VIDEO DETECTADO
            print(f"\n[NEW] {video['title']}")

            # Generar titulos A/B
            from generate_ab_titles import generate_ab_titles
            variants = generate_ab_titles(video['title'], sb)

            print(f"  Variante A: {variants['variant_a']}")
            print(f"  Variante B: {variants['variant_b']}")
            print(f"  Variante C: {variants['variant_c']}")

            # Insertar en monitoring
            sb.table("video_monitoring").insert({
                "video_id": video['video_id'],
                "title_original": video['title'],
                "published_at": video['published_at'],
                "status": "pending",
                "monitoring_stage": "new_video",
                "title_variant_a": variants['variant_a'],
                "title_variant_b": variants['variant_b'],
                "title_variant_c": variants['variant_c'],
                "notifications_sent": {"new_video": datetime.now(timezone.utc).isoformat()}
            }).execute()

            # Enviar email de notificacion
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                <h2 style="color: #2563eb;">Nuevo Video Detectado</h2>
                <p><strong>Titulo Original:</strong></p>
                <p style="background: #f3f4f6; padding: 10px; border-radius: 5px;">{video['title']}</p>

                <h3 style="color: #16a34a;">Titulos A/B Sugeridos:</h3>
                <ul style="list-style: none; padding: 0;">
                    <li style="margin: 10px 0; padding: 10px; background: #fef3c7; border-radius: 5px;">
                        <strong>Variante A (Curiosidad):</strong><br>{variants['variant_a']}
                    </li>
                    <li style="margin: 10px 0; padding: 10px; background: #dbeafe; border-radius: 5px;">
                        <strong>Variante B (Beneficio):</strong><br>{variants['variant_b']}
                    </li>
                    <li style="margin: 10px 0; padding: 10px; background: #fce7f3; border-radius: 5px;">
                        <strong>Variante C (Urgencia):</strong><br>{variants['variant_c']}
                    </li>
                </ul>

                <h3 style="color: #dc2626;">Como Responder:</h3>
                <p><strong>Responde a este email con:</strong></p>
                <ul>
                    <li><code>OK</code> - Para usar estos titulos tal cual</li>
                    <li><code>A: nuevo titulo</code> - Para modificar variante A</li>
                    <li><code>B: nuevo titulo</code> - Para modificar variante B</li>
                    <li><code>C: nuevo titulo</code> - Para modificar variante C</li>
                    <li><code>CANCEL</code> - Para no hacer nada</li>
                </ul>

                <p style="background: #fef2f2; padding: 15px; border-left: 4px solid #dc2626; margin-top: 20px;">
                    <strong>IMPORTANTE:</strong> Si no respondes en <strong>2 horas</strong>,
                    los titulos se subiran automaticamente a YouTube A/B Testing.
                </p>

                <hr style="margin: 30px 0;">
                <p style="color: #6b7280; font-size: 12px;">
                    Video ID: {video['video_id']}<br>
                    Publicado: {video['published_at']}<br>
                    Sistema A/B Testing Automatico
                </p>
            </body>
            </html>
            """

            send_email(
                f"[NUEVO VIDEO] {video['title'][:50]}...",
                email_body
            )

            videos_procesados += 1

    print(f"\n[RESUMEN] Videos nuevos procesados: {videos_procesados}")

if __name__ == "__main__":
    detect_new_videos()
