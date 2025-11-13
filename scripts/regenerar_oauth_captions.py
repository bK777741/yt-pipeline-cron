#!/usr/bin/env python3
"""
Script para re-generar OAuth Refresh Token con acceso a Captions API
=====================================================================

PROBLEMA:
Tu token actual tiene scope limitado (youtube.readonly)
Captions API requiere scope completo (youtube.force-ssl)

ESTE SCRIPT:
1. Abre navegador para autorizar con el scope correcto
2. Genera nuevo refresh token
3. Te muestra el token para actualizar en GitHub Secrets

INSTRUCCIONES:
1. Ejecuta: python scripts/regenerar_oauth_captions.py
2. Se abrirá tu navegador
3. Autoriza el acceso (selecciona tu canal de YouTube)
4. Copia el nuevo REFRESH_TOKEN que aparecerá
5. Actualiza el secret en GitHub: YT_REFRESH_TOKEN
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

# Scope completo que incluye acceso a Captions
SCOPES = [
    'https://www.googleapis.com/auth/youtube.force-ssl',  # Acceso completo (incluye captions)
    'https://www.googleapis.com/auth/yt-analytics.readonly',  # Analytics (ya lo tienes)
]

def generar_nuevo_token():
    """Genera nuevo refresh token con scope de captions"""

    print("="*80)
    print("GENERADOR DE OAUTH TOKEN PARA CAPTIONS API")
    print("="*80)
    print()

    # Verificar que existan las credenciales
    client_id = os.getenv("YT_CLIENT_ID")
    client_secret = os.getenv("YT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("❌ ERROR: Variables YT_CLIENT_ID y YT_CLIENT_SECRET no encontradas")
        print()
        print("Opciones:")
        print("1. Exporta las variables:")
        print("   export YT_CLIENT_ID='tu_client_id'")
        print("   export YT_CLIENT_SECRET='tu_client_secret'")
        print()
        print("2. O crea un archivo client_secrets.json:")
        print("""
{
  "installed": {
    "client_id": "TU_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "TU_CLIENT_SECRET",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost"]
  }
}
""")
        return

    # Crear client_secrets.json temporal
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost", "urn:ietf:wg:oauth:2.0:oob"]
        }
    }

    print("📋 SCOPES QUE SE SOLICITARÁN:")
    print()
    for scope in SCOPES:
        print(f"   ✓ {scope}")
    print()
    print("🌐 ABRIENDO NAVEGADOR...")
    print("   Por favor autoriza el acceso a tu canal de YouTube")
    print()

    try:
        # Iniciar flujo OAuth
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=SCOPES
        )

        # Ejecutar flujo (abre navegador automáticamente)
        credentials = flow.run_local_server(
            port=8080,
            prompt='consent',
            success_message='¡Autorización exitosa! Puedes cerrar esta ventana.'
        )

        print()
        print("="*80)
        print("✅ ¡TOKEN GENERADO EXITOSAMENTE!")
        print("="*80)
        print()
        print("📝 NUEVO REFRESH TOKEN (cópialo):")
        print()
        print(f"   {credentials.refresh_token}")
        print()
        print("="*80)
        print("🔧 PRÓXIMOS PASOS:")
        print("="*80)
        print()
        print("1. Copia el token de arriba")
        print()
        print("2. Ve a GitHub → Settings → Secrets → Actions")
        print("   URL: https://github.com/TU_USUARIO/yt-pipeline-cron/settings/secrets/actions")
        print()
        print("3. Actualiza el secret: YT_REFRESH_TOKEN")
        print("   - Haz clic en YT_REFRESH_TOKEN")
        print("   - Pega el nuevo token")
        print("   - Guarda los cambios")
        print()
        print("4. ¡Listo! El próximo workflow podrá acceder a captions")
        print()
        print("="*80)

    except Exception as e:
        print()
        print("❌ ERROR durante la autorización:")
        print(f"   {e}")
        print()
        print("💡 SOLUCIÓN ALTERNATIVA:")
        print()
        print("Si el flujo local no funciona, usa el flujo manual:")
        print()
        print("1. Ve a: https://developers.google.com/oauthplayground")
        print()
        print("2. Haz clic en el ⚙️ (Settings) en la esquina superior derecha")
        print()
        print("3. Marca: ☑ Use your own OAuth credentials")
        print(f"   OAuth Client ID: {client_id}")
        print(f"   OAuth Client secret: {client_secret}")
        print()
        print("4. En la izquierda, busca 'YouTube Data API v3'")
        print("   Selecciona: https://www.googleapis.com/auth/youtube.force-ssl")
        print()
        print("5. Haz clic en 'Authorize APIs'")
        print()
        print("6. Autoriza con tu cuenta de YouTube")
        print()
        print("7. Haz clic en 'Exchange authorization code for tokens'")
        print()
        print("8. Copia el 'Refresh token' que aparece")
        print()

if __name__ == "__main__":
    generar_nuevo_token()
