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
