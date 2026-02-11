import re
import unicodedata
from typing import Dict, List, Tuple, Set

from .structure_constants import (
    BULLET_RE,
    DATE_RANGE_RE,
    DEGREE_HINTS,
    EMAIL_RE,
    EXTRA_KEYWORDS,
    LOCATION_RE,
    MONTHS,
    MONTHS_REVERSE,
    ORG_HINTS,
    PHONE_RE,
    SECTION_KEYWORDS,
    URL_RE,
)

# --------------------
# Helpers de agrupacion
# --------------------

def _split_extra_blocks(lines: List[str]) -> List[List[str]]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in lines:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        if _is_heading(line) and current:
            blocks.append(current)
            current = [line]
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks or [[]]


def _group_entries(lines: List[str], section: str) -> List[List[str]]:
    entries: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        if not line.strip():
            continue
        if _match_heading(line)[0]:
            continue
        if current and _looks_like_entry_start(line, current, section):
            entries.append(current)
            current = [line]
            continue
        current.append(line)

    if current:
        entries.append(current)

    return entries or [[]]


# Reglas para detectar cuando empieza una nueva entrada
def _looks_like_entry_start(line: str, current: List[str], section: str) -> bool:
    if _is_bullet(line) or _looks_like_tech(line) or DATE_RANGE_RE.search(line):
        return False
    if not _looks_like_org(line):
        return False

    has_date = any(DATE_RANGE_RE.search(item) for item in current)
    has_bullets = any(_is_bullet(item) for item in current)
    if section == "experience":
        return has_date or has_bullets
    if section == "education":
        return has_date or any(_looks_like_org(item) for item in current)
    return False


# --------------------
# Heuristicas basicas
# --------------------

def _is_bullet(line: str) -> bool:
    return bool(BULLET_RE.search(line.strip()))


def _looks_like_tech(line: str) -> bool:
    """Heurística para detectar líneas de tecnologías/stack.

    Importante: en PDFs la línea de tecnologías suele venir SIN prefijo
    (p.ej. "Python, Pandas, scikit-learn"), y por el layout a veces el extractor
    la entrega después de la fecha. Esta función debe ser lo suficientemente
    tolerante para evitar que esa línea se interprete como inicio de una nueva entrada.
    """
    raw = (line or "").strip()
    if not raw:
        return False

    normalized = _normalize_ascii(raw)

    # 1) Palabras clave explícitas
    if any(key in normalized for key in (
        "tecnolog", "technolog", "tech", "stack", "herramient", "plataform",
        "framework", "lenguaj", "tools", "tooling", "motor"
    )):
        return True

    # 2) Listas típicas: varios elementos separados por coma / punto medio / slash
    #    Ej: "Unity, C#, Realidad Virtual" o "Python · Pandas · PyTorch"
    if any(sep in raw for sep in (",", " · ", " • ", " / ")):
        # Normalizar separadores a coma y tokenizar
        tokens = re.split(r"\s*(?:,|·|•|/)\s*", raw)
        tokens = [t.strip() for t in tokens if t and t.strip()]
        if len(tokens) >= 2:
            short_ratio = sum(1 for t in tokens if len(t) <= 22) / len(tokens)
            has_symbols = any(re.search(r"[#\+\.\-/\\]", t) for t in tokens)
            # Tokens alfabéticos o mixtos típicos en stacks (C#, C++, Node.js, scikit-learn)
            looks_like_stack_token = any(
                re.search(r"^(c\+\+|c#|node\.js|[a-z]{2,}(?:[-\.][a-z0-9]+)+)$", _normalize_ascii(t))
                for t in tokens
            )
            # Muchos tokens con mayúscula inicial (Unity, Pandas, Excel) también es señal.
            title_like_ratio = sum(1 for t in tokens if t[:1].isupper()) / len(tokens)

            # Caso especial de 2 tokens ("Docker, Vercel" vs "Santiago, Chile"):
            # lo tratamos como tech SOLO si hay señales fuertes (abreviaturas en MAYÚSCULA).
            if len(tokens) == 2 and not has_symbols and not looks_like_stack_token:
                if all(t.strip().isupper() and len(t.strip()) <= 6 for t in tokens):
                    return True
                return False

            if short_ratio >= 0.7 and (has_symbols or looks_like_stack_token or title_like_ratio >= 0.6):
                return True


    # 3) Fallback ultra-permisivo:
    #    Si parece una lista con comas y contiene tokens típicos de stack (símbolos o 'scikit' etc),
    #    preferimos tratarlo como tech para NO partir entradas.
    if "," in raw:
        low = _normalize_ascii(raw)
        if any(k in low for k in ("c#", "c++", "node", "python", "pandas", "scikit", "pytorch", "keras", "docker", "react", "django", "astro", "sql", "excel", "unity", "aws", "gcp", "vercel")):
            return True
        if re.search(r"[#\+\.\-/\\]", raw):
            return True
    return False


def _looks_like_org(line: str) -> bool:
    normalized = _normalize_ascii(line)
    if len(line.strip()) > 80:
        return False
    if "honor" in normalized or "mencion" in normalized or "distincion" in normalized or "cum laude" in normalized:
        return False
    if any(hint in normalized for hint in DEGREE_HINTS):
        return False
    if _looks_like_location(line) and not any(hint in normalized for hint in ORG_HINTS):
        return False
    if any(hint in normalized for hint in ORG_HINTS):
        return True
    words = [w for w in line.split() if w]
    if not words:
        return False
    if line.strip().isupper():
        return True
    if len(words) == 1:
        return False
    title_like = sum(1 for w in words if w[:1].isupper())
    ratio = title_like / len(words)
    return title_like >= 2 and ratio >= 0.6


def _looks_like_location(line: str) -> bool:
    if any(char.isdigit() for char in line):
        return False
    if len(line) >= 60:
        return False
    if "," in line:
        return True
    if " · " in line or " • " in line or " | " in line or " / " in line:
        return True
    return False


def _split_role_company(line: str) -> Tuple[str, str]:
    lowered = _normalize_ascii(line)
    if " - " in line:
        role, company = [part.strip() for part in line.split(" - ", 1)]
        return role, company
    if " — " in line:
        role, company = [part.strip() for part in line.split(" — ", 1)]
        return role, company
    if " – " in line:
        role, company = [part.strip() for part in line.split(" – ", 1)]
        return role, company
    if " | " in line:
        role, company = [part.strip() for part in line.split(" | ", 1)]
        return role, company
    if " en " in lowered:
        role, company = [part.strip() for part in line.split(" en ", 1)]
        return role, company
    if " at " in lowered:
        role, company = [part.strip() for part in line.split(" at ", 1)]
        return role, company
    return line.strip(), ""


def _normalize_heading_line(line: str) -> str:
    cleaned = _clean_bullet(line).strip()
    cleaned = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", cleaned)
    return cleaned.strip()


def _match_heading(line: str) -> Tuple[str, str]:
    if _is_bullet(line):
        return "", ""
    cleaned_line = _normalize_heading_line(line)
    if not cleaned_line:
        return "", ""
    # Evita falsos positivos en líneas "clave: valor", p.ej. "Tecnologías: Python, ...".
    if ":" in cleaned_line and not cleaned_line.endswith(":"):
        left, right = cleaned_line.split(":", 1)
        if left.strip() and right.strip():
            return "", ""
    normalized = _normalize_ascii(cleaned_line).strip(":")
    for key, keywords in SECTION_KEYWORDS.items():
        for keyword in keywords:
            if normalized == keyword or normalized.startswith(keyword):
                return key, cleaned_line.strip()
    if _is_explicit_extra_heading(line):
        return "extra", cleaned_line.strip().rstrip(":")
    return "", ""


def _is_extra_keyword_heading(line: str) -> bool:
    if _is_bullet(line):
        return False
    cleaned_line = _normalize_heading_line(line)
    if not cleaned_line:
        return False
    normalized = _normalize_ascii(cleaned_line).strip(":")
    for keyword in EXTRA_KEYWORDS:
        if normalized == keyword or normalized.startswith(keyword):
            return True
    return False




def _is_extra_heading_after_skills(line: str) -> bool:
    if _is_explicit_extra_heading(line):
        return True
    if _is_bullet(line):
        return False
    cleaned_line = _normalize_heading_line(line)
    if not cleaned_line:
        return False
    normalized = _normalize_ascii(cleaned_line).strip(":")
    for keywords in SECTION_KEYWORDS.values():
        for keyword in keywords:
            if normalized == keyword or normalized.startswith(keyword):
                return False
    if cleaned_line.endswith(":"):
        return True
    if cleaned_line.isupper():
        if len(normalized) >= 4 and len(normalized) <= 40 and "," not in normalized:
            return True
    return False
def _is_explicit_extra_heading(line: str) -> bool:
    if _is_bullet(line):
        return False
    cleaned_line = _normalize_heading_line(line)
    if not cleaned_line:
        return False
    normalized = _normalize_ascii(cleaned_line).strip(":")
    for keyword in EXTRA_KEYWORDS:
        if normalized == keyword or normalized.startswith(keyword):
            return True
    if cleaned_line.endswith(":"):
        return True
    if cleaned_line.isupper() and len(normalized) >= 14 and "/" not in normalized:
        if "," in cleaned_line:
            return False
        if any(ch.isdigit() for ch in cleaned_line):
            return False
        words = [w for w in normalized.split() if w]
        if len(words) >= 2:
            return True
    return False


def _is_heading(line: str) -> bool:
    if _is_bullet(line):
        return False
    stripped = _normalize_heading_line(line)
    if len(stripped) < 3 or len(stripped) > 48:
        return False
    if stripped.isupper():
        if "," in stripped:
            return False
        if any(ch.isdigit() for ch in stripped):
            return False
        return True
    if stripped.endswith(":"):
        return True
    return False


def _extract_date_range_from_line(line: str) -> Tuple[str, str, str]:
    if not line:
        return "", "", line
    match = DATE_RANGE_RE.search(line)
    if not match:
        return "", "", line
    start = _normalize_date_token(match.group("start"))
    end = _normalize_date_token(match.group("end"))
    cleaned = (line[: match.start()] + line[match.end() :]).strip()
    cleaned = cleaned.strip("()[]{}")
    cleaned = re.sub(r"\s*[|·•]\s*", " ", cleaned)
    cleaned = cleaned.strip("-–— ")
    return start, end, cleaned


def _extract_location_from_line(line: str) -> Tuple[str, str]:
    if not line:
        return "", ""
    cleaned = re.sub(r"^(ubicacion|ubicación|location)\s*:\s*", "", line.strip(), flags=re.IGNORECASE)
    cleaned = cleaned.strip("()[]{}")
    candidates = re.split(r"\s*[|·•]\s*|\s+—\s+|\s+–\s+|\s+-\s+", cleaned)
    for candidate in [cleaned] + candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        city, country = _parse_location(candidate)
        if city:
            return city, country
    return "", ""


def _extract_tech_from_line(line: str) -> str:
    if not line:
        return ""
    stripped = line.strip()
    normalized = _normalize_ascii(stripped)
    tech_keys = ("tecnolog", "tech", "stack", "herramient", "tools", "tooling", "plataform", "framework", "lenguaj", "motor")
    if ":" in stripped:
        label, _rest = stripped.split(":", 1)
        label_norm = _normalize_ascii(label)
        if any(key in label_norm for key in tech_keys):
            return stripped
    if any(normalized.startswith(key) for key in ("tecnolog", "detalle", "tech", "stack")):
        return stripped
    return ""


def _contains_bullet_symbol(text: str) -> bool:
    return any(sym in text for sym in ("•", "‣", "●", "■", "▪", "○", "◦", "⁃", "∙", "·"))


def _format_date_range(start: str, end: str) -> str:
    start = _format_date_token(start)
    end = _format_date_token(end)
    if start and end:
        return f"{start} - {end}"
    if start and not end:
        return f"{start} - Actualidad"
    if end and not start:
        return end
    return ""


def _normalize_date_token(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if re.match(r"^\d{4}-\d{2}$", value):
        return value
    if re.match(r"^\d{4}$", value):
        return value
    if re.match(r"^\d{1,2}/\d{4}$", value):
        month, year = value.split("/", 1)
        if len(month) == 1:
            month = f"0{month}"
        return f"{year}-{month}"

    parts = value.replace(".", "").split()
    if len(parts) >= 2:
        month_key = _normalize_ascii(parts[0])
        year = parts[1]
        month_num = MONTHS.get(month_key)
        if month_num and year.isdigit():
            return f"{year}-{month_num}"
    return value


def _format_date_token(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    match = re.match(r"^(?P<year>\d{4})-(?P<month>\d{2})$", value)
    if match:
        month = MONTHS_REVERSE.get(match.group("month"), match.group("month"))
        return f"{month} {match.group('year')}"
    return value


def _join_paragraph(lines: List[str]) -> str:
    chunks = []
    current: List[str] = []
    for line in lines:
        if not line:
            if current:
                chunks.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        chunks.append(" ".join(current))
    return "\n".join(chunks).strip()


def _has_content(items: List[Dict], keys: List[str]) -> bool:
    for item in items or []:
        for key in keys:
            value = item.get(key)
            if isinstance(value, list) and any(value):
                return True
            if isinstance(value, str) and value.strip():
                return True
    return False


def _trim_trailing_blanks(lines: List[str]) -> List[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _compact_lines(lines: List[str]) -> List[str]:
    compacted: List[str] = []
    seen: Dict[str, int] = {}
    last = ""
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned == last:
            continue
        last = cleaned
        key = _normalize_ascii(cleaned)
        seen[key] = seen.get(key, 0) + 1
        # Evita duplicados frecuentes (headers, footers) sin eliminar contenido corto unico.
        if seen[key] > 2 and len(cleaned) > 40:
            continue
        compacted.append(cleaned)
    return compacted


def _first_match(pattern, text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def _normalize_ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    cleaned = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned.lower()


def _clean_bullet(text: str) -> str:
    cleaned = text
    for bullet in ("\u2022", "\u2023", "\u25cf", "\u25a0", "\u25aa", "\u25cb", "\u25e6", "\u2043", "\u2219", "\u00b7"):
        cleaned = cleaned.replace(bullet, "")
    cleaned = BULLET_RE.sub("", cleaned)
    return cleaned.strip("-* ").strip()


def _append_highlight(highlights: List[str], line: str) -> None:
    raw = line or ""
    if _contains_bullet_symbol(raw):
        parts = re.split(r"[•‣●■▪○◦⁃∙·]+", raw)
        for part in parts:
            cleaned = _clean_bullet(part)
            if not cleaned:
                continue
            for chunk in _split_highlight_chunks(cleaned):
                if highlights and _is_continuation(highlights[-1], chunk):
                    highlights[-1] = f"{highlights[-1].rstrip()} {chunk.lstrip()}"
                else:
                    highlights.append(chunk)
        return
    cleaned = _clean_bullet(raw)
    if not cleaned:
        return
    for chunk in _split_highlight_chunks(cleaned):
        if highlights and _is_continuation(highlights[-1], chunk):
            highlights[-1] = f"{highlights[-1].rstrip()} {chunk.lstrip()}"
        else:
            highlights.append(chunk)


def _is_continuation(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous[-1] in ".;:!?":
        return False
    if current[:1].islower():
        return True
    if previous.endswith(","):
        return True
    return False


def _split_highlight_chunks(text: str) -> List[str]:
    chunks: List[str] = []
    raw_parts = text.replace("\r", "").split("\\n")
    for part in raw_parts:
        for sub in part.splitlines():
            cleaned = sub.strip()
            if cleaned:
                chunks.append(cleaned)
    return chunks or [text]


def _parse_location(line: str) -> Tuple[str, str]:
    candidate = line.strip()
    if not candidate:
        return "", ""
    candidate = re.sub(r"\s*[|·•/]\s*", ", ", candidate)
    normalized = _normalize_ascii(candidate)
    if ":" in candidate or _looks_like_tech(candidate):
        return "", ""
    if EMAIL_RE.search(candidate) or URL_RE.search(candidate) or PHONE_RE.search(candidate):
        return "", ""
    if any(word in normalized for word in ("honor", "mencion", "distincion", "cum laude")):
        return "", ""
    if not _looks_like_location(candidate):
        return "", ""
    match = LOCATION_RE.match(candidate)
    if match:
        return match.group("city").strip(), match.group("country").strip()
    parts = [part.strip() for part in candidate.split(",") if part.strip()]
    if len(parts) >= 2:
        if len(parts[0].split()) > 4 or len(parts[1].split()) > 4:
            return "", ""
        return parts[0], ", ".join(parts[1:])
    return "", ""


def _is_location_candidate(candidate: str, contact_values: Set[str]) -> bool:
    if any(value in candidate for value in contact_values):
        return False
    normalized = _normalize_ascii(candidate)
    if ":" in candidate or _looks_like_tech(candidate):
        return False
    if EMAIL_RE.search(candidate) or URL_RE.search(candidate) or PHONE_RE.search(candidate):
        return False
    if any(word in normalized for word in ("honor", "mencion", "distincion", "cum laude")):
        return False
    return _looks_like_location(candidate)
