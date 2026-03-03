# TrufaDocs

Aplicacion web en Django para importar CVs (`.docx` / `.pdf`), normalizarlos a una estructura editable y exportarlos a DOCX/PDF.

## Estado actual

- Parser de CV con schema unico (`basics`, `experience`, `education`, `skills`, `extra_sections`).
- UI ES/EN con mensajes localizados y persistencia de idioma.
- Reorden de modulos con preservacion de `core_order`.
- Export DOCX por plantilla (`templates/cv_template.docx`).
- Export PDF via `docx2pdf` (requiere Microsoft Word en Windows/macOS).
- Suite de tests enfocada en regresiones de parsing, localizacion y orden.

## Stack

- Python 3.12+
- Django 6.0.2
- python-docx 1.2.0
- pdfplumber 0.10.4
- docx2pdf 0.1.8

## Instalacion local

```bash
python -m venv .venv
```

PowerShell (Windows):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py runserver
```

Bash (Linux/macOS):

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py runserver
```

Abrir: `http://127.0.0.1:8000/`

## Endpoints

| Metodo | Ruta                 | Uso |
| ------ | -------------------- | --- |
| GET    | `/`                  | Editor principal |
| POST   | `/upload/`           | Importar y detectar campos |
| POST   | `/text/export/docx/` | Exportar DOCX |
| POST   | `/text/export/pdf/`  | Exportar PDF |

Nota: `GET /upload/` redirige a `/`.

## Variables de entorno

Definidas en `.env.example` y consumidas en `trufadocs/settings.py`.

Minimas:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `MAX_UPLOAD_MB`
- `CV_TEMPLATE_PATH`

Produccion (seguridad):

- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_CSRF_COOKIE_SECURE`
- `DJANGO_SECURE_HSTS_SECONDS`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `DJANGO_SECURE_HSTS_PRELOAD`
- `DJANGO_SECURE_PROXY_SSL_HEADER`
- `DJANGO_USE_X_FORWARDED_HOST`

## Tests

```bash
python manage.py test editor.tests
```

## Documentacion

- Guia tecnica completa paso a paso para onboarding junior:
  - `docs/DOCUMENTACION_TECNICA_COMPLETA.md`
- Mapa de estructura del repo:
  - `ARBOL.md`

