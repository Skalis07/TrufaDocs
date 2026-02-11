from __future__ import annotations

import re

MONTHS_ES = r"(Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)"
YEAR = r"(19|20)\d{2}"

DATE_RANGE_RE = re.compile(
    rf"\b{MONTHS_ES}\s+{YEAR}\s*(?:[-–—]|a|hasta)\s*{MONTHS_ES}\s+{YEAR}\b"
)

DATE_RANGE_OPEN_RE = re.compile(
    rf"\b{MONTHS_ES}\s+{YEAR}\s*(?:[-–—]|a|hasta)\s*(Presente|Actualidad|Hoy)\b",
    re.IGNORECASE,
)

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE)

BULLET_CHARS = ("●", "•", "◦", "-", "–", "—", "·")
TECH_PREFIX_RE = re.compile(r"^\s*Tecnolog[ií]as\s*:\s*", re.IGNORECASE)
HONORS_PREFIX_RE = re.compile(r"^\s*Honores\s*:\s*", re.IGNORECASE)

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
