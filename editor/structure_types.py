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
