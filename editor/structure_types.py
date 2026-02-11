from __future__ import annotations

from typing import List, TypedDict


class ExtraLine(TypedDict, total=False):
    text: str
    indent: float
    is_bullet: bool
    is_bold: bool
    size_ratio: float
    ends_with_colon: bool


class ExtraSectionRaw(TypedDict):
    title: str
    lines: List[str | ExtraLine]


class ExtraEntryRequired(TypedDict):
    subtitle: str
    title: str
    where: str
    tech: str
    start: str
    end: str
    city: str
    country: str
    items: List[str]


class ExtraEntry(ExtraEntryRequired, total=False):
    # Modo a nivel de entrada (para permitir mezclar dentro de una misma sección)
    # Valores esperados: "detailed", "subtitle_items"
    # Compatibilidad: "items" se trata como alias de "subtitles"
    mode: str


class ExtraSectionRequired(TypedDict):
    section_id: str
    title: str
    entries: List[ExtraEntry]


class ExtraSection(ExtraSectionRequired, total=False):
    # Compatibilidad: modo a nivel sección (puede usarse como "default" para nuevas entradas)
    mode: str
