import io
from unittest.mock import patch

from django.test import SimpleTestCase

from editor.pdf_parse.bridge import parse_pdf_to_structure
from editor.pdf_parse.parsers import parse_experience


def _line(
    text: str,
    *,
    indent: float = 0.0,
    is_bullet: bool = False,
    is_bold: bool = False,
) -> dict:
    return {
        "text": text,
        "indent": indent,
        "is_bullet": is_bullet,
        "is_bold": is_bold,
        "size_ratio": 1.0,
        "ends_with_colon": False,
    }


class PdfEnglishDatesHonorsTests(SimpleTestCase):
    def test_parse_experience_detects_english_month_date_ranges(self) -> None:
        raw_lines = [
            _line("Example Corp | Remote", is_bold=True),
            _line("Developer | Jan 2023 – May 2023"),
        ]

        blocks = parse_experience(raw_lines)

        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].get("date_range"), "Jan 2023 – May 2023")
        self.assertEqual(blocks[0].get("role"), "Developer")

    def test_parse_pdf_education_in_english_maps_dates_and_honors(self) -> None:
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
        self.assertEqual(education[0].get("honors"), "Distinction")
        self.assertEqual(education[1].get("start"), "2023-03")
        self.assertEqual(education[1].get("end"), "2024-12")
        self.assertEqual(education[1].get("honors"), "Magna Cum Laude")
