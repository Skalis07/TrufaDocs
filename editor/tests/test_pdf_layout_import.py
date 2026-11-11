"""Anonymous PDFs exercise real extraction, layout, parsing and upload rendering."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase


def _pdf_bytes(pages: list[list[tuple]], *, sidebar: bool = True) -> bytes:
    """Build small, positioned PDFs without a PDF-generation dependency."""
    objects = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    page_ids = []
    for index, lines in enumerate(pages):
        commands = ["0.2 g 0 0 202 842 re f 0 g"] if sidebar and index == 0 else []
        for x, y, size, text in lines:
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"BT /F1 {size} Tf {x} {842 - y} Td ({escaped}) Tj ET")
        stream = "\n".join(commands).encode("cp1252")
        page_id = len(objects) + 1
        page_ids.append(page_id)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(document)
    document.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode())
    return bytes(document)


def _line(y, text, size=10.5, x=224):
    return x, y, size, text


def _sidebar(*, wrapped=False):
    contacts = [
        _line(40, "Contactar", 13, 22),
        _line(61, "candidate@example.co" if wrapped else "candidate@example.com", x=22),
        _line(74, "m", x=22) if wrapped else _line(85, "github.com/example", x=22),
        _line(99, "www.linkedin.com/in/", x=22),
        _line(111.6, "candidate-123456789", x=22),
        _line(140, "Aptitudes principales", 13, 22),
        _line(158, "Python", x=22),
        _line(175.6, "SQL", x=22),
        _line(193.2, "Data Analysis", x=22),
    ]
    if wrapped:
        contacts.append(_line(225, "Certifications", 13, 22))
        for index in range(5):
            y = 248 + index * 30.2
            contacts.extend([_line(y, f"Certificate {index + 1}", x=22), _line(y + 12.6, "Professional Course", x=22)])
    else:
        contacts.extend([
            _line(225, "Languages", 13, 22),
            _line(248, "English (Professional)", x=22),
            _line(266, "Spanish (Native)", x=22),
        ])
    return contacts


class PdfLayoutImportTests(SimpleTestCase):
    def _upload(self, pages):
        response = self.client.post("/upload/", {"file": SimpleUploadedFile("anonymous.pdf", _pdf_bytes(pages))})
        self.assertEqual(response.status_code, 200)
        return response.context["structured"]

    def test_job_locations_and_independent_paragraphs_survive_page_boundaries(self):
        for location, city, country in (
            ("Westhaven", "Westhaven", ""),
            ("Westhaven, Northern District, Exampleland", "Westhaven, Northern District", "Exampleland"),
        ):
            with self.subTest(location=location):
                data = self._upload([
                    [_line(40, "Alex Example", 26), _line(100, "Experience", 15.75),
                     _line(130, "Example Company", 12), _line(149, "Software Engineer", 11.5),
                     _line(165, "January 2021 - December 2022"), _line(180, location),
                     _line(210, "Completed the first paragraph.")],
                    [_line(40, "Started another paragraph.")],
                ])
                self.assertEqual(len(data["experience"]), 1)
                job = data["experience"][0]
                self.assertEqual((job["city"], job["country"]), (city, country))
                self.assertEqual(job["highlights"], ["Completed the first paragraph.", "Started another paragraph."])

    def test_sidebar_columns_wrapped_name_and_page_continuations(self):
        pages = [
            _sidebar() + [
                _line(40, "Alex", 26), _line(70, "Example", 26),
                _line(105, "Software Engineer", 11.5), _line(120, "Cloud Platforms", 11.5),
                _line(139, "Example City, Example Region, Chile"),
                _line(158, "Extracto", 15.75),
                _line(181, "Builds reliable systems."), _line(193.6, "Works across teams."),
                _line(230, "Experiencia", 15.75),
                _line(255, "Example Company", 12), _line(274, "Software Engineer", 11.5),
                _line(289, "enero de 2024 - Present (2 años)"),
                _line(305, "Example City, Chile"),
                _line(350, "Second Company", 12), _line(369, "Data Engineer", 11.5),
                _line(384, "febrero de 2022 - noviembre de 2023 (1 año 10 meses)"),
                _line(405, "• Built reliable"), _line(423, "data services."),
                _line(735, "Example Company", 12), _line(812, "Page 1 of 3", 9),
            ],
            [
                _line(40, "Platform Engineer", 11.5),
                _line(55, "marzo de 2020 - diciembre de 2021 (1 año 10 meses)"),
                _line(80, "• Led Migration"), _line(98, "• Improved Monitoring"),
                _line(150, "Third Company", 12), _line(169, "Intern", 11.5),
                _line(184, "abril de 2019 - agosto de 2019 (5 meses)"),
                _line(210, "• Built Tools"), _line(812, "Page 2 of 3", 9),
            ],
            [
                _line(40, "Educación", 15.75),
                _line(65, "Example University", 12), _line(84, "Computer Science"),
                _line(99, "Advanced Program · (marzo de 2016 - diciembre de 2019)"),
                _line(135, "Example University", 12), _line(154, "Engineering Studies · (marzo de"),
                _line(169, "2014 - noviembre de 2015)"), _line(812, "Page 3 of 3", 9),
            ],
        ]
        data = self._upload(pages)
        self.assertEqual(data["basics"]["name"], "Alex Example")
        self.assertEqual(data["basics"]["email"], "candidate@example.com")
        self.assertEqual(data["basics"]["phone"], "")
        self.assertEqual(data["basics"]["github"], "github.com/example")
        self.assertEqual(data["basics"]["linkedin"], "www.linkedin.com/in/candidate-123456789")
        self.assertEqual(data["basics"]["city"], "Example City, Example Region")
        self.assertEqual(data["basics"]["country"], "Chile")
        self.assertIn("Builds reliable systems. Works across teams.", data["basics"]["description"])
        self.assertIn("Software Engineer", data["basics"]["description"])
        self.assertEqual(len(data["experience"]), 4)
        self.assertEqual([job["company"] for job in data["experience"]], ["Example Company", "Second Company", "Example Company", "Third Company"])
        self.assertEqual([job["role"] for job in data["experience"]], ["Software Engineer", "Data Engineer", "Platform Engineer", "Intern"])
        self.assertEqual([(job["start"], job["end"]) for job in data["experience"]], [("2024-01", "Present"), ("2022-02", "2023-11"), ("2020-03", "2021-12"), ("2019-04", "2019-08")])
        self.assertEqual([job["highlights"] for job in data["experience"]], [[], ["Built reliable data services."], ["Led Migration", "Improved Monitoring"], ["Built Tools"]])
        self.assertEqual(len(data["education"]), 2)
        self.assertEqual([(entry["start"], entry["end"]) for entry in data["education"]], [("2016-03", "2019-12"), ("2014-03", "2015-11")])
        self.assertEqual([entry["degree"] for entry in data["education"]], ["Computer Science Advanced Program", "Engineering Studies"])
        self.assertEqual(data["skills"][0]["items"], "Python, SQL, Data Analysis")
        self.assertEqual(len(data["extra_sections"]), 1)
        extras = str(data["extra_sections"])
        self.assertIn("English (Professional)", extras)
        self.assertIn("Spanish (Native)", extras)
        self.assertNotIn("Page ", str(data))

    def test_wrapped_contacts_grouped_roles_certifications_and_year_only_dates(self):
        pages = [
            _sidebar(wrapped=True) + [
                _line(40, "Taylor Example", 26), _line(80, "API", 11.5),
                _line(95, "Engineer", 11.5), _line(115, "Example City, Chile"),
                _line(150, "Extracto", 15.75), _line(175, "Delivers software."),
                _line(215, "Experiencia", 15.75), _line(245, "Example Company", 12),
                _line(262, "3 años 2 meses"), _line(285, "Senior Engineer", 11.5),
                _line(301, "January 2022 - September 2024 (2 years 9 months)"),
                _line(325, "Built a platform that"), _line(343, "serves several teams"),
                _line(812, "Page 1 of 3", 9),
            ],
            [
                _line(40, "across regions."), _line(90, "Junior Engineer", 11.5),
                _line(106, "November 2021 - December 2021 (2 months)"),
                _line(130, "Maintained Services"), _line(175, "Second Company", 12),
                _line(194, "Intern", 11.5), _line(210, "February 2021 - July 2021"),
                _line(235, "Wrote Tests"), _line(812, "Page 2 of 3", 9),
            ],
            [
                _line(40, "Education", 15.75), _line(65, "Example University", 12),
                _line(84, "Computer Science · (2018 - 2020)"),
                _line(140, "Second University", 12),
                _line(159, "Engineering · (March 2016 - November 2017)"),
                _line(215, "Second University", 12),
                _line(234, "General Studies · (2014 - 2015)"), _line(812, "Page 3 of 3", 9),
            ],
        ]
        data = self._upload(pages)
        self.assertEqual(data["basics"]["name"], "Taylor Example")
        self.assertEqual(data["basics"]["email"], "candidate@example.com")
        self.assertEqual(data["basics"]["linkedin"], "www.linkedin.com/in/candidate-123456789")
        self.assertEqual(data["basics"]["phone"], "")
        self.assertIn("API Engineer", data["basics"]["description"])
        self.assertEqual([job["company"] for job in data["experience"]], ["Example Company", "Example Company", "Second Company"])
        self.assertEqual([job["role"] for job in data["experience"]], ["Senior Engineer", "Junior Engineer", "Intern"])
        self.assertEqual([(job["start"], job["end"]) for job in data["experience"]], [("2022-01", "2024-09"), ("2021-11", "2021-12"), ("2021-02", "2021-07")])
        self.assertEqual(data["experience"][0]["highlights"], ["Built a platform that serves several teams across regions."])
        self.assertEqual(len(data["education"]), 3)
        self.assertEqual([(entry["start"], entry["end"]) for entry in data["education"]], [("2018", "2020"), ("2016-03", "2017-11"), ("2014", "2015")])
        self.assertEqual([entry["degree"] for entry in data["education"]], ["Computer Science", "Engineering", "General Studies"])
        self.assertEqual(data["skills"][0]["items"], "Python, SQL, Data Analysis")
        self.assertEqual(len(data["extra_sections"]), 1)
        entries = data["extra_sections"][0]["entries"]
        self.assertEqual(len(entries), 5)
        for index, entry in enumerate(entries, 1):
            self.assertEqual(entry["subtitle"], f"Certificate {index} Professional Course")
        self.assertNotIn("Page ", str(data))
