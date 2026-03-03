# TRUFADOCS - GUIA TECNICA PASO A PASO (JUNIOR)

Fecha de actualizacion: 2026-02-25

Esta guia esta escrita para alguien que recien entra al proyecto.
La idea es que puedas seguirla en orden y entender que hace cada parte sin asumir conocimiento previo del repo.

---

## 1) Primero: como correr el proyecto

1. Crear entorno virtual:

```bash
python -m venv .venv
```

2. Activarlo en PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Crear `.env` desde ejemplo:

```bash
copy .env.example .env
```

5. Levantar servidor:

```bash
python manage.py runserver
```

6. Abrir en navegador: `http://127.0.0.1:8000/`

Si esto falla, no sigas con codigo todavia. Primero arregla el entorno.

---

## 2) Mapa mental rapido del sistema

- `trufadocs/`: configuracion Django (settings, urls, asgi, wsgi).
- `editor/`: toda la logica de negocio.
- `templates/cv_template.docx`: plantilla para export final.
- `editor/templates/editor/editor.html`: formulario principal.
- `editor/static/editor/editor.js`: comportamiento frontend.
- `editor/tests/`: red de seguridad para no romper comportamiento.

### Endpoints reales

- `GET /` -> abre editor vacio.
- `POST /upload/` -> sube archivo y detecta campos.
- `POST /text/export/docx/` -> exporta DOCX.
- `POST /text/export/pdf/` -> exporta PDF.

---

## 3) Flujo completo (de punta a punta)

Este es el flujo mas importante del proyecto:

1. Usuario entra a `/`.
2. Sube `.docx` o `.pdf` en `/upload/`.
3. Backend transforma archivo a estructura normalizada (`structured`).
4. UI muestra esa estructura en formulario editable.
5. Usuario modifica campos/reordena modulos.
6. Usuario exporta.
7. Backend reconstruye `structured` desde el formulario (`structure_from_post`).
8. Se genera DOCX con plantilla.
9. Si pide PDF, se convierte DOCX -> PDF con `docx2pdf`.

Si entiendes este flujo, entiendes el 80% del proyecto.

---

## 4) Contrato de datos (schema interno)

Todo gira en torno a este schema (simplificado):

```python
{
  "meta": {"core_order": "experience,education,skills,extra-1"},
  "basics": {
    "name": "",
    "description": "",
    "email": "",
    "phone": "",
    "linkedin": "",
    "github": "",
    "city": "",
    "country": "",
  },
  "experience": [
    {
      "role": "",
      "company": "",
      "start": "",
      "end": "",
      "city": "",
      "country": "",
      "technologies": "",
      "highlights": [],
    }
  ],
  "education": [
    {
      "degree": "",
      "institution": "",
      "start": "",
      "end": "",
      "city": "",
      "country": "",
      "honors": "",
    }
  ],
  "skills": [{"category": "", "items": ""}],
  "extra_sections": [
    {
      "section_id": "extra-1",
      "title": "",
      "mode": "detailed|subtitle_items|subtitles|items(legacy)",
      "entries": [],
    }
  ],
}
```

Reglas clave:

- `core_order` define orden final de render/export.
- `extra_sections` permite modulos no core entre secciones base.
- `extra.mode` canonico hoy: `detailed` o `subtitle_items`.
- Alias legacy `items`/`subtitles` se normalizan internamente para compatibilidad.
- `default_structure()` garantiza que siempre haya estructura minima valida.

---

## 5) Backend por archivo (que toca cada uno)

## 5.1 `editor/views.py`

Responsabilidad: entrada/salida HTTP.

Funciones que debes conocer:

- `text_upload`: valida archivo, decide flujo DOCX/PDF, arma `structured`.
- `export_docx`: reconstruye `structured` desde POST y renderiza plantilla.
- `export_pdf`: igual que DOCX pero luego convierte a PDF.
- `_render_text_editor`: render central del template.
- `_extract_docx_text`: extraccion de texto DOCX (parrafos/tablas + fallback XML).
- `_convert_docx_bytes_to_pdf`: conversion docx2pdf en carpeta temporal.

Si quieres cambiar validaciones de upload, siempre empiezas en `views.py`.

## 5.2 `editor/structure.py`

Responsabilidad: normalizacion y conversion de estructura.

Funciones importantes:

- `default_structure()`
- `parse_resume(text)` -> texto libre a estructura.
- `structure_from_post(post_data)` -> formulario a estructura.
- `build_text_from_structure(data)` -> estructura a texto legible.
- `_split_sections`, `_parse_experience`, `_parse_education`, `_parse_skills`.

`structure_from_post` es critica porque es la puerta de salida del frontend.
Si rompe, rompen exportaciones aunque la UI "se vea" bien.

## 5.3 `editor/structure_helpers.py`

Responsabilidad: heuristicas reutilizables.

Ejemplos:

- detectar headings,
- detectar fechas,
- separar rol/empresa,
- limpiar bullets,
- normalizar tokens de fecha,
- detectar ubicacion.

Regla practica: si una heuristica sirve en mas de un parser, debe vivir aqui.

Complemento importante:

- `editor/structure_constants.py`: centraliza aliases de headings, listas de meses y tokens comunes de parse.
- Si cambias vocabulario/keywords de deteccion, revisa este archivo antes de tocar regex sueltas.

## 5.4 `editor/structure_extras.py`

Responsabilidad: parser robusto de secciones extra.

Maneja casos complejos:

- entries fragmentadas,
- mezcla de bullets + subtitulos,
- modo `detailed` vs `subtitle_items`,
- merge de fragmentos para no perder contenido.

Si aparece un bug raro solo en extras, este archivo es primer sospechoso.

## 5.5 `editor/pdf_parse/*`

Pipeline PDF en 4 etapas:

1. `extract.py`: extrae lineas y rasgos visuales (indent, bold, bullets, etc.).
2. `assemble.py`: arma header + secciones.
3. `parsers.py`: parsea experience/education/skills desde raw lines.
4. `bridge.py`: mapea todo al schema interno final.

Si falla solo en PDF y no en DOCX, casi seguro el problema esta aqui.

## 5.6 `editor/docx_template.py`

Responsabilidad: generar documento final desde `structured` + plantilla.

Hace:

- ubicar filas de plantilla,
- insertar/modificar bloques de experiencia/educacion/skills/extras,
- aplicar orden de modulos (`core_order`),
- localizar headings ES/EN,
- aplicar fuente seleccionada.

Si "se ve mal" el DOCX exportado, revisa este archivo antes que el parser.

---

## 6) Frontend (lo que no debes pasar por alto)

## 6.1 `editor/templates/editor/editor.html`

Es el contrato HTML del frontend.

Campos ocultos fundamentales:

- `core_order`
- `module_order_map`
- `ui_lang`
- `use_structured`

Campos de extras fundamentales:

- `extra_section_id`
- `extra_mode`
- `extra_entry_section`
- `extra_entry_subtitle`
- `extra_entry_title`
- `extra_entry_where`
- `extra_entry_tech`
- `extra_entry_start`
- `extra_entry_end`
- `extra_entry_city`
- `extra_entry_country`
- `extra_entry_items_si`
- `extra_entry_items_detailed`

Si cambias nombres `name="..."`, debes actualizar `structure_from_post`.

## 6.2 `editor/static/editor/editor.js`

Responsabilidad:

- idioma ES/EN en vivo,
- tema,
- manejo de fechas,
- add/remove de bloques repeat,
- sincronizacion de extras por modo,
- reorder de modulos,
- serializacion final antes de submit.

Regla critica: siempre que agregues campos dinamicos, valida que efectivamente viajen en el POST.

## 6.3 `editor/static/editor/styles.css`

Solo presentacion visual.
No debe contener logica funcional.

---

## 7) Como leer los tests (orden recomendado)

Lee en este orden:

1. `test_view_localization.py`
   - valida mensajes ES/EN de upload.

2. `test_structure_from_post.py`
   - protege normalizacion de payload sparse en extras.

3. `test_import_module_order.py`
   - protege preservacion de orden de modulos.

4. `test_pdf_english_dates_honors.py`
   - protege parse EN de fechas y honors.

5. `test_pdf_section_title_detection.py`
   - evita falsos positivos de headings en contenido PDF (regresiones de deteccion).

6. `test_pdf_extra_section_parsing.py`
   - protege parse de extras desde PDF.

7. `test_docx_template_localization.py`
   - valida headings/labels EN en export.

8. `test_docx_template_module_order.py`
   - valida espaciado/orden visual entre modulos.

9. `test_docx_template_skills_pagination.py`
   - valida reglas de paginacion en skills.

Comando:

```bash
python manage.py test editor.tests
```

---

## 8) Recetas practicas (cambiar algo sin romper)

## Caso A: agregar un nuevo campo en `basics`

1. Agregar input en `editor.html`.
2. Leer/escribir ese campo en `structure_from_post`.
3. Incluirlo en `default_structure`.
4. Si aplica, mostrarlo en `build_text_from_structure`.
5. Si debe salir en DOCX, tocar `docx_template.py`.
6. Crear o ajustar test.

## Caso B: cambiar regla de parse de fechas

1. Revisar `structure_helpers.py` y/o `editor/pdf_parse/constants.py`.
2. Ajustar parser afectado (`structure.py` o `pdf_parse/parsers.py`).
3. Ejecutar tests de PDF y structure.
4. Agregar test de regresion del formato nuevo.

## Caso C: cambiar comportamiento de extras

1. Revisar primero `structure_extras.py`.
2. Revisar `structure_from_post` si el cambio viene de UI.
3. Validar que `editor.js` serializa bien por modo.
4. Ejecutar `test_structure_from_post.py` y `test_pdf_extra_section_parsing.py`.

## Caso D: cambiar orden de modulos

1. Ver `editor.js` (genera `core_order` y `module_order_map`).
2. Ver `structure_from_post` (reconstruye orden final).
3. Ver `docx_template.py` (`_apply_module_order`).
4. Ejecutar tests de module order.

---

## 9) Checklist de debugging rapido

Si algo falla, sigue este orden:

1. Confirmar que el frontend envio el dato (Network -> Form Data).
2. Confirmar que `structure_from_post` lo interpreta bien.
3. Confirmar que `structured` llega bien a export.
4. Si problema es PDF, revisar pipeline `pdf_parse`.
5. Si problema es visual en DOCX, revisar `docx_template.py`.
6. Correr tests relevantes.

No depures "a ciegas" en todos los archivos a la vez.

---

## 10) Cosas que NO existen (para evitar confusiones)

1. No hay modelos persistentes de negocio (DB dummy backend).
2. No existe documentacion fuente separada tipo `*_detailed_docs.md` en el repo actual.
3. En `structure_types.py` solo quedan tipos usados:
   - `ExtraLine`
   - `ExtraSectionRaw`

---

## 11) Antes de dar por terminado un cambio

1. `python manage.py test editor.tests`
2. Probar flujo manual minimo:
   - upload
   - editar
   - export docx
   - export pdf (si entorno tiene Word)
3. Revisar que no rompiste `core_order`.
4. Revisar que no cambiaste nombres `name="..."` sin tocar backend.
5. Si cambiaste contrato, actualizar esta guia y README.

---

## 12) Resumen final para junior

Si te pierdes, vuelve a esta secuencia:

1. Entender `views.py`.
2. Entender `structure.py`.
3. Entender `structure_extras.py` y `structure_helpers.py`.
4. Entender `pdf_parse`.
5. Entender `docx_template.py`.
6. Entender `editor.html` + `editor.js`.
7. Validar con tests.

Ese orden funciona para casi cualquier tarea del proyecto.

---

## 13) Capitulo adicional: funcion por funcion

Esta seccion es una referencia rapida de que hace cada funcion en los modulos core.
Usala cuando necesites tocar una parte puntual y no quieras leer todo el archivo.

## 13.1 `editor/views.py`

- `_ui_lang`: resuelve idioma activo (`es`/`en`) desde request.
- `_msg`: devuelve mensaje localizado desde `UI_MESSAGES`.
- `_translate_backend_error`: traduce errores tecnicos a mensajes de UI.
- `_extract_structured_countries`: extrae paises detectados desde `structured`.
- `_merge_country_choices`: merge de paises base + detectados, sin duplicados.
- `index`: render inicial del editor con `default_structure`.
- `text_upload`: valida archivo y dispara parse DOCX/PDF.
- `export_docx`: reconstruye `structured` desde POST y exporta DOCX.
- `export_pdf`: exporta PDF a partir de DOCX generado.
- `_render_text_editor`: render central de `editor.html` con contexto completo.
- `_text_error`: helper para devolver editor con mensaje de error.
- `_is_allowed_extension`: valida extension permitida.
- `_max_upload_mb`: obtiene limite de upload desde settings.
- `_extension`: devuelve extension normalizada en minusculas.
- `_safe_filename`: limpia y normaliza nombre de archivo para descarga.
- `_extract_docx_text`: extrae texto de DOCX (python-docx + fallback XML).
- `_template_path`: resuelve la ruta valida de `cv_template.docx`.
- `_selected_font`: valida fuente elegida contra `FONT_CHOICES`.
- `_normalize_key`: normaliza texto para comparaciones/deduplicacion.
- `_convert_docx_bytes_to_pdf`: convierte DOCX bytes a PDF bytes con `docx2pdf`.

## 13.2 `editor/structure.py`

- `default_structure`: devuelve schema minimo estable para UI/export.
- `_build_core_order_from_detected`: construye `core_order` segun orden detectado.
- `parse_resume`: parsea CV en texto libre a `structured`.
- `build_text_from_structure`: serializa `structured` a texto legible.
- `structure_from_post`: normaliza payload del formulario a schema interno.
- `_extract_contact`: extrae email/telefono/links del texto.
- `_extract_name_and_description`: toma nombre, descripcion y resto de lineas.
- `_extract_location`: detecta ciudad/pais de cabecera.
- `_split_sections`: separa lineas en experience/education/skills/extras.
- `_parse_experience`: parsea bloque de experiencia a lista normalizada.
- `_parse_education`: parsea bloque de educacion a lista normalizada.
- `_parse_skills`: parsea habilidades por categoria/items.
- `_ensure_minimums`: garantiza filas minimas en core sections.

### Helpers internos relevantes en `build_text_from_structure`

- `_fmt_month_year`: transforma `YYYY-MM` a mes corto + anio.
- `_format_date_range`: compone rango de fechas legible.
- `_format_location`: une ciudad/pais.
- `_format_detail_line`: limpia lineas opcionales.
- `emit_detail_section`: render de experience/education.
- `emit_detail_entry`: render de entrada extra en modo detailed.
- `emit_subtitle_items_entry`: render de entrada extra en modo subtitle_items.
- `emit_skills_section`: render de skills por categoria.
- `emit_extras`: render de extras en bloque compat.

### Helpers internos relevantes en `structure_from_post`

- `_entry_field_value`: lee valores alineados o sparse por modo.
- `parse_items`: parsea items multilinea y limpia bullets.

## 13.3 `editor/structure_extras.py`

- `_split_escaped_newlines`: divide texto soportando `\\n` escapado.
- `_empty_extra_entry`: genera entrada extra vacia de compatibilidad.
- `_has_extra_entry_content`: valida si una entry tiene contenido util.
- `_infer_extra_mode`: infiere modo global de seccion extra.
- `_infer_entry_mode`: infiere modo puntual de entry.
- `_looks_like_inline_list`: detecta lista inline separada por comas.
- `_split_items_text`: convierte texto de items a lista normalizada.
- `_extract_line_payload`: normaliza linea raw y extrae metadatos.
- `_split_extra_blocks`: agrupa lineas extra en bloques logicos.
- `_infer_block_indents`: infiere indent base y bullet indent del bloque.
- `_split_location_tail_loose`: separa cola de ubicacion flexible.
- `_looks_like_location_prefix`: detecta prefijos tipo ubicacion.
- `_apply_location_prefix`: aplica prefijo de ubicacion a una entry.
- `_split_trailing_location`: separa ubicacion al final de una linea.
- `_is_location_prefix_only`: detecta lineas solo de prefijo de ubicacion.
- `_is_location_stub`: detecta stubs parciales de ubicacion.
- `_split_location_prefix_from_text`: separa prefijo de ubicacion desde texto.
- `_merge_location_prefix`: mergea prefijo/stub de ubicacion en entry.
- `_split_title_location_suffix`: separa sufijo de ubicacion en titulo.
- `_entry_has_location`: indica si entry ya contiene ubicacion.
- `_entry_has_core`: indica si entry tiene campos base.
- `_is_sparse_extra_entry`: detecta entry sparse sin cuerpo suficiente.
- `_is_subtitle_only_extra_entry`: detecta entry solo subtitulo.
- `_is_detailed_extra_entry`: detecta entry detallada.
- `_merge_extra_entries`: mergea dos entradas complementarias.
- `_should_merge_extra_entries`: decide si dos entries deben fusionarse.
- `_merge_extra_entry_fragments`: fusiona fragmentos segun heuristicas.
- `_should_start_new_extra_entry`: decide corte de nueva entry.
- `_looks_like_detailed_bullet`: detecta bullet que pertenece a detailed.
- `_parse_extra_entries`: parser principal de entries extras.
- `_parse_extras`: parser principal de secciones extra completas.

## 13.4 `editor/docx_template.py`

### I18n y normalizacion inicial

- `_normalize_ui_lang`: normaliza idioma de export (`es`/`en`).
- `_export_text`: devuelve bundle de textos localizados para export.
- `_format_detail_line`: limpia texto opcional de detalle.
- `_normalize_extra_mode`: normaliza modo de extras (`items` legacy -> `subtitles`).
- `_entry_items_inline`: junta lista de items en una linea.

### Pipeline principal

- `render_from_template`: orquesta todo el render DOCX final.
- `_apply_experience`: escribe bloque de experiencia en la tabla.
- `_apply_education`: escribe bloque de educacion en la tabla.
- `_apply_skills`: escribe bloque de habilidades.
- `_normalize_skills_bullets`: ajusta formato/tamano de bullets de skills.
- `_extra_entry_lines`: convierte una entry extra a lineas renderizables.
- `_extra_entry_has_content`: valida si la entry extra tiene contenido util.
- `_apply_extras`: inserta bloques extras en la tabla.
- `_apply_module_order`: reordena modulos segun `core_order`.

### Fillers de filas

- `_fill_experience_role_row`: rellena fila rol/empresa de experiencia.
- `_fill_extra_detail_role_row`: rellena fila principal de extra detailed.
- `_fill_extra_detail_highlights_row`: escribe highlights de extra detailed.
- `_fill_experience_highlights_row`: escribe highlights de experiencia.
- `_fill_education_row`: rellena fila de educacion.
- `_fill_extra_row`: rellena fila simple de extra subtitle/items.
- `_set_contact_row`: escribe datos de contacto en su fila.

### Texto, links y formato

- `_normalize_url`: normaliza URL antes de renderizar.
- `_add_run_with_size`: agrega run con tamano de fuente opcional.
- `_add_hyperlink`: inserta hyperlink clickeable en un parrafo.
- `_format_date_range`: formatea rango de fechas para salida.
- `_format_date_token`: formatea token de fecha individual.
- `_join_location`: une ciudad/pais para salida.
- `_set_row_text`: setea texto de una fila completa.
- `_has_experience_content`: valida si item de experiencia tiene contenido.
- `_has_education_content`: valida si item de educacion tiene contenido.
- `_set_row_keep_with_next`: configura `keep_with_next` en una fila.
- `_clear_row_height`: limpia altura fija de fila.
- `_apply_section_keep_with_next_gap`: ajusta gap de paginacion entre secciones.
- `_set_cell_lines_preserve`: escribe lineas preservando formato base de celda.
- `_set_paragraph_text`: setea texto de parrafo respetando estilo run base.
- `_clear_cell`: limpia contenido de celda.
- `_clear_paragraph_content`: limpia runs de un parrafo.
- `_paragraph_has_numbering`: detecta si parrafo tiene numbering.
- `_add_paragraph`: agrega parrafo con estilo/numbering controlado.
- `_filter_empty_lines`: filtra lineas vacias.
- `_clone_run_format`: clona formato de run fuente a run destino.
- `_clone_paragraph_format`: clona formato de parrafo fuente a destino.
- `_set_numbering_level_size`: ajusta tamano en niveles de listas numeradas.

### Fuente global

- `_apply_font`: aplica fuente global al documento completo.
- `_set_run_font_name`: aplica nombre de fuente a un run.

### Helpers de tabla y busqueda

- `_unique_cells`: devuelve celdas unicas de una fila.
- `_row_text`: extrae texto consolidado de fila.
- `_row_is_heading`: detecta si una fila parece heading.
- `_is_blank_row`: detecta filas vacias.
- `_row_has_borders`: detecta si fila tiene bordes.
- `_find_blank_row_without_borders`: busca fila vacia sin bordes en rango.
- `_find_any_blank_row_without_borders`: busca fila vacia sin bordes global.
- `_find_trailing_blank_row_without_borders`: busca separador vacio al final de bloque.
- `_collapse_blank_rows`: colapsa filas vacias consecutivas.
- `_find_row_index`: busca fila por marcador textual.
- `_find_heading_row_index`: busca heading por clave de modulo.
- `_localize_core_headings`: traduce headings core al idioma de export.
- `_find_row_index_predicate`: busca fila usando predicado.
- `_find_next_non_empty_row`: siguiente fila no vacia en rango.
- `_find_first_non_empty_before`: primera fila no vacia antes de indice.
- `_remove_rows`: elimina un rango de filas.
- `_insert_row_before`: inserta fila XML antes de indice.
