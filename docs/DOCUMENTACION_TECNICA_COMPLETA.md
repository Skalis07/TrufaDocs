# TRUFA DOCS — DOCUMENTACIÓN TÉCNICA COMPLETA
> Documento consolidado de TODO el sistema: parsing, helpers, estructura, render DOCX y UI.



---

# Fuente: views_editor_detailed_docs.md

# views.py (editor) — Documentación detallada (por función)

> Formato: `archivo`
> `función`: explicación detallada (intención/reglas/parámetros/retorno) para mantener el código limpio.

---

## Archivo: `views.py` (módulo editor / upload / export)

### Constantes / configuración (contexto)
- `ALLOWED_EXTENSIONS`: set con extensiones permitidas para upload (`.docx`, `.pdf`).
- `FONT_CHOICES`: lista de fuentes disponibles para exportar en UI.
- `CURRENT_YEAR` y `YEAR_CHOICES`: generan lista de años para selectores (desde año actual + 5 hacia 1970).
- `COUNTRY_CHOICES`: lista mínima viable de países para selector (base).

Estas constantes se usan en:
- validación de uploads (`_is_allowed_extension`, `text_upload`)
- render del template con selects (`_render_text_editor`)

---

### Función: `_extract_structured_countries(structured: dict | None) -> list[str]`
**Qué hace:**  
Recoge países (`country`) desde la estructura parseada para enriquecer el selector de país en la UI.

**Intención:**
- El usuario puede subir un CV que contiene países distintos a los de `COUNTRY_CHOICES`.
- Para que el selector no “pierda” un país ya detectado y el usuario lo vea disponible, se extraen países del contenido estructurado y se agregan dinámicamente.

**Flujo / reglas:**
1) Inicializa `countries` vacío.
2) Si `structured` no es dict, lo reemplaza por `{}` (defensa ante valores inválidos).
3) Define helper interno `add(country)`:
   - ignora `None` o strings vacíos
   - aplica `strip()` y agrega si queda contenido.
4) Busca país en:
   - `structured["basics"]["country"]`
   - cada item en `structured["experience"]`
   - cada item en `structured["education"]`
   - en `structured["extra_sections"]`: itera sus `entries` y toma `entry["country"]`
5) Retorna lista (sin deduplicar: la deduplicación sucede en `_merge_country_choices`).

**Parámetros:**
- `structured`: dict con la estructura del CV (o `None`).

**Retorno:**
- `list[str]` con países encontrados (puede incluir repetidos si aparecen varias veces).

---

### Función: `_merge_country_choices(base: list[str], extra: list[str]) -> list[str]`
**Qué hace:**  
Une lista base de países (definidos) con países extra detectados en el CV, evitando duplicados por comparación case-insensitive.

**Intención:**
- Mantener un set base (mínimo viable) y añadir países que aparezcan en datos del usuario sin romper el selector.

**Reglas:**
1) Copia `base` a `merged` (no muta el input).
2) Construye `seen` con claves normalizadas (`strip().lower()`), filtrando vacíos.
3) Itera `extra`:
   - normaliza `country` con `strip().lower()` como `key`
   - si `key` no está en `seen`, agrega el país “limpio” (`strip()`) a `merged` y marca como visto.
4) Retorna `merged`.

**Parámetros:**
- `base`: lista base (p.ej. `COUNTRY_CHOICES`).
- `extra`: lista de países detectados desde estructura.

**Retorno:**
- Lista combinada, estable (base primero), sin duplicados por casefold básico.

---

### Vista: `index(request)`
**Qué hace:**  
Renderiza el estado inicial del editor con una estructura vacía.

**Intención:**
- Mostrar el editor listo para usar sin upload, con defaults.

**Flujo:**
1) Construye `structured = default_structure()`.
2) Renderiza usando `_render_text_editor(..., filename="documento")`.

**Retorno:**
- `HttpResponse` renderizando template `editor/editor.html` con contexto inicial.

---

### Vista: `text_upload(request)`  *(GET/POST)*
Decorador: `@require_http_methods(["GET", "POST"])`

**Qué hace:**  
Recibe un archivo subido, valida formato/tamaño, extrae texto o estructura, y renderiza el editor con la estructura parseada.

**Intención:**
- Este es el entrypoint de “subir CV y parsear”.
- Soporta `.docx` y `.pdf` con pipelines distintos.

**Flujo / reglas (en orden real):**
1) Si `GET`:
   - redirige a `index` (no procesa uploads por GET).
2) Toma `uploaded = request.FILES.get("file")`:
   - si no existe => `_text_error("Selecciona un archivo...")`.
3) Valida tamaño:
   - lee `max_mb = _max_upload_mb()` (por settings o default 25)
   - si `uploaded.size > max_mb * 1024 * 1024` => error de tamaño.
4) Valida extensión:
   - `_is_allowed_extension(uploaded.name)` debe ser True
   - si no => error de formato.
5) Decide pipeline según extensión:
   - Si `.docx`:
     - `text, error = _extract_docx_text(uploaded)`
     - si `error` => `_text_error(error)`
     - si `text` vacío => `_text_error("No se pudo extraer texto...")`
     - `structured = parse_resume(text)` (parse heurístico desde texto)
   - Si `.pdf`:
     - `structured, error = parse_pdf_to_structure(uploaded)`
     - si `error` => `_text_error(error)`
6) Calcula nombre base de archivo para UI:
   - `filename = _safe_filename(uploaded.name)`
7) Renderiza editor con `_render_text_editor(request, structured, filename)`

**Puntos críticos:**
- El `.docx` se transforma a texto y luego se parsea con `parse_resume`.
- El `.pdf` idealmente ya retorna estructura con `parse_pdf_to_structure`.
- Los errores se devuelven como render del editor con estructura default.

**Retorno:**
- `HttpResponseRedirect` (si GET) o `HttpResponse` render (POST con resultado o error).

---

### Vista: `export_docx(request)` *(POST)*
Decorador: `@require_http_methods(["POST"])`

**Qué hace:**  
Exporta un DOCX, ya sea:
- desde estructura usando plantilla (`use_structured=1`)
- o desde texto libre (columna derecha) generando un DOCX básico

**Flujo:**
1) Lee `raw_text` y `use_structured` del POST.
2) Si `use_structured`:
   - `structured = structure_from_post(request.POST)` (reconstruye dict desde el form)
   - `template_path = _template_path()` (busca docx plantilla)
   - `font_choice = _selected_font(request)` (valida fuente)
   - si no hay plantilla => render editor con error (mantiene estructura)
   - intenta `render_from_template(structured, template_path, font_name=font_choice)`:
     - si falla => captura excepción, recorta detalle a 400 chars, render error
   - si OK => arma `HttpResponse` con bytes DOCX y header de descarga
3) Si NO `use_structured`:
   - `text = raw_text`
   - `docx_bytes = _build_docx_bytes(text)`
   - crea `HttpResponse` con DOCX y filename seguro

**Retorno:**
- `HttpResponse` con attachment `.docx`, o render de editor con error si se usa plantilla y falla.

---

### Vista: `export_pdf(request)` *(POST)*
Decorador: `@require_http_methods(["POST"])`

**Qué hace:**  
Exporta PDF en dos modos:
- desde estructura: estructura -> DOCX (plantilla) -> PDF (docx2pdf)
- desde texto libre: texto -> DOCX básico -> PDF

**Flujo:**
1) Lee `raw_text`, `use_structured`, `filename` (seguro).
2) Si `use_structured`:
   - `structured = structure_from_post(...)`
   - `template_path = _template_path()`
   - `font_choice = _selected_font(request)`
   - si no hay plantilla => render con error
   - intenta `render_from_template(...)`:
     - si falla => `rendered_docx = None`
   - si no hay `rendered_docx` => render con error
   - `docx_bytes = rendered_docx`
3) Si NO `use_structured`:
   - `structured = default_structure()` (para mantener contrato de render si falla)
   - `docx_bytes = _build_docx_bytes(raw_text)`
4) Convierte DOCX->PDF:
   - `pdf_bytes, error = _convert_docx_bytes_to_pdf(docx_bytes)`
   - si hay `pdf_bytes` => responde PDF como attachment
   - si no => render editor con `error` o genérico

**Retorno:**
- `HttpResponse` PDF o render con error.

**Dependencias / limitaciones:**
- `_convert_docx_bytes_to_pdf` usa `docx2pdf` y típicamente requiere Microsoft Word instalado (sobre todo en Windows).

---

## Helpers (no vistas)

### Función: `_render_text_editor(request, structured, filename="documento", error: str | None = None)`
**Qué hace:**  
Renderiza `editor/editor.html` con el contexto completo que necesita la UI.

**Incluye en el contexto:**
- `text`: texto reconstruido desde estructura (`build_text_from_structure`)
- `filename`: base name para export
- `structured`: dict de estructura para poblar el formulario
- `error`: mensaje de error para mostrar (si existe)
- `font_choices` y `selected_font`
- `country_choices`: merge de base + detectados desde estructura
- `year_choices`: lista de años para selects

**Flujo:**
1) Obtiene `font_choice` desde `_selected_font(request)`
2) Extrae países desde estructura (`_extract_structured_countries`)
3) Combina con base (`_merge_country_choices`)
4) `render(request, "editor/editor.html", context)`

**Retorno:**
- `HttpResponse` (template render).

---

### Función: `_text_error(request, message: str)`
**Qué hace:**  
Helper de error para flujos de upload/parsing.

**Flujo:**
- crea `structured = default_structure()`
- delega a `_render_text_editor(..., error=message)`

**Retorno:**
- `HttpResponse` render con error.

---

### Función: `_is_allowed_extension(filename: str) -> bool`
**Qué hace:**  
Valida si la extensión del archivo está dentro de `ALLOWED_EXTENSIONS`.

**Flujo:**
- `ext = _extension(filename)` (lowercase)
- `return ext in ALLOWED_EXTENSIONS`

---

### Función: `_max_upload_mb() -> int`
**Qué hace:**  
Obtiene tamaño máximo permitido en MB desde settings (`MAX_UPLOAD_MB`) o default 25.

---

### Función: `_extension(name: str) -> str`
**Qué hace:**  
Extrae extensión con `os.path.splitext(...)[1]` y la normaliza a minúscula.

---

### Función: `_safe_filename(name: str) -> str`
**Qué hace:**  
Genera un nombre seguro para export (sin path, sin caracteres raros, longitud acotada).

**Flujo:**
1) Obtiene `base` = nombre de archivo sin extensión, usando basename.
2) Aplica `slugify(base)` (Django) para dejarlo URL/file-safe.
3) recorta a 80 chars.
4) fallback a `"documento"` si queda vacío.

---

### Función: `_build_docx_bytes(text: str) -> bytes`
**Qué hace:**  
Construye un DOCX básico (sin plantilla) desde texto libre.

**Flujo:**
- crea `io.BytesIO()`
- crea `DocxDocument()` (python-docx)
- agrega cada línea como párrafo (`add_paragraph`)
- si el texto está vacío, agrega un párrafo vacío
- `doc.save(buffer)` y retorna `buffer.getvalue()`

**Retorno:**
- bytes del DOCX.

---

### Función: `_extract_docx_text(file_obj) -> tuple[str, str | None]`
**Qué hace:**  
Extrae texto de un `.docx` desde un file-like object, intentando:
1) python-docx (párrafos + tablas)
2) fallback leyendo XML interno del DOCX (para textboxes/shapes/headers)

**Intención:**
- Muchos CVs en DOCX traen información en tablas o incluso shapes, que python-docx a veces no expone bien.
- Se intenta “lo usual” primero y luego un fallback de bajo nivel.

**Flujo detallado:**
1) Lee `raw = file_obj.read()`
   - si está vacío => `("", "El archivo DOCX esta vacio.")`
2) Intenta parse con python-docx:
   - `doc = DocxDocument(io.BytesIO(raw))`
   - recorre `doc.paragraphs`: agrega `paragraph.text.strip()` si no vacío
   - recorre `doc.tables`:
     - por cada fila, arma `row_cells` con lista de líneas por celda (parrafos no vacíos)
     - si fila sin contenido => continue
     - dedup por celda:
       - `key = _normalize_key(" ".join(cell_lines))`
       - evita agregar celdas repetidas dentro de la misma fila
     - agrega `cell_lines` al resultado
   - si hay excepción => retorna error con detalle
3) Si `lines` tiene contenido => retorna texto unido por `\n`
4) Fallback XML:
   - abre el docx como zip (DOCX es un ZIP)
   - busca candidatos: `word/document.xml` y headers `word/header*`
   - para cada XML:
     - parsea con `ElementTree.fromstring`
     - busca párrafos `<w:p>` y dentro textos `<w:t>`
     - concatena textos y agrega líneas no vacías
   - si falla => error específico de XML
5) Si al final hay `lines` => retorna join y None
6) Si no => `("", "No se encontro texto legible dentro del DOCX.")`

**Retorno:**
- `(text, None)` si éxito
- `("", error_message)` si falla

---

### Función: `_template_path() -> Path | None`
**Qué hace:**  
Resuelve la ruta de la plantilla DOCX usada para export estructurado.

**Reglas / prioridad:**
1) Si `settings.CV_TEMPLATE_PATH` existe:
   - si es relativa => la vuelve absoluta con `settings.BASE_DIR`
   - si existe como archivo => retorna ese Path
2) Fallback default:
   - `BASE_DIR/templates/cv_template.docx`
   - si existe => retorna
3) Si nada => `None`

---

### Función: `_selected_font(request) -> str`
**Qué hace:**  
Lee la fuente pedida en POST (`doc_font`) y valida contra `FONT_CHOICES`.

**Reglas:**
- Si no es POST => `""`
- Si está vacía => `""`
- Si está en `FONT_CHOICES` => retorna el nombre
- Si no => `""` (evita inyección de valores raros)

---

### Función: `_normalize_key(text: str) -> str`
**Qué hace:**  
Normaliza texto para usar como clave de deduplicación:
- NFKD
- elimina acentos (combining chars)
- lower()
- strip()

Se usa para evitar duplicar celdas de tablas en `_extract_docx_text`.

---

### Función: `_convert_docx_bytes_to_pdf(docx_bytes: bytes) -> tuple[bytes | None, str | None]`
**Qué hace:**  
Convierte DOCX (bytes) a PDF (bytes) usando `docx2pdf` dentro de un directorio temporal.

**Dependencia crítica:**
- `docx2pdf` requiere estar instalado.
- En muchos entornos requiere Microsoft Word (sobre todo Windows) para la conversión.

**Flujo detallado:**
1) Importa `docx2pdf.convert` dentro del try:
   - si falla => retorna error “docx2pdf no está instalado...”
2) Crea `TemporaryDirectory()`:
   - escribe input en `documento.docx`
   - define output esperado `documento.pdf`
3) Intenta inicializar COM (Windows):
   - intenta importar `pythoncom`
   - si existe, hace `CoInitialize()` antes de convertir y marca flag
4) Ejecuta `docx2pdf_convert(str(input_path), str(output_path))`
5) Manejo de errores:
   - captura excepción, recorta detalle a 400 chars si existe
   - devuelve mensajes con contexto (o mensaje genérico si no hay detalle)
6) Finally:
   - si COM inicializado => `CoUninitialize()` con try/except silencioso
7) Verifica salida:
   - si `output_path` no existe, prueba `alt_path = input_path.with_suffix(".pdf")`
   - si tampoco existe => error “no generó PDF esperado”
8) Retorna `(output_path.read_bytes(), None)`

**Retorno:**
- `(pdf_bytes, None)` en éxito
- `(None, error_message)` en falla

---


---

# Fuente: structure_helpers_detailed_docs.md

# structure_helpers.py — Documentación detallada (por función)

> Formato: `archivo`
> `función`: explicación detallada (tal como la pediste en el chat, con intención/reglas/parámetros/retorno).

---

## Archivo: `structure_helpers.py`

### Función: `_split_extra_blocks(lines: List[str]) -> List[List[str]]`
**Qué hace:**  
Divide una lista de líneas en "bloques" (sub-listas) para secciones tipo "extra".

**Intención:**
- Cuando procesas un CV ya “lineado” (por OCR/extractor PDF/DOCX), a menudo las secciones
  extra vienen como texto suelto con saltos de línea, headers, espacios, etc.
- Esta función intenta separar "bloques" lógicos:
  - Un bloque se corta cuando aparece una línea vacía (separador natural).
  - También se corta cuando aparece un heading (título) mientras ya hay un bloque en curso.

**Reglas:**
- Línea vacía:
  - Si `current` tiene contenido, se empuja a `blocks` y se reinicia.
  - Si no tiene contenido, simplemente se ignora (no crea bloque vacío).
- Heading:
  - Si la línea "parece heading" y ya hay un bloque acumulado, se cierra el bloque actual
    y se inicia uno nuevo que parte con este heading.
- Al final:
  - Si queda algo en `current`, se agrega como último bloque.
- Si no se detectó nada (todo vacío), retorna `[[]]` para mantener consistencia aguas abajo.

**Parámetros:**
- `lines`: líneas originales (ya “limpias” a nivel de string, pero no necesariamente compactadas).

**Retorno:**
- Lista de bloques (cada bloque es una lista de líneas).

---

### Función: `_group_entries(lines: List[str], section: str) -> List[List[str]]`
**Qué hace:**  
Agrupa líneas en "entradas" (entries) dentro de una sección (experience/education/etc).

**Intención:**
- Dentro de una sección, una "entrada" suele ser algo como:
  - Experiencia: [Rol/Empresa], [Fecha], [Ubicación], [bullets...]
  - Educación: [Institución], [Grado], [Fecha], etc.
- En PDFs, el extractor puede desordenar o juntar líneas, así que necesitamos heurísticas
  para detectar cuándo “arranca” una nueva entrada.

**Reglas principales:**
- Ignora líneas vacías.
- Ignora headings (si se cuelan en el cuerpo) usando `_match_heading`.
- Si ya tenemos `current` y la línea actual "parece inicio de entrada" según
  `_looks_like_entry_start`, cerramos el `current` y comenzamos una nueva entrada.

**Parámetros:**
- `lines`: líneas crudas de la sección.
- `section`: nombre lógico de sección (p.ej. `"experience"`, `"education"`) para ajustar heurísticas.

**Retorno:**
- Lista de entradas; cada entrada es una lista de líneas.
- Si no hay nada, retorna `[[]]` por consistencia.

---

### Función: `_looks_like_entry_start(line: str, current: List[str], section: str) -> bool`
**Qué hace:**  
Decide si `line` debería iniciar una nueva "entrada" dentro de la sección.

**Filosofía:**
- En experiencia/educación, el inicio de entrada suele ser un "org-like" (empresa/institución),
  a veces junto a rol.
- Pero hay líneas engañosas que NO deben partir entrada: bullets, listas de tecnologías, fechas.

**Filtros (en orden):**
1) Si la línea es bullet, o parece stack/tech, o contiene una fecha => **NO** partir entrada.  
   (Porque típicamente esos elementos pertenecen a la entrada actual.)
2) Si la línea no parece organización (empresa/institución) => **NO** partir.
3) Si sí parece org, entonces validamos contexto:
   - Si la entrada actual ya tiene evidencia de "contenido completo" (fecha o bullets),
     entonces una nueva org-like probablemente indica una nueva entrada.

**Diferencias por sección:**
- `experience`:
  - Parte nueva entrada si la entrada actual ya tiene fecha o bullets.
- `education`:
  - Parte nueva entrada si la entrada actual ya tiene fecha o si ya hay org-like en `current`
    (porque educación puede encadenar institución/grado y luego otra institución).
- otras:
  - actualmente `False`.

**Parámetros:**
- `line`: línea candidata a inicio.
- `current`: líneas acumuladas de la entrada actual.
- `section`: sección actual.

**Retorno:**
- `True` si se considera inicio de nueva entrada, `False` si se considera continuación.

---

### Función: `_is_bullet(line: str) -> bool`
**Qué hace:**  
Detecta si una línea parece ítem de lista (bullet).

**Cómo lo decide:**
- Usa `BULLET_RE` (regex) definido en constants, típicamente capturando:
  - símbolos: `•`, `-`, `*`, etc.
  - formatos tipo `"- logro ..."`
- Se aplica sobre `line.strip()` para ignorar espacios accidentales.

**Retorno:**
- `True` si parece bullet, si no `False`.

---

### Función: `_looks_like_tech(line: str) -> bool`
**Qué hace:**  
Detecta si una línea parece "stack/tecnologías/herramientas" en lugar de una línea que inicia una nueva entrada.

**Problema que resuelve:**
- En PDFs, la línea `"Python, Pandas, scikit-learn"` puede venir sin prefijo (`"Tech:"`).
- Además, por el layout, a veces la extracción la coloca cerca de fechas/roles y podría
  confundirse con una nueva entrada si solo miramos “parece nombre propio”.

**Estrategia (3 capas):**
1) **Palabras clave explícitas:**
   - Si contiene fragmentos tipo `"tech"`, `"stack"`, `"framework"`, `"tools"`, etc.
2) **Patrón de lista:**
   - Si contiene separadores (coma, `·`, `•`, `/`) => tokenizamos.
   - Exigimos `>= 2` tokens y calculamos señales:
     - `short_ratio`: tokens relativamente cortos (stacks suelen ser cortos)
     - `has_symbols`: tokens con `# + . - / \` (ej: `C#`, `C++`, `Node.js`)
     - `looks_like_stack_token`: regex para tokens típicos (ej: `node.js`, `foo-bar`, etc.)
     - `title_like_ratio`: proporción con Mayúscula inicial (Unity, Pandas, Excel)
   - **Caso especial `len(tokens) == 2`:**
     - Evitamos confundir `"Santiago, Chile"` con tech.
     - Solo lo tratamos como tech si ambos tokens son siglas en mayúscula (`<= 6` chars).
3) **Fallback permisivo:**
   - Si hay coma y contiene palabras típicas (`python`, `django`, `react`...) o símbolos,
     lo tratamos como tech para **NO** partir entradas por error.

**Retorno:**
- `True` si parece tech/stack, `False` si no.

---

### Función: `_looks_like_org(line: str) -> bool`
**Qué hace:**  
Decide si una línea parece “organización” (empresa/institución) y no otra cosa.

**Evita confundir org con:**
- un grado (degree) / distinción
- una ubicación
- texto largo de descripción

**Heurística:**
- Rechaza líneas demasiado largas (`> 80`) porque suelen ser descripciones.
- Rechaza menciones honoríficas (`honor`, `cum laude`...) porque no son org.
- Rechaza `DEGREE_HINTS` (licenciatura/ingeniería/etc) porque eso es grado/título.
- Si parece ubicación y no contiene pistas fuertes de org (`ORG_HINTS`), se rechaza.
- Si contiene `ORG_HINTS` (corp, ltd, universidad, institute...), se acepta.
- Luego usa heurística de “Title Case”:
  - Si está en MAYÚSCULAS, se acepta (muchas empresas vienen así).
  - Si tiene 1 palabra, se rechaza (muy ambiguo).
  - Si tiene >=2 palabras y varias con mayúscula inicial (`>=2` y `ratio>=0.6`), se acepta.

**Nota:**
- Esto es probabilístico: busca minimizar falsos positivos que rompen el agrupado.

---

### Función: `_looks_like_location(line: str) -> bool`
**Qué hace:**  
Heurística liviana para detectar si una línea parece ubicación.

**Reglas:**
- Si contiene dígitos: rechazamos (calles, teléfonos, fechas).
- Si es muy larga (`>= 60`): rechazamos (descripciones).
- Si contiene coma: suele ser `"Ciudad, País"`.
- Si contiene separadores tipo `" · "`, `" | "`, `" / "` => suele ser `"Ciudad · País"` o similar.

---

### Función: `_split_role_company(line: str) -> Tuple[str, str]`
**Qué hace:**  
Intenta separar una línea en `(rol, compañía)`.

**Casos soportados (prioridad de separadores):**
- `"Rol - Empresa"`
- `"Rol — Empresa"`
- `"Rol – Empresa"`
- `"Rol | Empresa"`
- `"Rol en Empresa"` (español)
- `"Role at Company"` (inglés)

**Si no encuentra patrón:**
- retorna `(line.strip(), "")`.

**Importante:**
- No valida que sea org real; solo hace split.
- Se usa `_normalize_ascii` para chequear `" en "` / `" at "` en minúsculas y sin acentos.

---

### Función: `_normalize_heading_line(line: str) -> str`
**Qué hace:**  
Normaliza una línea para evaluación de headings.

**Pasos:**
1) Quita bullets y prefijos vía `_clean_bullet`.
2) Elimina caracteres no alfabéticos al inicio (p.ej. `"### EXPERIENCE"`).
3) Devuelve `strip()` final.

---

### Función: `_match_heading(line: str) -> Tuple[str, str]`
**Qué hace:**  
Detecta si una línea es un heading (título de sección) y lo mapea a una key interna.

**Retorna:**
- `(section_key, display_text)` si es heading reconocido
- `("", "")` si no lo es

**Lógica:**
1) Si es bullet, NO puede ser heading.
2) Normaliza con `_normalize_heading_line`.
3) Evita falsos positivos `"clave: valor"`:
   - Si hay `":"` en medio (no al final), asumimos label/value => NO heading.
4) Normaliza ASCII y compara contra `SECTION_KEYWORDS`:
   - match exacto o prefijo
5) Si no calza, pero parece heading extra por `_is_explicit_extra_heading`:
   - retorna `("extra", <texto>)`.

---

### Función: `_is_extra_keyword_heading(line: str) -> bool`
**Qué hace:**  
Detecta headings de "extra" basados SOLO en `EXTRA_KEYWORDS` (match exacto o prefijo).  
No usa heurísticas de mayúsculas o `":"`.

---

### Función: `_is_extra_heading_after_skills(line: str) -> bool`
**Qué hace:**  
Detector para headings no estándar después de skills u otras secciones.

**Reglas:**
1) Si `_is_explicit_extra_heading` => True.
2) Si es bullet => False.
3) Si coincide con heading conocido (`SECTION_KEYWORDS`) => False.
4) Si termina en `":"` => True.
5) Si está en mayúsculas, longitud razonable y sin coma => True.

---

### Función: `_is_explicit_extra_heading(line: str) -> bool`
**Qué hace:**  
Detector "permisivo" de headings extra.

**Reglas por capas:**
1) bullet => False
2) match con `EXTRA_KEYWORDS` => True
3) termina en `":"` => True
4) MAYÚSCULAS con filtros (sin comas/dígitos, >=2 palabras) => True

---

### Función: `_is_heading(line: str) -> bool`
**Qué hace:**  
Heurística general de “parece heading” sin mapear a sección.

**Reglas:**
- bullet => False
- longitud 3..48
- MAYÚSCULAS sin coma ni dígitos => True
- termina en `":"` => True

---

### Función: `_extract_date_range_from_line(line: str) -> Tuple[str, str, str]`
**Qué hace:**  
Extrae un rango de fechas desde una línea y devuelve:
- `start` (normalizado)
- `end` (normalizado)
- `cleaned_line` (línea sin el rango y con limpieza)

**Flujo:**
1) Busca `DATE_RANGE_RE`.
2) Si no match => `("", "", line)`
3) Si match:
   - normaliza tokens con `_normalize_date_token`
   - remueve el match del texto
   - limpia paréntesis
   - reemplaza separadores (`| · •`) por espacio
   - trim de guiones/espacios

---

### Función: `_extract_location_from_line(line: str) -> Tuple[str, str]`
**Qué hace:**  
Intenta extraer `(ciudad, país)` desde una línea.

**Estrategia:**
- Quita prefijos `"Ubicación:"` / `"Location:"`
- Limpia paréntesis
- Divide en candidatos por delimitadores
- Prueba `_parse_location` y retorna el primero válido

---

### Función: `_extract_tech_from_line(line: str) -> str`
**Qué hace:**  
Retorna la línea completa si parece una línea explícita de tecnologías.

**Casos:**
- `"Tecnologías: ..."`
- líneas que empiezan por `tecnolog`, `detalle`, `tech`, `stack`

Si no => `""`.

---

### Función: `_contains_bullet_symbol(text: str) -> bool`
**Qué hace:**  
Detecta si el texto contiene símbolos bullet (•, ·, etc).  
Se usa para dividir múltiples bullets en una sola línea.

---

### Función: `_format_date_range(start: str, end: str) -> str`
**Qué hace:**  
Formatea `(start, end)` a texto legible usando `_format_date_token`.

**Reglas:**
- ambos => `"start - end"`
- solo start => `"start - Actualidad"`
- solo end => `"end"`
- ninguno => `""`

---

### Función: `_normalize_date_token(value: str) -> str`
**Qué hace:**  
Normaliza tokens de fecha a `"YYYY-MM"` o `"YYYY"` cuando se pueda.

**Casos:**
- `"YYYY-MM"` => igual
- `"YYYY"` => igual
- `"M/YYYY"` => `"YYYY-0M"`
- `"Ene 2020"` => `"2020-01"` según `MONTHS`

Si no puede => retorna original.

---

### Función: `_format_date_token(value: str) -> str`
**Qué hace:**  
Convierte `"YYYY-MM"` => `"Mes YYYY"` usando `MONTHS_REVERSE`.  
Si no calza => devuelve igual.

---

### Función: `_join_paragraph(lines: List[str]) -> str`
**Qué hace:**  
Une líneas en párrafos preservando líneas vacías como separadores (`\n`).

---

### Función: `_has_content(items: List[Dict], keys: List[str]) -> bool`
**Qué hace:**  
Verifica si `items` contiene contenido real en alguna key:
- listas con `any(value)`
- strings con `.strip()`

---

### Función: `_trim_trailing_blanks(lines: List[str]) -> List[str]`
**Qué hace:**  
Elimina líneas vacías al final del array para evitar basura de export/parse.

---

### Función: `_compact_lines(lines: List[str]) -> List[str]`
**Qué hace:**  
Limpia ruido típico de PDF:
- elimina vacías
- elimina duplicados consecutivos
- filtra headers/footers repetidos (seen>2 y len>40)

---

### Función: `_first_match(pattern, text: str) -> str`
**Qué hace:**  
Retorna el primer match de un regex en el texto, o `""`.

---

### Función: `_normalize_ascii(text: str) -> str`
**Qué hace:**  
Normaliza texto para comparación:
- quita acentos (NFKD)
- colapsa espacios
- `lower()`

---

### Función: `_clean_bullet(text: str) -> str`
**Qué hace:**  
Elimina símbolos de bullet y prefijos (`-`, `*`, etc.) para dejar texto plano.

---

### Función: `_append_highlight(highlights: List[str], line: str) -> None`
**Qué hace:**  
Agrega highlights desde una línea, manejando:
- múltiples bullets en una línea
- split en chunks por saltos
- unión de continuaciones con `_is_continuation`

---

### Función: `_is_continuation(previous: str, current: str) -> bool`
**Qué hace:**  
Detecta si `current` continúa `previous`:
- si previous termina en `. ; : ! ?` => no
- si current empieza en minúscula => sí
- si previous termina en coma => sí

---

### Función: `_split_highlight_chunks(text: str) -> List[str]`
**Qué hace:**  
Divide texto por `\n` literal y saltos reales, devuelve lista de chunks no vacíos.

---

### Función: `_parse_location(line: str) -> Tuple[str, str]`
**Qué hace:**  
Parsea `(ciudad, país)` descartando cosas que no son ubicación (tech, contactos, honors).

**Flujo:**
- normaliza separadores a coma
- descarta `":"`, tech, email/url/phone, honors
- exige `_looks_like_location`
- intenta `LOCATION_RE`
- fallback split por coma con límites de palabras

---

### Función: `_is_location_candidate(candidate: str, contact_values: Set[str]) -> bool`
**Qué hace:**  
Valida si un texto puede ser ubicación, excluyendo:
- valores de contacto ya detectados
- tech o label con `":"`
- email/url/phone
- honors
- exige `_looks_like_location`


---

# Fuente: structure_detailed_docs.md

# structure.py — Documentación detallada (por función)

> Formato: `archivo`
> `función`: explicación detallada (intención/reglas/parámetros/retorno) para mantener el código limpio.

---

## Archivo: `structure.py` (parser principal + estructura <-> texto + POST -> estructura)

### Imports (contexto)
- Regex/utilidades: `re`, tipos `Dict/List/Tuple/Optional/Any`
- Constantes regex: `DATE_RANGE_RE`, `EMAIL_RE`, `PHONE_RE`, `URL_RE`
- Extras: `_empty_extra_entry`, `_has_extra_entry_content`, `_parse_extras` (manejo de secciones extra)
- Helpers: utilidades de parsing/heurísticas (bullets, headings, location, tech, date extraction, grouping, etc.)
- Types: `ExtraSectionRaw` (tipo de sección extra cruda: típicamente `{"title": str, "lines": list[str]}`)

---

## 1) Estructura base

### Función: `default_structure() -> Dict`
**Qué hace:**  
Devuelve el “shape” base de datos que usan:
- la UI del editor (form fields)
- el parser (`parse_resume`)
- los exports (DOCX/PDF) vía estructura

**Intención:**
- Tener un contrato fijo para el front: siempre existen `basics`, `experience`, `education`, `skills`.
- Evitar que templates/JS fallen por claves ausentes.
- Asegurar que siempre exista al menos 1 entry por sección core (mínimo viable).

**Contenido:**
- `meta.core_order`: string con orden de secciones core (`experience,education,skills`).
- `basics`: info principal (nombre, descripción, contactos, ciudad/país).
- `experience`: lista con 1 entry default con campos: rol/empresa/fechas/ubicación/tech/highlights.
- `education`: lista con 1 entry default (grado/institución/fechas/ubicación/honors).
- `skills`: lista con 1 categoría default (category/items).
- `extra_sections`: lista vacía para secciones dinámicas.

**Retorno:**
- Dict completo con defaults.

---

## 2) Entrada principal del parser

### Función: `parse_resume(text: str) -> Dict`
**Qué hace:**  
Convierte texto crudo de CV (ya extraído de PDF/DOCX) en una estructura dict lista para UI/export.

**Intención (pipeline general):**
1) Normalizar/compactar líneas (limpiar ruido típico de extracción).
2) Extraer contactos (email, phone, urls).
3) Detectar nombre + descripción inicial.
4) Detectar ubicación (ciudad, país).
5) Separar en secciones (experience/education/skills + extras).
6) Parsear cada sección con su parser específico.
7) Parsear extras.
8) Asegurar mínimos (para UI).

**Flujo detallado (en orden real):**
1) `data = default_structure()` crea el “molde”.
2) `lines = _compact_lines([...])`
   - toma `text.splitlines()`
   - hace `strip()` por línea
   - compacta duplicados/ruido con `_compact_lines`
3) `contact = _extract_contact(text)`
   - extrae email/teléfono/LinkedIn/GitHub
   - `data["basics"].update(contact)`
4) `name, description, remaining = _extract_name_and_description(lines, contact)`
   - primer bloque no-heading, excluyendo líneas de contacto
   - nombre = 1ra línea válida
   - descripción = párrafo hasta heading
5) ubicación:
   - `city, country = _extract_location(text, lines, contact)`
   - actualiza `data["basics"]["city"]`, `["country"]`
6) separación de secciones:
   - `sections, extras = _split_sections(remaining)`
   - `sections`: dict con listas de líneas por sección core
   - `extras`: lista de secciones extra crudas
7) parseo por sección:
   - `data["experience"] = _parse_experience(sections.get("experience", []))`
   - `data["education"] = _parse_education(sections.get("education", []))`
   - `data["skills"] = _parse_skills(sections.get("skills", []))`
8) extras:
   - `data["extra_sections"] = _parse_extras(extras)`
9) mínimos:
   - `_ensure_minimums(data)`
10) retorna `data`.

**Parámetros:**
- `text`: texto completo del CV, como string.

**Retorno:**
- Dict con la estructura parseada, listo para UI/export.

---

## 3) Estructura -> Texto (vista previa / export libre)

### Función: `build_text_from_structure(data: Dict) -> str`
**Qué hace:**  
Convierte la estructura (dict) a un texto “humano” en formato tipo CV, usado en:
- vista previa en el editor
- exportación “texto libre” (DOCX básico / PDF desde DOCX básico)

**Intención:**
- Tener un renderer consistente cuando el usuario edita por formulario.
- Respetar orden configurable (`meta.core_order`), incluyendo módulos extra individuales.

**Defensa:**
- Si `data` es `None` o falsy, lo reemplaza por `{}` para evitar errores.

### Helpers internos (importante entenderlos)
#### `_fmt_month_year(token: str) -> str`
- Acepta `YYYY` o `YYYY-MM`.
- Si es `YYYY` => devuelve año.
- Si es `YYYY-MM` => convierte mes numérico a abreviación ES (Ene, Feb, ...).
- Si no calza regex => devuelve token original sin romper.

#### `_format_date_range(start, end, is_current=False) -> str`
- Normaliza start/end con `_fmt_month_year`.
- Si `is_current=True` y `end` vacío => “Actual”.
- Construye:
  - `"start - end"` si ambos
  - `"start"` si solo start
  - `"end"` si solo end
  - `""` si nada

#### `_format_location(city, country) -> str`
- Une `city` y `country` con coma, ignorando vacíos.

#### `_format_detail_line(value) -> str`
- `str(value or "").strip()`; convierte cualquier valor a string limpio.

### Flujo principal del renderer
1) Lee `basics` y orden core:
   - `core_order_raw = data.meta.core_order or "experience,education,skills,extras"`
   - `core_order = [...]` split por comas
2) Construye `lines` (lista de strings) que luego se junta en `\r\n`.

#### Header
- Si hay nombre: lo agrega.
- Si hay descripción: la agrega.

#### Contacto
- arma `contact_lines` con:
  - Email / Teléfono / LinkedIn / GitHub / Ubicación
- Si hay algo, inserta “Contacto” como heading y luego bullets con `- ...`.

### Render de secciones core (helpers internos)
#### `emit_detail_section(title, entries, include_current_flag=False)`
- Renderiza Experience/Education (entries con campos role/company/degree/institution, etc.).
- Por cada entry:
  - construye heading “rol — empresa (fechas)” o “grado — institución (fechas)”
  - imprime ubicación si existe
  - imprime tecnologías si existe (`technologies` o `tech`)
  - imprime highlights como bullets
- Mantiene separaciones en blanco y recorta trailing blanks al final de cada sección.

#### `emit_detail_entry(entry, include_current_flag=True)`
- Renderiza 1 entry “detailed” de extras:
  - `subtitle` + `where` + fechas
  - ubicación
  - tech
  - items como bullets

#### `emit_subtitle_items_entry(entry)`
- Renderiza 1 entry modo “subtitle_items”:
  - Si no hay subtítulo pero hay 1 item: promueve item → subtítulo.
  - Si hay subtítulo y items: `- subtitle: item1, item2`
  - Si solo subtítulo: `- subtitle`
  - Si no hay subtítulo: imprime items como bullets

#### `emit_skills_section(title, categories)`
- Renderiza skills como:
  - `Category: item1, item2` cuando ambos existen
  - fallback si falta category o items.

#### `emit_extras(title, extra_sections)`
- Renderiza todas las extras como un bloque (modo compat):
  - imprime título general
  - por cada sección: imprime su título, luego entries según modo (`detailed` o `subtitle_items`)

### Orden de impresión (core_order)
- Toma `extra_ids` de cada extra_section (`section_id`) y los agrega si faltan.
- Itera `core_order`:
  - `experience` => `emit_detail_section("Experiencia", ...)`
  - `education` => idem con "Educacion"
  - `skills` => `emit_skills_section("Habilidades", ...)`
  - `extras` => imprime todas extras en bloque
  - otro => asume módulo extra individual (busca sección por `section_id`):
    - imprime título en MAYÚSCULA y subrayado
    - renderiza entries según modo (`subtitle_items` o `detailed`)
    - solo imprime si tiene contenido (usa `_has_extra_entry_content`)

**Retorno:**
- Un string con saltos CRLF `\r\n` (para compat Windows/Word).

---

## 4) POST -> Estructura (cuando el usuario editó el formulario)

### Función: `structure_from_post(post_data) -> Dict`
**Qué hace:**  
Reconstruye la estructura completa del CV desde los campos del formulario HTML (`request.POST`).

**Intención:**
- Convertir inputs de listas (`getlist`) de la UI a listas de dicts en el backend.
- Normalizar fechas a formato consistente (`_normalize_date_token`).
- Limpiar bullets en highlights/items.
- Reconstruir secciones extra (que son dinámicas y tienen múltiples modos).
- Reconstruir el orden final de módulos para export (`meta.core_order`).

### Flujo general (por bloques)
1) `data = default_structure()` (molde)
2) Construye `data["basics"]` desde campos simples (`name`, `email`, etc.) con `.strip()`.

### Orden de módulos (inputs de UI)
- `core_order_raw`: string “experience,education,skills,...” según UI
- `module_order_map_raw`: string tipo `"experience:1,education:2,extra-0:3"` generado por JS para orden preciso

### 4.1 Experiencia (listas paralelas)
- Lee listas: `exp_role`, `exp_company`, `exp_start`, ... `exp_highlights`.
- Itera por índice de `exp_roles`:
  - toma el texto de highlights del textarea correspondiente
  - parsea líneas no vacías, limpia bullets con `_clean_bullet`
  - arma dict con campos y fechas normalizadas (`_normalize_date_token`)
- Asigna a `data["experience"]`.

**Punto importante:**
- Se protege contra desalineación de listas verificando `idx < len(list)`.

### 4.2 Educación (listas paralelas)
- Igual que experiencia:
  - normaliza start/end
  - arma dict con degree/institution/honors
- Asigna a `data["education"]`.

### 4.3 Skills
- Toma `skill_category` y `skill_items`.
- Cada skill queda como:
  - `{"category": ..., "items": ...}` (items queda como string, no lista aquí).
- Asigna a `data["skills"]`.

### 4.4 Secciones extra (estructura dinámica)
**Inputs:**
- Secciones: `extra_section_id`, `extra_title`, `extra_mode`
- Entries: `extra_entry_section`, `extra_entry_subtitle`, `extra_entry_title`, `extra_entry_where`, ...
- Items (distintos formatos):
  - `extra_entry_items_si` (modo subtitle_items)
  - `extra_entry_items_detailed` (modo detailed)
  - `extra_entry_items` (legacy)

**Construcción de secciones base:**
1) Crea `sections` (lista) e `id_to_index` (mapa).
2) Para cada sección:
   - determina `sid` (si no viene, fallback `extra-{idx}`)
   - valida `mode` contra set permitido (`items`, `subtitles`, `subtitle_items`, `detailed`)
   - inicializa `entries` vacío
   - guarda en `sections` y mapea `id_to_index[sid]`.

**Problema central que resuelve:**  
Los entries pueden venir en modo:
- alineado por entrada (1 input por entry)
- “sparse” (inputs ocultos deshabilitados en UI; solo se envían los visibles)
- legacy (compat vieja con doble textarea por entry)

Para esto existe `_entry_field_value`.

#### Helper interno: `_entry_field_value(values, idx, entry_mode, field_mode, cursor_key) -> str`
- Caso 1: `len(values) == entry_count`:
  - toma `values[idx]` (alineado por entry)
- Caso 2: “sparse por modo”:
  - si `entry_mode != field_mode` => `""`
  - si coincide:
    - consume secuencialmente usando `field_cursors[cursor_key]`
    - incrementa cursor

#### Helper interno: `parse_items(raw_text: str) -> List[str]`
- Parsea items del editor: “un item por línea”.
- Normaliza saltos `\r\n`/`\r` a `\n`.
- Por cada línea:
  - strip
  - quita prefijos bullet/guiones via regex
  - limpia con `_clean_bullet`
- Retorna lista de items (strings).

**Asignación de entries a secciones:**
- Resuelve `sid` por entry con fallback:
  - si viene vacío, reutiliza `last_valid_sid` (para formularios que no repiten sid)
  - si solo hay 1 sección, usa `single_section_sid`
- Decide `entry_mode`:
  - si `section_mode == "detailed"` => entry_mode = "detailed"
  - else entry_mode = "si"
- Obtiene `raw_items` según:
  - modo-específico (`entry_items_si` / `entry_items_detailed`)
  - legacy pareado (`legacy_entry_items` con 2x)
  - legacy simple

Arma `entry` con campos:
- `subtitle` (si)
- `title`, `where`, `tech`, fechas, ciudad/país (detailed)
- `items` parseados

**Regla especial de subtitle_items:**
- Si modo `subtitle_items` y entry no trae subtítulo pero trae items:
  - promueve el primer item a subtítulo y deja el resto como items.
  - Esto evita pérdida de contenido al exportar.

**Filtro de contenido:**
- Solo agrega entry si `_has_extra_entry_content(entry)`.

**Normalización final de secciones extra:**
- Para cada sección:
  - filtra entries sin contenido
  - si no hay entries pero hay título: agrega `_empty_extra_entry()` (para que UI no quede vacía)
  - agrega sección si tiene título o entries
- Asigna a `data["extra_sections"]`.

### 4.5 Orden final (`meta.core_order`)
Objetivo: reconstruir el orden real de módulos en export.

- `available_ids`: empieza con `["experience", "education", "skills"]` y agrega `section_id` de extras.
- `core_order_ids`: parsea `core_order_raw`:
  - si token es `"extras"`, expande a todos los section_id extra
  - si token existe en `available_ids`, lo agrega
- `map_order_ids`: parsea `module_order_map_raw`:
  - parsea pares `key:order`
  - valida `key` y que `order` sea int >= 1
  - ordena por `(order, raw_idx)` y genera lista estable
- `final_order`: combina `map_order_ids + core_order_ids + available_ids` sin duplicar
- Si existe `final_order`, guarda en `data["meta"]["core_order"]` como string join por comas.

Finalmente:
- `_ensure_minimums(data)`
- retorna `data`.

**Retorno:**
- Dict estructura completa reconstruida desde POST.

---

## 5) Extracción de básicos

### Función: `_extract_contact(text: str) -> Dict[str, str]`
**Qué hace:**  
Extrae datos de contacto desde el texto completo del CV.

**Flujo:**
1) `email = _first_match(EMAIL_RE, text)`
2) `phone = _first_match(PHONE_RE, text)`
3) `urls = URL_RE.findall(text)`
4) Heurística para LinkedIn/GitHub:
   - primer URL que contenga `linkedin.com` => `linkedin`
   - primer URL que contenga `github.com` => `github`
5) retorna dict con esas 4 claves (pueden ser `""`).

---

### Función: `_extract_name_and_description(lines, contact) -> Tuple[str, str, List[str]]`
**Qué hace:**  
Intenta extraer:
- `name`: primera línea “no contacto”
- `description`: líneas siguientes hasta encontrar heading
- `remaining`: resto de líneas desde el heading (o tras finalizar)

**Intención:**
- CVs suelen venir con:
  - Nombre
  - Título/resumen
  - Luego headings (Experience, Education...)
- Evita capturar email/teléfono como nombre o descripción.

**Reglas clave:**
- `contact_values`: set de valores (email/phone/urls relevantes) para saltarlos si aparecen en líneas.
- Itera líneas:
  - si línea vacía y ya hay nombre => agrega separador (""), para respetar párrafos en descripción
  - si línea contiene un valor de contacto => ignora
  - si no hay nombre aún => esa línea se vuelve `name`
  - si detecta heading (`_is_heading`) => corta y setea `remaining = cleaned[idx:]`
  - si no, agrega línea a `description_lines`
- Si no encontró heading, `remaining` queda como el resto posterior a `last_index`.

**Post-proceso:**
- `description = _join_paragraph(description_lines)` (une en párrafos)

**Retorno:**
- `(name, description, remaining_lines)`

---

### Función: `_extract_location(text, lines, contact) -> Tuple[str, str]`
**Qué hace:**  
Detecta `(ciudad, país)` desde el encabezado del CV (antes de la primera sección).

**Intención:**
- La ubicación suele aparecer en el bloque superior junto con contacto.
- Se intenta detectar antes de entrar a secciones.

**Flujo:**
1) Construye `contact_values` para excluir coincidencias con email/phone/urls.
2) Itera sobre `lines` hasta antes del primer heading (`_is_heading`):
   - para cada línea, divide en chunks por separadores comunes (`·`, bullet, `|`)
   - si el chunk pasa `_is_location_candidate(...)`:
     - intenta `_parse_location(chunk)`
     - si retorna city y country => devuelve inmediatamente
3) Si no se encontró => `("", "")`.

---

## 6) Separación de secciones

### Función: `_split_sections(lines: List[str]) -> Tuple[Dict[str, List[str]], List[ExtraSectionRaw]]`
**Qué hace:**  
Parte el cuerpo del CV en:
- `sections`: dict con `experience`, `education`, `skills` (listas de líneas)
- `extras`: lista de secciones extra crudas (`{"title": str, "lines": [...]}`)

**Intención:**
- Reconocer headings usando `_match_heading`.
- Soportar “extras” tanto por headings explícitos como por headings extra detectados después de skills.

**Variables de estado:**
- `current_section`: `"other"`, `"experience"`, `"education"`, `"skills"`, `"extra"`
- `current_extra`: dict actual de extra si estamos en `"extra"`

**Reglas de flujo:**
- Línea vacía:
  - si `current_section` es core => append `""` a esa sección
  - si está en extra => append `""` a `current_extra["lines"]`
- Caso especial: si estamos en `skills` y detectamos heading extra (`_is_extra_heading_after_skills`):
  - switch a `"extra"` y crea sección extra con título normalizado
- Heading detectado por `_match_heading`:
  - si `key == "extra"`:
    - en skills: solo acepta si `_is_extra_keyword_heading`; si no, trata como línea de skills
    - en general: crea nueva `current_extra` con título y lista lines
  - si `key` es sección core:
    - cambia `current_section` a esa key y resetea `current_extra`

- Si no es heading:
  - agrega la línea a la sección actual (core o extra).

**Retorno:**
- `(sections, extras)`

---

## 7) Parsers por sección

### Función: `_parse_experience(lines: List[str]) -> List[Dict]`
**Qué hace:**  
Convierte líneas de la sección Experience en lista de entries estructuradas.

**Paso 1: agrupar**
- `blocks = _group_entries(lines, section="experience")`
- cada block es una “entrada” (rol/empresa/fechas/bullets...).

**Paso 2: parse por bloque**
Por cada `block`:
- inicializa `item` con campos vacíos
- `highlights` como lista

Por cada línea:
1) intenta extraer fechas (solo si `item["start"]` está vacío):
   - `_extract_date_range_from_line` devuelve (start, end, remainder)
   - si encontró fechas:
     - setea start/end
     - reemplaza `line` por remainder
     - si remainder queda vacío => continue
2) intenta extraer línea de tecnologías explícita:
   - `tech = _extract_tech_from_line(line)`
   - si existe y `item["technologies"]` vacío => setea y continue
3) heurística “tech sin label”:
   - si aún no hay technologies
   - y ya hay señales de entrada (rol/empresa/fecha)
   - y la línea no contiene fecha, no es heading
   - y `_looks_like_tech(line)` => setea technologies y continue
4) bullets/highlights:
   - si `_is_bullet` o `_contains_bullet_symbol` => `_append_highlight(highlights, line)` y continue
5) ubicación:
   - si no hay city => `_extract_location_from_line(line)`; si retorna city => setea y continue
6) rol/empresa:
   - si no hay role ni company:
     - `_split_role_company(line)`:
       - si trae company: setea role+company
       - si no: asume que la línea es company (fallback)
   - else si hay company pero no role => role = line
   - else si hay role pero no company => company = line
7) fallback:
   - si nada aplicó => trata como highlight: `_append_highlight`

Al final:
- `item["highlights"] = [h for h in highlights if h]`
- agrega item a lista.

**Retorno:**
- lista de experiencia; si queda vacía => default experience (mínimo UI).

---

### Función: `_parse_education(lines: List[str]) -> List[Dict]`
**Qué hace:**  
Parsea Education en entries (grado/institución/fechas/ubicación/honors).

**Agrupado:**
- `blocks = _group_entries(lines, section="education")`

**Parse por bloque:**
Para cada línea:
1) Normaliza `normalized = _normalize_ascii(line)` para detectar “honor/mención”.
2) Fechas:
   - si start vacío => `_extract_date_range_from_line`, setea start/end y ajusta line/recompute normalized
3) Honors por bullet:
   - si `_is_bullet` => `cleaned = _clean_bullet(line)`
   - si honors vacío => setea honors = cleaned
4) Honors por keyword:
   - si contiene “honor” o “mencion”:
     - si hay ":" => toma derecha; si no => usa línea completa
5) Ubicación:
   - si no hay city => `_extract_location_from_line`; si city => setea y continue
6) Institución:
   - si institution vacío y `_looks_like_org(line)` => setea institution
7) Grado:
   - si degree vacío => setea degree
8) Fallback institution:
   - si institution vacío => setea institution con la línea

**Retorno:**
- lista education; si vacía => default.

---

### Función: `_parse_skills(lines: List[str]) -> List[Dict]`
**Qué hace:**  
Parsea Skills en categorías con items (como string separado por coma).

**Modelo mental:**
- Skills suele venir como:
  - headings/categorías (“Lenguajes”, “Herramientas”)
  - debajo una lista (bullets o líneas) de items
- Esta función hace heurísticas para detectar “línea de categoría”.

**Estado:**
- `current_category`: categoría actual
- `current_items`: items acumulados

**Helper interno: `is_category_line(line, next_line) -> bool`**
Decide si una línea “es” una categoría. Usa varias señales:
- si es bullet o heading => True (trata como nueva categoría)
- si ya hay categoría y aún no hay items => False (evita partir demasiado rápido)
- si contiene ":" y no hay categoría => True (ej: “Lenguajes: Python, ...”)
- si tiene coma o es muy larga => False (probablemente lista de items)
- si contiene email/url => False
- si está en mayúsculas => True
- si contiene "/" => True (a veces “Backend/Frontend” como categoría)
- heurística por conectores “de” o “y” => True
- title-like ratio: si todas palabras empiezan en mayúscula => True
- mira `next_line` para casos de layout en dos líneas (categoría corta seguida de items)

**Flujo principal:**
1) `non_empty = [line for line in lines if line.strip()]`
2) Itera con índice para tener `next_line`:
   - si `is_category_line(...)`:
     - si hay categoría/items acumulados => flush a `items` (dict con category + join items)
     - setea `current_category = _clean_bullet(line)`
     - resetea `current_items = []`
   - else:
     - si `":"` y no hay categoría => split y agrega dict directo
     - si no => agrega `_clean_bullet(line)` a `current_items`
3) Al final, flush si hay algo.
4) Retorna `items` o default skills.

**Retorno:**
- lista de dicts: `{"category": str, "items": "a, b, c"}`

---

## 8) Mínimos para UI

### Función: `_ensure_minimums(data: Dict) -> None`
**Qué hace:**  
Garantiza que las secciones core existan con al menos 1 entry (mínimo UI).

**Reglas:**
- si `experience` vacío => setea default experience
- si `education` vacío => setea default education
- si `skills` vacío => setea default skills

**Retorno:**
- None (mutación in-place).

---


---

# Fuente: structure_extras_detailed_docs.md

# structure_extras.py — Documentación detallada (por función)

> Formato: `archivo`
> `función`: explicación detallada (intención/reglas/parámetros/retorno) para mantener el código limpio.
>
> Este archivo se centra en **parsear “secciones extra”** (Projects, Certifications, Awards, etc.)
> con heurísticas fuertes para PDFs: bullets raros, listas inline, columnas con `|`, identación,
> y ubicaciones al final tipo `Ciudad, País` sin confundirlas con listas de tecnologías.

---

## Archivo: `structure_extras.py` (parser de extras)

### Imports (contexto)
- `re`, tipos `Dict/List/Tuple/Any`
- Constantes:
  - `DATE_RANGE_RE`: regex de rangos de fecha (ej: `2020 - 2022`, `Jan 2021 - Present`)
  - `_CITY_CONNECTORS`, `_CITY_PREFIXES`, `_NON_CITY_HINTS`: vocabulario para detectar cola de ciudad/ubicación
- Helpers de parsing:
  - Limpieza y detección: `_clean_bullet`, `_is_bullet`, `_is_heading`, `_looks_like_location`, `_looks_like_org`, `_looks_like_tech`
  - Normalización: `_normalize_ascii`, `_normalize_date_token`
  - Location parser: `_parse_location`
  - Split rol/empresa: `_split_role_company`
- Types:
  - `ExtraSectionRaw`: sección extra cruda (típicamente `{"title": str, "lines": list[Any]}`)

---

## 1) Utilidades base

### Función: `_split_escaped_newlines(text: str) -> List[str]`
**Qué hace:**  
Divide un string en “líneas” aceptando:
- saltos reales (`\n`, `\r\n`)
- secuencias literales `"\n"` que vienen como dos caracteres (común en algunos extractores o JSON intermedio)

**Flujo:**
1) Si `text is None` => `[]`.
2) Convierte a string.
3) Normaliza literales:
   - `"\r\n"` → `"\n"`
   - `"\n"` → `"\n"` (salto real)
4) Normaliza saltos reales:
   - `\r\n` y `\r` → `\n`
5) Split por `\n`:
   - strip cada línea
   - solo conserva no vacías

**Retorno:**
- Lista de líneas limpias (sin vacíos).

---

### Función: `_empty_extra_entry() -> Dict`
**Qué hace:**  
Devuelve un dict “entry extra” vacío con todas las keys esperadas por UI/export.

**Campos:**
- `subtitle`, `title`, `where`, `tech`, `start`, `end`, `city`, `country`, `items`

**Intención:**
- Contrato estable, similar a `default_structure()` pero para entries extra.

---

### Función: `_has_extra_entry_content(entry: Dict) -> bool`
**Qué hace:**  
Determina si una entry extra tiene “contenido real”.

**Reglas:**
- Revisa campos string clave:
  - `subtitle/title/where/tech/start/end/city/country`
  - True si cualquiera existe y `.strip()` no queda vacío
- Si no, revisa `items`:
  - True si algún item tiene contenido no vacío

**Uso:**
- Filtrar entries “fantasma” creadas por heurísticas o layout del PDF.

---

## 2) Inferencia de modos (extra sections)

### Función: `_infer_extra_mode(entries: List[Dict]) -> str`
**Qué hace:**  
Decide modo global de una sección extra según sus entries.

**Regla:**
- Si cualquier entry tiene señales de “detalle” (`title/where/start/end/city/country`) → `"detailed"`
- Si no → `"subtitle_items"`

**Intención:**
- Solo soportar dos presentaciones macro:
  - `detailed`: entries con campos tipo “Proyecto — Cliente (fechas) + tech + items”
  - `subtitle_items`: entries tipo “• Subtitle” con items debajo

---

### Función: `_infer_entry_mode(entry: Dict) -> str`
**Qué hace:**  
Misma idea que `_infer_extra_mode`, pero por entry.

**Regla:**
- Si hay campos de detalle (`title/where/start/end/city/country`) → `"detailed"`
- Si no → `"subtitle_items"`

**Nota:**
- Comentario “compat”: no se mezcla por entrada en el UI, pero al importar PDFs pueden salir entries en distinto “modo” y se marca para export/compat.

---

## 3) Parseo de items y líneas “inline”

### Función: `_looks_like_inline_list(line: str) -> bool`
**Qué hace:**  
Detecta si una línea **sin bullets** parece un listado “A, B, C” (p.ej. items, números o tecnologías).

**Problema que resuelve:**
- “Ciudad, País” también tiene coma, pero NO queremos tratarlo como lista.
- En extras, estas listas pueden aparecer como una sola línea sin prefijo.

**Reglas:**
- Si vacío → False
- Si contiene rango de fecha (`DATE_RANGE_RE`) → False
- Split por coma:
  - Requiere al menos 3 partes (o al menos 2 comas)
  - Si exactamente 2 partes → False (para no confundir ubicaciones)

**Retorno:**
- True si parece lista inline.

---

### Función: `_split_items_text(raw_text: str) -> List[str]`
**Qué hace:**  
Parsea items **por línea** (no por coma).

**Razón:**
- Hay items que incluyen comas internas (ej: “1, 2, 3”) y deben mantenerse como un solo item.

**Flujo:**
1) Si `raw_text is None` → `[]`.
2) Normaliza `"\n"` literal a salto real.
3) Itera `.splitlines()`:
   - strip
   - limpia bullets con `_clean_bullet`
   - agrega a `items`
4) Caso especial números sueltos:
   - Si hay >=2 items y todos son dígitos de un solo carácter (`"1"`, `"2"`, `"3"`) → retorna `["1, 2, 3"]`
   - Esto reconstituye listas numéricas que el PDF cortó en líneas separadas.

**Retorno:**
- Lista de items strings.

---

## 4) “Payload” de línea: soporta strings y dicts con metadata

### Función: `_extract_line_payload(raw_line: Any) -> Tuple[str, Dict[str, Any]]`
**Qué hace:**  
Normaliza una “línea” de entrada que puede ser:
- string normal
- dict con `text` + metadata (útil para PDF parsing con indent/bold/bullet)

**Si `raw_line` es dict:**
- `text = raw_line["text"]` (strip)
- meta:
  - `indent`: float
  - `is_bullet`: bool (heurística del extractor)
  - `is_bold`: bool
  - `size_ratio`: float (tamaño relativo de fuente)
  - `ends_with_colon`: bool

**Si es string:**
- retorna (string.strip(), meta default con indent 0, etc.)

**Intención:**
- Permitir que `_parse_extra_entries` use señales de layout.

---

## 5) Bloques dentro de extras

### Función: `_split_extra_blocks(lines: List[Any]) -> List[List[Any]]`
**Qué hace:**  
Divide las líneas de una sección extra en **bloques** (sublistas) usando:
- líneas vacías como separador fuerte
- headings detectados por `_is_heading` como separador (cuando hay contenido previo)

**Flujo:**
- Para cada `raw_line`:
  - extrae `text` con `_extract_line_payload`
  - si `text` vacío:
    - si `current` tiene contenido → push y reset
  - si `text` parece heading y `current` no está vacío:
    - cierra bloque actual y comienza nuevo con esta línea
  - else: agrega línea
- Al final: agrega `current` si hay algo
- Si no hay nada: retorna `[[]]` por consistencia

---

### Función: `_infer_block_indents(block: List[Any]) -> Tuple[float, float | None]`
**Qué hace:**  
Infiera “base indent” y un “umbral de columna derecha” (si aplica).

**Motivación:**
- Algunos PDFs representan columnas (izquierda: título, derecha: fechas/ubicación) usando indentación.
- Si hay una diferencia fuerte de indent, se considera que hay “columna derecha” y se calcula `right_threshold`.

**Flujo:**
- Recolecta `indent` de cada línea no vacía del bloque.
- `base_indent = min(indents)`
- `max_indent = max(indents)`
- Si `max - base < 120` → no hay columnas: retorna `(base_indent, None)`
- Si hay: `threshold = base + (max-base)*0.6`

**Retorno:**
- `(base_indent, right_threshold | None)`

---

## 6) Heurísticas de ubicación complejas (cola, prefijos y stubs)

> Estas funciones se enfocan en casos reales de PDF donde:
> - La ubicación viene pegada al final: `"Curso de X — Universidad Y — Santiago, Chile"`
> - Parte del “prefijo” de ciudad queda separado en otra columna o línea: `"Región Metropolitana" + "Santiago, Chile"`
> - Hay conectores como “de”, “del”, “la” y prefijos como “Región”, “Provincia”, etc.

### Función: `_split_location_tail_loose(text: str) -> Tuple[str, str]`
**Qué hace:**  
Intenta separar un string en (leftover, city_tail) buscando el “rabo” que parece ciudad/prefix.

**Estrategia:**
- Si hay separadores (`| / - – — ·`) hace `rsplit` por el último y devuelve `left, right`.
- Si no:
  - toma última palabra como inicio de `city_words`
  - mientras palabras anteriores sean conectores/prefijos (`_CITY_CONNECTORS | _CITY_PREFIXES`), las mueve a `city_words`
- Retorna:
  - leftover = resto
  - city_tail = lo movido

**Uso:**
- Fallback cuando `_split_trailing_location` no puede detectar ciudad por coma.

---

### Función: `_looks_like_location_prefix(text: str) -> bool`
**Qué hace:**  
Decide si un texto corto puede ser un “prefijo” de ubicación (ej: “Región Metropolitana”).

**Reglas:**
- No dígitos
- No fechas
- Largo <= 45
- No vacío

---

### Función: `_apply_location_prefix(entry: Dict, prefix: str) -> str`
**Qué hace:**  
Aplica un `prefix` a `entry["city"]` si corresponde.

**Reglas:**
- Si no hay `prefix` → ""
- Si no hay `city` aún → retorna `prefix` (queda “pendiente”)
- Si `city` ya empieza con `prefix` (normalizado) → no aplica
- Si aplica:
  - `entry["city"] = f"{prefix} {city}"`
  - retorna "" (prefijo consumido)

**Uso:**
- Cuando el prefijo vino en otra línea/columna y luego aparece la ciudad real.

---

### Función: `_split_trailing_location(line: str) -> Tuple[str, str, str]`
**Qué hace:**  
Intenta detectar una ubicación en cola del tipo `"... Ciudad, País"` y separarla en:
- `leftover`: texto sin la ubicación
- `city`
- `country` (normalizado vía `_parse_location`)

**Reglas fuertes anti falsos positivos:**
- Debe contener coma y **exactamente una coma** (`count(",")==1`), porque listas tech tienen múltiples comas.
- `country_part` no puede tener dígitos.
- Analiza `left_part` palabra por palabra desde el final:
  - Usa `_NON_CITY_HINTS` para cortar (palabras que indican que no es ciudad)
  - Permite `_CITY_CONNECTORS` dentro del segmento ciudad
  - Usa heurística de “Title words” (mayúscula inicial) para acumular hasta 3 palabras “significativas”
- Si no logra city_words, usa `_split_location_tail_loose` como fallback.
- Detecta casos donde el “País” está repetido en la cola de ciudad (para limpiar).
- Valida ciudad final haciendo `_parse_location(f"{city}, {country_part}")`.
  - Si falla, fallback a loose split.

**Retorno:**
- `(leftover, city, country)` o `(candidate, "", "")` si no detecta ubicación.

---

### Función: `_is_location_prefix_only(text: str) -> bool`
**Qué hace:**  
Devuelve True si el texto solo contiene conectores/prefijos (sin contenido real).

**Uso:**
- Para evitar tratar “de la”/“Región” como `where` válido.

---

### Función: `_is_location_stub(text: str) -> bool`
**Qué hace:**  
Detecta “stubs” de texto que suelen ser basura o fragmentos sueltos:
- vacío
- solo dígitos
- siglas cortas en mayúscula (<=4)

**Uso:**
- Evitar que esos fragmentos se asignen a `where/title`.

---

### Función: `_split_location_prefix_from_text(text: str) -> Tuple[str, str]`
**Qué hace:**  
Separa un prefijo de ubicación del final de un texto, en casos como:
- `"Algo Región"` (conector al final)
- `"Región Metropolitana"` (prefijo + palabra título)

**Reglas:**
- Usa las últimas 2 palabras:
  - Si last es conector y prev es TitleWord → separa
  - Si prev es prefix y last es TitleWord → separa

**Retorno:**
- `(base_text, prefix_suffix)` o `(text, "")`

---

### Función: `_merge_location_prefix(entry: Dict, source_key: str, line_stub: str) -> bool`
**Qué hace:**  
Mueve un prefijo de ubicación desde `entry[source_key]` hacia `entry["city"]` cuando:
- ya existe `city`
- la línea actual es stub (poco confiable)
- el `source_key` termina con un patrón que parece prefijo de ubicación

**Flujo:**
- Si no city → False
- Si `line_stub` no es stub → False
- `base, prefix = _split_location_prefix_from_text(entry[source_key])`
- Si no prefix → False
- Si city ya empieza con prefix → False
- Si aplica:
  - `entry[source_key]=base`
  - `entry["city"]=f"{prefix} {city}"`
  - True

**Intención:**
- Reparar casos donde el prefijo quedó pegado al título en vez de a la ciudad.

---

### Función: `_split_title_location_suffix(title: str) -> Tuple[str, str]`
**Qué hace:**  
Detecta si el `title` termina con un segmento que parece prefijo de ubicación y lo separa.

**Estrategia:**
- Considera segmentos de longitud 2..4 al final
- Requiere que todas sean “TitleWords”
- Requiere presencia de `_CITY_PREFIXES` en el segmento
- Distingue patrones:
  - `... <conectores/prefixes> <prefix>`
  - `... <prefix> <Title>` (len<=3)
- Retorna `(base_title, suffix)` o `(title, "")`

**Uso:**
- Ajustar `title` cuando parte era en verdad “Región X” que debe ir con city.

---

## 7) Heurísticas de “fragmentos” de entries extra

### Función: `_entry_has_location(entry: Dict) -> bool`
- True si `where/city/country` existe.

### Función: `_entry_has_core(entry: Dict) -> bool`
- True si `title/start/end` existe.

### Función: `_is_sparse_extra_entry(entry: Dict) -> bool`
**Qué hace:**  
Detecta entries “sparse” (fragmento): no subtitle y no items con contenido.

**Uso:**
- Merge de fragments: un fragmento puede traer solo ubicación o solo fechas.

### Función: `_is_subtitle_only_extra_entry(entry: Dict) -> bool`
**Qué hace:**  
Detecta entry que solo tiene `subtitle` y nada más (sin items ni detalles).

**Uso:**
- A veces el PDF mete “Santiago, Chile” como bullet/entry; se usa para re-asignarlo.

### Función: `_is_detailed_extra_entry(entry: Dict) -> bool`
**Qué hace:**  
True si tiene cualquiera de los campos detallados.

---

### Función: `_merge_extra_entries(core_entry: Dict, loc_entry: Dict) -> Dict`
**Qué hace:**  
Fusiona dos entries (una con “core” y otra con “location”) en una sola.

**Reglas de preferencia:**
- `subtitle/title/tech`: prioriza `core_entry` si existe, sino `loc_entry`.
- `where/city/country`: prioriza `loc_entry` si existe, sino `core_entry`.
- Fechas: toma primero que exista.
- Items: concatena items de ambas entries, limpiando strings vacíos.

**Retorno:**
- Nueva entry completa (no muta las originales).

---

### Función: `_should_merge_extra_entries(first: Dict, second: Dict) -> bool`
**Qué hace:**  
Decide si 2 entries sparse deben fusionarse.

**Regla:**
- Deben ser ambas sparse.
- Caso A:
  - first tiene location sin core
  - second tiene core sin location
- Caso B: viceversa
- Si cumple → True

---

### Función: `_merge_extra_entry_fragments(entries: List[Dict]) -> List[Dict]`
**Qué hace:**  
Arregla secuencias de entries mal fragmentadas por el extractor.

**Tres estrategias principales:**
1) Si `current` es detailed:
   - Consume entradas siguientes que sean “subtitle-only”:
     - si el subtitle parece ubicación, lo pone en city/country si faltaba
     - si parece tech, lo pone en tech si faltaba
     - si no, lo agrega como item
2) Caso “detailed + subtitle-only” inmediato:
   - Merge simple: agrega subtitle como item
3) Caso “sparse + sparse” que deben mergearse:
   - Usa `_should_merge_extra_entries` y `_merge_extra_entries`

**Retorno:**
- Lista de entries corregida.

---

## 8) Detección de inicio de nueva entry dentro de un bloque

### Función: `_should_start_new_extra_entry(entry, items, line, meta, right_threshold) -> bool`
**Qué hace:**  
Regla clave: decide si una línea debería **cerrar** la entry actual y **abrir** una nueva.

**Condiciones que bloquean (NO iniciar nueva):**
- si no hay entry actual con contenido ni items
- si la línea es bullet (o meta.is_bullet) → la trata como item/subtitle, no como inicio
- si estamos en columna derecha (indent >= right_threshold) y la línea es fecha → NO cortar

**Señales fuertes para cortar:**
- línea en bold (`meta.is_bold`) y ya hay contenido y además hay campos que indican entry “completa”
- línea con fecha cuando la entry ya tenía fecha
- línea que parece split `Rol — Org` (via `_split_role_company`) cuando entry ya tiene algo
- línea org-like en bold cuando ya hay fechas/ciudad, etc.

**Anti-falsos positivos (muy importante):**
- Si entry ya está en modo detallado (tiene title/where) y aún no tiene tech,
  una línea libre no-boldeada y no-org-like se trata como detalle, NO como nueva entry.
- Si entry está en modo detallado y la línea parece tech (`_looks_like_tech`) o empieza con “tecnologias:”,
  NO parte nueva entry aunque tenga comas.
- Si la línea termina en ubicación (cola ciudad) pero entry ya tiene ciudad:
  - puede ser nueva entry… pero se protege con el caso anterior de “detalle libre” para no cortar por error.

**Retorno:**
- True si debe partir nueva entry.

---

### Función: `_looks_like_detailed_bullet(entry: Dict, line: str) -> bool`
**Qué hace:**  
Detecta cuando un bullet en PDF realmente es una **línea de detalle** (fecha/ubicación/tech/rol-org),
y no un item de lista.

**Reglas:**
- si al limpiar bullet queda vacío → False
- si tiene fecha → True
- si `Rol — Org` → True
- si entry ya tiene contexto detallado y la línea parece:
  - ubicación
  - tech
  - “tecnologias:”
  → True

**Uso:**
- En `_parse_extra_entries`: si un bullet parece “detalle”, lo reinterpreta como línea normal.

---

## 9) Parser principal de entries extra

### Función: `_parse_extra_entries(lines: List[Any]) -> List[Dict]`
**Qué hace:**  
Convierte líneas crudas de una sección extra en entries estructuradas,
soportando:
- bullets normales
- bullets que son “detalle”
- listas inline sin bullets
- entradas en columnas con `|` y/o indentación
- fechas/ubicación pegadas a la derecha
- prefijos de ubicación flotantes
- merge de fragmentos post-proceso

**Paso 1: bloques**
- `blocks = _split_extra_blocks(lines)`

**Paso 2: parse por bloque**
Para cada `block`:
1) `right_threshold = _infer_block_indents(block)`
2) inicia:
   - `entry = _empty_extra_entry()`
   - `items = []`
   - `pending_location_prefix = ""`
3) Itera líneas del bloque:
   - extrae `(line, meta)` con `_extract_line_payload`
   - si `_should_start_new_extra_entry(...)`:
     - flush entry actual (set items), append, reset entry/items/prefix

### Manejo de bullets
- Si `meta.is_bullet` o `_is_bullet(line)`:
  - `bullet_text = _clean_bullet(line)`
  - si `_looks_like_detailed_bullet(entry, bullet_text)`:
    - convierte bullet a línea normal (is_bullet=False) y re-evalúa si corta entry
  - else:
    - En modo subtitle_items: cada bullet inicia nueva entry:
      - flush entry previa si tenía contenido
      - `entry["subtitle"] = bullet_text`
      - `continue` (no procesa como detalle)

### Listas inline (sin bullets)
- Si `_looks_like_inline_list(line)` y entry no tiene campos detallados:
  - si no hay `subtitle` → la línea se vuelve subtitle
  - si ya hay subtitle → se agrega como items (por línea)

### “Modo subtítulo”: forzar líneas no-bullet a items
- Si ya hay `subtitle` y no hay campos de detalle:
  - cualquier línea no-fecha y no-heading se agrega a items (soporta \n escapados)

### Prioridad tech antes que ubicación
- Si estamos en modo detallado (title/where) y no hay `tech`:
  - si línea empieza con “tecnologías” → `entry["tech"]=line`
  - else si `_looks_like_tech(line)` o (inline list y NO location) → `tech=line`
Esto evita confundir `"Python, Pandas, ..."` como `"Ciudad, País"`.

### Segmentos con `|`
- Si `"|" in line`:
  - separa left/right
  - procesa en right:
    - fechas primero
    - luego ubicación (con `_split_trailing_location` o `_parse_location`)
    - si no fue fecha/ubicación y parece prefijo → acumula `pending_location_prefix`
  - luego se queda con `line = left_segment or right_segment` para seguir parseando

### Fechas en la línea
- Si no se procesó fecha aún:
  - busca `DATE_RANGE_RE` y setea start/end si entry no tenía start
  - limpia el texto removiendo el match

### Ubicación trailing
- Usa `_split_trailing_location` para detectar `..., País`.
- Si detecta city y entry ya tenía city:
  - evita truncar líneas (protección anti falsos positivos con comas)
- Si detecta city y entry no tenía city:
  - setea city/country
  - aplica `pending_location_prefix` si existía
  - intenta mover prefijos desde title con `_merge_location_prefix`
  - puede reubicar `where` si el texto remanente parecía “where”
  - puede ajustar `title` si trae sufijo de prefijo de ciudad (`_split_title_location_suffix`)

### Post ubicación: reordenamiento title/where
- Caso especial si se aplicó prefijo y se detectó que `title` y `where` deben swapear.

### Captura tech (otra vez, antes de title/where)
- Si hay contexto detallado y la línea parece tech → setea `entry["tech"]`.

### Bold como señal de title/where
- Si `meta.is_bold` y no hay `where`:
  - si parece ubicación o contiene coma → setea `where`
  - si no hay title → setea `title`

### Parse ubicación “pura”
- Si `_looks_like_location(line)` y no city y solo 0-1 comas:
  - usa `_parse_location` y setea city/country

### Fallback de detalle libre a tech
- Si ya hay `title` y `where` y no hay tech y la línea no es heading → tech=line

### Subtítulo con `:`
- Si no hay subtitle y hay `:`:
  - `subtitle = left`, items desde `right`

### Asignación title/where general
- Si no hay title ni where:
  - usa `_split_role_company`
  - si encuentra where → setea ambos
  - si no:
    - si había location => prioriza where
    - si no => title
- Si ya hay title y no where: where=line
- Si ya hay where y no title: title=line (si no heading, o si venía con fecha)
- Si no subtitle y es heading → subtitle=line

### Default: todo lo demás se vuelve item
- agrega partes soportando saltos escapados y limpieza bullets.

**Cierre del bloque:**
- setea `entry["items"]`
- append entry

**Post-proceso global:**
- `entries = _merge_extra_entry_fragments(entries)`
- retorna `entries` o `[_empty_extra_entry()]`

---

## 10) Parser de secciones extra (wrapper)

### Función: `_parse_extras(extras: List[ExtraSectionRaw]) -> List[Dict]`
**Qué hace:**  
Convierte secciones extra crudas (title + lines) en secciones estructuradas para el CV.

**Flujo:**
- `parsed = []`
- Por cada `extra` con índice `idx`:
  1) `title = extra["title"].strip()`
  2) `entries = _parse_extra_entries(extra["lines"])`
  3) Por cada entry:
     - si no trae `mode`, setea `mode=_infer_entry_mode(entry)`
     - compat: si `mode=='subtitles'` y no subtitle:
       - junta items en una línea y lo pone como subtitle (items=[])  
       (compat con formatos antiguos de UI)
  4) Filtra entries sin contenido si corresponde:
     - `entries = [e for e in entries if _has_extra_entry_content(e)] or entries`
  5) Si no hay title y tampoco hay entries con contenido → skip sección.
  6) `mode = _infer_extra_mode(entries)` (modo global)
  7) append dict final:
     - `section_id = f"extra-{idx}"`
     - `title`, `mode`, `entries`

**Retorno:**
- Lista de secciones extra estructuradas.

---


---

# Fuente: docx_template_detailed_docs.md

# docx_template.py — Documentación detallada (por función)

> Objetivo del archivo: **renderizar un CV estructurado (dict)** hacia un **DOCX** basado en una **plantilla**.
>
> En vez de “construir” el documento desde cero, este módulo:
> - Abre un `.docx` plantilla (con **tablas** y estilos ya definidos).
> - Busca filas “marcadoras” (headers como *EXPERIENCIA / EDUCACIÓN / HABILIDADES*).
> - Clona filas plantilla (copiando XML `w:tr`) para repetir bloques (experiencia/educación/extras).
> - Rellena texto respetando formato (clona `pPr` y formato de runs).
> - Ajusta detalles finos (links clickeables, tamaños de bullets, keep-with-next, colapsar filas en blanco).
> - Reordena módulos según el orden que el usuario definió en la UI (`meta.core_order`).

---

## Constantes y TypeAlias

### `DocxDocumentType: TypeAlias = Any`
Alias “blando” para el tipo de documento `python-docx`. Se usa porque `python-docx` no expone typing completo.

### `ContactPart: TypeAlias = tuple[str, str, str | None, int]`
Representa un “fragmento” dentro de la línea de contacto:
- kind: `"text"` o `"link"`
- text: texto visible
- url: destino del link (o `None` si no es link)
- size_pt: tamaño de fuente que se desea aplicar

### `MONTHS_REVERSE`
Mapeo `"MM" -> "Mes"` usado por `_format_date_token()` para transformar `"YYYY-MM"` en `"Mes YYYY"`.

---

## Helpers de normalización simple

### `_format_detail_line(value: str | None) -> str`
- Limpia `value` con `.strip()`.
- Devuelve string “listo para imprimir” (o `""`).

Se usa para líneas como “Tecnologías” / “Tech” donde no se quiere imprimir basura en blanco.

### `_normalize_extra_mode(value: str | None, default: str = "subtitles") -> str`
Normaliza el modo de render de Extras.

Reglas:
- `"items"` (modo histórico) => se trata como alias de `"subtitles"` (Punto/Listado).
- Solo acepta: `{subtitles, subtitle_items, detailed}`
- Si viene otra cosa => vuelve a `default`.

Impacto: evita que la UI o CVs viejos rompan el export.

### `_entry_items_inline(entry: dict) -> str`
- Toma `entry["items"]` (lista).
- Limpia y une por `", "`.
- Devuelve una sola línea (útil en modos tipo “subtitles”).

---

## Punto de entrada principal

### `render_from_template(structured: dict, template_path: Path, font_name: str | None = None) -> bytes`
**Qué hace:** genera un `.docx` final (bytes) usando una plantilla.

Flujo (alto nivel, en orden):
1. **Carga el DOCX plantilla** con `DocxDocument(template_path)`.
2. **Valida que exista al menos una tabla** (`doc.tables`), porque todo el layout está basado en la primera tabla.
3. Obtiene los datos desde `structured`:
   - `basics`, `experience`, `education`, `skills`, `extras`.
4. **Localiza filas header** dentro de la tabla con `_find_row_index()`:
   - “experiencia”, “educación”, “habilidades”.
   - Si faltan => `ValueError` (plantilla incompatible).
5. Detecta filas “especiales”:
   - `contact_row_idx`: usando `_find_row_index_predicate()` (busca “linkedin”, “github” o “@”).
   - `name_row_idx`: primera fila no vacía antes del contacto.
   - `summary_row_idx`: primera fila no vacía entre contacto y experiencia.
6. **Rellena basics**:
   - Nombre: `_set_row_text()`
   - Contacto: `_set_contact_row()` (incluye hyperlinks)
   - Descripción: `_set_row_text()`
7. **Aplica “keep with next”** a headers y gaps:
   - `_set_row_keep_with_next()` + `_apply_section_keep_with_next_gap()`
   - Esto evita que Word “corte” el header al final de página separado del contenido.
8. **Renderiza experiencia**:
   - `_apply_experience(table, exp_header_idx, edu_header_idx, experience)`
9. Recalcula `edu_header_idx` y `skills_header_idx` (porque `_apply_experience` modifica filas).
10. **Renderiza educación**:
   - `_apply_education(table, edu_header_idx, skills_header_idx, education)`
11. Recalcula `skills_header_idx` y renderiza skills:
   - `skills_content_idx = _apply_skills(...)`
12. **Renderiza extras** debajo de skills:
   - `extra_blocks = _apply_extras(...)`
   - Retorna “bloques” de filas insertadas por extra para reordenarlas después.
13. Ajuste fino:
   - `_normalize_skills_bullets(...)`: fuerza tamaño del numerado/bullets en skills.
   - `_apply_module_order(...)`: reordena módulos según `meta.core_order`.
   - `_apply_font(...)`: aplica fuente global elegida por el usuario.
   - `_collapse_blank_rows(...)`: elimina dobles filas en blanco consecutivas sin bordes.
14. Guarda a `BytesIO` y retorna `buffer.getvalue()`.

**Errores típicos controlados:**
- Plantilla sin tablas.
- Plantilla sin headers esperados (o mal formateados, ej. no en mayúsculas).

---

## Render de Experience / Education / Skills

### `_apply_experience(table, exp_header_idx: int, edu_header_idx: int, experience: list[dict]) -> None`
Inserta bloques de experiencia clonando filas plantilla.

Conceptos:
- En plantilla, experiencia suele tener:
  - una fila “role/company/tech” (2 columnas)
  - una fila “highlights” (1 columna)
  - filas “spacer” (en blanco, sin bordes) opcionales
- Este método **detecta cuáles filas se usan como templates**, las clona, borra el contenido viejo del rango, e inserta filas nuevas.

Flujo:
1. Encuentra:
   - `exp_role_idx`: primera fila no vacía después del header de experiencia.
   - `exp_high_idx`: siguiente fila no vacía (highlights).
2. Clona XML `w:tr` de ambas filas (`deepcopy(row._tr)`).
3. Busca `spacer_idx` y `section_spacer_idx`:
   - filas en blanco sin bordes (para separación entre entradas y al final de sección).
4. Detecta si hay “gap” inmediatamente después del header:
   - si existe y es fila en blanco => `keep_with_next` + limpiar altura (para no dejar espacios raros).
5. Filtra items con `_has_experience_content()`.
6. Elimina filas del rango de experiencia “viejo”:
   - `_remove_rows(table, delete_start, edu_header_idx)`
7. Inserta por cada entry:
   - Inserta role row -> `_fill_experience_role_row()`
   - Si hay highlights -> inserta highlights row -> `_fill_experience_highlights_row()`
   - Si aplica, inserta spacer rows.
8. Inserta un spacer de cierre (si existe template) al final.

### `_apply_education(table, edu_header_idx: int, skills_header_idx: int, education: list[dict]) -> None`
Similar a experiencia pero con una sola fila template por entry (2 columnas).

Pasos:
1. `edu_template_idx`: primera fila no vacía tras el header de educación.
2. Clona template, detecta spacer(s) sin bordes.
3. Maneja `gap` post-header.
4. Filtra items con `_has_education_content()`.
5. Borra rango antiguo y reinsertar:
   - por cada entry: `_fill_education_row()`
   - spacer entre entries + spacer final.

### `_apply_skills(table, skills_header_idx: int, skills: list[dict]) -> int | None`
Rellena la **celda** de skills (normalmente una fila de 1 columna).

Idea:
- Usa los párrafos existentes como “plantilla de estilo”.
- Limpia la celda completa (borra párrafos).
- Reagrega párrafos replicando formato.

Flujo:
1. Encuentra `skills_content_idx`: primera fila no vacía después del header.
2. Obtiene celda “única” del row.
3. Captura `template_paragraphs` y estilos (para clonar).
4. `_clear_cell()` para borrar contenido.
5. Filtra categorías con contenido.
6. Detecta “roles” de párrafos plantilla:
   - `category_template`, `items_template`, `spacer_template`
7. Por cada categoría:
   - agrega párrafo para `category` (si existe)
   - agrega párrafo para `items` (si existe)
   - agrega spacer entre categorías (párrafo vacío)
8. Devuelve `skills_content_idx` para que otros pasos (bullets/ extras) sepan dónde insertar.

---

## Ajuste de bullets / numbering

### `_normalize_skills_bullets(doc: DocxDocumentType, table, skills_content_idx: int | None, *, size_pt: int = 11) -> None`
Problema: en DOCX, el tamaño del “número/bullet” puede ser distinto al texto.

Qué hace:
1. Recorre párrafos del row de skills.
2. Detecta aquellos con `numPr` (numeración/lista).
3. Captura pares `(numId, ilvl)` usados.
4. Para cada par, llama `_set_numbering_level_size()`.

### `_set_numbering_level_size(doc: DocxDocumentType, num_id: str, ilvl: str, size_pt: int) -> None`
Manipula el XML de numbering:
- Busca el `w:num` con `numId`.
- Obtiene `abstractNumId`.
- Busca `w:abstractNum` correspondiente.
- Busca nivel `w:lvl` con `ilvl`.
- Asegura `w:rPr` y setea:
  - `w:sz` y `w:szCs` a `size_pt * 2` (half-points).

Esto ajusta el tamaño del símbolo/número.

---

## Extras: render y compatibilidad

### `_extra_entry_lines(entry: dict, *, mode: str = "detailed") -> list[str]`
Helper de fallback/compatibilidad: transforma una `entry` en “líneas” imprimibles.

- Normaliza `mode` con `_normalize_extra_mode`.
- Para `subtitles`: devuelve solo `subtitle` o items inline.
- Para `subtitle_items`: devuelve `[subtitle, items_inline]` si existen.
- Para `detailed`: arma:
  - subtitle (si existe)
  - header “title — where” + `(date_range)`
  - tech
  - location
  - items (cada item como línea)

### `_extra_entry_has_content(entry: dict) -> bool`
Chequea si una entry tiene algún campo con contenido real o items no vacíos.

### `_flatten_extra_lines(extra: dict) -> list[str]`
Convierte una sección extra completa en lista de líneas:
- Si viene en formato antiguo con `items`, devuelve items.
- Si viene con `entries`, usa `entry.mode` (o `extra.mode` como default) y llama `_extra_entry_lines`.

### `_apply_extras(table, skills_header_idx: int, skills_content_idx: int | None, extras: list[dict]) -> list[dict[str, Any]]`
Inserta secciones extra debajo de habilidades.

Características clave:
- Soporta **modo por entrada** (`entry["mode"]`) para mezclar:
  - entries detalladas (2 columnas tipo experiencia)
  - entries tipo “subtitles/subtitle_items” en 1 columna (tipo skills)
- Mantiene compat con formato antiguo (`extra["items"]`).

Flujo:
1. Si no hay `skills_content_idx` o no hay extras => `[]`.
2. Filtra/normaliza secciones:
   - Define `title` fallback si viene vacío (“SECCION EXTRA N”) para conservar límites al reimportar PDF.
   - Normaliza `section_mode`.
   - Filtra entries con `_extra_entry_has_content`.
   - Normaliza `entry["mode"]` (fallback a `section_mode`).
   - Si no hay entries y hay `items` => guarda como formato antiguo.
3. Prepara templates:
   - `header_template`: clona fila header de skills.
   - `gap_template`: si hay fila en blanco inmediatamente tras header.
   - `content_template`: clona fila de contenido de skills (1 columna).
   - `spacer_template`: fila en blanco sin bordes para separación.
   - Templates “detalle” (2 columnas) tomando filas de experiencia si existen:
     - `exp_role_template`, `exp_high_template`
4. Inserción:
   - Inserta un spacer entre skills y la primera extra.
   - Para cada sección extra:
     - Inserta header row con `title.upper()` y `keep_with_next`.
     - Inserta gap row si hay template.
     - Inserta contenido:
       - Si formato antiguo `items`: una fila 1-col y `_fill_extra_row`.
       - Si entries:
         - Si `mode == detailed` y hay templates de experiencia:
           - Inserta role row y `_fill_extra_detail_role_row`
           - Inserta highlights row si hay items y template disponible
         - Else:
           - Inserta fila 1-col con líneas `_extra_entry_lines`
           - Si modo es subtitles/subtitle_items: pone el primer párrafo en itálica (diferenciación visual)
       - Spacer entre entries
     - Spacer entre secciones
5. Retorna `extra_blocks`: lista con `{section_id, rows:[tr,...]}` para que `_apply_module_order()` pueda moverlos.

---

## Reordenamiento de módulos (core_order)

### `_apply_module_order(table, structured: dict, extra_blocks: list[dict[str, Any]]) -> None`
Respeta el orden de módulos que la UI guardó en `structured["meta"]["core_order"]`
Ej: `"experience,education,skills,extra-0,extra-1"` o `"experience,skills,extras,education"`.

Pasos:
1. Lee `meta.core_order`. Si no existe => no hace nada.
2. Re-ubica índices de headers (`_find_row_index`).
3. Construye listas de filas (`tr`) para cada módulo:
   - experience: desde header exp hasta header edu
   - education: desde header edu hasta header skills
   - skills: desde header skills hasta antes del primer extra insertado
   - extras: desde `extra_blocks` (con start position calculado)
4. Expande token `"extras"` a ids reales de extras (en orden actual).
5. Construye `final_modules`:
   - primero los pedidos (sin duplicar)
   - luego los que falten (para no perder secciones)
6. Calcula `insert_at`: primera posición donde aparecen filas movibles.
7. Remueve del XML de tabla todas las filas de módulos que se van a reordenar.
8. Re-inserta en el orden final usando `_insert_row_before`.
9. Inserta spacer rows (si hay template) entre módulos cuando corresponde.

---

## “Fillers” (rellenar filas específicas)

### `_fill_experience_role_row(row, item: dict) -> None`
Rellena la fila 2-col de experiencia:
- Columna izquierda: company, role, tech
- Columna derecha: location, date_range

Usa `_set_cell_lines_preserve()` para escribir múltiples líneas sin perder formato.

### `_fill_experience_highlights_row(row, item: dict) -> None`
Rellena la fila de highlights (1 col):
- Cada highlight es una línea.

### `_fill_education_row(row, item: dict) -> None`
Rellena educación (2 col):
- Izq: institution, degree, “Honores: ...” si existe
- Der: location, date_range

### `_fill_extra_detail_role_row(row, entry: dict) -> None`
Rellena fila 2-col para extra en modo detailed:
- Izq: where, title, tech (en ese orden para parecerse a experiencia)
- Der: location, date_range

### `_fill_extra_detail_highlights_row(row, items: list[str]) -> None`
Imprime items como líneas (equivalente a highlights).

### `_fill_extra_row(row, items: list[str]) -> None`
Imprime lista de líneas en celda 1-col (estilo skills).

---

## Contacto y hyperlinks

### `_set_contact_row(row, basics: dict) -> None`
Construye la fila de contacto con separadores “ · ” y enlaces clickeables.

Detalles:
- Lee: city, country, linkedin, phone, email, github.
- “parts” principales (una sola línea) en el primer párrafo:
  - location (text)
  - linkedin (link) -> `_normalize_url()`
  - phone (text)
  - email (link) -> `mailto:...`
- Luego, si hay `github`, lo pone en un **segundo párrafo** como hyperlink (y agrega un spacer vacío).
- Si no hay nada, genera un párrafo vacío para conservar layout.

Usa:
- `_add_run_with_size()` para texto normal clonando formato.
- `_add_hyperlink()` para insertar links con `w:hyperlink` y relación externa.

### `_normalize_url(value: str) -> str`
Asegura protocolo:
- si ya empieza con http:// o https:// => ok
- si no => antepone https://

### `_add_run_with_size(paragraph, text: str, run_template=None, *, size_pt: int | None = None)`
Crea run, clona formato de `run_template` y aplica `font.size` si se indica.

### `_add_hyperlink(paragraph, text: str, url: str, run_template=None, *, size_pt: int | None = None) -> None`
Inserta hyperlink “real” en OOXML:
- Crea relación externa (`part.relate_to(url, RT.HYPERLINK, is_external=True)`).
- Crea `w:hyperlink` + `w:r` y lo inserta en el párrafo.
- Crea `Run` con `python-docx` sobre ese XML.
- Clona formato y fuerza:
  - `underline=True`
  - color azul (RGB 05 63 C1)
  - tamaño si aplica

---

## Fechas, ubicaciones y texto simple

### `_format_date_range(start: str | None, end: str | None) -> str`
- Convierte tokens con `_format_date_token()`.
- Formatos:
  - start y end: `"start–end"`
  - start y sin end: `"start–Actualidad"`
  - end solo: `"end"`
  - ninguno: `""`

### `_format_date_token(value: str | None) -> str`
- Si calza `YYYY-MM` => `Mes YYYY` (usa `MONTHS_REVERSE`)
- Si no => devuelve tal cual (para no perder info).

### `_join_location(city: str | None, country: str | None) -> str`
Une como `"Ciudad, País"` omitiendo vacíos.

### `_set_row_text(row, text: str) -> None`
Escribe texto en primera celda única de la fila, preservando estilo.

---

## Keep-with-next y altura

### `_set_row_keep_with_next(row, value: bool = True) -> None`
Pone `paragraph.paragraph_format.keep_with_next = True` en todos los párrafos de la fila.

### `_clear_row_height(row) -> None`
Borra `w:trHeight` de `trPr` si existe para evitar alturas fijas heredadas al clonar.

### `_apply_section_keep_with_next_gap(table, header_idx: int) -> None`
Si existe una fila en blanco inmediatamente después del header, también la marca con keep-with-next.

---

## Escritura preservando formato (núcleo)

### `_set_cell_lines_preserve(cell, lines: list[str], *, trim_extra_paragraphs: bool = False) -> None`
Función clave para escribir “líneas” en una celda sin romper estilos.

Estrategia:
1. Usa párrafos existentes como templates.
2. Reescribe/crea párrafos para cada línea.
3. Elimina párrafos sobrantes (o limpia) sin dejar numbering fantasma.

---

## Mutación de tabla (borrado e inserción)

### `_remove_rows(table, start: int, end: int) -> None`
Elimina filas del rango.

### `_insert_row_before(table, row_idx: int, tr_element) -> None`
Inserta un `w:tr` antes de `row_idx` (o append si row_idx está al final).

---

## Riesgos típicos / debugging rápido
- **Plantilla no compatible:** headers no en mayúsculas o texto distinto.
- **Merged cells:** si no se usan `_unique_cells`, se escribe duplicado.
- **Numbering raro:** skills con estilos distintos puede no tener `numPr`.
- **Hyperlinks:** revisar relación externa y el `w:hyperlink`.


---

# Fuente: editor_ui_script_detailed_docs.md

# Documentación detallada — script de UI (editor)

> Archivo: script IIFE + helpers globales (modo claro/oscuro, repeats, fechas, extras por sección/entrada, reorden de módulos).
>
> Objetivo: este documento explica **en orden de ejecución** cada bloque del script, qué elementos DOM toca, qué `data-*` usa como contratos con el HTML, qué efectos secundarios produce (mutaciones del DOM, `dataset`, `localStorage`, inputs hidden), y cómo se conectan entre sí.

---

## 0) Estructura general del archivo

El archivo contiene **tres grandes piezas**:

1) Un **IIFE principal** (Immediately Invoked Function Expression):

```js
(() => { /* ... */ })();
```

Este bloque se ejecuta apenas se carga el script y:

- define helpers (`qs`, `qsa`, `randomId`)
- inicializa tema (light/dark)
- inicializa repetidores (experience/education/skills)
- inicializa fechas y toggle “Actualidad”
- inicializa extras (secciones y entradas)
- inicializa listeners delegados globales (click/change)
- prepara el `submit` del formulario para serializar highlights y fechas
- expone `window.__trufadocs_reorder` para sincronizar el orden cuando se agregan/eliminen módulos

2) Una función global **`applyExtraMode(sectionEl)`** (fuera del IIFE) que aplica el modo por sección a las entradas extras y habilita/deshabilita inputs.

3) Otro IIFE **`initCoreModuleReorder()`** (fuera del IIFE principal) que implementa:
- mover módulos con flechas arriba/abajo
- persistir el orden en inputs hidden (`core_order`, `module_order_map`)
- animación y “scroll follow” al mover

---

## 1) Helpers base del IIFE principal

### 1.1 `qs` y `qsa`

```js
const qs  = (sel, root=document) => root.querySelector(sel);
const qsa = (sel, root=document) => Array.from(root.querySelectorAll(sel));
```

- **Contrato**: permiten buscar elementos rápidamente.
- `qs` devuelve el primer match o `null`.
- `qsa` siempre devuelve un array (vacío si no hay matches), ideal para `forEach`.

### 1.2 `randomId`

```js
const randomId = () => Math.random().toString(16).slice(2,10);
```

- Genera un id corto pseudoaleatorio (8 hex chars).
- Se usa para `section_id` de módulos extra nuevos: `extra-${randomId()}`.
- **Nota**: no es criptográficamente seguro; suficiente para IDs UI.

---

## 2) Tema claro/oscuro (persistente)

### 2.1 Cálculo del tema inicial

```js
const root = document.documentElement;
const storedTheme = window.localStorage ? localStorage.getItem("theme") : "";
const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
const initialTheme = storedTheme || (prefersDark ? "dark" : "light");
root.dataset.theme = initialTheme;
```

Efectos:

- Lee `localStorage.theme` si existe.
- Si no existe, usa `prefers-color-scheme: dark`.
- Escribe en `document.documentElement.dataset.theme`:
  - `root.dataset.theme = "dark"` o `"light"`.
- **Contrato CSS**: típicamente hay estilos como:

```css
:root[data-theme="dark"] { ... }
:root[data-theme="light"] { ... }
```

### 2.2 Botones de toggle de tema

```js
const themeButtons = Array.from(document.querySelectorAll("[data-theme-toggle]"));
```

- Busca todos los toggles con atributo `data-theme-toggle`.

#### `updateThemeButtons()`

- Decide si está en modo dark.
- Actualiza accesibilidad:
  - `aria-pressed`
  - `aria-label`
  - `title`

Esto mantiene UI coherente aunque haya múltiples botones (ej: uno en header y otro en footer).

#### Click handler

Al click:

- calcula `nextTheme`
- setea `root.dataset.theme`
- persiste en `localStorage.theme`
- llama `updateThemeButtons()`

---

## 3) Configuración de “Add repeat” (Experience/Education/Skills)

### 3.1 Tabla de configuración `addHandlers`

```js
const addHandlers = [
  { button: "[data-add='experience']", list: "#experience-list", tpl: "#tpl-experience" },
  { button: "[data-add='education']",  list: "#education-list",  tpl: "#tpl-education" },
  { button: "[data-add='skills']",     list: "#skills-list",     tpl: "#tpl-skills" },
];
```

Contrato HTML:

- botones con `data-add="experience|education|skills"`
- contenedores de lista con ids `#experience-list`, `#education-list`, `#skills-list`
- templates opcionales con ids `#tpl-experience`, `#tpl-education`, `#tpl-skills`

---

## 4) Highlights (hitos) en experiencia

### 4.1 `highlightRow(value="")`

Crea dinámicamente:

- `<div class="highlight-row">`
  - `<input class="highlight-input" type="text">`
  - `<button class="ghost small" data-remove-highlight>Eliminar</button>`

**Importante**: el botón usa:

```js
remove.dataset.removeHighlight = "";
```

En HTML se traduce a atributo: `data-remove-highlight=""`, que luego se captura con delegación.

### 4.2 `ensureHighlightRows(block)`

- Busca `.highlight-list` dentro del bloque.
- Si está vacío, agrega una fila inicial con `highlightRow()`.

Esto evita que el usuario tenga que apretar “Agregar hito” para la primera línea.

---

## 5) Fechas (YYYY / YYYY-MM) + toggle “Actualidad”

El sistema de fechas tiene dos representaciones:

1) **Visible**: `<select data-year-select>` y `<select data-month-select>`
2) **Hidden**: `<input type="hidden">` con el valor real enviado al backend (ej: `2024-09`, `2024`, `Actualidad`).

### 5.1 `parseDateValue(value)`

- Si está vacío: `{year:"", month:"", current:false}`
- Si es “actualidad/presente/current/present/hoy”: `{current:true}`
- Si matchea `YYYY` o `YYYY-MM`: extrae año/mes
- Si no: retorna vacío (evita parseos raros)

### 5.2 `syncDateField(block)`

Contrato DOM del `block`:

- `input[type='hidden']`
- `[data-month-select]`
- `[data-year-select]`
- opcional: `block.dataset.forceCurrent === "1"` (controlado por toggle de “Actualidad”)

Comportamiento:

- Si `forceCurrent`:
  - hidden.value = `"Actualidad"`
  - deshabilita selects mes/año
- Si no:
  - habilita selects
  - setea hidden.value:
    - `YYYY-MM` si hay año y mes
    - `YYYY` si hay solo año
    - `""` si no hay año

### 5.3 `initDateField(block)`

- idempotente: si `block.dataset.dateInit === "1"` no hace nada.
- Lee el hidden, lo parsea y setea selects.
- Si era “Actualidad”, pone `block.dataset.forceCurrent = "1"`.
- Registra listeners `change` en año y mes para resinc.

### 5.4 `initCurrentToggle(repeat)`

Contrato DOM:

- checkbox/radio con `[data-role-current]`
- un campo fin con `[data-date-field][data-date-end]`

Objetivo: cuando “Actualidad” está activo, la fecha fin se bloquea.

Guarda backups:

- `endField.dataset.prevYear`
- `endField.dataset.prevMonth`

para restaurar cuando el usuario desmarca “Actualidad”.

También detecta si el hidden ya venía en “Actualidad” y auto-checkea el toggle.

### 5.5 `initDateFields(rootEl=document)`

- Inicializa todos los `[data-date-field]` y `.repeat` en el `rootEl`.
- Se llama:
  - al inicio de la página
  - después de agregar nuevos repeats
  - dentro de `initExtraEntry(entry)` (extras detalladas)

---

## 6) Extras: modo por ENTRADA (entry) y por SECCIÓN

Este script maneja extras complejos con 2 niveles:

- **Sección extra**: `data-extra-section`
- **Entrada dentro de sección**: `data-extra-entry`

y puede decidir modo de render/inputs por:
- select por entrada: `[data-extra-entry-mode]` (legacy o avanzado)
- o select por sección: `[data-extra-mode]` (actual principal)

### 6.1 `syncExtraEntryMode(entry)`

Decide el modo:

1) Si hay select por entry (`[data-extra-entry-mode]`):
   - toma su valor
   - normaliza:
     - `"subtitles"` o `"items"` -> `"subtitle_items"`
2) Si no, busca la sección padre `[data-extra-section]`:
   - lee `[data-extra-mode]`
   - fallback `"subtitle_items"`

Guarda:

- `entry.dataset.extraEntryMode = mode`

Luego aplica visibilidad a fields:

```js
entry.querySelectorAll("[data-extra-entry-show]").forEach((field) => {
  const allowed = (field.dataset.extraEntryShow || "").split(" ");
  const isHidden = allowed.length > 0 && !allowed.includes(mode);
  field.style.display = isHidden ? "none" : "";
});
```

Contrato:

- Cada bloque/field controlado debe tener `data-extra-entry-show="detailed subtitle_items ..."`
- Si el modo no está en la lista, se oculta.

### 6.2 `initExtraEntry(entry, sectionId)`

Responsabilidades:

1) **Asociar la entrada a la sección** mediante hidden:

- `input[name="extra_entry_section"]`
- Si viene `sectionId` se usa.
- Si no, intenta resolverlo desde `input[name="extra_section_id"]` del padre.
- Si aún no, usa lo que ya traía el input.

2) Bind de cambio de modo por entry:

- sólo una vez (`modeSelect.dataset.bound !== "1"`)

3) Ejecuta:

- `syncExtraEntryMode(entry)`
- `initDateFields(entry)` (para start/end dentro de extras en modo detallado)

### 6.3 `initExtraSection(section)`

`section` es el nodo `[data-extra-section]`.

- `moduleBlock` = contenedor `.module-block` que representa la sección como módulo reordenable (si existe).

Pasos:

1) Generar `extra_section_id` si está vacío:

- hidden: `input[name="extra_section_id"]`
- valor: `extra-${randomId()}`

2) Mapear sección -> módulo reordenable:

- `moduleBlock.dataset.moduleKey = sectionId`
- mantiene consistencia con reorder (`core_order`)

3) Mantener tipo de módulo:

- lee select `[data-extra-mode]`
- setea `moduleBlock.dataset.moduleType = mode`
- actualiza en `change`

4) Sincronizar título en header del módulo:

- input `[data-extra-title]`
- label `[data-module-name]`
- si está vacío: `"(sin título)"`

5) Eliminar sección:

- botón `[data-action="remove-extra-section"]`
- elimina el **módulo completo** si existe `.module-block`
- luego: `window.__trufadocs_reorder.sync()` para recalcular orden

6) Inicializar entradas existentes:

- contenedor `[data-extra-entries]`
- hijos `[data-extra-entry]` -> `initExtraEntry(entry, sectionId)`

7) Aplicar modo por sección:

- `applyExtraMode(section)`

8) Botón “Agregar entrada”:

- `[data-action="add-extra-entry"]`
- usa template `#tpl-extra-entry`
- clona y agrega al entriesRoot
- inicializa entry y reaplica modo

### 6.4 `initExtraSections(rootEl=document)`

Inicializa todas las secciones extras existentes.

---

## 7) Agregar repeats (experience/education/skills) — template o fallback

Este bloque ofrece robustez:

- Si hay `<template>` lo usa.
- Si no, clona el último `.repeat` existente.

### 7.1 `clearInputs(rootEl)`

Limpia inputs en un clon:

- `select`: intenta setear a `value=""` si existe option vacía; si no, `selectedIndex=0`.
- `checkbox/radio`: `checked=false`
- `hidden`: limpia si el name termina en `_start`, `_end` o incluye `id`
- otros: `value=""`

### 7.2 `cloneRepeatFallback(listEl)`

- toma el último `.repeat` dentro de la lista
- `cloneNode(true)`
- remueve `.highlight-row` ya existentes (porque se reconstruyen)
- remueve marca `data-reorder-init` (para que re-inicialice comportamiento si aplica)
- corre `clearInputs(clone)`
- devuelve el clon listo

### 7.3 Listener “Add”

Por cada handler:

- on click:
  - si hay template: `template.content.cloneNode(true)` y append
  - si no: `cloneRepeatFallback` y append
- luego rehidrata:
  - `ensureHighlightRows` en `[data-highlight-block]`
  - `initDateFields(listEl)` para fechas dentro de los nuevos repeats

---

## 8) Inicializaciones al cargar

Dentro del IIFE principal:

1) Garantiza highlight inicial en cada bloque:
```js
document.querySelectorAll("[data-highlight-block]").forEach(ensureHighlightRows);
```

2) Inicializa fechas en todo el documento:
```js
initDateFields();
```

3) Inicializa extras:
```js
initExtraSections();
```

---

## 9) Dialog de ayuda (`<dialog class="help">`)

Si existe `.help`:

- `pointerdown` en capture:
  - si el dialog está abierto y el click fue fuera: `helpDialog.open = false`
- `keydown`:
  - si `Escape`: cierra

Contrato: se asume `<dialog class="help">`.

---

## 10) Delegación global de clicks (hitos y eliminar repeats)

Listener:

```js
document.addEventListener("click", (event) => { ... })
```

Casos:

1) `[data-add-highlight]`:
- busca el bloque `[data-highlight-block]`
- agrega `highlightRow()` a `.highlight-list`

2) `[data-remove-highlight]`:
- busca `.highlight-row` y lo elimina del parent

3) `[data-remove]`:
- elimina el `.repeat` completo donde está el botón

---

## 11) Delegación change (fallback de “Actualidad”)

Listener:

```js
document.addEventListener("change", (event) => { ... })
```

Se activa cuando cambia cualquier `[data-role-current]`.

Motivo: aunque el init por repeat fallara (por modo dinámico de extras), este handler asegura que:

- al check:
  - guarda `prevYear/prevMonth` si no estaba forzado
  - limpia selects
  - setea `forceCurrent=1`
  - setea hidden="Actualidad"
- al uncheck:
  - restaura `prevYear/prevMonth`
  - borra `forceCurrent`
  - limpia hidden si estaba en “Actualidad”
- siempre corre `syncDateField(endField)`

---

## 12) Submit del formulario `#structured-form`

En `submit`:

1) Serializa highlights:
- por cada `[data-highlight-block]`:
  - toma `.highlight-input`
  - filtra vacíos
  - junta con `\n`
  - escribe en `.highlight-textarea`

Esto transforma UI de múltiples inputs en el campo que el backend espera (un textarea por repeat).

2) Resync de fechas:
- por cada `[data-date-field]`:
  - llama `syncDateField(block)`
- asegura que hidden tenga el formato final antes de enviar.

---

## 13) Agregar “módulo extra” completo (botón global)

Bloque:

```js
(function initAddExtraModule(){ ... })();
```

- delega click en todo el document
- dispara si el click viene de `[data-action="add-extra-module"]`

Pasos:

1) encuentra contenedor de módulos:
- `#modules-list` o `[data-modules]`

2) encuentra el bloque fijo “Agregar módulo”:
- `[data-add-module]` (para insertar antes)

3) clona template `#tpl-extra-module`

4) genera `sid = extra-${randomId()}`

5) setea:
- `node.dataset.moduleKey = sid`
- `input[name="extra_section_id"].value = sid`
- modo por defecto: `"subtitle_items"`

6) crea una primera entry dentro:
- clona `#tpl-extra-entry`
- setea `extra_entry_section = sid`
- agrega entry al entriesRoot

7) inserta el nodo en el DOM

8) inicializa:
- `initExtraSection(...)`
- `window.__trufadocs_reorder.sync()` (si existe)

---

## 14) `applyExtraMode(sectionEl)` (fuera del IIFE)

Esta función aplica el **modo por sección** a cada entry.

- Lee select `[data-extra-mode]` dentro de la sección.
- Por cada entry `[data-extra-entry]`:
  - por cada bloque `[data-extra-entry-show]`:
    - decide visible si su lista incluye el modo
    - setea `display`
    - llama `setEnabled(el, visible)`

### 14.1 `setEnabled(containerEl, enabled)`

Habilita/deshabilita inputs dentro de un sub-bloque visible/oculto.

Excepciones:

- nunca deshabilitar:
  - `[data-remove-extra-entry]` (botón de borrar entry)
  - `[data-extra-mode]` (selector de modo)
- botones:
  - solo deshabilita `[data-add-highlight]`, `[data-remove-highlight]`
- fecha “Actualidad”:
  - si es `data-date-end` y `forceCurrent=1`, no re-habilita año/mes.

### 14.2 Listeners para aplicar modo

- `change` delegado: si cambia `[data-extra-mode]`, aplica al section padre.
- `DOMContentLoaded`: aplica `applyExtraMode` a todas las secciones al cargar.

---

## 15) Reorden de módulos core (Experience/Education/Skills/Extras)

Bloque IIFE `initCoreModuleReorder()` al final.

### 15.1 Elementos relevantes

- Contenedor:
  - `#modules-list` o `[data-modules]` o `document.body`
- Inputs hidden:
  - `input[name="core_order"]` (o `#core-order`)
  - `input[name="module_order_map"]` (o `#module-order-map`)

### 15.2 ¿Qué módulos son movibles?

```js
el.classList.contains("module-block")
&& !!el.dataset.moduleKey
&& !el.classList.contains("module-fixed")
&& !el.classList.contains("module-add")
```

- Deben tener `data-module-key`
- Excluye módulos fijos (Datos) y el bloque “Agregar módulo extra”.

### 15.3 Persistencia de orden (dos campos)

1) `core_order`:
- lista simple en orden visual:
  - `experience,education,skills,extra-abc123,...`

2) `module_order_map`:
- mapa con índice:
  - `experience:1,education:2,skills:3,extra-abc123:4`

Esto sirve para:
- reconstruir el orden al recargar
- tener tolerancia a módulos que aparezcan/desaparezcan

### 15.4 `applyOrderFromHiddenInput()`

Si `core_order` trae orden solicitado:

- crea un array `requested`
- arma `ordered`:
  - primero los que aparecen en `requested`
  - luego los que faltan (en orden actual)
- re-inserta en el DOM antes del bloque `[data-add-module]`

### 15.5 Botones de mover y estados

`updateMoveButtonsState()`:

- deshabilita “up” en el primero
- deshabilita “down” en el último

### 15.6 Animación + seguimiento con scroll

- `snapshotBlockPositions()` guarda `getBoundingClientRect()` antes del movimiento
- `animateReorder(before)` aplica FLIP:
  - setea `transform: translateY(deltaY)`
  - luego transiciona a `transform: ""`
- `followMovedBlock(block)` intenta mantener el módulo movido visible:
  - calcula target en el viewport (24% desde arriba)
  - hace `smoothScrollWindowTo`

Respeta `prefers-reduced-motion`.

### 15.7 Movimiento real

`moveBlock(block, dir)`:

- captura posiciones antes
- calcula índice actual
- hace insertBefore/append según dir
- sincroniza:
  - `syncOrderToHiddenInput()`
  - `syncInternalModuleOrder()`
  - `updateMoveButtonsState()`
- follow scroll + animate

### 15.8 Delegación de click dentro del container

Busca el botón con `[data-move]` (up/down) y mueve su `.module-block`.

### 15.9 API global para sync externo

Expone:

```js
window.__trufadocs_reorder = { sync: () => { ... } }
```

Para que otros flujos (agregar/eliminar módulos) recalculen:

- `core_order`
- `module_order_map`
- estado de botones

---

## 16) Contratos `data-*` usados (resumen)

### Tema
- `[data-theme-toggle]`

### Repeats base
- `[data-add="experience|education|skills"]`
- `#experience-list`, `#education-list`, `#skills-list`
- `.repeat`
- `[data-remove]`

### Highlights
- `[data-highlight-block]`
- `.highlight-list`
- `.highlight-input`
- `.highlight-textarea`
- `[data-add-highlight]`
- `[data-remove-highlight]`

### Fechas
- `[data-date-field]`
- `[data-date-end]`
- `[data-year-select]`
- `[data-month-select]`
- `[data-role-current]`
- `block.dataset.forceCurrent`, `prevYear`, `prevMonth`, `dateInit`

### Extras
- `[data-extra-section]`
- `input[name="extra_section_id"]`
- `[data-extra-title]`
- `[data-extra-mode]`
- `[data-extra-entries]`
- `[data-extra-entry]`
- `input[name="extra_entry_section"]`
- `[data-extra-entry-mode]`
- `[data-extra-entry-show]`
- `[data-action="add-extra-entry"]`
- `[data-action="remove-extra-section"]`
- `[data-action="add-extra-module"]`
- templates:
  - `#tpl-extra-module`
  - `#tpl-extra-entry`

### Reorder de módulos
- `.module-block[data-module-key]`
- `.module-fixed`, `.module-add`
- `[data-move="up|down"]`
- `[data-add-module]`
- inputs: `core_order`, `module_order_map`

---

## 17) Flujo típico “happy path” (alto nivel)

1) Carga página:
- tema inicial
- highlights mínimos
- fechas inicializadas (hidden <-> selects)
- extras inicializados (section_id, moduleKey, entradas, modo)
- reorder aplica `core_order` si existe

2) Usuario agrega experiencia:
- se usa template o clon fallback
- se rehidratan highlights y fechas

3) Usuario marca “Actualidad”:
- guarda prev year/month
- deshabilita selects, hidden="Actualidad"

4) Usuario agrega módulo extra:
- crea section_id nuevo
- inserta antes del bloque “Agregar”
- inicializa extra section/entry
- resync reorder

5) Usuario mueve módulos:
- update inputs hidden
- animación y scroll follow

6) Submit:
- highlights -> textarea
- fechas -> hidden final

---

## 18) Puntos de atención / riesgos comunes

- **Duplicación de handlers**: se evita en algunos lugares con `dataset.bound` y `dataset.dateInit`, pero si se clonan nodos con listeners ya puestos, podría haber duplicados. Este script usa mayormente delegación o inicialización idempotente para mitigarlo.
- **randomId collisions**: improbable, pero no imposible. Si esto fuera crítico, migrar a `crypto.getRandomValues`.
- **applyExtraMode fuera del IIFE**: depende de que exista globalmente al llamar desde el IIFE principal. En este archivo, está definido después; en JS eso funciona porque el IIFE principal termina antes de que `applyExtraMode` sea referenciado? Ojo: en tu script, `initExtraSection()` llama `applyExtraMode(section)` dentro del IIFE principal **antes** de que se declare `applyExtraMode` (que está fuera, abajo).  
  - En JS, las **function declarations** se hoistean, pero aquí `applyExtraMode` es una `function applyExtraMode(...) {}` (declaración), así que sí está hoisteada globalmente y es accesible.
- **inputs hidden de fecha**: el backend asume formatos específicos; este script intenta normalizar a `YYYY` / `YYYY-MM` / `Actualidad`.

---

Si quieres, el siguiente documento puede ser un “mapa HTML” (esqueleto de templates y `data-*`) para que no tengas que adivinar qué atributos requiere cada bloque.
