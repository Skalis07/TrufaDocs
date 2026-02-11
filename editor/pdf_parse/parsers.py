from __future__ import annotations

import re

from .constants import (
    BULLET_CHARS,
    DATE_RANGE_OPEN_RE,
    DATE_RANGE_RE,
    HONORS_PREFIX_RE,
    TECH_PREFIX_RE,
)
from .extract import calc_comma_density, normalize_spaces

LOCATION_TRAILING_RE = re.compile(r"(Viña del Mar|Santiago),\s*Chile$", re.IGNORECASE)


def _strip_trailing_bullet(text: str) -> str:
    stripped = text.strip()
    if stripped and stripped[-1] in BULLET_CHARS:
        return stripped[:-1].strip()
    return text


def _strip_bullet_markers(text: str) -> tuple[str, bool]:
    stripped = text.strip()
    if not stripped:
        return text, False
    is_bullet = False
    if stripped[0] in BULLET_CHARS:
        is_bullet = True
        stripped = stripped[1:].strip()
    if stripped and stripped[-1] in BULLET_CHARS:
        is_bullet = True
        stripped = stripped[:-1].strip()
    return normalize_spaces(stripped), is_bullet


def _infer_bullet_indents(raw_lines: list[dict]) -> tuple[float, float]:
    indents = sorted({float(entry.get("indent", 0.0)) for entry in raw_lines if entry.get("indent", 0.0) > 0})
    if not indents:
        return 0.0, 0.0
    bullet_indent = indents[0]
    continuation_indent = indents[1] if len(indents) > 1 else bullet_indent + 8.0
    return bullet_indent, continuation_indent


def _extract_date_from_line(text: str) -> tuple[str, str]:
    match = DATE_RANGE_RE.search(text) or DATE_RANGE_OPEN_RE.search(text)
    if not match:
        return "", ""
    date_range = match.group(0)
    remainder = text.replace(date_range, "")
    remainder = re.sub(r"\s*\|\s*", " ", remainder)
    remainder = normalize_spaces(remainder.strip(" -–—()"))
    return date_range, remainder


def _split_org_location(text: str) -> tuple[str, str]:
    if "|" in text:
        parts = [normalize_spaces(part) for part in text.split("|") if normalize_spaces(part)]
        if len(parts) > 1:
            for idx in range(len(parts) - 1, 0, -1):
                candidate = parts[idx]
                if "," in candidate and len(candidate) <= 40:
                    org = normalize_spaces(" ".join(parts[:idx]))
                    return org, candidate
    match = LOCATION_TRAILING_RE.search(text)
    if match:
        location = match.group(0).strip()
        org = text[: match.start()].strip()
        return org, location
    return text, ""


def _looks_like_new_org(line: str) -> bool:
    if TECH_PREFIX_RE.match(line):
        return False
    if DATE_RANGE_RE.search(line) or DATE_RANGE_OPEN_RE.search(line):
        return False
    if len(line) > 65:
        return False
    return True


def parse_experience(raw_lines: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    current: dict | None = None
    pending_bullet_index: int | None = None
    bullet_indent, continuation_indent = _infer_bullet_indents(raw_lines)

    def start_block() -> dict:
        return {
            "org": None,
            "role": None,
            "location": None,
            "date_range": None,
            "meta_tech": None,
            "items": [],
            "extra": [],
        }

    for entry in raw_lines:
        raw_text = normalize_spaces(entry.get("text", ""))
        if not raw_text:
            continue

        indent = float(entry.get("indent", 0.0))
        text, marker_bullet = _strip_bullet_markers(raw_text)
        is_bullet = bool(entry.get("is_bullet")) or marker_bullet
        is_tech = bool(TECH_PREFIX_RE.match(text))
        date_range, remainder = _extract_date_from_line(text)
        is_date = bool(date_range)
        comma_density = calc_comma_density(text)
        is_location = text.count(",") == 1 and len(text) <= 40
        is_indent_bullet = bullet_indent > 0 and indent >= (bullet_indent - 0.5) and not is_tech and not is_date
        is_continuation = pending_bullet_index is not None and continuation_indent > 0 and indent >= (continuation_indent - 0.5)

        if current is None:
            current = start_block()
            blocks.append(current)

        if is_continuation and not is_bullet:
            existing = current["items"][pending_bullet_index]["text"]
            current["items"][pending_bullet_index]["text"] = normalize_spaces(f"{existing} {text}")
            continue

        if is_bullet or (is_indent_bullet and indent < (continuation_indent - 0.5)):
            current["items"].append({"text": text})
            pending_bullet_index = len(current["items"]) - 1
            continue

        if pending_bullet_index is not None:
            if not is_tech and not is_date and not is_location and not _looks_like_new_org(text):
                existing = current["items"][pending_bullet_index]["text"]
                current["items"][pending_bullet_index]["text"] = normalize_spaces(f"{existing} {text}")
                continue
            pending_bullet_index = None

        if (
            current["org"]
            and (current["role"] or current["date_range"] or current["items"])
            and not is_bullet
            and not is_tech
            and (
                comma_density < 0.01
                or bool(entry.get("is_bold"))
                or "|" in text
                or bool(LOCATION_TRAILING_RE.search(text))
            )
            and _looks_like_new_org(text)
        ):
            current = start_block()
            blocks.append(current)

        if is_date:
            current["date_range"] = date_range
            if remainder:
                if TECH_PREFIX_RE.match(remainder):
                    current["meta_tech"] = remainder
                elif current["role"] is None:
                    current["role"] = remainder
                else:
                    current["extra"].append(remainder)
            continue

        if is_tech:
            current["meta_tech"] = text
            continue

        if (
            current["org"]
            and (current["role"] or current["date_range"])
            and current["meta_tech"] is None
            and not is_bullet
            and not is_location
            and comma_density >= 0.01
        ):
            current["meta_tech"] = text
            continue

        org, location = _split_org_location(text)
        if location and current["org"] is None:
            current["org"] = org or text
            current["location"] = location
            continue

        if is_location and current["location"] is None:
            current["location"] = text
            continue

        if current["org"] is None:
            current["org"] = text
        elif current["role"] is None:
            current["role"] = text
        else:
            current["extra"].append(text)

    cleaned = []
    for block in blocks:
        if any(
            [
                block["org"],
                block["role"],
                block["items"],
                block["date_range"],
                block["location"],
                block["meta_tech"],
            ]
        ):
            cleaned.append(block)
    return cleaned


def parse_education(raw_lines: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    current: dict | None = None

    def start_block() -> dict:
        return {
            "org": None,
            "program": None,
            "honors": None,
            "location": None,
            "date_range": None,
            "extra": [],
        }

    for entry in raw_lines:
        text = normalize_spaces(entry.get("text", ""))
        if not text:
            continue

        is_honor = bool(HONORS_PREFIX_RE.match(text))
        date_range, remainder = _extract_date_from_line(text)
        is_date = bool(date_range)

        if current is None:
            current = start_block()
            blocks.append(current)

        if (
            current["org"]
            and (current["program"] or current["date_range"])
            and not is_honor
            and _looks_like_new_org(text)
        ):
            current = start_block()
            blocks.append(current)

        if is_honor:
            current["honors"] = text
            continue

        if is_date:
            current["date_range"] = date_range
            if remainder and current["program"] is None:
                current["program"] = remainder
            elif remainder:
                current["extra"].append(remainder)
            continue

        org, location = _split_org_location(text)
        if location and current["org"] is None:
            current["org"] = org or text
            current["location"] = location
            continue

        if "," in text and len(text) <= 40 and current["location"] is None:
            current["location"] = text
            continue

        if current["org"] is None:
            current["org"] = text
        elif current["program"] is None:
            current["program"] = text
        else:
            current["extra"].append(text)

    cleaned = []
    for block in blocks:
        if any([block["org"], block["program"], block["honors"], block["date_range"], block["location"]]):
            cleaned.append(block)
    return cleaned


def parse_skills(raw_lines: list[dict]) -> list[dict]:
    groups: list[dict] = []
    current: dict | None = None

    for entry in raw_lines:
        raw_text = normalize_spaces(entry.get("text", ""))
        if not raw_text:
            continue
        segments = [normalize_spaces(part) for part in raw_text.split("|") if normalize_spaces(part)]
        if len(segments) > 1:
            for segment in segments:
                segment_text, segment_is_bullet = _strip_bullet_markers(segment)
                if not segment_text:
                    continue
                comma_density = calc_comma_density(segment_text)

                if segment_is_bullet:
                    current = {"group_title": segment_text, "values": []}
                    groups.append(current)
                    continue

                if current is None:
                    current = {"group_title": "OTRAS", "values": []}
                    groups.append(current)

                if comma_density >= 0.01:
                    parts = [
                        normalize_spaces(part)
                        for part in segment_text.split(",")
                        if normalize_spaces(part)
                    ]
                    current["values"].extend(parts)
                else:
                    current["values"].append(segment_text)
            continue

        is_bullet = bool(entry.get("is_bullet")) or raw_text.strip().endswith(BULLET_CHARS)
        label = _strip_trailing_bullet(raw_text)
        comma_density = calc_comma_density(raw_text)

        if is_bullet:
            current = {"group_title": label, "values": []}
            groups.append(current)
            continue

        if current is None:
            current = {"group_title": "OTRAS", "values": []}
            groups.append(current)

        if comma_density >= 0.01:
            parts = [normalize_spaces(part) for part in raw_text.split(",") if normalize_spaces(part)]
            current["values"].extend(parts)
        else:
            current["values"].append(raw_text)

    for group in groups:
        seen: set[str] = set()
        values: list[str] = []
        for value in group["values"]:
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            values.append(value)
        group["values"] = values

    return [group for group in groups if group.get("group_title") and group.get("values")]
