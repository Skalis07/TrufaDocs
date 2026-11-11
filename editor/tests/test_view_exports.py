"""Smokes end-to-end para las vistas de exportacion."""

import io
import zipfile
from unittest.mock import patch
from xml.etree import ElementTree as etree

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from docx import Document as DocxDocument


DOCX_EXPORT_URL = "/text/export/docx/"
PDF_EXPORT_URL = "/text/export/pdf/"


def _export_payload() -> dict:
    """Payload minimo pero realista para recorrer parseo y export."""
    return {
        "ui_lang": "en",
        "filename": "qa-cv",
        "doc_font": "Arial",
        "name": "Test Candidate",
        "description": "Profile",
        "email": "test@example.com",
        "phone": "+56 9 5555 5555",
        "linkedin": "linkedin.com/in/test",
        "github": "github.com/test",
        "country": "Chile",
        "city": "Santiago",
        "core_order": "experience,education,skills,extra-1",
        "module_order_map": "",
        "exp_role": ["Engineer"],
        "exp_company": ["ACME"],
        "exp_start": ["2023-01"],
        "exp_end": [""],
        "exp_city": ["Santiago"],
        "exp_country": ["Chile"],
        "exp_tech": ["Python"],
        "exp_highlights": ["Built feature\nLed migration"],
        "edu_degree": ["Computer Science"],
        "edu_institution": ["University X"],
        "edu_start": ["2018-01"],
        "edu_end": ["2022-12"],
        "edu_city": ["Santiago"],
        "edu_country": ["Chile"],
        "edu_items": ["Magna Cum Laude\nResearch scholarship"],
        "skill_category": ["Tools"],
        "skill_items": ["Python, SQL"],
        "extra_section_id": ["extra-1"],
        "extra_title": ["Projects"],
        "extra_mode": ["detailed"],
        "extra_entry_section": ["extra-1"],
        "extra_entry_subtitle": [""],
        "extra_entry_title": ["Platform Project"],
        "extra_entry_where": ["ACME Labs"],
        "extra_entry_tech": ["Django"],
        "extra_entry_start": ["2024-01"],
        "extra_entry_end": ["2024-12"],
        "extra_entry_city": ["Remote"],
        "extra_entry_country": ["Chile"],
        "extra_entry_items_si": [""],
        "extra_entry_items_detailed": ["Shipped v1\nImproved latency"],
    }


def _docx_text(blob: bytes) -> str:
    """Extrae texto del DOCX para asserts de humo."""
    doc = DocxDocument(io.BytesIO(blob))
    chunks: list[str] = []
    chunks.extend(paragraph.text for paragraph in doc.paragraphs if paragraph.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                text = cell.text.strip()
                if text:
                    chunks.append(text)
    return " | ".join(chunks)


def _zip_xml(blob: bytes, name: str) -> bytes:
    """Lee un XML interno del DOCX para asserts sobre fuente/estilos."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        return zf.read(name)


def _font_names_by_xml(blob: bytes) -> dict[str, set[str]]:
    """Extrae todos los nombres de fuente declarados en los XML del DOCX."""
    fonts: dict[str, set[str]] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            root = etree.fromstring(zf.read(name))
            found: set[str] = set()
            for elem in root.iter():
                local_tag = elem.tag.split("}")[-1]
                if local_tag == "rFonts":
                    for attr_name, attr_val in elem.attrib.items():
                        local_attr = attr_name.split("}")[-1]
                        if local_attr in {"ascii", "hAnsi", "eastAsia", "cs"}:
                            found.add(str(attr_val))
                elif local_tag in {"fontScheme", "majorFont", "minorFont"}:
                    continue
                elif "}" in elem.tag and elem.tag.split("}")[-1] in {
                    "latin",
                    "ea",
                    "cs",
                    "font",
                } and "typeface" in elem.attrib:
                    found.add(str(elem.attrib["typeface"]))
                elif local_tag == "font":
                    name_attr = next((value for key, value in elem.attrib.items() if key.split("}")[-1] == "name"), None)
                    if name_attr:
                        found.add(str(name_attr))
                elif local_tag == "altName":
                    val_attr = next((value for key, value in elem.attrib.items() if key.split("}")[-1] == "val"), None)
                    if val_attr:
                        found.add(str(val_attr))
            if found:
                fonts[name] = found
    return fonts


class ViewExportSmokeTests(SimpleTestCase):
    """Verifica cableado entre POST estructurado, parser y exportacion."""

    def test_docx_upload_preserves_existing_undated_education_entries(self) -> None:
        """Explicit institutions still delimit entries when no dates are available."""
        document = DocxDocument()
        for text in ("Alex Example", "Professional profile", "EDUCATION", "Example University", "Bachelor of Science", "Second University", "Master of Science"):
            document.add_paragraph(text)
        blob = io.BytesIO()
        document.save(blob)
        response = self.client.post("/upload/", {"file": SimpleUploadedFile("ordinary.docx", blob.getvalue())})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([entry["institution"] for entry in response.context["structured"]["education"]], ["Example University", "Second University"])

    def test_docx_upload_keeps_undated_institutions_without_organization_keywords(self) -> None:
        """Degree context delimits institutions without relying on their names."""
        document = DocxDocument()
        for text in ("Alex Example", "Professional profile", "EDUCATION", "Aurora Institute", "Bachelor of Science", "Meridian Conservatory", "Master of Science"):
            document.add_paragraph(text)
        blob = io.BytesIO()
        document.save(blob)
        response = self.client.post("/upload/", {"file": SimpleUploadedFile("ordinary.docx", blob.getvalue())})
        self.assertEqual(response.status_code, 200)
        education = response.context["structured"]["education"]
        self.assertEqual([(entry["institution"], entry["degree"]) for entry in education], [("Aurora Institute", "Bachelor of Science"), ("Meridian Conservatory", "Master of Science")])

    def test_docx_upload_does_not_reclassify_pre_date_prose_as_technologies(self) -> None:
        """Ordinary body prose remains a highlight even before the date line."""
        for prose in ("Maintained distributed services.", "Maintained distributed services"):
            with self.subTest(prose=prose):
                document = DocxDocument()
                for text in ("Alex Example", "Professional profile", "EXPERIENCIA", "Example Company", "Software Engineer", prose, "Jan 2021 - Dec 2022", "- Delivered reliable releases."):
                    document.add_paragraph(text)
                blob = io.BytesIO()
                document.save(blob)
                response = self.client.post("/upload/", {"file": SimpleUploadedFile("ordinary.docx", blob.getvalue())})
                self.assertEqual(response.status_code, 200)
                jobs = response.context["structured"]["experience"]
                self.assertEqual(len(jobs), 1)
                self.assertEqual(jobs[0]["technologies"], "")
                self.assertEqual(jobs[0]["highlights"], [prose, "Delivered reliable releases."])

    def test_export_docx_returns_a_generated_document_from_structured_post(self) -> None:
        """DOCX debe generarse desde el POST actual sin perder items ni extras."""
        response = self.client.post(DOCX_EXPORT_URL, _export_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertIn('filename="qa-cv.docx"', response["Content-Disposition"])

        exported_text = _docx_text(response.content)
        self.assertIn("Engineer", exported_text)
        self.assertIn("Built feature", exported_text)
        self.assertIn("University X", exported_text)
        self.assertIn("Magna Cum Laude", exported_text)
        self.assertIn("PROJECTS", exported_text)
        self.assertIn("Platform Project", exported_text)
        self.assertNotIn("Honors:", exported_text)

    def test_export_pdf_uses_generated_docx_before_conversion(self) -> None:
        """PDF debe generar DOCX intermedio y delegar la conversion final."""
        with patch("editor.views._convert_docx_bytes_to_pdf", return_value=(b"%PDF-1.4 fake", None)) as mocked:
            response = self.client.post(PDF_EXPORT_URL, _export_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="qa-cv.pdf"', response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-1.4 fake")
        mocked.assert_called_once()
        (docx_bytes,), _ = mocked.call_args
        self.assertTrue(docx_bytes)

    def test_export_docx_forces_selected_font_across_content_and_defaults(self) -> None:
        """La fuente elegida debe quedar aplicada en contenido, estilos, theme y numbering."""
        payload = _export_payload()
        payload["doc_font"] = "STIX Two Text"

        response = self.client.post(DOCX_EXPORT_URL, payload)

        self.assertEqual(response.status_code, 200)
        fonts_by_xml = _font_names_by_xml(response.content)
        self.assertTrue(fonts_by_xml)
        for xml_name, font_names in fonts_by_xml.items():
            self.assertEqual(font_names, {"STIX Two Text"}, msg=xml_name)

    def test_export_docx_english_localizes_current_end_from_post_token(self) -> None:
        """Si el POST trae `Present`, la exportación EN debe renderizar `Present`, no `Actualidad`."""
        payload = _export_payload()
        payload["exp_end"] = ["Present"]
        payload["edu_end"] = ["Present"]

        response = self.client.post(DOCX_EXPORT_URL, payload)

        self.assertEqual(response.status_code, 200)
        exported_text = _docx_text(response.content)
        self.assertIn("Present", exported_text)
        self.assertNotIn("Actualidad", exported_text)

    def test_generated_docx_reimports_without_splitting_entries_or_losing_items(self) -> None:
        """The public export/upload path must preserve both supported languages."""
        for language in ("en", "es"):
            with self.subTest(language=language):
                payload = _export_payload()
                payload.update({
                    "ui_lang": language,
                    "exp_company": ["Example Company", "Second Company"],
                    "exp_role": ["Software Engineer", "Platform Engineer"],
                    "exp_start": ["2021-01", "2023-07"],
                    "exp_end": ["2023-06", "2025-12"],
                    "exp_city": ["Santiago", "Santiago"],
                    "exp_country": ["Chile", "Chile"],
                    "exp_tech": ["Python", "SQL"],
                    "exp_highlights": ["Built Service\nLed Migration", "Improved Performance"],
                    "edu_institution": ["Example University", "Second University"],
                    "edu_degree": ["Computer Science", "Software Engineering"],
                    "edu_start": ["2015-03", "2020-01"],
                    "edu_end": ["2019-12", "2020-12"],
                    "edu_city": ["Santiago", "Santiago"],
                    "edu_country": ["Chile", "Chile"],
                    "edu_items": ["Research Scholarship\nGraduation Project", "Advanced Course"],
                })
                exported = self.client.post(DOCX_EXPORT_URL, payload)
                self.assertEqual(exported.status_code, 200)
                uploaded = self.client.post("/upload/", {
                    "ui_lang": language,
                    "file": SimpleUploadedFile("generated.docx", exported.content),
                })
                self.assertEqual(uploaded.status_code, 200)
                structured = uploaded.context["structured"]
                jobs = structured["experience"]
                self.assertEqual(len(jobs), 2)
                for index in range(2):
                    for field in ("company", "role", "start", "end", "city", "country", "technologies"):
                        key = "exp_tech" if field == "technologies" else f"exp_{field}"
                        self.assertEqual(jobs[index][field], payload[key][index])
                    self.assertEqual(jobs[index]["highlights"], payload["exp_highlights"][index].splitlines())
                education = structured["education"]
                self.assertEqual(len(education), 2)
                for index in range(2):
                    for field in ("institution", "degree", "start", "end", "city", "country"):
                        self.assertEqual(education[index][field], payload[f"edu_{field}"][index])
                    self.assertEqual(education[index]["items"], payload["edu_items"][index].splitlines())
                self.assertEqual(structured["basics"]["name"], payload["name"])
                self.assertEqual(structured["basics"]["email"], payload["email"])
                self.assertEqual(structured["skills"][0]["items"], "Python, SQL")
                self.assertEqual(structured["meta"]["core_order"], "experience,education,skills,extra-0")
