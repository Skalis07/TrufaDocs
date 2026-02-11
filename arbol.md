# Árbol del proyecto (resumen actualizado)

**Nota:**  
Se omite el contenido interno de carpetas auto-generadas como `.venv`, `.ruff_cache` y `__pycache__`.

```text
.
|-- .ruff_cache/                     caché local de Ruff
|-- .venv/                           entorno virtual local
|-- docs/
|   \-- img/                         imágenes usadas en el README
|-- editor/                          app principal
|   |-- pdf_parse/                   pipeline de parseo de PDF
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
|   \-- cv_template.docx             plantilla base para exportación DOCX
|-- trufadocs/                       configuración del proyecto Django
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

---

## Archivos clave

- `editor/views.py`: manejo de subida (`/upload/`) y exportación (`/text/export/docx/`, `/text/export/pdf/`).
- `editor/structure.py`: normalización y estructura de datos del CV.
- `editor/structure_extras.py`: parser de secciones extra y sus entradas.
- `editor/docx_template.py`: renderizado final del DOCX según plantilla.
- `editor/pdf_parse/*`: extracción y parseo de PDF.
- `editor/templates/editor/editor.html`: interfaz principal del formulario.
- `editor/static/editor/editor.js`: lógica frontend (módulos, fechas, orden interno).
- `editor/static/editor/styles.css`: estilos de la interfaz.
- `editor/tests/test_structure_from_post.py`: cobertura base del procesamiento estructurado.
- `templates/cv_template.docx`: plantilla DOCX utilizada para exportar.
- `docs/img/*`: capturas de pantalla usadas en el README.
