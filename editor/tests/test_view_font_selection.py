"""Pruebas para la seleccion de fuente de exportacion."""

from django.test import RequestFactory, SimpleTestCase

from editor.views import DEFAULT_FONT, FONT_CHOICES, _selected_font


class ViewFontSelectionTests(SimpleTestCase):
    """Garantiza que exportacion y UI usen siempre una fuente valida."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_selected_font_defaults_to_default_font_on_get(self) -> None:
        """La vista inicial debe partir con una fuente efectiva ya definida."""
        request = self.factory.get("/")
        self.assertEqual(_selected_font(request), DEFAULT_FONT)

    def test_selected_font_defaults_to_default_font_on_missing_or_invalid_post(self) -> None:
        """Posts vacios o invalidos no deben reactivar el modo plantilla."""
        missing = self.factory.post("/", {})
        invalid = self.factory.post("/", {"doc_font": "Comic Sans"})
        self.assertEqual(_selected_font(missing), DEFAULT_FONT)
        self.assertEqual(_selected_font(invalid), DEFAULT_FONT)

    def test_index_does_not_render_template_font_option(self) -> None:
        """La UI solo debe mostrar fuentes reales seleccionables."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'<option value="{DEFAULT_FONT}" selected>')
        self.assertNotContains(response, "Fuente de la plantilla")
        for font in FONT_CHOICES:
            self.assertContains(response, font)
