import unittest
from copy import deepcopy

from app.extraction import detect_with_scope, paragraphs_for, statutory_details
from app.metrics import assessment_metrics, report_overview
from app.sources import identity_matches


def finding(kind, label, status="not_checked", **extra):
    return {
        "kind": kind, "label": label, "status": status, "decision": None,
        "identity_checked": False, "quote_checked": False, "sources": [],
        **extra,
    }


def source():
    return {
        "id": "source-1", "url": "https://indiankanoon.org/doc/123/",
        "repository": "Indian Kanoon", "retrieved_at": "2026-09-26T00:00:00Z",
        "locator": "Retrieved paragraph 1", "passage": "Synthetic judgment passage.",
        "content_sha256": "a" * 64,
    }


class ReportFormulaTests(unittest.TestCase):
    def test_plan_example_uses_separate_denominators(self):
        cases = [
            finding("case_citation", f"Case {i}", "source_found", identity_checked=True,
                    identity_assessment="matched", sources=[source()])
            for i in range(5)
        ]
        cases.append(finding("case_citation", "Case 5", "ambiguous", identity_checked=True,
                             identity_assessment="not_matched", sources=[source()]))
        cases.extend(finding("case_citation", f"Case {i}", "unavailable") for i in range(6, 10))
        quotes = [
            finding("quotation", f"Quote {i}", "source_found" if i < 3 else "quote_mismatch",
                    quote_checked=True, sources=[source()])
            for i in range(4)
        ]
        quotes.extend(finding("quotation", f"Quote {i}") for i in range(4, 8))
        result = assessment_metrics(cases + quotes)
        expected = {
            "identity_coverage": (6, 10, 60.0), "identity_match": (5, 6, 83.3),
            "located_case_coverage": (5, 10, 50.0),
            "quote_comparison_coverage": (4, 8, 50.0), "wording_match": (3, 4, 75.0),
            "provenance_completeness": (10, 10, 100.0),
        }
        for key, (n, d, percentage) in expected.items():
            with self.subTest(key=key):
                row = result["metrics"][key]
                self.assertEqual((row["numerator"], row["denominator"], row["percentage"]), (n, d, percentage))
                self.assertEqual(row["definition_version"], "evidence-2")
                self.assertTrue(row["formula"] and row["description"])

    def test_empty_report_has_no_fake_scores(self):
        result = assessment_metrics([])
        self.assertTrue(all(row["percentage"] is None for row in result["metrics"].values()))
        self.assertEqual(report_overview(result)["state"], "no_detections")

    def test_statute_only_report_has_no_identity_or_quote_denominator(self):
        result = assessment_metrics([finding("statutory_reference", "Section 335", "unsupported")])
        for key in ("identity_coverage", "identity_match", "quote_comparison_coverage", "wording_match"):
            self.assertIsNone(result["metrics"][key]["percentage"])
        self.assertEqual(result["metrics"]["review_completion"]["percentage"], 0)
        self.assertEqual(result["counts"]["statutory_references"], 1)
        self.assertEqual(report_overview(result)["attention"][0]["count"], 1)

    def test_repeated_citations_do_not_inflate_distinct_coverage(self):
        matches = [
            finding("case_citation", label, "source_found", identity_checked=True, sources=[source()])
            for label in ("Alpha v. Beta", "ALPHA V. BETA", "Alpha   v. Beta")
        ]
        result = assessment_metrics(matches + [finding("case_citation", "Gamma v. Delta", "unavailable")])
        self.assertEqual(result["metrics"]["located_case_coverage"]["percentage"], 75)
        self.assertEqual(result["metrics"]["unique_case_coverage"]["percentage"], 50)
        self.assertEqual(result["counts"]["distinct_case_labels"], 2)

    def test_legacy_ambiguity_is_not_a_conclusive_failure(self):
        result = assessment_metrics([
            finding("case_citation", "Alpha v. Beta", "ambiguous", identity_checked=True),
            finding("case_citation", "Gamma v. Delta", "not_found"),
        ])
        self.assertEqual(result["counts"]["assessed_identities"], 0)
        self.assertIsNone(result["metrics"]["identity_match"]["percentage"])
        self.assertEqual(result["metrics"]["identity_coverage"]["percentage"], 0)

    def test_review_completion_and_disposition_are_different(self):
        findings = [
            finding("statutory_reference", f"Section {i}", "unsupported", decision=decision)
            for i, decision in enumerate(("confirmed", "corrected", "rejected", "unresolved", None))
        ]
        result = assessment_metrics(findings)
        self.assertEqual(result["metrics"]["review_completion"]["percentage"], 80)
        self.assertEqual(result["metrics"]["review_disposition"]["percentage"], 60)
        self.assertEqual(report_overview(result)["state"], "review_incomplete")
        findings.pop()
        self.assertEqual(report_overview(assessment_metrics(findings))["state"], "reviewed_with_unresolved")
        findings.pop()
        self.assertEqual(report_overview(assessment_metrics(findings))["state"], "reviewed")

    def test_provenance_requires_all_sources_and_hash(self):
        sources = [source(), source()]
        sources[1].pop("content_sha256")
        result = assessment_metrics([
            finding("quotation", "Quote", "quote_mismatch", quote_checked=True, sources=sources),
        ])
        self.assertEqual(result["metrics"]["provenance_completeness"]["numerator"], 0)
        self.assertEqual(result["metrics"]["provenance_completeness"]["denominator"], 1)

    def test_metrics_do_not_mutate_inputs_and_obey_bounds(self):
        findings = [finding("statutory_reference", "Section 335", "unsupported", decision="unresolved")]
        before = deepcopy(findings)
        result = assessment_metrics(findings)
        self.assertEqual(findings, before)
        for row in result["metrics"].values():
            self.assertLessEqual(0, row["numerator"])
            self.assertLessEqual(row["numerator"], row["denominator"])


class StatutoryContextTests(unittest.TestCase):
    def test_bare_section_does_not_guess_criminal_procedure_code(self):
        result = statutory_details("Section 335")
        self.assertEqual(result["statute"], {"identifier": "Section 335", "act": None})
        self.assertIn("not identified in this reference", result["note"])
        self.assertIn("Section 335", result["evidence_message"])
        self.assertNotIn("CrPC", result["note"])
        self.assertNotIn("fabricat", result["evidence_message"])

    def test_named_acts_and_articles_have_targeted_instructions(self):
        for label, act in (
            ("Section 335 of IPC", "IPC"),
            ("Section 7 of the Arbitration and Conciliation Act, 1996", "Arbitration and Conciliation Act, 1996"),
            ("Article 21 of the Constitution of India", "Constitution of India"),
        ):
            with self.subTest(label=label):
                result = statutory_details(label)
                self.assertEqual(result["statute"]["act"], act)
                self.assertIn(act, result["note"])
                self.assertNotIn("CrPC/BNSS", result["note"])
                self.assertIn("not been verified", result["note"])
        self.assertIsNone(statutory_details("Article 21")["statute"]["act"])

    def test_crpc_warning_only_for_matching_explicit_act(self):
        for label in ("Section 41 of CrPC", "Section 41A Cr.P.C.", "Section 35 of BNSS"):
            self.assertIn("transitional provisions", statutory_details(label)["note"])

    def test_detection_scope_preserves_offsets_and_discloses_truncation(self):
        text = "😀 Context\n" + "\n".join(f"Section {i} of IPC" for i in range(1, 56))
        paragraphs = paragraphs_for([(text, 10)])["paragraphs"]
        findings, warnings, scope = detect_with_scope(text, paragraphs)
        self.assertEqual((scope["detected"], scope["processed"], scope["deferred"]), (55, 50, 5))
        self.assertEqual(scope["detected_by_kind"]["statutory_reference"], 55)
        self.assertTrue(any("first 50" in warning for warning in warnings))
        for item in findings:
            self.assertEqual(text[item["start"]:item["end"]], item["excerpt"])
            self.assertEqual(item["page"], 10)

    def test_reporter_page_prefix_is_not_identity_match(self):
        self.assertFalse(identity_matches("(2020) 1 SCC 100", "Alpha v. Beta",
                                          "Equivalent citations: (2020) 1 SCC 1000"))
        self.assertTrue(identity_matches("(2020) 1 SCC 100", "Alpha v. Beta",
                                         "Equivalent citations: (2020) 1 SCC 100, AIR 2020 SC 50"))
