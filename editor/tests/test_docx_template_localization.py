import io
import unicodedata
from pathlib import Path

from django.test import SimpleTestCase
from docx import Document as DocxDocument

from editor.docx_template import render_from_template


def _row_text(row) -> str:
    return " ".join(cell.text for cell in row.cells if cell.text).strip()


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(without_marks.upper().split())


def _contains_heading(table, heading: str) -> bool:
    target = _normalize(heading)
    for row in table.rows:
        if target in _normalize(_row_text(row)):
            return True
    return False


class DocxTemplateLocalizationTests(SimpleTestCase):
    def test_export_english_localizes_core_headings_and_labels(self) -> None:
        template_path = Path(__file__).resolve().parents[2] / "templates" / "cv_template.docx"
        structured = {
            "basics": {
                "name": "Test Candidate",
                "description": "Profile",
                "email": "",
                "phone": "",
                "linkedin": "",
                "github": "",
                "country": "",
                "city": "",
            },
            "experience": [
                {
                    "role": "Engineer",
                    "company": "ACME",
                    "technologies": "Python",
                    "start": "2023-01",
                    "end": "",
                    "city": "Santiago",
                    "country": "Chile",
                    "highlights": ["Built feature"],
                }
            ],
            "education": [
                {
                    "degree": "Computer Science",
                    "institution": "University X",
                    "start": "2018-01",
                    "end": "2022-12",
                    "city": "Santiago",
                    "country": "Chile",
                    "honors": "Magna Cum Laude",
                }
            ],
            "skills": [{"category": "Tools", "items": "Python, SQL"}],
            "extra_sections": [],
            "meta": {"core_order": "experience,education,skills"},
        }

        output = render_from_template(structured, template_path, ui_lang="en")
        doc = DocxDocument(io.BytesIO(output))
        table = doc.tables[0]

        self.assertTrue(_contains_heading(table, "PROFESSIONAL EXPERIENCE"))
        self.assertTrue(_contains_heading(table, "EDUCATION"))
        self.assertTrue(_contains_heading(table, "SKILLS"))

        all_rows = " | ".join(_row_text(row) for row in table.rows)
        self.assertIn("Present", all_rows)
        self.assertIn("Honors:", all_rows)
