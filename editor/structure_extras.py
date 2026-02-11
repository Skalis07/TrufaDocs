import re
from typing import Dict, List, Tuple, Any

from .structure_constants import DATE_RANGE_RE, _CITY_CONNECTORS, _CITY_PREFIXES, _NON_CITY_HINTS
from .structure_helpers import (
    _clean_bullet,
    _is_bullet,
    _is_heading,
    _looks_like_location,
    _looks_like_org,
    _looks_like_tech,
    _normalize_ascii,
    _normalize_date_token,
    _parse_location,
    _split_role_company,
)
from .structure_types import ExtraSectionRaw



def _split_escaped_newlines(text: str) -> List[str]:
    """Separa texto en líneas, soportando tanto saltos reales como literales \\n.

    Algunos extractores (o transformaciones intermedias) pueden devolver la secuencia
    "\\n" como dos caracteres dentro del texto, incluso junto a saltos reales.
    Para el import del CV, tratamos esas secuencias como separadores de línea.
    """
    if text is None:
        return []
    s = str(text)
    # Normalizar literales comunes
    s = s.replace("\\r\\n", "\n")
    s = s.replace("\\n", "\n")
    # Normalizar saltos reales
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    parts: List[str] = []
    for line in s.split("\n"):
        t = (line or "").strip()
        if t:
            parts.append(t)
    return parts

def _empty_extra_entry() -> Dict:
    return {
        "subtitle": "",
        "title": "",
        "where": "",
        "tech": "",
        "start": "",
        "end": "",
        "city": "",
        "country": "",
        "items": [],
    }


def _has_extra_entry_content(entry: Dict) -> bool:
    if not entry:
        return False
    fields = [
        entry.get("subtitle"),
        entry.get("title"),
        entry.get("where"),
        entry.get("tech"),
        entry.get("start"),
        entry.get("end"),
        entry.get("city"),
        entry.get("country"),
    ]
    if any(field and str(field).strip() for field in fields):
        return True
    return any(item for item in (entry.get("items") or []) if str(item).strip())


def _infer_extra_mode(entries: List[Dict]) -> str:
    # Solo dos modos en Extras: detailed o subtitle_items
    for entry in entries:
        if any(entry.get(key) for key in ["title", "where", "start", "end", "city", "country"]):
            return "detailed"
    return "subtitle_items"



def _infer_entry_mode(entry: Dict) -> str:
    # Mantener compat: no se mezcla por entrada.
    if any(entry.get(key) for key in ["title", "where", "start", "end", "city", "country"]):
        return "detailed"
    return "subtitle_items"




def _looks_like_inline_list(line: str) -> bool:
    """Detecta líneas tipo listado 'A, B, C' (sin bullets).

    La meta es capturar listados de items (incluyendo numéricos) y evitar que se confundan con
    'Ciudad, País'. Para eso:
    - Requiere al menos 3 partes (o 2 comas).
    - Evita rangos de fecha.
    - Evita casos claramente de ubicación única (solo 2 partes y la 2da parece país).
    """
    s = (line or "").strip()
    if not s:
        return False
    if DATE_RANGE_RE.search(s):
        return False

    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) < 3 and s.count(",") < 2:
        return False

    # Heurística anti-ubicación: si son EXACTAMENTE 2 partes, no es listado (p.ej. 'Miami, Chile')
    if len(parts) == 2:
        return False

    return True

def _split_items_text(raw_text: str) -> List[str]:
    """Parsea items por *línea* (no por coma).

    - Mantiene comas dentro del item (p.ej. "1, 2, 3" es un solo item).
    - Limpia bullets/guiones al inicio de cada línea si existen.
    """
    items: List[str] = []
    if raw_text is None:
        return items

    # Normaliza \n literal (dos caracteres) a salto real.
    raw = str(raw_text).replace("\\n", "\n")
    for raw_line in raw.splitlines():
        s = (raw_line or "").strip()
        if not s:
            continue
        items.append(_clean_bullet(s))

    # Si la extracción del PDF cortó una lista "inline" en múltiples líneas (p.ej. 1\n2\n3),
    # reconstruimos en una sola línea con comas para que el import coincida con el PDF/export.
    clean = [it.strip() for it in items if it and it.strip()]
    if len(clean) >= 2 and all(re.fullmatch(r"\d", it.strip()) for it in clean):
        return [", ".join(clean)]

    return [item for item in items if item]

def _extract_line_payload(raw_line: Any) -> Tuple[str, Dict[str, Any]]:
    if isinstance(raw_line, dict):
        text = str(raw_line.get("text", "") or "").strip()
        return (
            text,
            {
                "indent": float(raw_line.get("indent") or 0.0),
                "is_bullet": bool(raw_line.get("is_bullet")),
                "is_bold": bool(raw_line.get("is_bold")),
                "size_ratio": float(raw_line.get("size_ratio") or 0.0),
                "ends_with_colon": bool(raw_line.get("ends_with_colon")),
            },
        )
    return (
        str(raw_line or "").strip(),
        {
            "indent": 0.0,
            "is_bullet": False,
            "is_bold": False,
            "size_ratio": 0.0,
            "ends_with_colon": False,
        },
    )


def _split_extra_blocks(lines: List[Any]) -> List[List[Any]]:
    blocks: List[List[Any]] = []
    current: List[Any] = []
    for raw_line in lines:
        text, _meta = _extract_line_payload(raw_line)
        if not text:
            if current:
                blocks.append(current)
                current = []
            continue
        if _is_heading(text) and current:
            blocks.append(current)
            current = [raw_line]
            continue
        current.append(raw_line)
    if current:
        blocks.append(current)
    return blocks or [[]]


def _infer_block_indents(block: List[Any]) -> Tuple[float, float | None]:
    indents: List[float] = []
    for raw_line in block:
        text, meta = _extract_line_payload(raw_line)
        if text:
            indents.append(float(meta.get("indent", 0.0) or 0.0))
    if not indents:
        return 0.0, None
    base_indent = min(indents)
    max_indent = max(indents)
    if max_indent - base_indent < 120:
        return base_indent, None
    threshold = base_indent + (max_indent - base_indent) * 0.6
    return base_indent, threshold


def _split_location_tail_loose(text: str) -> Tuple[str, str]:
    candidate = (text or "").strip()
    if not candidate:
        return "", ""
    for sep in (" | ", " / ", " - ", " – ", " — ", " · "):
        if sep in candidate:
            left, right = candidate.rsplit(sep, 1)
            return left.strip(), right.strip()
    words = [word for word in candidate.split() if word]
    if not words:
        return candidate, ""
    city_words = [words.pop()]
    while words and _normalize_ascii(words[-1]) in (_CITY_CONNECTORS | _CITY_PREFIXES):
        city_words.insert(0, words.pop())
    return " ".join(words).strip(), " ".join(city_words).strip()


def _looks_like_location_prefix(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    if any(char.isdigit() for char in candidate):
        return False
    if DATE_RANGE_RE.search(candidate):
        return False
    if len(candidate) > 45:
        return False
    return True


def _apply_location_prefix(entry: Dict, prefix: str) -> str:
    prefix = (prefix or "").strip()
    if not prefix:
        return ""
    city = (entry.get("city") or "").strip()
    if not city:
        return prefix
    if _normalize_ascii(city).startswith(_normalize_ascii(prefix)):
        return ""
    entry["city"] = f"{prefix} {city}".strip()
    return ""


def _split_trailing_location(line: str) -> Tuple[str, str, str]:
    candidate = (line or "").strip()
    if not candidate or "," not in candidate:
        return candidate, "", ""

    last_comma = candidate.rfind(",")
    left_part = candidate[:last_comma].strip()
    country_part = candidate[last_comma + 1 :].strip()
    if not left_part or not country_part:
        return candidate, "", ""
    if any(char.isdigit() for char in country_part):
        return candidate, "", ""

    left_words = left_part.split()
    if not left_words:
        return candidate, "", ""

    start_idx = len(left_words)
    significant = 0

    for idx in range(len(left_words) - 1, -1, -1):
        word = left_words[idx]
        lowered = _normalize_ascii(word)
        if lowered in _NON_CITY_HINTS:
            break
        if lowered in _CITY_CONNECTORS:
            start_idx = idx
            continue
        prev_lowered = _normalize_ascii(left_words[idx - 1]) if idx - 1 >= 0 else ""
        if prev_lowered in _NON_CITY_HINTS and lowered not in _CITY_PREFIXES:
            break
        if word[:1].isupper() and len(word) >= 2:
            significant += 1
            start_idx = idx
            if significant >= 3:
                break
            continue
        break

    city_words = left_words[start_idx:]
    if not city_words:
        leftover, city = _split_location_tail_loose(left_part)
        if city:
            return leftover, city, country_part
        return candidate, "", ""

    leftover_words = left_words[:start_idx]

    while city_words and _normalize_ascii(city_words[0]) in _CITY_CONNECTORS:
        leftover_words.append(city_words.pop(0))

    country_words = [word for word in country_part.split() if word]
    if country_words and len(city_words) >= len(country_words):
        city_head = [_normalize_ascii(word) for word in city_words[: len(country_words)]]
        country_head = [_normalize_ascii(word) for word in country_words]
        if city_head == country_head:
            for _ in country_words:
                leftover_words.append(city_words.pop(0))

    if not city_words:
        leftover, city = _split_location_tail_loose(left_part)
        if city:
            return leftover, city, country_part
        return candidate, "", ""

    city = " ".join(city_words).strip()
    city, country = _parse_location(f"{city}, {country_part}")
    if not city:
        leftover, fallback_city = _split_location_tail_loose(left_part)
        if fallback_city:
            return leftover, fallback_city, country_part
        return candidate, "", ""

    leftover = " ".join(leftover_words).strip()
    return leftover, city, country


def _is_location_prefix_only(text: str) -> bool:
    words = [_normalize_ascii(word) for word in (text or "").split() if word]
    if not words:
        return True
    for word in words:
        if word not in _CITY_CONNECTORS and word not in _CITY_PREFIXES:
            return False
    return True


def _is_location_stub(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    if stripped.isdigit():
        return True
    if len(stripped) <= 4 and stripped.isalpha() and stripped.isupper():
        return True
    return False


def _split_location_prefix_from_text(text: str) -> Tuple[str, str]:
    words = (text or "").split()
    if len(words) < 2:
        return text, ""

    last = words[-1]
    prev = words[-2]
    last_norm = _normalize_ascii(last)
    prev_norm = _normalize_ascii(prev)

    def is_title_word(word: str) -> bool:
        return word[:1].isupper() and not word.isdigit()

    if last_norm in _CITY_CONNECTORS and is_title_word(prev):
        base = " ".join(words[:-2]).strip()
        suffix = f"{prev} {last}".strip()
        return base, suffix

    if prev_norm in _CITY_PREFIXES and is_title_word(last):
        base = " ".join(words[:-2]).strip()
        suffix = f"{prev} {last}".strip()
        return base, suffix

    return text, ""


def _merge_location_prefix(entry: Dict, source_key: str, line_stub: str) -> bool:
    if not entry.get("city"):
        return False
    if not _is_location_stub(line_stub):
        return False
    text = entry.get(source_key) or ""
    base, prefix = _split_location_prefix_from_text(text)
    if not prefix:
        return False
    city_norm = _normalize_ascii(entry.get("city") or "")
    prefix_norm = _normalize_ascii(prefix)
    if city_norm.startswith(prefix_norm):
        return False
    entry[source_key] = base
    entry["city"] = f"{prefix} {entry['city']}".strip()
    return True


def _split_title_location_suffix(title: str) -> Tuple[str, str]:
    words = [word for word in (title or "").split() if word]
    if len(words) < 3:
        return title, ""

    def is_title_word(word: str) -> bool:
        return word[:1].isupper() and not word.isdigit()

    max_len = min(4, len(words))
    for length in range(max_len, 1, -1):
        segment = words[-length:]
        if not all(is_title_word(word) for word in segment):
            continue
        normalized = [_normalize_ascii(word) for word in segment]
        if not any(word in _CITY_PREFIXES for word in normalized):
            continue
        base = " ".join(words[:-length]).strip()
        if not base:
            continue
        if normalized[-1] in _CITY_PREFIXES and any(
            word in _CITY_CONNECTORS for word in normalized[:-1]
        ):
            if normalized[0] not in _CITY_CONNECTORS and normalized[0] not in _CITY_PREFIXES:
                continue
            return base, " ".join(segment).strip()
        if normalized[0] in _CITY_PREFIXES and length <= 3:
            return base, " ".join(segment).strip()
    return title, ""




def _entry_has_location(entry: Dict) -> bool:
    return any(entry.get(key) for key in ("where", "city", "country"))


def _entry_has_core(entry: Dict) -> bool:
    return any(entry.get(key) for key in ("title", "start", "end"))


def _is_sparse_extra_entry(entry: Dict) -> bool:
    if not entry:
        return False
    if entry.get("subtitle"):
        return False
    if any(item for item in (entry.get("items") or []) if str(item).strip()):
        return False
    return True


def _is_subtitle_only_extra_entry(entry: Dict) -> bool:
    if not entry:
        return False
    subtitle = (entry.get("subtitle") or "").strip()
    if not subtitle:
        return False
    if any((entry.get(key) or "").strip() for key in ("title", "where", "tech", "start", "end", "city", "country")):
        return False
    if any(str(item).strip() for item in (entry.get("items") or [])):
        return False
    return True


def _is_detailed_extra_entry(entry: Dict) -> bool:
    if not entry:
        return False
    return any((entry.get(key) or "").strip() for key in ("title", "where", "tech", "start", "end", "city", "country"))


def _merge_extra_entries(core_entry: Dict, loc_entry: Dict) -> Dict:
    merged = _empty_extra_entry()
    merged["subtitle"] = (core_entry.get("subtitle") or loc_entry.get("subtitle") or "").strip()
    merged["title"] = (core_entry.get("title") or loc_entry.get("title") or "").strip()
    merged["where"] = (loc_entry.get("where") or core_entry.get("where") or "").strip()
    merged["tech"] = (core_entry.get("tech") or loc_entry.get("tech") or "").strip()
    merged["start"] = core_entry.get("start") or loc_entry.get("start") or ""
    merged["end"] = core_entry.get("end") or loc_entry.get("end") or ""
    merged["city"] = (loc_entry.get("city") or core_entry.get("city") or "").strip()
    merged["country"] = (loc_entry.get("country") or core_entry.get("country") or "").strip()
    items: List[str] = []
    for entry in (core_entry, loc_entry):
        for item in entry.get("items") or []:
            cleaned = str(item).strip()
            if cleaned:
                items.append(cleaned)
    merged["items"] = items
    return merged


def _should_merge_extra_entries(first: Dict, second: Dict) -> bool:
    if not (_is_sparse_extra_entry(first) and _is_sparse_extra_entry(second)):
        return False
    first_loc = _entry_has_location(first)
    second_loc = _entry_has_location(second)
    first_core = _entry_has_core(first)
    second_core = _entry_has_core(second)
    if first_loc and not first_core and second_core and not second_loc:
        return True
    if second_loc and not second_core and first_core and not first_loc:
        return True
    return False


def _merge_extra_entry_fragments(entries: List[Dict]) -> List[Dict]:
    if len(entries) < 2:
        return entries
    merged: List[Dict] = []
    idx = 0
    while idx < len(entries):
        current = entries[idx]
        if _is_detailed_extra_entry(current):
            merged_entry = dict(current)
            merged_items = [str(item).strip() for item in (merged_entry.get("items") or []) if str(item).strip()]
            merged_entry["items"] = merged_items
            cursor = idx + 1
            consumed = False
            while cursor < len(entries) and _is_subtitle_only_extra_entry(entries[cursor]):
                subtitle_value = (entries[cursor].get("subtitle") or "").strip()
                if subtitle_value:
                    city, country = _parse_location(subtitle_value)
                    if city and not (merged_entry.get("city") or "").strip():
                        merged_entry["city"] = city
                        merged_entry["country"] = country
                    elif not (merged_entry.get("tech") or "").strip() and _looks_like_tech(subtitle_value):
                        merged_entry["tech"] = subtitle_value
                    else:
                        merged_entry["items"].append(subtitle_value)
                consumed = True
                cursor += 1
            if consumed:
                merged.append(merged_entry)
                idx = cursor
                continue

        nxt = entries[idx + 1] if idx + 1 < len(entries) else None
        if nxt and _is_detailed_extra_entry(current) and _is_subtitle_only_extra_entry(nxt):
            merged_entry = dict(current)
            merged_items = [str(item).strip() for item in (merged_entry.get("items") or []) if str(item).strip()]
            subtitle_item = (nxt.get("subtitle") or "").strip()
            if subtitle_item:
                merged_items.append(subtitle_item)
            merged_entry["items"] = merged_items
            merged.append(merged_entry)
            idx += 2
            continue
        if nxt and _should_merge_extra_entries(current, nxt):
            if _entry_has_core(current):
                merged_entry = _merge_extra_entries(current, nxt)
            else:
                merged_entry = _merge_extra_entries(nxt, current)
            merged.append(merged_entry)
            idx += 2
            continue
        merged.append(current)
        idx += 1
    return merged

def _should_start_new_extra_entry(
    entry: Dict,
    items: List[str],
    line: str,
    meta: Dict[str, Any],
    right_threshold: float | None,
) -> bool:
    if not (entry and (_has_extra_entry_content(entry) or items)):
        return False
    if meta.get("is_bullet") or _is_bullet(line):
        return False
    if right_threshold is not None and meta.get("indent", 0.0) >= right_threshold:
        if DATE_RANGE_RE.search(line):
            return False
    if meta.get("is_bold") and _has_extra_entry_content(entry):
        if entry.get("where") or entry.get("start") or entry.get("end") or entry.get("items") or entry.get("subtitle"):
            return True
    if DATE_RANGE_RE.search(line):
        if entry.get("start") or entry.get("end"):
            return True
        return False

    # Entrada detallada en curso sin "tech": una línea libre no-boldeada y
    # no-organización debe tratarse como posible detalle, no como nueva entrada.
    if (
        (entry.get("where") or entry.get("title"))
        and not (entry.get("tech") or "").strip()
        and not meta.get("is_bold")
        and not _is_heading(line)
        and not _looks_like_org(line)
    ):
        return False

    # Si la entrada ya está en modo detallado y esta línea parece detalle/tecnologías,
    # no debe partir una entrada nueva aunque contenga comas.
    if (entry.get("where") or entry.get("title") or entry.get("start") or entry.get("end")) and not entry.get("tech"):
        normalized = _normalize_ascii(line)
        if normalized.startswith("tecnologias:") or normalized.startswith("tecnologias "):
            return False
        if _looks_like_tech(line):
            return False

    leftover, city, _country = _split_trailing_location(line)
    if city:
        if entry.get("city"):
            if (
                (entry.get("where") or entry.get("title"))
                and not (entry.get("tech") or "").strip()
                and not meta.get("is_bold")
                and not _looks_like_org(line)
            ):
                return False
            return True
        if entry.get("title") and entry.get("where") and not _is_location_prefix_only(leftover):
            return True
        return False

    if not _looks_like_location(line):
        title, where = _split_role_company(line)
        if where and (entry.get("title") or entry.get("where") or entry.get("start") or items):
            return True
        if (
            meta.get("is_bold")
            and (entry.get("start") or entry.get("end") or entry.get("city"))
            and _looks_like_org(line)
        ):
            return True

    return False


def _looks_like_detailed_bullet(entry: Dict, line: str) -> bool:
    text = _clean_bullet(line).strip()
    if not text:
        return False

    if DATE_RANGE_RE.search(text):
        return True

    _title, where = _split_role_company(text)
    if where:
        return True

    has_detail_context = any(
        (entry.get(key) or "").strip()
        for key in ("title", "where", "start", "end", "city", "country", "tech")
    )
    if not has_detail_context:
        return False

    if _looks_like_location(text):
        return True
    if _looks_like_tech(text):
        return True

    low = _normalize_ascii(text)
    if low.startswith("tecnologias:") or low.startswith("tecnologias "):
        return True

    return False


def _parse_extra_entries(lines: List[Any]) -> List[Dict]:
    blocks = _split_extra_blocks(lines)
    entries: List[Dict] = []
    for block in blocks:
        _base_indent, right_threshold = _infer_block_indents(block)
        entry = _empty_extra_entry()
        items: List[str] = []
        pending_location_prefix = ""
        for raw_line in block:
            prefix_applied = False
            line, meta = _extract_line_payload(raw_line)
            if not line:
                continue
            if _should_start_new_extra_entry(entry, items, line, meta, right_threshold):
                entry["items"] = [item for item in items if item]
                entries.append(entry)
                entry = _empty_extra_entry()
                items = []
                pending_location_prefix = ""
            if meta.get("is_bullet") or _is_bullet(line):
                bullet_text = _clean_bullet(line)

                # En imports desde PDF hay entradas detalladas detectadas como bullet.
                # Si la linea parece detalle, se parsea como linea normal (no como subtitulo).
                if _looks_like_detailed_bullet(entry, bullet_text):
                    bullet_meta = dict(meta)
                    bullet_meta["is_bullet"] = False
                    if _should_start_new_extra_entry(entry, items, bullet_text, bullet_meta, right_threshold):
                        entry["items"] = [item for item in items if item]
                        entries.append(entry)
                        entry = _empty_extra_entry()
                        items = []
                        pending_location_prefix = ""
                    line = bullet_text
                    meta = bullet_meta
                else:
                    # En extras modo subtitulo(+items): cada bullet inicia una nueva entrada.
                    if entry and (_has_extra_entry_content(entry) or items):
                        entry["items"] = [item for item in items if item]
                        entries.append(entry)
                        entry = _empty_extra_entry()
                        items = []
                        pending_location_prefix = ""

                    entry["subtitle"] = bullet_text
                    continue
            
            # Si viene una línea tipo 'A, B, C' sin bullet:
            # - Si no hay subtítulo aún, lo tratamos como subtítulo (caso 'solo item' => punto).
            # - Si ya hay subtítulo, lo tratamos como items (separados por coma).
            if _looks_like_inline_list(line) and not any(entry.get(k) for k in ["title", "where", "tech", "start", "end", "city", "country"]):
                if not (entry.get("subtitle") or "").strip():
                    entry["subtitle"] = _clean_bullet(line)
                else:
                    items.extend(_split_items_text(line))
                continue
            
            # Modo subtítulo(+items): si ya tenemos subtítulo y NO hay campos de detalle,
            # toda línea no-bullet se considera item (no se parsea como ubicación).
            if (entry.get("subtitle") or "").strip() and not any(entry.get(k) for k in ["title", "where", "tech", "start", "end", "city", "country"]):
                if not DATE_RANGE_RE.search(line) and not _is_heading(line):
                    for _part in _split_escaped_newlines(_clean_bullet(line)):
                        items.append(_part)
                    continue

            # Modo detallado: si ya tenemos Empresa/Rol y aún no hay 'tech',
            # interpretamos una línea como Tecnologías/Detalle ANTES de intentar parsear ubicación.
            #
            # Importante: algunos PDFs hacen que una línea tipo "A, B, C" parezca ubicación (por comas).
            # Para evitar que esa línea rompa la entrada (y cree una entrada vacía extra),
            # priorizamos _looks_like_tech() y aceptamos la línea como 'tech' aunque parezca ubicación.
            # Si viene explícitamente como "Tecnologías: ..." (como en Experiencia),
            # extraemos el valor después de ":".
            if "|" not in line and (entry.get("where") or entry.get("title")) and not entry.get("tech"):
                low = line.strip().lower()
                if (
                    low.startswith("tecnologías:")
                    or low.startswith("tecnologias:")
                    or low.startswith("tecnologías ")
                    or low.startswith("tecnologias ")
                ):
                    entry["tech"] = line.strip()
                    continue

            if "|" not in line and (entry.get("where") or entry.get("title")) and not entry.get("tech"):
                if not DATE_RANGE_RE.search(line) and not _is_heading(line):
                    if _looks_like_tech(line) or (_looks_like_inline_list(line) and not _looks_like_location(line)):
                        entry["tech"] = line.strip()
                        continue


            line_had_location = False
            line_had_date = False
            if "|" in line:
                segments = [segment.strip() for segment in line.split("|") if segment.strip()]
                left_segment = ""
                right_segment = ""
                if segments:
                    if len(segments) == 1:
                        left_segment = segments[0]
                    else:
                        left_segment = segments[0]
                        right_segment = " ".join(segments[1:]).strip()

                if right_segment:
                    if not entry["start"]:
                        match = DATE_RANGE_RE.search(right_segment)
                        if match:
                            entry["start"] = _normalize_date_token(match.group("start"))
                            entry["end"] = _normalize_date_token(match.group("end"))
                            cleaned = right_segment.replace(match.group(0), "").strip(" -–—()")
                            cleaned = re.sub(r"\s*[|·•]\s*", " ", cleaned).strip()
                            right_segment = cleaned
                            line_had_date = True
                    if not entry["city"] and right_segment:
                        leftover, city, country = _split_trailing_location(right_segment)
                        if city:
                            entry["city"] = city
                            entry["country"] = country
                            right_segment = leftover
                            line_had_location = True
                            if pending_location_prefix:
                                before_city = entry.get("city") or ""
                                pending_location_prefix = _apply_location_prefix(entry, pending_location_prefix)
                                if entry.get("city") != before_city:
                                    prefix_applied = True
                        else:
                            city, country = _parse_location(right_segment)
                            if city:
                                entry["city"] = city
                                entry["country"] = country
                                right_segment = ""
                                line_had_location = True
                                if pending_location_prefix:
                                    before_city = entry.get("city") or ""
                                    pending_location_prefix = _apply_location_prefix(entry, pending_location_prefix)
                                    if entry.get("city") != before_city:
                                        prefix_applied = True

                if right_segment and left_segment and not line_had_date and not line_had_location:
                    if _looks_like_location_prefix(right_segment):
                        pending_location_prefix = f"{pending_location_prefix} {right_segment}".strip()
                        right_segment = ""

                line = left_segment or right_segment

            date_match = None
            if not line_had_date:
                date_match = DATE_RANGE_RE.search(line)
            if date_match and not entry["start"]:
                entry["start"] = _normalize_date_token(date_match.group("start"))
                entry["end"] = _normalize_date_token(date_match.group("end"))
                line = line.replace(date_match.group(0), "").strip(" -–—()")
                line = re.sub(r"\s*[|·•]\s*", " ", line).strip()
                line_had_date = True

            if line:
                original_line = line
                split_line, city, country = _split_trailing_location(line)
                # Si ya existe ubicación en la entrada, no truncar líneas tipo detalle
                # por una detección de ubicación en cola (falso positivo con comas).
                if city and entry.get("city"):
                    line = original_line
                else:
                    line = split_line
                if city and not entry["city"]:
                    if not line and entry.get("title") and not entry.get("where"):
                        left_part = original_line.rsplit(",", 1)[0].strip()
                        alt_left, alt_city = _split_location_tail_loose(left_part)
                        if (
                            alt_left
                            and alt_city
                            and not _is_location_prefix_only(alt_left)
                            and not _is_location_stub(alt_left)
                        ):
                            line = alt_left
                            city = alt_city
                    entry["city"] = city
                    entry["country"] = country
                    line_had_location = True
                    if pending_location_prefix:
                        before_city = entry.get("city") or ""
                        pending_location_prefix = _apply_location_prefix(entry, pending_location_prefix)
                        if entry.get("city") != before_city:
                            prefix_applied = True
                    prefix_moved = False
                    if entry.get("title"):
                        prefix_moved = _merge_location_prefix(entry, "title", line)
                    if (
                        prefix_moved
                        and entry.get("title")
                        and not entry.get("where")
                        and _is_location_stub(line)
                    ):
                        entry["where"] = entry["title"]
                        entry["title"] = ""
                    if (
                        line
                        and entry.get("title")
                        and not entry.get("where")
                        and not _is_location_stub(line)
                    ):
                        entry["where"] = line.strip()
                        line = ""
                        if entry.get("city") and entry.get("country"):
                            base, prefix = _split_title_location_suffix(entry.get("title") or "")
                            if prefix and base:
                                entry["title"] = base
                                entry["city"] = f"{prefix} {entry['city']}".strip()

            if line and line_had_location and entry.get("title") and not entry.get("where") and prefix_applied:
                entry["where"] = entry["title"]
                entry["title"] = line.strip()
                continue

            if not line:
                continue

            # Tecnologías/Detalle (modo detallado): suele ser una línea tipo lista sin prefijo
            # (ej: "Python, Pandas, scikit-learn"). La capturamos ANTES de tratarla como título/where.
            if (
                line
                and not (entry.get("tech") or "").strip()
                and any((entry.get(k) or "").strip() for k in ["title", "where", "start", "end", "city", "country"])
                and _looks_like_tech(line)
                and not DATE_RANGE_RE.search(line)
            ):
                entry["tech"] = line.strip()
                continue

            if meta.get("is_bold") and not entry["where"] and not line_had_date:
                if line_had_location or _looks_like_location(line) or "," in line:
                    entry["where"] = line.strip()
                    continue
                if not entry["title"]:
                    entry["title"] = line.strip()
                    continue
            if _looks_like_location(line) and not entry["city"]:
                city, country = _parse_location(line)
                if city:
                    entry["city"] = city
                    entry["country"] = country
                    if pending_location_prefix:
                        before_city = entry.get("city") or ""
                        pending_location_prefix = _apply_location_prefix(entry, pending_location_prefix)
                        if entry.get("city") != before_city:
                            prefix_applied = True
                    continue
            # Fallback de detalle libre (modo detallado):
            # si ya existe "Empresa/Proyecto" y "Rol/Curso" y aún no hay detalle,
            # priorizamos guardar esta línea en 'tech' antes de convertirla en hito/item.
            if (
                line
                and not (entry.get("tech") or "").strip()
                and (entry.get("title") or "").strip()
                and (entry.get("where") or "").strip()
                and not line_had_location
                and not _is_heading(line)
            ):
                entry["tech"] = line.strip()
                continue
            if ":" in line and not entry["subtitle"]:
                left, right = line.split(":", 1)
                if right.strip():
                    entry["subtitle"] = left.strip()
                    items.extend(_split_items_text(right))
                    continue
            if not entry["title"] and not entry["where"]:
                title, where = _split_role_company(line)
                if where:
                    entry["title"] = title
                    entry["where"] = where
                    continue
                if line_had_location:
                    entry["where"] = title or line.strip()
                else:
                    entry["title"] = title or line.strip()
                continue
            if entry["title"] and not entry["where"] and not _is_heading(line):
                entry["where"] = line.strip()
                continue
            if entry["where"] and not entry["title"] and (line_had_date or not _is_heading(line)):
                entry["title"] = line.strip()
                continue
            if not entry["subtitle"] and _is_heading(line):
                entry["subtitle"] = line.strip()
                continue
            for _part in _split_escaped_newlines(_clean_bullet(line)):
                items.append(_part)
        entry["items"] = [item for item in items if item]
        entries.append(entry)
    entries = _merge_extra_entry_fragments(entries)
    return entries or [_empty_extra_entry()]


def _parse_extras(extras: List[ExtraSectionRaw]) -> List[Dict]:
    parsed = []
    for idx, extra in enumerate(extras):
        title = extra["title"].strip()
        lines = extra["lines"]
        entries = _parse_extra_entries(lines)
        # Modo por entrada (si el parser lo infiere al cargar CVs)
        for entry in entries:
            if not entry.get('mode'):
                entry['mode'] = _infer_entry_mode(entry)
            # Compat: entradas antiguas 'items' / items-only -> Punto/Listado (subtitles)
            if entry.get('mode') == 'subtitles' and not (entry.get('subtitle') or '').strip():
                items_inline = ', '.join([str(x).strip() for x in (entry.get('items') or []) if str(x).strip()])
                if items_inline:
                    entry['subtitle'] = items_inline
                    entry['items'] = []

        entries = [entry for entry in entries if _has_extra_entry_content(entry)] or entries
        if not title and not any(_has_extra_entry_content(entry) for entry in entries):
            continue
        mode = _infer_extra_mode(entries)
        parsed.append(
            {
                "section_id": f"extra-{idx}",
                "title": title,
                "mode": mode,
                "entries": entries,
            }
        )
    return parsed
