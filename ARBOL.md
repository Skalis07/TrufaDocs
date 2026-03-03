# Arbol del proyecto (resumen)

Nota: se omite contenido interno de carpetas generadas localmente (`.venv`, caches, `__pycache__`).

```text
.
|-- docs/
|   |-- img/
|   \-- DOCUMENTACION_TECNICA_COMPLETA.md
|-- editor/
|   |-- pdf_parse/
|   |   |-- __init__.py
|   |   |-- assemble.py
|   |   |-- bridge.py
|   |   |-- constants.py
|   |   |-- extract.py
|   |   \-- parsers.py
|   |-- static/editor/
|   |   |-- editor.js
|   |   |-- styles.css
|   |   |-- favicons/
|   |   \-- images/banner/
|   |-- templates/editor/
|   |   \-- editor.html
|   |-- tests/
|   |   |-- __init__.py
|   |   |-- test_docx_template_localization.py
|   |   |-- test_docx_template_module_order.py
|   |   |-- test_docx_template_skills_pagination.py
|   |   |-- test_import_module_order.py
|   |   |-- test_pdf_english_dates_honors.py
|   |   |-- test_pdf_section_title_detection.py
|   |   |-- test_pdf_extra_section_parsing.py
|   |   |-- test_structure_from_post.py
|   |   \-- test_view_localization.py
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
|   \-- cv_template.docx
|-- trufadocs/
|   |-- __init__.py
|   |-- asgi.py
|   |-- settings.py
|   |-- urls.py
|   \-- wsgi.py
|-- .env.example
|-- .gitignore
|-- ARBOL.md
|-- README.md
|-- manage.py
\-- requirements.txt
```

## Referencia rapida por responsabilidad

- `editor/views.py`: upload, validaciones, export DOCX/PDF, mensajes ES/EN.
- `editor/structure.py`: schema base, parse texto y normalizacion de POST.
- `editor/structure_extras.py`: parse robusto de secciones extra.
- `editor/docx_template.py`: render final sobre la plantilla DOCX.
- `editor/pdf_parse/*`: extraccion y parseo de PDF.
- `editor/templates/editor/editor.html`: formulario principal.
- `editor/static/editor/editor.js`: logica de UI (idioma, tema, reorder, extras, fechas).
- `editor/tests/*`: regresiones de parsing, orden y localizacion.
