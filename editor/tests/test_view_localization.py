from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase


class ViewLocalizationTests(SimpleTestCase):
    def test_upload_missing_file_error_defaults_to_spanish(self) -> None:
        response = self.client.post("/upload/", {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selecciona un archivo .docx o .pdf.")

    def test_upload_missing_file_error_uses_english_when_requested(self) -> None:
        response = self.client.post("/upload/", {"ui_lang": "en"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please select a .docx or .pdf file.")

    def test_upload_unsupported_extension_error_uses_english_when_requested(self) -> None:
        uploaded = SimpleUploadedFile("cv.txt", b"plain text", content_type="text/plain")
        response = self.client.post("/upload/", {"ui_lang": "en", "file": uploaded})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported format. Use .docx or .pdf.")
