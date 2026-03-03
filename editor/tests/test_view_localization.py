"""Pruebas de regresion para mensajes localizados en la vista de upload."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

UPLOAD_URL = "/upload/"


class ViewLocalizationTests(SimpleTestCase):
    """Valida que los errores de upload respeten el idioma de la interfaz."""

    def test_upload_missing_file_error_defaults_to_spanish(self) -> None:
        """Si no se envia idioma, el mensaje por defecto debe quedar en espanol."""
        response = self.client.post(UPLOAD_URL, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selecciona un archivo .docx o .pdf.")

    def test_upload_missing_file_error_uses_english_when_requested(self) -> None:
        """Si ui_lang='en', el mensaje de archivo faltante debe salir en ingles."""
        response = self.client.post(UPLOAD_URL, {"ui_lang": "en"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please select a .docx or .pdf file.")

    def test_upload_unsupported_extension_error_uses_english_when_requested(self) -> None:
        """Con idioma ingles, las extensiones no soportadas deben avisar en ingles."""
        uploaded = SimpleUploadedFile("cv.txt", b"plain text", content_type="text/plain")
        response = self.client.post(UPLOAD_URL, {"ui_lang": "en", "file": uploaded})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported format. Use .docx or .pdf.")
