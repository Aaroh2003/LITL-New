import json
import shutil
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import DocumentRow, FindingRow, SummaryQuotaRow, now, uid


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(".test-data") / uid()
        self.directory.mkdir(parents=True)
        self.settings = Settings(
            database_url=f"sqlite:///{self.directory}/test.db", testing=True, worker_enabled=False,
            ik_token="", gemini_api_key="synthetic-key", gemini_enabled=True,
            gemini_model="gemini-3.5-flash-lite", gemini_budget_microusd=1_000_000,
        )
        self.calls = []
        self.override = None
        self.http = httpx.Client(transport=httpx.MockTransport(self.transport))
        self.app = create_app(self.settings, self.http)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.db = self.app.state.db
        self.document = self.client.post("/v1/documents/text", json={
            "title": "Never send this title",
            "text": "Section 4 of the POSH Act.\nSurrounding private-marker text must not be sent.",
            "consent": True,
        }).json()
        self.app.state.worker.tick()
        self.base = "/v1/documents/" + self.document["id"]
        self.document = self.client.get(self.base).json()
        self.finding = self.document["findings"][0]
        self.path = self.base + "/findings/" + self.finding["id"] + "/explanation"

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.db.engine.dispose()
        shutil.rmtree(self.directory)

    def transport(self, request):
        self.calls.append(request)
        self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
        self.assertEqual(request.headers["x-goog-api-key"], "synthetic-key")
        self.assertNotIn("synthetic-key", request.content.decode())
        self.assertNotIn("private-marker", request.content.decode())
        self.assertNotIn("Never send this title", request.content.decode())
        body = json.loads(request.content)
        content = body.get("generateContentRequest", body)
        packet = json.loads(content["contents"][0]["parts"][0]["text"])
        self.assertEqual(packet, {"reference": self.finding["label"], "kind": self.finding["kind"]})
        if self.override:
            return self.override(request)
        if request.url.path.endswith(":countTokens"):
            return httpx.Response(200, json={"totalTokens": 300})
        return self.output("This section generally concerns the constitution of an Internal Committee. Check the original Act for its requirements.")

    def output(self, text):
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({"text": text})}]}}],
            "usageMetadata": {"promptTokenCount": 300, "candidatesTokenCount": 30},
        })

    def explain(self, key="test"):
        return self.client.post(self.path, json={"consent": True, "request_key": key})

    def test_explicit_consent_and_no_automatic_calls(self):
        self.assertEqual(self.calls, [])
        for consent in (False, "true", 1, None):
            response = self.client.post(self.path, json={"consent": consent, "request_key": "x"})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.calls, [])

    def test_saved_concise_reference_only_and_cached(self):
        before = self.client.post(self.base + "/reports").json()
        response = self.explain()
        self.assertEqual(response.status_code, 200, response.text)
        finding = response.json()
        explanation = finding["ai_explanation"]
        self.assertEqual(explanation["status"], "completed")
        self.assertLessEqual(len(explanation["text"].split()), 80)
        self.assertLessEqual(len(explanation["text"]), 600)
        for field in ("status", "decision", "version", "note"):
            self.assertEqual(finding[field], self.finding[field])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.explain("another-click").json()["ai_explanation"], explanation)
        self.assertEqual(len(self.calls), 2)
        loaded = self.client.get(self.base).json()
        self.assertEqual(loaded["findings"][0]["ai_explanation"], explanation)
        self.assertEqual(loaded["metrics"], self.document["metrics"])
        report = self.client.post(self.base + "/reports").json()
        self.assertEqual(report["document"]["findings"][0]["ai_explanation"], explanation)
        old_report = self.client.get(self.base + "/reports/" + before["id"]).json()
        self.assertNotIn("ai_explanation", old_report["document"]["findings"][0])
        with self.db.sessions() as session:
            quota = session.get(SummaryQuotaRow, "gemini:account")
            self.assertEqual(quota.requests, 1)
            self.assertEqual(quota.reserved_microusd, 2115)

    def test_disabled_or_budget_exhausted_sends_nothing(self):
        self.settings.gemini_enabled = False
        self.assertEqual(self.explain().status_code, 503)
        self.settings.gemini_enabled = True
        self.settings.gemini_budget_microusd = 1
        self.assertEqual(self.explain().status_code, 429)
        self.assertEqual(self.calls, [])
        with self.db.sessions() as session:
            self.assertIsNone(session.get(SummaryQuotaRow, "gemini:account"))

    def test_provider_failure_persisted_and_retry_bounded(self):
        self.override = lambda request: httpx.Response(429, json={"error": {"message": "private provider details"}})
        first = self.explain().json()["ai_explanation"]
        self.assertEqual(first["status"], "failed")
        self.assertIn("quota", first["error"])
        self.assertNotIn("private", first["error"])
        self.assertEqual(self.explain().json()["ai_explanation"], first)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.explain("retry").json()["ai_explanation"]["attempts"], 2)
        self.assertEqual(self.explain("third").status_code, 429)
        self.assertEqual(len(self.calls), 2)

    def test_invalid_outputs_are_not_published(self):
        invalid = [
            "word " * 81, "x" * 601, "", "See https://example.com", "<script>bad</script>",
        ]
        for text in invalid:
            with self.subTest(text=text[:20]):
                with self.db.transaction() as session:
                    row = session.get(FindingRow, self.finding["id"])
                    row.data = {k: v for k, v in row.data.items() if k != "ai_explanation"}
                self.override = lambda request: (
                    httpx.Response(200, json={"totalTokens": 300})
                    if request.url.path.endswith(":countTokens") else self.output(text)
                )
                explanation = self.explain().json()["ai_explanation"]
                self.assertEqual(explanation["status"], "failed")
                self.assertIsNone(explanation["text"])

    def test_token_limit_stops_generation(self):
        self.override = lambda request: httpx.Response(200, json={"totalTokens": 2049})
        self.assertEqual(self.explain().json()["ai_explanation"]["status"], "failed")
        self.assertEqual(len(self.calls), 1)

    def test_oversized_reference_not_sent(self):
        with self.db.transaction() as session:
            row = session.get(FindingRow, self.finding["id"])
            row.data = {**row.data, "label": "x" * 601}
        self.assertEqual(self.explain().status_code, 422)
        self.assertEqual(self.calls, [])

    def test_incomplete_or_malformed_response_not_published(self):
        for result in (
            {"candidates": [{"finishReason": "MAX_TOKENS"}]},
            {"candidates": []},
            {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not JSON"}]}}]},
            {"candidates": None},
        ):
            with self.subTest(result=result):
                with self.db.transaction() as session:
                    row = session.get(FindingRow, self.finding["id"])
                    row.data = {k: v for k, v in row.data.items() if k != "ai_explanation"}
                self.override = lambda request: httpx.Response(200, json=(
                    {"totalTokens": 300} if request.url.path.endswith(":countTokens") else result
                ))
                explanation = self.explain().json()["ai_explanation"]
                self.assertEqual(explanation["status"], "failed")
                self.assertIsNone(explanation["text"])

    def test_deletion_during_request_does_not_restore_finding(self):
        def delete_during_generation(request):
            if request.url.path.endswith(":countTokens"):
                return httpx.Response(200, json={"totalTokens": 300})
            self.assertEqual(self.client.delete(self.base).status_code, 204)
            return self.output("A short explanation.")
        self.override = delete_during_generation
        self.assertIn(self.explain().status_code, (404, 410))
        with self.db.sessions() as session:
            self.assertIsNone(session.get(FindingRow, self.finding["id"]))
            self.assertEqual(session.get(SummaryQuotaRow, "gemini:account").requests, 1)

    def test_wrong_owner_missing_or_stale_finding_denied(self):
        with self.db.transaction() as session:
            session.get(DocumentRow, self.document["id"]).owner_id = "another-owner"
        self.assertEqual(self.explain().status_code, 404)
        with self.db.transaction() as session:
            session.get(DocumentRow, self.document["id"]).owner_id = "local-development-owner"
        self.assertEqual(self.client.post(self.base + "/findings/missing/explanation", json={
            "consent": True, "request_key": "x",
        }).status_code, 404)
        self.client.post(self.base + "/analyses")
        self.assertEqual(self.explain().status_code, 409)
        self.assertEqual(self.calls, [])

    def test_concurrent_click_does_not_duplicate_provider_request(self):
        entered, release = threading.Event(), threading.Event()
        results = []
        original = self.transport

        def blocked(request):
            if request.url.path.endswith(":countTokens"):
                entered.set()
                self.assertTrue(release.wait(5))
            return original(request)

        with patch.object(self.http, "_transport", httpx.MockTransport(blocked)):
            thread = threading.Thread(target=lambda: results.append(self.explain()))
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.explain("duplicate").status_code, 409)
            finally:
                release.set()
                thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0].json()["ai_explanation"]["status"], "completed")
        self.assertEqual(len(self.calls), 2)

    def test_interrupted_request_retries_only_explicitly(self):
        self.explain()
        with self.db.transaction() as session:
            row = session.get(FindingRow, self.finding["id"])
            row.data = {**row.data, "ai_explanation": {
                **row.data["ai_explanation"], "status": "processing", "text": None, "started_at": now() - 121,
            }}
        self.assertEqual(self.explain().json()["ai_explanation"]["status"], "failed")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.explain("retry").json()["ai_explanation"]["status"], "completed")
        self.assertEqual(len(self.calls), 4)

    def test_daily_limit_shared_with_document_summaries(self):
        self.settings.gemini_owner_daily_requests = 1
        self.explain()
        with self.db.transaction() as session:
            with self.assertRaisesRegex(ValueError, "per-user daily"):
                self.app.state.worker.summaries.reserve(session, "local-development-owner")
        with self.db.sessions() as session:
            quotas = list(session.scalars(select(SummaryQuotaRow)))
            self.assertTrue(all(q.requests == 1 for q in quotas))
