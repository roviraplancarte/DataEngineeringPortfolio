# LinkedIn Job Scraper

Este proyecto permite extraer ofertas de trabajo de LinkedIn y gestionarlas en Google Sheets, evitando duplicados y permitiendo un control eficiente de los procesos de búsqueda y postulación.

## Instalación y configuración

### 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPO>
cd ScraperLinkedInVacantes
```

### 2. Crear y activar el entorno virtual

Ejecuta el siguiente script para crear un entorno virtual, activarlo e instalar las dependencias necesarias:

```bash
bash setup_venv.sh
```

Luego, activa el entorno virtual:

```bash
source venv/bin/activate
```

### 3. Configuración del archivo `.env`

Debes crear un archivo `.env` en la raíz de `ScraperLinkedInVacantes` con las siguientes variables:

```
GOOGLE_SHEETS_CREDENTIALS='{"type": "service_account", ...}'
GSHEETS_TARGET='https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXX/edit#gid=0'
```

- **GOOGLE_SHEETS_CREDENTIALS**: El contenido JSON de tu cuenta de servicio de Google Cloud (puedes copiar el contenido del archivo descargado y ponerlo como valor de la variable, todo en una sola línea).
- **GSHEETS_TARGET**: La URL de tu Google Spreadsheet donde se gestionarán las hojas `NewJobs`, `Links`, `BlackList` y `Control`.

> **Nota:** Nunca subas tu archivo `.env` ni tus credenciales a un repositorio público.

## Uso

1. Ejecuta el script principal:

```bash
python src/main.py
```

2. El scraper buscará trabajos según los parámetros definidos en el script, guardará los resultados y actualizará las hojas de Google Sheets según la lógica implementada.

## Estructura de hojas esperadas en Google Sheets

- **NewJobs**: Ofertas nuevas que aún no han sido aplicadas ni descartadas.
- **Links**: Ofertas a las que ya has enviado tu CV.
- **BlackList**: Ofertas que quieres descartar permanentemente.
- **Control**: Registro detallado de los trabajos procesados.

---

Si tienes dudas sobre la configuración o el uso, revisa el código fuente o abre un issue. 