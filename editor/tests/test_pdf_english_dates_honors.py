"""Pruebas de fechas en ingles y honores en educacion dentro del flujo PDF."""

import io
from unittest.mock import patch

from django.test import SimpleTestCase

from editor.pdf_parse.bridge import parse_pdf_to_structure
from editor.pdf_parse.parsers import parse_education, parse_experience


def _line(
    text: str,
    *,
    indent: float = 0.0,
    is_bullet: bool = False,
    is_bold: bool = False,
) -> dict:
    """Construye una linea raw minima como las que entrega el extractor."""
    return {
        "text": text,
        "indent": indent,
        "is_bullet": is_bullet,
        "is_bold": is_bold,
        "size_ratio": 1.0,
        "ends_with_colon": False,
    }


class PdfEnglishDatesHonorsTests(SimpleTestCase):
    """Protege ramas de parseo especificas de ingles en `pdf_parse`."""

    def test_parse_experience_detects_english_month_date_ranges(self) -> None:
        """Los meses en ingles deben preservarse en `date_range` de experiencia."""
        raw_lines = [
            _line("Example Corp | Remote", is_bold=True),
            _line("Developer | Jan 2023 – May 2023"),
        ]

        blocks = parse_experience(raw_lines)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].get("date_range"), "Jan 2023 – May 2023")
        self.assertEqual(blocks[0].get("role"), "Developer")

    def test_parse_pdf_education_in_english_maps_dates_and_honors(self) -> None:
        """EDUCATION en ingles debe mapear fechas y honors al output estructurado."""
        assembled = {
            "header": {
                "name": "Sample Candidate",
                "email": "",
                "phone": "",
                "links": [],
                "location": "",
            },
            "header_lines": [],
            "sections": [
                {
                    "title": "EDUCATION",
                    "raw": [
                        _line("University X | Santiago, Chile", is_bold=True),
                        _line("BSc Computer Science | Mar 2017 – Nov 2023"),
                        _line("Honors: Distinction"),
                        _line("University Y | Santiago, Chile", is_bold=True),
                        _line("MSc Data Science | Mar 2023 – Dec 2024"),
                        _line("Honors: Magna Cum Laude"),
                    ],
                }
            ],
        }

        with (
            patch("editor.pdf_parse.bridge.extract_lines", return_value=[object()]),
            patch("editor.pdf_parse.bridge.assemble_sections", return_value=assembled),
        ):
            structured, error = parse_pdf_to_structure(io.BytesIO(b"fake"))

        self.assertIsNone(error)
        education = structured.get("education") or []
        self.assertEqual(len(education), 2)
        self.assertEqual(education[0].get("start"), "2017-03")
        self.assertEqual(education[0].get("end"), "2023-11")
        self.assertEqual(education[0].get("items"), ["Honors: Distinction"])
        self.assertEqual(education[0].get("honors"), "Distinction")
        self.assertEqual(education[1].get("start"), "2023-03")
        self.assertEqual(education[1].get("end"), "2024-12")
        self.assertEqual(education[1].get("items"), ["Honors: Magna Cum Laude"])
        self.assertEqual(education[1].get("honors"), "Magna Cum Laude")

    def test_parse_education_keeps_gpa_as_item_and_not_as_new_block(self) -> None:
        """Lineas cortas como `GPA: 3.8` no deben partir una nueva institucion."""
        raw_lines = [
            _line("Universidad Andrés Bello | Santiago, Chile", is_bold=True),
            _line("Magíster en Ciencias de la Computación | Mar 2023 – Dic 2024"),
            _line("Distinción Magna Cum Laude"),
            _line("GPA: 3.8"),
            _line("Universidad Andrés Bello | Viña del Mar, Chile", is_bold=True),
            _line("Ingeniería Civil Informática | Mar 2017 – Nov 2023"),
            _line("Distinción"),
            _line("GPA: 3.3"),
        ]

        blocks = parse_education(raw_lines)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].get("org"), "Universidad Andrés Bello")
        self.assertEqual(blocks[0].get("location"), "Santiago, Chile")
        self.assertEqual(blocks[0].get("honors"), "Distinción Magna Cum Laude")
        self.assertEqual(blocks[0].get("extra"), ["GPA: 3.8"])
        self.assertEqual(blocks[1].get("org"), "Universidad Andrés Bello")
        self.assertEqual(blocks[1].get("location"), "Viña del Mar, Chile")
        self.assertEqual(blocks[1].get("honors"), "Distinción")
        self.assertEqual(blocks[1].get("extra"), ["GPA: 3.3"])

    def test_parse_pdf_education_in_spanish_preserves_honores_prefix_in_items(self) -> None:
        """`Honores:` debe mantenerse como item visible en educación importada."""
        assembled = {
            "header": {
                "name": "Persona Ejemplo",
                "email": "",
                "phone": "",
                "links": [],
                "location": "",
            },
            "header_lines": [],
            "sections": [
                {
                    "title": "EDUCACIÓN",
                    "raw": [
                        _line("Universidad Andrés Bello | Viña del Mar, Chile", is_bold=True),
                        _line("Ingeniería Civil Informática | Mar 2017 – Nov 2023"),
                        _line("Honores: Distinción"),
                        _line("GPA: 3.3"),
                    ],
                }
            ],
        }

        with (
            patch("editor.pdf_parse.bridge.extract_lines", return_value=[object()]),
            patch("editor.pdf_parse.bridge.assemble_sections", return_value=assembled),
        ):
            structured, error = parse_pdf_to_structure(io.BytesIO(b"fake"))

        self.assertIsNone(error)
        education = structured.get("education") or []
        self.assertEqual(len(education), 1)
        self.assertEqual(education[0].get("items"), ["Honores: Distinción", "GPA: 3.3"])
        self.assertEqual(education[0].get("honors"), "Distinción")
