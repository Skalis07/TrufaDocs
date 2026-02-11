from __future__ import annotations

from .constants import EMAIL_RE, KNOWN_SECTION_TITLES, PHONE_RE, URL_RE
from .extract import Line, enrich_features


def normalize_section_title(title: str) -> str:
    return " ".join(title.split()).upper()


def _looks_like_visual_title(line: Line) -> bool:
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
    text = line.text.strip()
    if not text:
        return False
    if line.is_bullet:
        return False
    if line.has_email or line.has_phone or line.has_url:
        return False
    if line.is_date_range or line.is_open_date_range:
        return False
    if line.has_rule_below:
        return True
    if use_visual and _looks_like_visual_title(line):
        return True
    if not use_text:
        return False
    if text.upper() in KNOWN_SECTION_TITLES:
        return True
    if line.uppercase_ratio >= 0.8 and len(text) <= 40 and "," not in text:
        return True
    return False


def parse_header(lines: list[Line]) -> dict:
    header = {
        "name": None,
        "location": None,
        "email": None,
        "phone": None,
        "links": [],
        "raw_lines": [],
    }

    def _split_header_segments(text: str) -> list[str]:
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
        if match_phone and not header["phone"]:
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
    enrich_features(lines)
    lines = sorted(lines, key=lambda item: (item.page, item.top, item.x0))

    use_rule_only = any(line.has_rule_below for line in lines)
    use_text = not use_rule_only
    use_visual = not use_rule_only

    first_section_idx = None
    for index, line in enumerate(lines):
        if is_section_title(line, use_text=use_text, use_visual=False):
            first_section_idx = index
            break

    header_lines = lines[: first_section_idx or 0]
    header = parse_header(header_lines)

    sections: list[dict] = []
    current_section: dict | None = None

    for line in lines[first_section_idx or 0 :]:
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
            }
        )

    if current_section is not None:
        sections.append(current_section)

    return {"header": header, "sections": sections, "header_lines": header_lines}
