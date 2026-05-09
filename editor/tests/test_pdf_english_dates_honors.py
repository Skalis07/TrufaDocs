"""Pruebas de fechas en ingles y honores en educacion dentro del flujo PDF."""

import io
from unittest.mock import patch

from django.test import SimpleTestCase

from editor.pdf_parse.bridge import parse_pdf_to_structure
from editor.pdf_parse.parsers import parse_education, parse_experience, parse_skills


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
            _line("Developer | Jan 2031 – May 2031"),
        ]

        blocks = parse_experience(raw_lines)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].get("date_range"), "Jan 2031 – May 2031")
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
                        _line("University X | City One, Country Demo", is_bold=True),
                        _line("BSc Computer Science | Apr 2011 – Nov 2015"),
                        _line("Honors: Distinction"),
                        _line("University Y | City Two, Country Demo", is_bold=True),
                        _line("MSc Data Science | Mar 2016 – Dec 2017"),
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
        self.assertEqual(education[0].get("start"), "2011-04")
        self.assertEqual(education[0].get("end"), "2015-11")
        self.assertEqual(education[0].get("items"), ["Honors: Distinction"])
        self.assertEqual(education[0].get("honors"), "Distinction")
        self.assertEqual(education[1].get("start"), "2016-03")
        self.assertEqual(education[1].get("end"), "2017-12")
        self.assertEqual(education[1].get("items"), ["Honors: Magna Cum Laude"])
        self.assertEqual(education[1].get("honors"), "Magna Cum Laude")

    def test_parse_education_keeps_gpa_as_item_and_not_as_new_block(self) -> None:
        """Lineas cortas como `GPA: 3.8` no deben partir una nueva institucion."""
        raw_lines = [
            _line("Institución Demo Norte | Ciudad Uno, País Demo", is_bold=True),
            _line("Magíster en Ciencias Aplicadas | Mar 2016 – Dic 2017"),
            _line("Distinción Magna Cum Laude"),
            _line("GPA: 3.8"),
            _line("Institución Demo Sur | Ciudad Dos, País Demo", is_bold=True),
            _line("Ingeniería de Sistemas | Abr 2011 – Nov 2015"),
            _line("Distinción"),
            _line("GPA: 3.3"),
        ]

        blocks = parse_education(raw_lines)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].get("org"), "Institución Demo Norte")
        self.assertEqual(blocks[0].get("location"), "Ciudad Uno, País Demo")
        self.assertEqual(blocks[0].get("honors"), "Distinción Magna Cum Laude")
        self.assertEqual(blocks[0].get("extra"), ["GPA: 3.8"])
        self.assertEqual(blocks[1].get("org"), "Institución Demo Sur")
        self.assertEqual(blocks[1].get("location"), "Ciudad Dos, País Demo")
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
                        _line("Institución Demo Sur | Ciudad Dos, País Demo", is_bold=True),
                        _line("Ingeniería de Sistemas | Abr 2011 – Nov 2015"),
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

    def test_parse_skills_merges_indented_lowercase_wrap(self) -> None:
        """Una skill partida hacia abajo debe recomponerse sin crear item extra."""
        raw_lines = [
            _line("Herramientas", is_bullet=True),
            _line("Excel"),
            _line("tablas"),
            _line("dinámicas", indent=18.0),
            _line("Power BI"),
        ]

        groups = parse_skills(raw_lines)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].get("group_title"), "Herramientas")
        self.assertEqual(groups[0].get("values"), ["Excel", "tablas dinámicas", "Power BI"])

    def test_parse_skills_does_not_merge_regular_separate_values(self) -> None:
        """Skills separadas en líneas normales deben seguir separadas."""
        raw_lines = [
            _line("Herramientas", is_bullet=True),
            _line("Excel"),
            _line("SQL"),
            _line("Power BI"),
        ]

        groups = parse_skills(raw_lines)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].get("values"), ["Excel", "SQL", "Power BI"])

    def test_parse_skills_merges_wrapped_parenthetical_item_same_indent(self) -> None:
        """Un item con paréntesis abierto debe continuar aunque el indent no cambie."""
        raw_lines = [
            _line("Bases de Datos y BI", is_bullet=True),
            _line("PostgreSQL, Power BI (Power Query), Excel (macros, tablas"),
            _line("dinámicas)"),
        ]

        groups = parse_skills(raw_lines)

        self.assertEqual(len(groups), 1)
        self.assertEqual(
            groups[0].get("values"),
            ["PostgreSQL", "Power BI (Power Query)", "Excel (macros, tablas dinámicas)"],
        )

    def test_parse_pdf_skills_merges_wrapped_item_in_structured_output(self) -> None:
        """El flujo PDF completo debe exportar la skill recompuesta."""
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
                    "title": "HABILIDADES",
                    "raw": [
                        _line("Herramientas", is_bullet=True),
                        _line("Excel"),
                        _line("tablas"),
                        _line("dinámicas", indent=18.0),
                        _line("Power BI"),
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
        self.assertEqual(
            structured.get("skills"),
            [{"category": "Herramientas", "items": "Excel, tablas dinámicas, Power BI"}],
        )

    def test_parse_pdf_skills_merges_real_parenthetical_wrap_in_structured_output(self) -> None:
        """El flujo PDF debe recomponer items partidos dentro de paréntesis."""
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
                    "title": "HABILIDADES",
                    "raw": [
                        _line("Bases de Datos y BI", is_bullet=True),
                        _line("PostgreSQL, Power BI (Power Query), Excel (macros, tablas"),
                        _line("dinámicas)"),
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
        self.assertEqual(
            structured.get("skills"),
            [{"category": "Bases de Datos y BI", "items": "PostgreSQL, Power BI (Power Query), Excel (macros, tablas dinámicas)"}],
        )
