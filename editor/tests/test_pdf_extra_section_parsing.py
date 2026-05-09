"""Pruebas de parseo de secciones extra de PDF hacia formas estables."""

from django.test import SimpleTestCase

from editor.pdf_parse.bridge import _parse_extra_section


def _line(
    text: str,
    *,
    indent: float = 0.0,
    is_bullet: bool = False,
    is_bold: bool = False,
) -> dict:
    """Construye una linea sintetica con el formato esperado por el parser."""
    return {
        "text": text,
        "indent": indent,
        "is_bullet": is_bullet,
        "is_bold": is_bold,
        "size_ratio": 1.0,
        "ends_with_colon": False,
    }


class PdfExtraSectionParsingTests(SimpleTestCase):
    """Cubre deteccion de forma y parseo para secciones no core del PDF."""

    def test_project_like_extra_prefers_experience_shape(self) -> None:
        """Entradas tipo proyecto con rol/fecha deben mapear a modo detailed."""
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
        """Secciones con solo bullets deben conservar modo subtitle_items."""
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
        """Titulos en ingles de proyectos deben activar parseo detailed igual."""
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

    def test_publication_like_wrapped_bullet_keeps_subtitle_items_mode(self) -> None:
        """Un subtítulo largo partido no debe convertir publicaciones en modo detailed."""
        raw_lines = [
            _line(
                "Long Research Title About Generated Features for Imbalanced Medical",
                is_bullet=True,
                indent=14,
                is_bold=True,
            ),
            _line("Data", indent=32, is_bold=True),
            _line(
                "Author A., Author B., & Author C. Applied AI for Health: Workshop 2025",
                indent=32,
            ),
            _line(
                "Proceedings, Example Venue. Series 42, 10-20. DOI 10.1000/example",
                indent=32,
            ),
        ]

        section = _parse_extra_section("PUBLICACIONES", raw_lines, 3)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "subtitle_items")
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0].get("subtitle"),
            "Long Research Title About Generated Features for Imbalanced Medical Data",
        )
        self.assertEqual(
            entries[0].get("items"),
            [
                "Author A., Author B., & Author C. Applied AI for Health: Workshop 2025 Proceedings, Example Venue. Series 42, 10-20. DOI 10.1000/example",
            ],
        )

    def test_publication_inline_reference_does_not_split_after_trailing_comma(self) -> None:
        """Una referencia corrida no debe convertirse en dos líneas por una coma final."""
        raw_lines = [
            _line("Generic Publication Title", is_bullet=True, indent=14, is_bold=True),
            _line("Author A., Author B. Example Conference 2025,"),
            _line("Proceedings, Example Venue. Pages 10-20. DOI 10.1000/example"),
        ]

        section = _parse_extra_section("PUBLICACIONES", raw_lines, 4)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "subtitle_items")
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0].get("items"),
            [
                "Author A., Author B. Example Conference 2025, Proceedings, Example Venue. Pages 10-20. DOI 10.1000/example"
            ],
        )

    def test_publication_inline_reference_does_not_split_after_trailing_semicolon(self) -> None:
        """Una referencia corrida tampoco debe partirse si la línea previa termina en `;`."""
        raw_lines = [
            _line("Generic Publication Title", is_bullet=True, indent=14, is_bold=True),
            _line("Author A., Author B. Example Conference 2025;"),
            _line("Proceedings, Example Venue. Pages 10-20. DOI 10.1000/example"),
        ]

        section = _parse_extra_section("PUBLICACIONES", raw_lines, 5)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "subtitle_items")
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0].get("items"),
            [
                "Author A., Author B. Example Conference 2025; Proceedings, Example Venue. Pages 10-20. DOI 10.1000/example"
            ],
        )

    def test_publication_inline_reference_does_not_split_after_year_without_separator(self) -> None:
        """Una continuación bibliográfica no debe partirse aunque la línea previa termine en año."""
        raw_lines = [
            _line("Generic Publication Title Part One", is_bullet=True, indent=14, is_bold=True),
            _line("Part Two", indent=32, is_bold=True),
            _line("Author A., Author B. Example Conference / Example Event 2025", indent=32),
            _line("Workshops, Example City, Example Country. Series 42, 132 – 148. DOI 10.1000/example", indent=32),
        ]

        section = _parse_extra_section("PUBLICACIONES", raw_lines, 6)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "subtitle_items")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].get("subtitle"), "Generic Publication Title Part One Part Two")
        self.assertEqual(
            entries[0].get("items"),
            [
                "Author A., Author B. Example Conference / Example Event 2025 Workshops, Example City, Example Country. Series 42, 132-148. DOI 10.1000/example"
            ],
        )

    def test_publication_doi_colon_is_preserved_inside_reference(self) -> None:
        """`DOI:` dentro de una referencia no debe separarse ni perder los dos puntos."""
        raw_lines = [
            _line("Generic Publication Title", is_bullet=True, indent=14, is_bold=True),
            _line("Part Two", indent=32, is_bold=True),
            _line("Author A., Author B. Example Conference 2025", indent=32),
            _line("Workshops, Example City, Example Country. Series 42, 132-148. DOI: 10.1000/example", indent=32),
        ]

        section = _parse_extra_section("PUBLICACIONES", raw_lines, 7)
        entries = section.get("entries") or []

        self.assertEqual(section.get("mode"), "subtitle_items")
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0].get("items"),
            [
                "Author A., Author B. Example Conference 2025 Workshops, Example City, Example Country. Series 42, 132-148. DOI: 10.1000/example"
            ],
        )
