from django.http import QueryDict
from django.test import SimpleTestCase

from editor.structure import structure_from_post


def _base_querydict() -> QueryDict:
    qd = QueryDict("", mutable=True)

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
        qd.appendlist(key, value)

    # Minimum rows expected by structure_from_post for core modules.
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
        qd.appendlist(key, "")

    for key in [
        "education_degree",
        "education_institution",
        "education_start",
        "education_end",
        "education_city",
        "education_country",
        "education_honors",
    ]:
        qd.appendlist(key, "")

    qd.appendlist("skill_category", "")
    qd.appendlist("skill_items", "")
    return qd


class StructureFromPostSparseItemsTests(SimpleTestCase):
    def test_sparse_mode_specific_items_do_not_shift_between_sections(self) -> None:
        qd = _base_querydict()

        # Two sections: first detailed, second subtitle+items.
        qd.appendlist("extra_section_id", "extra-1")
        qd.appendlist("extra_title", "TITULO SECCION 1")
        qd.appendlist("extra_mode", "detailed")
        qd.appendlist("extra_section_id", "extra-2")
        qd.appendlist("extra_title", "TITULO SECCION 2")
        qd.appendlist("extra_mode", "subtitle_items")

        # Entry order as sent by the form (2 detailed + 3 SI).
        for sid in ["extra-1", "extra-1", "extra-2", "extra-2", "extra-2"]:
            qd.appendlist("extra_entry_section", sid)

        # Sparse payload by mode (inputs ocultos deshabilitados por UI):
        # - subtítulos e items SI incluyen solo entries SI (3)
        # - campos detallados incluyen solo entries detailed (2)
        for value in ["SUB1", "SUB2424,,12,242, 4,124,2, ,,", ""]:
            qd.appendlist("extra_entry_subtitle", value)
        for value in ["R1", "R2"]:
            qd.appendlist("extra_entry_title", value)
        for value in ["E1", "E2"]:
            qd.appendlist("extra_entry_where", value)
        for value in ["", "321, 111, OEEOOE ASD, JEJEM, JAJA"]:
            qd.appendlist("extra_entry_tech", value)
        for value in ["2013-03", "2013-12"]:
            qd.appendlist("extra_entry_start", value)
        for value in ["2030-02", "Actualidad"]:
            qd.appendlist("extra_entry_end", value)
        for value in ["Miami", "LA SUPER CIUDAD GUAIRA"]:
            qd.appendlist("extra_entry_city", value)
        for value in ["Chile", "Chile"]:
            qd.appendlist("extra_entry_country", value)

        qd.appendlist("extra_entry_items_detailed", "")
        qd.appendlist("extra_entry_items_detailed", "h1\nh2\nh3\ng4")

        qd.appendlist("extra_entry_items_si", "1, 2, 3")
        qd.appendlist("extra_entry_items_si", "")
        qd.appendlist("extra_entry_items_si", "SDFSDFJ12,2 ,4123,412,")

        structured = structure_from_post(qd)
        extras = structured.get("extra_sections") or []
        self.assertEqual(len(extras), 2)

        detailed = extras[0]
        si = extras[1]

        self.assertEqual(detailed.get("title"), "TITULO SECCION 1")
        self.assertEqual(detailed.get("mode"), "detailed")
        self.assertEqual(len(detailed.get("entries") or []), 2)
        self.assertEqual(detailed["entries"][0].get("title"), "R1")
        self.assertEqual(detailed["entries"][0].get("where"), "E1")
        self.assertEqual(detailed["entries"][1].get("title"), "R2")
        self.assertEqual(detailed["entries"][1].get("where"), "E2")
        self.assertEqual((detailed["entries"][0].get("items") or []), [])
        self.assertEqual((detailed["entries"][1].get("items") or []), ["h1", "h2", "h3", "g4"])

        self.assertEqual(si.get("title"), "TITULO SECCION 2")
        self.assertEqual(si.get("mode"), "subtitle_items")
        self.assertEqual(len(si.get("entries") or []), 3)
        self.assertEqual(si["entries"][0].get("subtitle"), "SUB1")
        self.assertEqual((si["entries"][0].get("items") or []), ["1, 2, 3"])
        self.assertEqual(si["entries"][1].get("subtitle"), "SUB2424,,12,242, 4,124,2, ,,")
        self.assertEqual(si["entries"][2].get("subtitle"), "SDFSDFJ12,2 ,4123,412,")
