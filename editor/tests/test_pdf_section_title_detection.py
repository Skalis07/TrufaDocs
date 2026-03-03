"""Regresiones de deteccion de titulos de seccion en parseo PDF."""

from django.test import SimpleTestCase

from editor.pdf_parse.assemble import is_section_title
from editor.pdf_parse.extract import Line


class PdfSectionTitleDetectionTests(SimpleTestCase):
    """Verifica que lineas de contenido no se clasifiquen como headings."""

    def test_pipe_separated_uppercase_content_is_not_section_title(self) -> None:
        """Evita falsos positivos en lineas tipo 'ROL | CIUDAD'."""
        line = Line(
            text="E2 | LA SUPER CIUDAD",
            page=1,
            x0=0.0,
            top=0.0,
            x1=100.0,
            bottom=10.0,
            is_bullet=False,
            has_email=False,
            has_phone=False,
            has_url=False,
            is_date_range=False,
            is_open_date_range=False,
            has_rule_below=False,
            uppercase_ratio=1.0,
            size_ratio=1.0,
            is_bold=True,
        )

        self.assertFalse(is_section_title(line))
