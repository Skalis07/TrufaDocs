from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import (
    BULLET_CHARS,
    DATE_RANGE_OPEN_RE,
    DATE_RANGE_RE,
    EMAIL_RE,
    PHONE_RE,
    URL_RE,
)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _most_common(values: list[str]) -> Optional[str]:
    if not values:
        return None
    counts: dict[str, int] = {}
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])[0]


def normalize_spaces(text: str) -> str:
    return " ".join(text.split())


def _join_words_with_columns(words: list[dict]) -> str:
    if not words:
        return ""
    ordered = sorted(words, key=lambda word: word["x0"])
    gaps = []
    for idx in range(1, len(ordered)):
        gap = (ordered[idx]["x0"] or 0.0) - (ordered[idx - 1]["x1"] or 0.0)
        gaps.append(gap)
    if not gaps:
        return normalize_spaces(" ".join(word["text"] for word in ordered))
    if len(gaps) == 1:
        threshold = 120.0
    elif len(gaps) == 2:
        threshold = max(80.0, min(gaps) * 6)
    else:
        median_gap = _median(gaps)
        threshold = max(80.0, median_gap * 6)
    parts = [ordered[0]["text"]]
    for idx in range(1, len(ordered)):
        gap = (ordered[idx]["x0"] or 0.0) - (ordered[idx - 1]["x1"] or 0.0)
        if gap >= threshold:
            parts.append("|")
        parts.append(ordered[idx]["text"])
    return normalize_spaces(" ".join(parts))


def calc_uppercase_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    uppers = sum(1 for char in letters if char.isupper())
    return uppers / len(letters)


def calc_comma_density(text: str) -> float:
    text = text.strip()
    if not text:
        return 0.0
    return text.count(",") / max(1, len(text))


def strip_bullet_prefix(text: str) -> tuple[str, Optional[str]]:
    stripped = text.lstrip()
    if not stripped:
        return text, None
    first = stripped[0]
    if first in BULLET_CHARS:
        return normalize_spaces(stripped[1:]), first
    return text, None


@dataclass
class Line:
    text: str
    page: int
    x0: float
    top: float
    x1: float
    bottom: float
    fontname: Optional[str] = None
    font_size: float = 0.0
    has_rule_below: bool = False
    indent: float = 0.0
    is_bullet: bool = False
    bullet_char: Optional[str] = None
    uppercase_ratio: float = 0.0
    comma_density: float = 0.0
    ends_with_colon: bool = False
    has_email: bool = False
    has_phone: bool = False
    has_url: bool = False
    is_date_range: bool = False
    is_open_date_range: bool = False
    is_bold: bool = False
    size_ratio: float = 0.0


def extract_lines(file_obj) -> list[Line]:
    try:
        import pdfplumber  # type: ignore
    except Exception as exc:
        raise RuntimeError("pdfplumber no esta instalado. Ejecuta pip install -r requirements.txt.") from exc
    lines: list[Line] = []
    file_obj.seek(0)
    with pdfplumber.open(file_obj) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=False,
                extra_attrs=["fontname", "size"],
            )
            if not words:
                continue

            words_sorted = sorted(words, key=lambda word: (round(word["top"], 1), word["x0"]))
            current: list[dict] = []
            current_key = None
            page_lines: list[Line] = []

            def flush() -> None:
                nonlocal current
                if not current:
                    return
                text = _join_words_with_columns(current)
                x0 = min(word["x0"] for word in current)
                x1 = max(word["x1"] for word in current)
                top = min(word["top"] for word in current)
                bottom = max(word["bottom"] for word in current)
                sizes = [float(word["size"]) for word in current if word.get("size")]
                fontnames = [word.get("fontname") for word in current if word.get("fontname")]
                font_size = _median(sizes) if sizes else 0.0
                fontname = _most_common([name for name in fontnames if name])
                page_lines.append(
                    Line(
                        text=text,
                        page=page_index,
                        x0=x0,
                        x1=x1,
                        top=top,
                        bottom=bottom,
                        fontname=fontname,
                        font_size=font_size,
                    )
                )
                current = []

            for word in words_sorted:
                key = round(word["top"], 1)
                if current_key is None:
                    current_key = key
                    current = [word]
                    continue
                if abs(key - current_key) > 2.0:
                    flush()
                    current_key = key
                    current = [word]
                else:
                    current.append(word)

            flush()

            rects = page.rects or []
            if rects and page_lines:
                page_width = page.width or 0.0
                rule_rects = []
                for rect in rects:
                    height = rect.get("height", 0.0) or 0.0
                    if height > 1.5:
                        continue
                    width = (rect.get("x1", 0.0) or 0.0) - (rect.get("x0", 0.0) or 0.0)
                    if page_width and width < page_width * 0.7:
                        continue
                    rule_rects.append(rect)

                if rule_rects:
                    for line in page_lines:
                        for rect in rule_rects:
                            if abs((rect.get("top", 0.0) or 0.0) - line.bottom) <= 1.2:
                                line.has_rule_below = True
                                break

            lines.extend(page_lines)

    return lines


def enrich_features(lines: list[Line]) -> None:
    if not lines:
        return
    per_page_min_x0: dict[int, float] = {}
    per_page_sizes: dict[int, list[float]] = {}
    for line in lines:
        per_page_min_x0[line.page] = min(per_page_min_x0.get(line.page, line.x0), line.x0)
        if line.font_size:
            per_page_sizes.setdefault(line.page, []).append(line.font_size)

    per_page_median_size = {
        page: _median(values) for page, values in per_page_sizes.items() if values
    }

    for line in lines:
        line.text = normalize_spaces(line.text)
        line.indent = line.x0 - per_page_min_x0.get(line.page, 0.0)
        median_size = per_page_median_size.get(line.page, 0.0)
        if median_size and line.font_size:
            line.size_ratio = line.font_size / median_size
        else:
            line.size_ratio = 0.0
        fontname = (line.fontname or "").lower()
        if fontname:
            line.is_bold = any(token in fontname for token in ("bold", "black", "heavy", "semibold", "demi"))

        stripped, bullet_char = strip_bullet_prefix(line.text)
        if bullet_char is not None:
            line.is_bullet = True
            line.bullet_char = bullet_char
            line.text = stripped

        line.uppercase_ratio = clamp01(calc_uppercase_ratio(line.text))
        line.comma_density = clamp01(calc_comma_density(line.text))
        line.ends_with_colon = line.text.rstrip().endswith(":")

        line.has_email = EMAIL_RE.search(line.text) is not None
        line.has_phone = PHONE_RE.search(line.text) is not None
        line.has_url = URL_RE.search(line.text) is not None

        line.is_date_range = DATE_RANGE_RE.search(line.text) is not None
        line.is_open_date_range = DATE_RANGE_OPEN_RE.search(line.text) is not None
