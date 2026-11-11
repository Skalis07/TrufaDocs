from __future__ import annotations

import re
from dataclasses import replace

from .constants import EMAIL_RE, KNOWN_SECTION_TITLES, PHONE_RE, URL_RE
from .extract import Line, enrich_features


def normalize_section_title(title: str) -> str:
    """Normaliza un titulo de seccion para comparaciones estables."""
    normalized = " ".join(title.split()).strip()
    normalized = re.sub(r"[:\s]+$", "", normalized)
    return normalized.upper()


def _looks_like_textual_title(line: Line, normalized_text: str) -> bool:
    """Evalua si una linea parece titulo por su forma textual."""
    text = line.text.strip()
    if normalized_text in KNOWN_SECTION_TITLES:
        return True
    if line.uppercase_ratio < 0.8:
        return False
    if len(text) > 40 or "," in text:
        return False
    if any(char.isdigit() for char in text):
        return False
    if " - " in text or " – " in text or " — " in text:
        return False
    if ":" in text and not text.rstrip().endswith(":"):
        return False

    allowed_chars = {" ", "&", "/", "+", "-"}
    if not normalized_text:
        return False
    if not any(char.isalpha() for char in normalized_text):
        return False
    if not all(char.isalpha() or char in allowed_chars for char in normalized_text):
        return False
    return True


def _looks_like_visual_title(line: Line) -> bool:
    """Evalua si una linea parece titulo por rasgos visuales."""
    text = line.text.strip()
    if not text:
        return False
    if line.is_bullet:
        return False
    if line.has_email or line.has_phone or line.has_url:
        return False
    if line.is_date_range or line.is_open_date_range:
        return False
    if len(text) > 60:
        return False
    if "," in text:
        return False
    if any(char.isdigit() for char in text):
        return False
    if " - " in text or " – " in text or " — " in text:
        return False
    if line.indent > 8:
        return False

    if line.size_ratio >= 1.18:
        return True
    if line.is_bold and line.size_ratio >= 1.08:
        if line.uppercase_ratio >= 0.25 or line.ends_with_colon:
            return True
    return False


def is_section_title(line: Line, use_text: bool = True, use_visual: bool = True) -> bool:
    """Determina si una linea debe tratarse como titulo de seccion."""
    text = line.text.strip()
    normalized_text = normalize_section_title(text)
    if line.region and normalized_text not in KNOWN_SECTION_TITLES and line.size_ratio < 1.18 and not line.has_rule_below:
        return False
    if not text:
        return False
    if line.is_bullet:
        return False
    if line.has_email or line.has_phone or line.has_url:
        return False
    if line.is_date_range or line.is_open_date_range:
        return False
    # Evita falsos positivos en lineas de contenido tipo "ROL | CIUDAD".
    # Los titulos reales casi nunca usan pipe, mientras que las filas de
    # experiencia/extras si lo usan frecuentemente como separador.
    if "|" in text and normalized_text not in KNOWN_SECTION_TITLES:
        return False
    if line.has_rule_below:
        return True
    if use_visual and _looks_like_visual_title(line):
        return True
    if not use_text:
        return False
    return _looks_like_textual_title(line, normalized_text)


def parse_header(lines: list[Line]) -> dict:
    """Extrae nombre, contactos y ubicacion desde lineas de cabecera."""
    header = {
        "name": None,
        "location": None,
        "email": None,
        "phone": None,
        "links": [],
        "raw_lines": [],
    }

    def _split_header_segments(text: str) -> list[str]:
        """Divide una linea de cabecera en segmentos por separadores visuales."""
        segments = [part.strip() for part in text.split("|") if part.strip()]
        return segments or [text]

    for line in lines:
        if line.text.strip():
            header["name"] = line.text.strip()
            break

    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        header["raw_lines"].append(text)

        match_email = EMAIL_RE.search(text)
        if match_email and not header["email"]:
            header["email"] = match_email.group(0)

        match_phone = PHONE_RE.search(text)
        phone_in_url = match_phone and any(
            match.start() <= match_phone.start() < match.end() for match in URL_RE.finditer(text)
        )
        if match_phone and not phone_in_url and not header["phone"]:
            header["phone"] = match_phone.group(0)

        for url in URL_RE.findall(text):
            if url not in header["links"]:
                header["links"].append(url)

    if header["location"] is None:
        for line in lines:
            text = line.text.strip()
            for segment in _split_header_segments(text):
                if "·" in segment and "," in segment:
                    candidate = segment.split("·", 1)[0].strip()
                    if "," in candidate:
                        header["location"] = candidate
                        break
            if header["location"]:
                break

    for line in lines:
        if line.has_url or line.has_email:
            continue
        text = line.text.strip()
        for segment in _split_header_segments(text):
            if "," in segment and len(segment) <= 40:
                header["location"] = segment
                break
        if header["location"]:
            break

    return header


def assemble_sections(lines: list[Line]) -> dict:
    """Agrupa lineas enriquecidas en header y secciones detectadas."""
    enrich_features(lines)
    lines = sorted(lines, key=lambda item: (item.page, item.top, item.x0))
    if any(line.region for line in lines):
        return _assemble_columns(lines)
    return _assemble_stream(lines)


def _assemble_columns(lines: list[Line]) -> dict:
    """Keep independent sidebar/main section state and merge only contact fields."""
    result = _assemble_stream([line for line in lines if line.region == "main"])
    header_lines = result["header_lines"]
    if header_lines:
        largest = max(line.font_size for line in header_lines)
        names = [line for line in header_lines if line.font_size >= largest - 0.1]
        result["header"]["name"] = " ".join(line.text for line in names)
        result["header_lines"] = [line for line in header_lines if line not in names]
        locations = [line.text for line in header_lines if "," in line.text and not (line.has_email or line.has_url)]
        if locations:
            result["header"]["location"] = locations[-1]
    sidebar = _assemble_stream([line for line in lines if line.region == "sidebar"])
    for section in sidebar["sections"]:
        if section["title"] in {"CONTACTAR", "CONTACTO", "CONTACT"}:
            contact_lines: list[Line] = []
            for raw in section["raw"]:
                line = Line(**{key: raw[key] for key in ("text", "page", "x0", "x1", "top", "bottom")})
                previous = contact_lines[-1] if contact_lines else None
                if (
                    previous and line.page == previous.page and line.top - previous.bottom < 5
                    and (EMAIL_RE.search(previous.text) or URL_RE.search(previous.text))
                    and re.fullmatch(r"[\w@./+\-]+", line.text)
                    and not (EMAIL_RE.search(line.text) or URL_RE.search(line.text))
                ):
                    contact_lines[-1] = replace(previous, text=previous.text + line.text, bottom=line.bottom)
                else:
                    contact_lines.append(line)
            contacts = parse_header(contact_lines)
            for key in ("email", "phone", "links"):
                if contacts[key]:
                    result["header"][key] = contacts[key]
        else:
            result["sections"].append(section)
    result["column_layout"] = True
    return result


def _assemble_stream(lines: list[Line]) -> dict:
    """Assemble one reading stream without mixing independently flowing columns."""

    # Mantener detección textual/visual activa en todo el documento.
    # has_rule_below ya actúa como señal fuerte dentro de is_section_title.
    use_text = True
    use_visual = True

    first_section_idx = None
    for index, line in enumerate(lines):
        if is_section_title(line, use_text=use_text, use_visual=False):
            first_section_idx = index
            break
    if first_section_idx is None:
        for index, line in enumerate(lines):
            if is_section_title(line, use_text=use_text, use_visual=use_visual):
                first_section_idx = index
                break

    if first_section_idx is None:
        header_lines = list(lines)
    else:
        header_lines = lines[:first_section_idx]
    header = parse_header(header_lines)

    sections: list[dict] = []
    current_section: dict | None = None

    if first_section_idx is None:
        section_source: list[Line] = []
    else:
        section_source = lines[first_section_idx:]

    for line in section_source:
        if is_section_title(line, use_text=use_text, use_visual=use_visual):
            if current_section is not None:
                sections.append(current_section)
            current_section = {
                "title": normalize_section_title(line.text),
                "raw": [],
            }
            continue

        if current_section is None:
            continue

        current_section["raw"].append(
            {
                "text": line.text,
                "page": line.page,
                "is_bullet": line.is_bullet,
                "indent": line.indent,
                "is_bold": line.is_bold,
                "size_ratio": line.size_ratio,
                "ends_with_colon": line.ends_with_colon,
                "top": line.top,
                "bottom": line.bottom,
                "x0": line.x0,
                "x1": line.x1,
                "font_size": line.font_size,
                "region": line.region,
            }
        )

    if current_section is not None:
        sections.append(current_section)

    return {"header": header, "sections": sections, "header_lines": header_lines}
