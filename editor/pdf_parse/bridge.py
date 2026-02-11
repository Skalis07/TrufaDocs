from __future__ import annotations

from typing import Iterable

from .assemble import assemble_sections
from .constants import HONORS_PREFIX_RE, URL_RE
from .extract import extract_lines
from .parsers import parse_education, parse_experience, parse_skills

from .. import structure

REMOTE_LOCATION_HINTS = {
    "remoto",
    "remote",
    "hibrido",
    "híbrido",
    "presencial",
}


def _strip_prefix(text: str, pattern) -> str:
    if not text:
        return ""
    return pattern.sub("", text).strip()


def _map_date_range(date_range: str) -> tuple[str, str]:
    if not date_range:
        return "", ""
    start, end, _ = structure._extract_date_range_from_line(date_range)
    return start, end


def _map_location(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    city, country = structure._parse_location(value)
    return city, country


def _map_tech(value: str) -> str:
    if not value:
        return ""
    mapped = structure._extract_tech_from_line(value)
    if mapped:
        return mapped
    return str(value).strip()


def _select_link(links: Iterable[str], keyword: str) -> str:
    keyword = keyword.lower()
    for link in links:
        if keyword in link.lower():
            return link
    return ""


def _infer_description(header_lines, header_name: str | None, location: str | None, contacts: list[str]) -> str:
    description_parts: list[str] = []
    for line in header_lines:
        text = line.text.strip()
        if not text:
            continue
        if header_name and text == header_name:
            continue
        if location and text == location:
            continue
        if URL_RE.search(text):
            continue
        if any(contact and contact in text for contact in contacts):
            continue
        description_parts.append(text)
    return " ".join(description_parts).strip()


def _map_experience(blocks: list[dict]) -> list[dict]:
    mapped: list[dict] = []
    for block in blocks:
        start, end = _map_date_range(block.get("date_range") or "")
        city, country = _map_location(block.get("location") or "")
        technologies = _map_tech(block.get("meta_tech") or "")
        highlights: list[str] = []
        for item in block.get("items", []):
            text = item.get("text") if isinstance(item, dict) else str(item)
            if text:
                highlights.append(text)
        for extra in block.get("extra", []) or []:
            if extra:
                highlights.append(extra)
        mapped.append(
            {
                "role": block.get("role") or "",
                "company": block.get("org") or "",
                "start": start,
                "end": end,
                "city": city,
                "country": country,
                "technologies": technologies,
                "highlights": highlights,
            }
        )
    return mapped


def _map_education(blocks: list[dict]) -> list[dict]:
    mapped: list[dict] = []
    for block in blocks:
        start, end = _map_date_range(block.get("date_range") or "")
        city, country = _map_location(block.get("location") or "")
        honors = _strip_prefix(block.get("honors") or "", HONORS_PREFIX_RE)
        mapped.append(
            {
                "degree": block.get("program") or "",
                "institution": block.get("org") or "",
                "start": start,
                "end": end,
                "city": city,
                "country": country,
                "honors": honors,
            }
        )
    return mapped


def _map_skills(groups: list[dict]) -> list[dict]:
    mapped: list[dict] = []
    for group in groups:
        title = group.get("group_title") or ""
        values = group.get("values") or []
        items = ", ".join(value for value in values if value)
        mapped.append({"category": title, "items": items})
    return mapped


def _split_org_with_inline_location(value: str) -> tuple[str, str]:
    text = (value or "").strip()
    if not text:
        return "", ""
    for sep in ("|", "·", "/", " - ", " – ", " — "):
        if sep in text:
            left, right = text.split(sep, 1)
            left = left.strip()
            right = right.strip()
            if left and right:
                return left, right
    return text, ""


def _map_extra_entries_from_experience(blocks: list[dict]) -> list[dict]:
    entries: list[dict] = []
    for block in blocks:
        start, end = _map_date_range(block.get("date_range") or "")
        where_raw = (block.get("org") or "").strip()
        where, inline_location = _split_org_with_inline_location(where_raw)
        where = where or where_raw

        city, country = _map_location(block.get("location") or "")
        if not city and inline_location:
            city, country = _map_location(inline_location)
            if not city and not country and inline_location.lower() in REMOTE_LOCATION_HINTS:
                city = inline_location

        technologies = _map_tech(block.get("meta_tech") or "")
        items: list[str] = []
        for item in block.get("items", []):
            text = item.get("text") if isinstance(item, dict) else str(item)
            if text and str(text).strip():
                items.append(str(text).strip())
        for extra in block.get("extra", []) or []:
            if extra and str(extra).strip():
                items.append(str(extra).strip())

        entry = {
            "subtitle": "",
            "title": (block.get("role") or "").strip(),
            "where": where.strip(),
            "tech": technologies,
            "start": start,
            "end": end,
            "city": city,
            "country": country,
            "items": items,
        }
        if any(entry.get(key) for key in ("title", "where", "tech", "start", "end", "city", "country")) or items:
            entries.append(entry)
    return entries


def _is_detailed_extra_entry(entry: dict) -> bool:
    return any((entry.get(key) or "").strip() for key in ("title", "where", "tech", "start", "end", "city", "country"))


def _should_prefer_experience_extra(
    title: str,
    generic_entries: list[dict],
    experience_entries: list[dict],
) -> bool:
    if not experience_entries:
        return False

    with_dates = sum(1 for entry in experience_entries if (entry.get("start") or entry.get("end")))
    with_context = sum(
        1
        for entry in experience_entries
        if (entry.get("where") or entry.get("title"))
        and ((entry.get("start") or entry.get("end")) or (entry.get("items") or entry.get("tech")))
    )
    if with_dates == 0 or with_context == 0:
        return False

    generic_count = len(generic_entries)
    title_upper = (title or "").upper()
    is_project_like_title = "PROYECT" in title_upper

    if is_project_like_title and generic_count > len(experience_entries):
        return True

    detailed_generic = sum(1 for entry in generic_entries if _is_detailed_extra_entry(entry))
    if generic_count >= len(experience_entries) * 2:
        return True
    if detailed_generic == 0 and len(experience_entries) >= 1:
        return True
    if with_context >= 2 and (generic_count - len(experience_entries)) >= 2:
        return True
    return False


def _parse_extra_section(title: str, raw_lines: list[dict], section_index: int) -> dict:
    section_id = f"extra-{section_index}"
    parsed_generic = structure._parse_extras([{"title": title, "lines": raw_lines}])
    generic_section = (
        parsed_generic[0]
        if parsed_generic
        else {"section_id": section_id, "title": title, "mode": "subtitle_items", "entries": []}
    )
    generic_section["section_id"] = section_id
    generic_section["title"] = title

    experience_entries = _map_extra_entries_from_experience(parse_experience(raw_lines))
    if _should_prefer_experience_extra(title, generic_section.get("entries") or [], experience_entries):
        return {
            "section_id": section_id,
            "title": title,
            "mode": "detailed",
            "entries": experience_entries,
        }

    return generic_section


def parse_pdf_to_structure(file_obj) -> tuple[dict, str | None]:
    try:
        lines = extract_lines(file_obj)
    except Exception as exc:
        detail = str(exc).strip()
        return structure.default_structure(), (
            f"No se pudo leer el PDF: {detail or 'error desconocido.'}"
        )

    if not lines:
        return structure.default_structure(), "No se pudo extraer texto del PDF."

    assembled = assemble_sections(lines)
    header = assembled["header"]
    header_lines = assembled["header_lines"]

    data = structure.default_structure()
    data["experience"] = []
    data["education"] = []
    data["skills"] = []

    basics = data["basics"]
    basics["name"] = header.get("name") or ""
    basics["email"] = header.get("email") or ""
    basics["phone"] = header.get("phone") or ""

    links = header.get("links") or []
    basics["linkedin"] = _select_link(links, "linkedin")
    basics["github"] = _select_link(links, "github")

    header_location = header.get("location")
    if header_location:
        city, country = _map_location(header_location)
        basics["city"] = city
        basics["country"] = country

    contacts = [basics["email"], basics["phone"], basics["linkedin"], basics["github"]]
    basics["description"] = _infer_description(header_lines, basics["name"], header_location, contacts)

    parsed_extras: list[dict] = []

    for section in assembled["sections"]:
        title = section.get("title") or ""
        raw_lines = section.get("raw") or []

        if title in {"EXPERIENCIA", "EXPERIENCIA PROFESIONAL", "EXPERIENCIA LABORAL"}:
            data["experience"].extend(_map_experience(parse_experience(raw_lines)))
            continue
        if title in {"EDUCACIÓN", "EDUCACION"}:
            data["education"].extend(_map_education(parse_education(raw_lines)))
            continue
        if title == "HABILIDADES":
            data["skills"].extend(_map_skills(parse_skills(raw_lines)))
            continue

        extra_lines = [entry for entry in raw_lines if entry.get("text")]
        if extra_lines:
            parsed_extras.append(_parse_extra_section(title, extra_lines, len(parsed_extras)))

    if parsed_extras:
        data["extra_sections"] = parsed_extras

    structure._ensure_minimums(data)
    return data, None
