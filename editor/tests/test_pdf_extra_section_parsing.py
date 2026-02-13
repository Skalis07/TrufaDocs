from django.test import SimpleTestCase

from editor.pdf_parse.bridge import _parse_extra_section


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


class PdfExtraSectionParsingTests(SimpleTestCase):
    def test_project_like_extra_prefers_experience_shape(self) -> None:
        raw_lines = [
            _line("Example Labs | Remoto", is_bold=True),
            _line("Desarrollador | Nov 2025 – Ene 2026"),
            _line("Astro, TypeScript, Tailwind, Vercel, Docker"),
            _line("Desarrollé una web app embebible en Notion.", indent=14, is_bullet=True),
            _line("Implementé enfoque en UX con modo día/noche.", indent=14, is_bullet=True),
            _line("Acme Platform | Remoto", is_bold=True),
            _line("Desarrollador | Ene 2026 – Feb 2026"),
            _line("Python, Django, JavaScript, CSS, HTML"),
            _line("Construí pipeline de parsing para CVs.", indent=14, is_bullet=True),
        ]

        section = _parse_extra_section("PROYECTOS", raw_lines, 0)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "detailed")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].get("where"), "Example Labs")
        self.assertEqual(entries[0].get("title"), "Desarrollador")
        self.assertEqual(entries[0].get("start"), "2025-11")
        self.assertEqual(entries[0].get("end"), "2026-01")
        self.assertEqual(entries[0].get("city"), "Remoto")
        self.assertGreaterEqual(len(entries[0].get("items") or []), 1)

    def test_bullet_only_extra_keeps_subtitle_items_mode(self) -> None:
        raw_lines = [
            _line("AWS Cloud Practitioner", is_bullet=True, indent=14),
            _line("Scrum Fundamentals Certified", is_bullet=True, indent=14),
        ]

        section = _parse_extra_section("CERTIFICACIONES", raw_lines, 1)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "subtitle_items")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].get("subtitle"), "AWS Cloud Practitioner")
        self.assertEqual(entries[1].get("subtitle"), "Scrum Fundamentals Certified")

    def test_projects_title_in_english_prefers_experience_shape(self) -> None:
        raw_lines = [
            _line("Example Labs | Remote", is_bold=True),
            _line("Developer | Nov 2025 – Jan 2026"),
            _line("Astro, TypeScript, Tailwind, Vercel, Docker"),
            _line("Built a production-ready Notion widget.", indent=14, is_bullet=True),
            _line("Acme Platform | Remote", is_bold=True),
            _line("Developer | Jan 2026 – Feb 2026"),
            _line("Python, Django, JavaScript, CSS, HTML"),
            _line("Implemented DOCX/PDF parsing pipeline.", indent=14, is_bullet=True),
        ]

        section = _parse_extra_section("PROJECTS", raw_lines, 2)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "detailed")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].get("start"), "2025-11")
        self.assertEqual(entries[0].get("end"), "2026-01")
        self.assertEqual(entries[1].get("start"), "2026-01")
        self.assertEqual(entries[1].get("end"), "2026-02")
        self.assertGreaterEqual(len(entries[0].get("items") or []), 1)
        self.assertGreaterEqual(len(entries[1].get("items") or []), 1)
