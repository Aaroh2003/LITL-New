"""Contract smoke tests against a running, local-only LiTL API.

Run with: python3 -m unittest discover -s tests -v
The tests create and delete only their own synthetic documents.
"""

import json
import os
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.environ.get("LITL_TEST_API_URL", "http://127.0.0.1:8000").rstrip("/")


class LocalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed = urllib.parse.urlparse(BASE_URL)
        if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("Smoke tests may run only against a loopback API.")
        config = cls.request("GET", "/v1/config")[1]
        if config["auth_mode"] != "local" or config["source_lookup_configured"]:
            raise RuntimeError(
                "Use local auth with the source provider disabled: these tests "
                "must not submit documents externally or spend API credit."
            )

    def setUp(self):
        self.document_ids = []

    def tearDown(self):
        for document_id in self.document_ids:
            status, _ = self.request("DELETE", f"/v1/documents/{document_id}")
            self.assertIn(status, (204, 404))

    @staticmethod
    def request(method, path, data=None, content_type="application/json"):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        headers = {"Content-Type": content_type} if data is not None else {}
        request = urllib.request.Request(
            BASE_URL + path, data=data, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None

    def create_text(self, text):
        status, document = self.request(
            "POST",
            "/v1/documents/text",
            {"title": "Synthetic smoke-test draft", "text": text, "consent": True},
        )
        self.assertIn(status, (200, 201, 202), document)
        self.document_ids.append(document["id"])
        return document

    def wait_for_analysis(self, document_id):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status, document = self.request("GET", f"/v1/documents/{document_id}")
            self.assertEqual(status, 200, document)
            run = document["latest_run"]
            if run and run["status"] in ("completed", "failed", "cancelled"):
                self.assertEqual(run["status"], "completed", run)
                return document
            time.sleep(0.2)
        self.fail("Analysis did not complete within 30 seconds.")

    def test_upload_review_snapshot_and_delete(self):
        text = (
            "Synthetic illustration \U0001f4c4, not a real client's case.\n\n"
            "Arnesh Kumar v. State of Bihar, (2014) 8 SCC 273 is cited.\n\n"
            "Section 41A CrPC is mentioned. "
            '"This invented quotation is deliberately unsupported."'
        )
        document = self.create_text(text)
        document_id = document["id"]
        document = self.wait_for_analysis(document_id)
        self.assertEqual(document["text"], text)
        self.assertGreaterEqual(len(document["findings"]), 2)
        for finding in document["findings"]:
            self.assertEqual(text[finding["start"]:finding["end"]], finding["excerpt"])
            self.assertIsNone(finding["decision"])
            self.assertNotEqual(finding["status"], "source_found")
        self.assertEqual(document["metrics"]["review_completion"]["numerator"], 0)

        finding = document["findings"][0]
        review_path = f"/v1/documents/{document_id}/findings/{finding['id']}/review"
        review = {
            "decision": "unresolved",
            "review_note": "Synthetic smoke test: source unavailable.",
            "correction": "",
            "expected_version": finding["version"],
        }
        status, saved = self.request("PUT", review_path, review)
        self.assertEqual(status, 200, saved)
        self.assertEqual(saved["decision"], "unresolved")
        self.assertGreater(saved["version"], finding["version"])

        status, _ = self.request("PUT", review_path, review)
        self.assertEqual(status, 409, "A stale review must not overwrite a decision.")

        status, report = self.request("POST", f"/v1/documents/{document_id}/reports")
        self.assertIn(status, (200, 201), report)
        self.assertEqual(report["document"]["metrics"]["review_completion"]["numerator"], 1)
        self.assertEqual(report["document"]["metrics"]["resolution_coverage"]["numerator"], 0)

        status, saved = self.request(
            "PUT",
            review_path,
            {
                **review,
                "decision": "rejected",
                "review_note": "Changed after the report snapshot.",
                "expected_version": saved["version"],
            },
        )
        self.assertEqual(status, 200, saved)
        status, unchanged_report = self.request(
            "GET", f"/v1/documents/{document_id}/reports/{report['id']}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(unchanged_report, report)

        status, reopened = self.request("GET", f"/v1/documents/{document_id}")
        self.assertEqual(status, 200)
        self.assertEqual(reopened["metrics"]["resolution_coverage"]["numerator"], 1)
        self.assertEqual(reopened["metrics"]["unresolved"], 0)
        self.assertEqual(reopened["text"], text, "A review must not edit the original.")

        status, _ = self.request("DELETE", f"/v1/documents/{document_id}")
        self.assertEqual(status, 204)
        self.document_ids.remove(document_id)
        for path in (
            f"/v1/documents/{document_id}",
            f"/v1/documents/{document_id}/reports/{report['id']}",
        ):
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_no_references_is_not_a_perfect_score(self):
        document = self.create_text("Synthetic document with no legal references.")
        document = self.wait_for_analysis(document["id"])
        self.assertEqual(document["findings"], [])
        self.assertEqual(document["metrics"]["total"], 0)
        for name in (
            "source_coverage", "review_completion", "resolution_coverage",
            "citation_consistency", "quotation_fidelity",
        ):
            self.assertIsNone(document["metrics"][name]["percentage"])

    def test_consent_required(self):
        status, _ = self.request(
            "POST",
            "/v1/documents/text",
            {"title": "No consent", "text": "Synthetic text.", "consent": False},
        )
        self.assertIn(status, (400, 422))

    def test_text_file_upload_preserves_content(self):
        text = "Synthetic upload: Section 41A CrPC.\nNo client information."
        boundary = "litl-smoke-test-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="consent"\r\n\r\ntrue\r\n'
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="synthetic.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            f"{text}\r\n--{boundary}--\r\n"
        ).encode()
        status, document = self.request(
            "POST", "/v1/documents/file", body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        self.assertIn(status, (200, 201, 202), document)
        self.document_ids.append(document["id"])
        completed = self.wait_for_analysis(document["id"])
        self.assertEqual(completed["text"], text)
        self.assertEqual(completed["file_name"], "synthetic.txt")

    def test_reanalysis_does_not_transfer_decisions(self):
        document = self.create_text("Synthetic draft: Section 439 CrPC.")
        document_id = document["id"]
        document = self.wait_for_analysis(document_id)
        finding = document["findings"][0]
        status, _ = self.request(
            "PUT",
            f"/v1/documents/{document_id}/findings/{finding['id']}/review",
            {
                "decision": "unresolved",
                "review_note": "Synthetic first-pass assessment.",
                "correction": "",
                "expected_version": finding["version"],
            },
        )
        self.assertEqual(status, 200)
        status, new_run = self.request("POST", f"/v1/documents/{document_id}/analyses")
        self.assertIn(status, (200, 201, 202), new_run)
        self.assertNotEqual(new_run["id"], document["latest_run"]["id"])
        status, _ = self.request(
            "PUT",
            f"/v1/documents/{document_id}/findings/{finding['id']}/review",
            {
                "decision": "confirmed",
                "review_note": "A stale browser tab must not save an obsolete finding.",
                "correction": "",
                "expected_version": finding["version"] + 1,
            },
        )
        self.assertEqual(status, 409)
        rerun = self.wait_for_analysis(document_id)
        self.assertEqual(rerun["latest_run"]["id"], new_run["id"])
        self.assertTrue(all(item["decision"] is None for item in rerun["findings"]))
        self.assertEqual(rerun["metrics"]["review_completion"]["numerator"], 0)

    def test_correction_requires_proposed_text(self):
        document = self.create_text("Synthetic draft: Section 41A CrPC.")
        document = self.wait_for_analysis(document["id"])
        finding = document["findings"][0]
        status, _ = self.request(
            "PUT",
            f"/v1/documents/{document['id']}/findings/{finding['id']}/review",
            {
                "decision": "corrected",
                "review_note": "A note alone is not a proposed correction.",
                "correction": " ",
                "expected_version": finding["version"],
            },
        )
        self.assertIn(status, (400, 422))

    def test_multiple_documents_keep_distinct_content(self):
        first = self.create_text("First synthetic draft: Section 41A CrPC.")
        second = self.create_text("Second synthetic draft: Section 439 CrPC.")
        first = self.wait_for_analysis(first["id"])
        second = self.wait_for_analysis(second["id"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertIn("First synthetic", first["text"])
        self.assertNotIn("Second synthetic", first["text"])
        self.assertIn("Second synthetic", second["text"])
        first_finding = first["findings"][0]
        status, _ = self.request(
            "PUT",
            f"/v1/documents/{second['id']}/findings/{first_finding['id']}/review",
            {
                "decision": "confirmed",
                "review_note": "",
                "correction": "",
                "expected_version": first_finding["version"],
            },
        )
        self.assertEqual(status, 404, "A finding cannot be reviewed under another document.")

    def test_unsupported_file_does_not_create_successful_analysis(self):
        boundary = "litl-rejected-file-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="consent"\r\n\r\ntrue\r\n'
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="not-supported.exe"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
            f"MZ-synthetic-not-executable\r\n--{boundary}--\r\n"
        ).encode()
        status, _ = self.request(
            "POST", "/v1/documents/file", body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        self.assertIn(status, (400, 415, 422))
