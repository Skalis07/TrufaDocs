"""Regresiones de render para items de educacion."""

from django.test import RequestFactory, SimpleTestCase

from editor.views import _render_text_editor


class ViewEducationItemsTests(SimpleTestCase):
    """Evita que `education.items` choque con `dict.items` en la template."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_render_normalizes_legacy_education_without_items_key(self) -> None:
        """Si falta `items`, la UI no debe iterar pares tipo `('city', '...')`."""
        request = self.factory.get("/")
        structured = {
            "meta": {"core_order": "experience,education,skills"},
            "basics": {
                "name": "",
                "description": "",
                "email": "",
                "phone": "",
                "linkedin": "",
                "github": "",
                "city": "",
                "country": "",
            },
            "experience": [
                {
                    "role": "",
                    "company": "",
                    "start": "",
                    "end": "",
                    "city": "",
                    "country": "",
                    "technologies": "",
                    "highlights": [],
                }
            ],
            "education": [
                {
                    "degree": "Ingeniería",
                    "institution": "Universidad X",
                    "start": "",
                    "end": "",
                    "city": "Ciudad Demo",
                    "country": "País Demo",
                    "honors": "Distinción académica",
                }
            ],
            "skills": [{"category": "", "items": ""}],
            "extra_sections": [],
        }

        response = _render_text_editor(request, structured, filename="documento")
        html = response.content.decode("utf-8")

        self.assertIn("Distinción académica", html)
        self.assertNotIn("('city', 'Ciudad Demo')", html)
        self.assertNotIn("('country', 'País Demo')", html)

    def test_render_subtitle_items_textarea_preserves_line_breaks_without_semicolons(self) -> None:
        """La UI debe cargar items subtitle_items uno por línea, no unidos con `;`."""
        request = self.factory.get("/")
        structured = {
            "meta": {"core_order": "experience,education,skills,extra-1"},
            "basics": {
                "name": "",
                "description": "",
                "email": "",
                "phone": "",
                "linkedin": "",
                "github": "",
                "city": "",
                "country": "",
            },
            "experience": [
                {
                    "role": "",
                    "company": "",
                    "start": "",
                    "end": "",
                    "city": "",
                    "country": "",
                    "technologies": "",
                    "highlights": [],
                }
            ],
            "education": [],
            "skills": [{"category": "", "items": ""}],
            "extra_sections": [
                {
                    "section_id": "extra-1",
                    "title": "Publicaciones",
                    "mode": "subtitle_items",
                    "entries": [
                        {
                            "subtitle": "Título genérico",
                            "items": [
                                "Referencia uno con comas, pero sin separador artificial",
                                "Referencia dos independiente",
                            ],
                        }
                    ],
                }
            ],
        }

        response = _render_text_editor(request, structured, filename="documento")
        html = response.content.decode("utf-8")

        marker = 'name="extra_entry_items_si" rows="3">'
        self.assertIn(marker, html)
        textarea_value = html.split(marker, 1)[1].split("</textarea>", 1)[0]

        self.assertIn("Referencia uno con comas, pero sin separador artificial", textarea_value)
        self.assertIn("Referencia dos independiente", textarea_value)
        self.assertIn("\n", textarea_value)
        self.assertNotIn(
            'Referencia uno con comas, pero sin separador artificial; Referencia dos independiente',
            html,
        )
