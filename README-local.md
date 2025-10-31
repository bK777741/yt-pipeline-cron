# Cron Job para Refrescar Tokens de Google API

## Propósito del Proyecto

Este proyecto contiene un conjunto de scripts de Python diseñados para refrescar automáticamente los tokens de acceso de la API de Google. Es útil para aplicaciones que necesitan mantener el acceso a las APIs de Google (como YouTube, Google Drive, etc.) a través de un proceso automatizado o "cron job".

El script principal (`refresh_token.py`) utiliza un token de refresco para solicitar un nuevo token de acceso a Google y lo muestra en la salida.

---

## Pruebas locales

Instrucciones para configurar y probar el proyecto en un entorno local.

1.  **Pega tus valores en `credentials/.env.local`**:
    ```
    CLIENT_ID=...
    CLIENT_SECRET=...
    REFRESH_TOKEN=...
    ```

2.  **Instala dependencias**:
    ```bash
    python -m pip install -r requirements.txt
    ```

3.  **Valida variables**:
    ```bash
    python scripts/check_env.py
    ```
    *Salida esperada*:
    ```
    CLIENT_ID: OK
    CLIENT_SECRET: OK
    REFRESH_TOKEN: OK
    VALIDACIÓN: OK (las 3 variables existen).
    ```

4.  **Prueba el refresco**:
    ```bash
    python scripts/refresh_token.py
    ```
    *Salida esperada*:
    ```
    REFRESH OK — access_token: ya29.xxxxxxxxxxxxx...xxxxxxxx
    ```

---

## Historial de Cambios

### 5 de Septiembre de 2025

-   **Configuración Inicial**: Se crearon los scripts iniciales `check_env.py` y `refresh_token.py`.
-   **Corrección de Carga de Entorno**: Se detectó un problema donde los scripts no cargaban correctamente las variables de entorno desde el archivo `.env.local` en sistemas Windows.
-   **Solución**: Se modificaron ambos scripts para que construyan la ruta al archivo `.env.local` de forma dinámica, asegurando la compatibilidad entre diferentes sistemas operativos. También se forzó la sobreescritura de las variables (`override=True`) para evitar conflictos con variables preexistentes en el entorno.

---

## Estado Actual

**Completado y Funcional.**

El proceso de configuración y prueba local se ha completado con éxito. Los scripts ahora pueden leer las credenciales del archivo `.env.local` y obtener un nuevo token de acceso sin problemas.

El sistema está listo para ser utilizado en un entorno de producción o para ser integrado en un cron job.

EJECUTA SIEMPRE EL validador de credenciales_env PARA COMPROBAR DE MANERA GENERAL QUE TODO FUNCIONE BIEN