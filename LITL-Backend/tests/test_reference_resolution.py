import unittest

import httpx

from app.config import Settings
from app.sources import IndianKanoon, legislation_target, link_details


class ReferenceResolutionTests(unittest.TestCase):
    def connector(self, transport):
        settings = Settings(ik_token="synthetic", ik_terms_accepted=True, ik_budget_paise=40000)
        client = httpx.Client(transport=httpx.MockTransport(transport))
        self.addCleanup(client.close)
        return IndianKanoon(settings, client, lambda operation: True)

    def test_exact_legislation_titles_and_years(self):
        cases = [
            ("Section 335 of IPC", "Section 335 in The Indian Penal Code, 1860", "statute_section"),
            ("Section 335 of IPC, 1860", "Section 335 in The Indian Penal Code, 1860", "statute_section"),
            ("Section 335 of IPC, 1860", "Section 335 in The Indian Penal Code, 2023", None),
            ("Section 335 of IPC", "The Indian Penal Code, 1860", "statute_act"),
            ("Section 335 of IPC", "Section 3350 in The Indian Penal Code, 1860", None),
            ("Section 335 of IPC", "Section 335 in The Bharatiya Nyaya Sanhita, 2023", None),
            ("Section 335", "Section 335 in The Indian Penal Code, 1860", None),
            ("Article 21 of Constitution", "Article 21 in The Constitution of India", "statute_section"),
            ("Section 335 of IPC", "Alpha vs State on Section 335 of IPC", None),
        ]
        for label, title, expected in cases:
            with self.subTest(label=label, title=title):
                self.assertEqual(legislation_target(label, title), expected)

    def test_statutory_lookup_uses_returned_numeric_document(self):
        def transport(request):
            if request.url.path == "/search/":
                return httpx.Response(200, json={"docs": [{"tid": 123}]})
            return httpx.Response(200, json={"title": "Section 335 in The Indian Penal Code, 1860",
                                             "doc": "<p>Synthetic provision fixture.</p>"})
        result = self.connector(transport).resolve({"kind": "statutory_reference", "label": "Section 335 of IPC"})
        self.assertEqual(result[0], "source_found")
        self.assertFalse(result[3], "A statute link does not verify legal applicability")
        self.assertEqual(result[2][0]["target_kind"], "statute_section")
        self.assertEqual(link_details(result[0], result[2])["reference_url"], "https://indiankanoon.org/doc/123/")

    def test_missing_act_makes_no_provider_request(self):
        def forbidden(request):
            raise AssertionError("No lookup without an Act")
        result = self.connector(forbidden).resolve({"kind": "statutory_reference", "label": "Section 335"})
        self.assertEqual(result[0], "missing_context")
        self.assertIsNone(link_details(result[0], result[2])["reference_url"])

    def test_judgment_discussing_section_remains_candidate(self):
        def transport(request):
            if request.url.path == "/search/":
                return httpx.Response(200, json={"docs": [{"tid": 99}]})
            return httpx.Response(200, json={"title": "Alpha v. State", "doc": "The matter mentions Section 335 of IPC."})
        result = self.connector(transport).resolve({"kind": "statutory_reference", "label": "Section 335 of IPC"})
        self.assertEqual(result[0], "ambiguous")
        self.assertEqual(link_details(result[0], result[2])["link_state"], "candidates")
        self.assertIsNone(link_details(result[0], result[2])["reference_url"])

    def test_pagination_does_not_override_explicit_citation_identity(self):
        def transport(request):
            if request.url.path == "/search/":
                return httpx.Response(200, json={"found": 100, "docs": [{"tid": i} for i in range(1, 11)]})
            page = "100" if request.url.path == "/doc/1/" else "200"
            return httpx.Response(200, json={"title": "Alpha v. Beta", "doc": f"Equivalent citations: (2020) 1 SCC {page}"})
        connector = self.connector(transport)
        result = connector.resolve({"label": "Alpha v. Beta, (2020) 1 SCC 100"})
        self.assertEqual(result[0], "source_found")
        self.assertEqual(result[2][0]["url"], "https://indiankanoon.org/doc/1/")
        self.assertIn("not an exhaustive search", result[1])
        name_only = connector.resolve({"label": "Alpha v. Beta"})
        self.assertEqual(name_only[0], "ambiguous")
