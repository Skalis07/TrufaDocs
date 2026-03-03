"""Pruebas para convertir POSTs sparsos en estructura normalizada."""

from django.http import QueryDict
from django.test import SimpleTestCase

from editor.structure import structure_from_post


def _base_querydict() -> QueryDict:
    """Crea el payload minimo que `structure_from_post` espera recibir."""
    query_dict = QueryDict("", mutable=True)

    for key, value in {
        "name": "Test User",
        "description": "",
        "email": "",
        "phone": "",
        "linkedin": "",
        "github": "",
        "country": "",
        "city": "",
        "core_order": "experience,education,skills,extra-1,extra-2",
        "module_order_map": "",
    }.items():
        query_dict.appendlist(key, value)

    # El parser espera al menos una fila por cada familia de modulos core.
    for key in [
        "experience_role",
        "experience_company",
        "experience_technologies",
        "experience_start",
        "experience_end",
        "experience_city",
        "experience_country",
        "experience_highlights",
    ]:
        query_dict.appendlist(key, "")

    for key in [
        "education_degree",
        "education_institution",
        "education_start",
        "education_end",
        "education_city",
        "education_country",
        "education_honors",
    ]:
        query_dict.appendlist(key, "")

    query_dict.appendlist("skill_category", "")
    query_dict.appendlist("skill_items", "")
    return query_dict


class StructureFromPostSparseItemsTests(SimpleTestCase):
    """Garantiza que arrays sparsos de extras mantengan alineacion por seccion."""

    def test_sparse_mode_specific_items_do_not_shift_between_sections(self) -> None:
        """Los arrays por modo no deben correrse entre secciones al normalizar."""
        query_dict = _base_querydict()

        # Dos secciones: una "detailed" y otra "subtitle_items".
        query_dict.appendlist("extra_section_id", "extra-1")
        query_dict.appendlist("extra_title", "TITULO SECCION 1")
        query_dict.appendlist("extra_mode", "detailed")
        query_dict.appendlist("extra_section_id", "extra-2")
        query_dict.appendlist("extra_title", "TITULO SECCION 2")
        query_dict.appendlist("extra_mode", "subtitle_items")

        # Orden canonico de entries enviado por el navegador.
        for sid in ["extra-1", "extra-1", "extra-2", "extra-2", "extra-2"]:
            query_dict.appendlist("extra_entry_section", sid)

        # Payload sparso:
        # - subtitle/items incluye solo filas subtitle_items (3)
        # - arrays detailed incluyen solo filas detailed (2)
        for value in ["SUB1", "SUB2424,,12,242, 4,124,2, ,,", ""]:
            query_dict.appendlist("extra_entry_subtitle", value)
        for value in ["R1", "R2"]:
            query_dict.appendlist("extra_entry_title", value)
        for value in ["E1", "E2"]:
            query_dict.appendlist("extra_entry_where", value)
        for value in ["", "321, 111, OEEOOE ASD, JEJEM, JAJA"]:
            query_dict.appendlist("extra_entry_tech", value)
        for value in ["2013-03", "2013-12"]:
            query_dict.appendlist("extra_entry_start", value)
        for value in ["2030-02", "Actualidad"]:
            query_dict.appendlist("extra_entry_end", value)
        for value in ["Miami", "LA SUPER CIUDAD GUAIRA"]:
            query_dict.appendlist("extra_entry_city", value)
        for value in ["Chile", "Chile"]:
            query_dict.appendlist("extra_entry_country", value)

        query_dict.appendlist("extra_entry_items_detailed", "")
        query_dict.appendlist("extra_entry_items_detailed", "h1\nh2\nh3\ng4")

        query_dict.appendlist("extra_entry_items_si", "1, 2, 3")
        query_dict.appendlist("extra_entry_items_si", "")
        query_dict.appendlist("extra_entry_items_si", "SDFSDFJ12,2 ,4123,412,")

        structured = structure_from_post(query_dict)
        extras = structured.get("extra_sections") or []
        self.assertEqual(len(extras), 2)

        detailed_section = extras[0]
        subtitle_items_section = extras[1]

        self.assertEqual(detailed_section.get("title"), "TITULO SECCION 1")
        self.assertEqual(detailed_section.get("mode"), "detailed")
        self.assertEqual(len(detailed_section.get("entries") or []), 2)
        self.assertEqual(detailed_section["entries"][0].get("title"), "R1")
        self.assertEqual(detailed_section["entries"][0].get("where"), "E1")
        self.assertEqual(detailed_section["entries"][1].get("title"), "R2")
        self.assertEqual(detailed_section["entries"][1].get("where"), "E2")
        self.assertEqual((detailed_section["entries"][0].get("items") or []), [])
        self.assertEqual(
            (detailed_section["entries"][1].get("items") or []), ["h1", "h2", "h3", "g4"]
        )

        self.assertEqual(subtitle_items_section.get("title"), "TITULO SECCION 2")
        self.assertEqual(subtitle_items_section.get("mode"), "subtitle_items")
        self.assertEqual(len(subtitle_items_section.get("entries") or []), 3)
        self.assertEqual(subtitle_items_section["entries"][0].get("subtitle"), "SUB1")
        self.assertEqual((subtitle_items_section["entries"][0].get("items") or []), ["1, 2, 3"])
        self.assertEqual(
            subtitle_items_section["entries"][1].get("subtitle"),
            "SUB2424,,12,242, 4,124,2, ,,",
        )
        self.assertEqual(
            subtitle_items_section["entries"][2].get("subtitle"), "SDFSDFJ12,2 ,4123,412,"
        )
