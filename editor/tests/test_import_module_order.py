import io
from unittest.mock import patch

from django.test import SimpleTestCase

from editor.pdf_parse.bridge import parse_pdf_to_structure
from editor.structure import parse_resume


class ImportModuleOrderTests(SimpleTestCase):
    def test_parse_resume_preserves_detected_module_order_with_extra_between_core_sections(self) -> None:
        text = """
Persona Ejemplo
Perfil profesional

EXPERIENCIA
Desarrollador
Empresa X
Ene 2020 - Ene 2021

PROYECTOS
Proyecto Uno

EDUCACION
Ingenieria
Universidad X
Mar 2015 - Nov 2019

HABILIDADES
Lenguajes
Python, SQL
"""
        structured = parse_resume(text)
        core_order = (structured.get("meta") or {}).get("core_order")
        self.assertEqual(core_order, "experience,extra-0,education,skills")

    def test_parse_pdf_preserves_detected_module_order_with_extra_between_core_sections(self) -> None:
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
                {"title": "EXPERIENCIA PROFESIONAL", "raw": [{"text": "exp"}]},
                {"title": "PROYECTOS", "raw": [{"text": "extra"}]},
                {"title": "EDUCACIÓN", "raw": [{"text": "edu"}]},
                {"title": "HABILIDADES", "raw": [{"text": "skills"}]},
            ],
        }

        with (
            patch("editor.pdf_parse.bridge.extract_lines", return_value=[object()]),
            patch("editor.pdf_parse.bridge.assemble_sections", return_value=assembled),
            patch("editor.pdf_parse.bridge.parse_experience", return_value=[]),
            patch("editor.pdf_parse.bridge.parse_education", return_value=[]),
            patch("editor.pdf_parse.bridge.parse_skills", return_value=[]),
            patch(
                "editor.pdf_parse.bridge._parse_extra_section",
                return_value={
                    "section_id": "extra-0",
                    "title": "PROYECTOS",
                    "mode": "detailed",
                    "entries": [],
                },
            ),
        ):
            structured, error = parse_pdf_to_structure(io.BytesIO(b"fake"))

        self.assertIsNone(error)
        core_order = (structured.get("meta") or {}).get("core_order")
        self.assertEqual(core_order, "experience,extra-0,education,skills")

    def test_parse_pdf_recognizes_english_core_titles_as_core_sections(self) -> None:
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
                {"title": "PROFESSIONAL EXPERIENCE", "raw": [{"text": "exp"}]},
                {"title": "PROJECTS", "raw": [{"text": "extra"}]},
                {"title": "EDUCATION", "raw": [{"text": "edu"}]},
                {"title": "SKILLS", "raw": [{"text": "skills"}]},
            ],
        }

        with (
            patch("editor.pdf_parse.bridge.extract_lines", return_value=[object()]),
            patch("editor.pdf_parse.bridge.assemble_sections", return_value=assembled),
            patch("editor.pdf_parse.bridge.parse_experience", return_value=[]),
            patch("editor.pdf_parse.bridge.parse_education", return_value=[]),
            patch("editor.pdf_parse.bridge.parse_skills", return_value=[]),
            patch(
                "editor.pdf_parse.bridge._parse_extra_section",
                return_value={
                    "section_id": "extra-0",
                    "title": "PROJECTS",
                    "mode": "detailed",
                    "entries": [],
                },
            ) as parse_extra_mock,
        ):
            structured, error = parse_pdf_to_structure(io.BytesIO(b"fake"))

        self.assertIsNone(error)
        core_order = (structured.get("meta") or {}).get("core_order")
        self.assertEqual(core_order, "experience,extra-0,education,skills")
        self.assertEqual(len(structured.get("extra_sections") or []), 1)
        self.assertEqual(parse_extra_mock.call_count, 1)
