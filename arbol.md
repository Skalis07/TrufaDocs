# Arbol del proyecto (resumen actualizado)

Referencia: 2026-02-11.

Nota:
- Se omite el contenido interno de carpetas auto-generadas como `.venv`, `.ruff_cache` y `__pycache__`.

```text
.
|-- .ruff_cache/                     cache local de ruff
|-- .venv/                           entorno virtual local
|-- editor/                          app principal
|   |-- pdf_parse/                   pipeline de parseo PDF
|   |   |-- __init__.py
|   |   |-- assemble.py
|   |   |-- bridge.py
|   |   |-- constants.py
|   |   |-- extract.py
|   |   \-- parsers.py
|   |-- static/editor/               assets frontend del editor
|   |   |-- editor.js
|   |   |-- styles.css
|   |   |-- favicons/
|   |   \-- images/banner/
|   |-- templates/editor/
|   |   \-- editor.html
|   |-- tests/
|   |   |-- __init__.py
|   |   \-- test_structure_from_post.py
|   |-- __init__.py
|   |-- apps.py
|   |-- docx_template.py
|   |-- structure.py
|   |-- structure_constants.py
|   |-- structure_extras.py
|   |-- structure_helpers.py
|   |-- structure_types.py
|   |-- urls.py
|   \-- views.py
|-- templates/
|   \-- cv_template.docx             plantilla DOCX base
|-- trufadocs/                       configuracion Django
|   |-- __init__.py
|   |-- asgi.py
|   |-- settings.py
|   |-- urls.py
|   \-- wsgi.py
|-- .env                             variables locales (no subir)
|-- .env.example                     ejemplo de variables de entorno
|-- .gitignore
|-- arbol.md
|-- manage.py
|-- README.md
\-- requirements.txt
```

## Archivos clave

- `editor/views.py`: upload (`/upload/`) y exportacion (`/text/export/docx/`, `/text/export/pdf/`).
- `editor/structure.py`: normalizacion/estructura de datos del CV.
- `editor/structure_extras.py`: parser de secciones extra y sus entradas.
- `editor/docx_template.py`: render DOCX final segun plantilla.
- `editor/pdf_parse/*`: extraccion y parseo de PDF.
- `editor/templates/editor/editor.html`: UI principal del formulario.
- `editor/static/editor/editor.js`: logica frontend (modulos, fechas, orden interno).
- `editor/static/editor/styles.css`: estilos de la interfaz.
- `editor/tests/test_structure_from_post.py`: cobertura base del post estructurado.
- `templates/cv_template.docx`: plantilla DOCX utilizada para exportar.
