from __future__ import annotations

import re

MONTH_TOKEN = (
    r"(?:"
    r"Ene(?:ro)?|Feb(?:rero)?|Mar(?:zo)?|Abr(?:il)?|May(?:o)?|Jun(?:io)?|"
    r"Jul(?:io)?|Ago(?:sto)?|Sep(?:tiembre)?|Oct(?:ubre)?|Nov(?:iembre)?|Dic(?:iembre)?|"
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    r")"
)
YEAR = r"(?:19|20)\d{2}"

DATE_RANGE_RE = re.compile(
    rf"\b{MONTH_TOKEN}\s+{YEAR}\s*(?:[-–—]|a|to|hasta)\s*{MONTH_TOKEN}\s+{YEAR}\b",
    re.IGNORECASE,
)

DATE_RANGE_OPEN_RE = re.compile(
    rf"\b{MONTH_TOKEN}\s+{YEAR}\s*(?:[-–—]|a|to|hasta)\s*(Presente|Actualidad|Hoy|Current|Present)\b",
    re.IGNORECASE,
)

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)

BULLET_CHARS = ("●", "•", "◦", "-", "–", "—", "·")
TECH_PREFIX_RE = re.compile(r"^\s*Tecnolog[ií]as\s*:\s*", re.IGNORECASE)
HONORS_PREFIX_RE = re.compile(r"^\s*(?:Honores?|Honors?|Honours?)\s*:\s*", re.IGNORECASE)

KNOWN_SECTION_TITLES = {
    "EXPERIENCIA",
    "EXPERIENCIA PROFESIONAL",
    "EXPERIENCIA LABORAL",
    "EDUCACIÓN",
    "EDUCACION",
    "HABILIDADES",
    "RESUMEN",
    "PERFIL",
    "PROYECTOS",
    "CERTIFICACIONES",
    "IDIOMAS",
    "PUBLICACIONES",
    "VOLUNTARIADO",
    "PREMIOS",
    "LOGROS",
    "REFERENCIAS",
}
