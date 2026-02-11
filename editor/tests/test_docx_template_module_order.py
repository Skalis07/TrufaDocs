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


def _find_heading_index(table, heading: str) -> int | None:
    target = _normalize(heading)
    for idx, row in enumerate(table.rows):
        if target in _normalize(_row_text(row)):
            return idx
    return None


class ModuleOrderSpacingTests(SimpleTestCase):
    def test_extra_between_experience_and_education_keeps_separator(self) -> None:
        template_path = Path(__file__).resolve().parents[2] / "templates" / "cv_template.docx"
        structured = {
            "basics": {
                "name": "Test User",
                "description": "Perfil de prueba.",
                "email": "",
                "phone": "",
                "linkedin": "",
                "github": "",
                "country": "",
                "city": "",
            },
            "experience": [
                {
                    "role": "Software Engineer",
                    "company": "ACME",
                    "technologies": "Python, Django",
                    "start": "2020-01",
                    "end": "2022-12",
                    "city": "Caracas",
                    "country": "Venezuela",
                    "highlights": ["Implementacion principal"],
                }
            ],
            "education": [
                {
                    "degree": "Ingenieria de Sistemas",
                    "institution": "Universidad X",
                    "start": "2015-01",
                    "end": "2019-12",
                    "city": "Caracas",
                    "country": "Venezuela",
                    "honors": "",
                }
            ],
            "skills": [{"category": "Tecnicas", "items": "Python, SQL"}],
            "extra_sections": [
                {
                    "section_id": "extra-1",
                    "title": "Proyectos",
                    "mode": "subtitle_items",
                    "entries": [{"subtitle": "Proyecto A", "items": ["Detalle relevante"]}],
                }
            ],
            "meta": {"core_order": "experience,extra-1,education,skills"},
        }

        output = render_from_template(structured, template_path)
        doc = DocxDocument(io.BytesIO(output))
        table = doc.tables[0]

        education_idx = _find_heading_index(table, "educacion")
        self.assertIsNotNone(education_idx)
        assert education_idx is not None
        self.assertGreater(education_idx, 1)

        previous_row_text = _row_text(table.rows[education_idx - 1])
        self.assertEqual(previous_row_text, "")

        experience_idx = _find_heading_index(table, "experiencia")
        projects_idx = _find_heading_index(table, "proyectos")
        self.assertIsNotNone(experience_idx)
        self.assertIsNotNone(projects_idx)
        assert experience_idx is not None and projects_idx is not None
        self.assertGreater(projects_idx, experience_idx)
        self.assertLess(projects_idx, education_idx)
