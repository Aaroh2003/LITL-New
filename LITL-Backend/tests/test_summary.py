import json
import shutil
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.main import create_app
from app.models import SummaryConsentRow, SummaryJobRow, SummaryQuotaRow, SummaryReviewEvent, now, uid
from app.summary import MAX_INPUT_TOKENS, SummaryOutput, build_packet, generation_config, output_schema, validate_output
from tests.test_backend import source_http


DRAFT = "This synthetic bail application requests a hearing."


def output_for(packet):
    paragraph = next(key for key, value in packet["evidence"].items() if value["kind"] == "draft")
    sources = [key for key, value in packet["evidence"].items() if value["kind"] == "source"]
    return {
        "overview": [{"text": "The draft requests a hearing.", "evidence_ids": [paragraph]}],
        "key_points": [], "issues": [],
        "source_observations": [{"text": "A source excerpt is available for the cited reference.", "evidence_ids": sources[:1]}] if sources else [],
        "review_questions": [],
    }


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(".test-data") / uid()
        self.directory.mkdir(parents=True)
        self.settings = Settings(
            database_url=f"sqlite:///{self.directory}/test.db", testing=True, worker_enabled=False,
            ik_token="", ik_terms_accepted=False, gemini_api_key="synthetic-gemini-key",
            gemini_enabled=True, gemini_model="gemini-2.5-flash", gemini_budget_microusd=1_000_000,
            gemini_input_rate=300000, gemini_output_rate=2500000,
            gemini_owner_daily_requests=5,
        )
        self.requests = []
        self.response_override = None
        self.http = httpx.Client(transport=httpx.MockTransport(self.transport))
        self.app = create_app(self.settings, self.http)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.worker = self.app.state.worker
        self.summaries = self.worker.summaries
        self.db = self.app.state.db

    def tearDown(self):
        self.client.__exit__(None, None, None)
        shutil.rmtree(self.directory)

    def transport(self, request):
        self.requests.append(request)
        if request.url.host == "api.indiankanoon.org":
            return source_http(request)
        self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
        self.assertEqual(request.url.scheme, "https")
        self.assertFalse(request.url.query)
        self.assertEqual(request.headers["x-goog-api-key"], "synthetic-gemini-key")
        self.assertNotIn("synthetic-gemini-key", request.content.decode())
        self.assertEqual(request.method, "POST")
        if self.response_override:
            override = self.response_override(request)
            if override is not None:
                return override
        if request.url.path.endswith(":countTokens"):
            return httpx.Response(200, json={"totalTokens": 300})
        body = json.loads(request.content)
        packet = json.loads(body["contents"][0]["parts"][0]["text"])
        self.assertEqual(body["generationConfig"], generation_config(self.settings.gemini_model, packet))
        return httpx.Response(200, json={
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(output_for(packet))}]}}],
            "usageMetadata": {"promptTokenCount": 300, "candidatesTokenCount": 80, "totalTokenCount": 380},
            "modelVersion": self.settings.gemini_model,
        })

    def document(self, consent=False, text=DRAFT):
        response = self.client.post("/v1/documents/text", json={
            "title": "Synthetic summary test", "text": text, "consent": True, "ai_summary_consent": consent,
        })
        self.assertEqual(response.status_code, 200, response.text)
        document = response.json()
        self.worker.tick()
        return self.client.get("/v1/documents/" + document["id"]).json()

    def summary_path(self, doc):
        return f"/v1/documents/{doc['id']}/analyses/{doc['latest_run']['id']}/summaries"

    def generate(self, doc, key="test-key"):
        return self.client.post(self.summary_path(doc), json={"consent": True, "request_key": key})

    def test_consent_disabled_by_default_and_key_never_public(self):
        doc = self.document()
        self.assertIsNone(doc["ai_summary"])
        self.assertFalse(self.summaries.tick(self.http))
        self.assertEqual(self.requests, [])
        self.assertNotIn("synthetic-gemini-key", self.client.get("/v1/config").text)
        self.assertNotIn("synthetic-gemini-key", repr(self.settings))
        for bad in (False, "true", 1, None):
            self.assertEqual(self.client.post(self.summary_path(doc), json={"consent": bad, "request_key": "x"}).status_code, 422)
        self.settings.gemini_enabled = False
        self.assertEqual(self.generate(doc).status_code, 503)

    def test_opted_in_upload_generates_grounded_draft_summary(self):
        doc = self.document(consent=True)
        self.assertEqual(doc["ai_summary"]["status"], "queued")
        self.assertTrue(doc["ai_summary_requested"])
        self.assertTrue(self.summaries.tick(self.http))
        summary = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(summary["status"], "completed", summary)
        paragraph_id = doc["paragraphs"][0]["id"]
        self.assertEqual(summary["output"]["overview"][0]["evidence_ids"], [paragraph_id])
        self.assertIn(paragraph_id, summary["evidence"])
        self.assertEqual(summary["review_state"], "unreviewed")
        self.assertEqual(summary["prompt_version"], "gemini-summary-2")
        self.assertEqual(summary["reserved_microusd"], 25450)
        self.assertEqual(summary["usage"]["totalTokenCount"], 380)
        self.assertTrue(any("Draft-only" in text for text in summary["limitations"]))
        self.assertEqual(len(self.requests), 2)

    def test_explicit_generation_and_idempotency(self):
        doc = self.document()
        first = self.generate(doc).json()
        self.assertEqual(self.generate(doc).json()["id"], first["id"])
        self.assertEqual(self.generate(doc, "other-key").json()["id"], first["id"])
        self.summaries.tick(self.http)
        self.assertEqual(self.generate(doc).json()["id"], first["id"])
        second = self.generate(doc, "regenerate")
        self.assertEqual(second.status_code, 200)
        self.summaries.tick(self.http)
        self.assertEqual(self.generate(doc, "third").status_code, 429)
        self.assertEqual(len(self.requests), 4)

    def test_pending_completed_and_reviewed_report_snapshots_are_frozen(self):
        doc = self.document(consent=True)
        base = f"/v1/documents/{doc['id']}"
        pending = self.client.post(base + "/reports").json()
        self.summaries.tick(self.http)
        complete = self.client.post(base + "/reports").json()
        summary = complete["document"]["ai_summary"]
        self.assertEqual(summary["status"], "completed")
        review_path = self.summary_path(doc) + f"/{summary['id']}/review"
        response = self.client.put(review_path, json={"decision": "reviewed", "expected_version": 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.put(review_path, json={"decision": "rejected", "expected_version": 0}).status_code, 409)
        self.assertEqual(self.client.get(base + "/reports/" + pending["id"]).json(), pending)
        self.assertEqual(self.client.get(base + "/reports/" + complete["id"]).json(), complete)
        with patch.object(self.http, "stream", side_effect=AssertionError("Report reads must not generate")):
            reviewed = self.client.post(base + "/reports").json()
        self.assertEqual(reviewed["document"]["ai_summary"]["review_state"], "reviewed")
        self.assertEqual(complete["document"]["ai_summary"]["review_state"], "unreviewed")
        with self.assertRaises(IntegrityError):
            with self.db.transaction() as session:
                session.execute(update(SummaryReviewEvent).values(decision="rejected"))

    def test_unknown_evidence_urls_and_unsupported_quotes_are_rejected(self):
        doc = self.document()
        with self.db.sessions() as session:
            from app.models import DocumentRow, RunRow
            packet = build_packet(session, session.get(DocumentRow, doc["id"]), session.get(RunRow, doc["latest_run"]["id"]))
        paragraph_id = doc["paragraphs"][0]["id"]
        for statement in (
            {"text": "Invented", "evidence_ids": ["not-in-packet"]},
            {"text": "See https://indiankanoon.org/doc/999/", "evidence_ids": [paragraph_id]},
            {"text": 'The draft says "release is guaranteed".', "evidence_ids": [paragraph_id]},
            {"text": "The rule in (2020) 1 SCC 999 applies.", "evidence_ids": [paragraph_id]},
        ):
            output = output_for(packet)
            output["overview"] = [statement]
            with self.assertRaises(ValueError):
                validate_output(json.dumps(output), packet)

    def test_schema_enumerates_actual_draft_ids_and_forbids_source_observations(self):
        packet = {
            "evidence": {f"p{i}": {"kind": "draft"} for i in range(1, 177)},
            "references": [{"finding_id": "not-an-evidence-id"}],
        }
        schema = output_schema(packet)
        ids = schema["$defs"]["Statement"]["properties"]["evidence_ids"]["items"]["enum"]
        self.assertEqual(set(ids), set(packet["evidence"]))
        self.assertEqual(len(ids), 176)
        self.assertNotIn("not-an-evidence-id", ids)
        self.assertEqual(schema["properties"]["source_observations"]["maxItems"], 0)

    def test_source_schema_excludes_draft_ids_without_mutating_shared_schema(self):
        packet = {"evidence": {"p1": {"kind": "draft"}, "source:one": {"kind": "source"}}}
        schema = output_schema(packet)
        generic_ids = schema["$defs"]["Statement"]["properties"]["evidence_ids"]["items"]["enum"]
        source_ids = schema["$defs"]["SourceStatement"]["properties"]["evidence_ids"]["items"]["enum"]
        self.assertEqual(set(generic_ids), {"p1", "source:one"})
        self.assertEqual(source_ids, ["source:one"])
        self.assertEqual(schema["properties"]["source_observations"]["items"], {"$ref": "#/$defs/SourceStatement"})
        other = output_schema({"evidence": {"p999": {"kind": "draft"}}})
        self.assertEqual(other["$defs"]["Statement"]["properties"]["evidence_ids"]["items"]["enum"], ["p999"])
        self.assertNotIn("enum", SummaryOutput.model_json_schema()["$defs"]["Statement"]["properties"]["evidence_ids"]["items"])
        with self.assertRaisesRegex(ValueError, "No evidence"):
            output_schema({"evidence": {}})

    def test_provider_ignoring_id_enum_is_rejected_and_usage_is_retained(self):
        def invalid(request):
            if not request.url.path.endswith(":generateContent"):
                return None
            body = json.loads(request.content)
            packet = json.loads(body["contents"][0]["parts"][0]["text"])
            output = output_for(packet)
            output["overview"][0]["evidence_ids"] = ["invented-id"]
            return httpx.Response(200, json={
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(output)}]}}],
                "usageMetadata": {"promptTokenCount": 300, "candidatesTokenCount": 80, "totalTokenCount": 380},
            })
        self.response_override = invalid
        doc = self.document(consent=True)
        self.summaries.tick(self.http)
        result = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["output"])
        self.assertIn("outside the input packet", result["error"])
        self.assertEqual(result["usage"]["totalTokenCount"], 380)
        self.assertEqual(result["usage"]["counted_input_tokens"], 300)
        self.assertEqual(result["reserved_microusd"], 25450)
        self.assertFalse(self.summaries.tick(self.http))
        self.assertEqual(len(self.requests), 2)

    def test_queued_prompt_version_is_updated_before_any_provider_request(self):
        doc = self.document(consent=True)
        with self.db.transaction() as session:
            row = session.get(SummaryJobRow, doc["ai_summary"]["id"])
            row.prompt_version = "gemini-summary-1"
        old_report = self.client.post(f"/v1/documents/{doc['id']}/reports").json()
        self.summaries.tick(self.http)
        result = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["prompt_version"], "gemini-summary-2")
        saved = self.client.get(f"/v1/documents/{doc['id']}/reports/{old_report['id']}").json()
        self.assertEqual(saved, old_report)
        self.assertEqual(saved["document"]["ai_summary"]["prompt_version"], "gemini-summary-1")

    def test_failures_are_explicit_and_do_not_block_evidence_report(self):
        for payload in ({"candidates": []}, {"candidates": [{"finishReason": "MAX_TOKENS"}]},
                        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}):
            self.response_override = lambda request, data=payload: httpx.Response(200, json=data) if request.url.path.endswith(":generateContent") else None
            doc = self.document(consent=True)
            self.summaries.tick(self.http)
            current = self.client.get("/v1/documents/" + doc["id"]).json()
            self.assertEqual(current["ai_summary"]["status"], "failed")
            self.assertIsNone(current["ai_summary"]["output"])
            self.assertTrue(current["ai_summary"]["error"])
            self.assertEqual(self.client.post(f"/v1/documents/{doc['id']}/reports").status_code, 200)

    def test_token_limit_prevents_generation_without_silent_truncation(self):
        self.response_override = lambda request: httpx.Response(200, json={"totalTokens": MAX_INPUT_TOKENS + 1})
        doc = self.document(consent=True)
        self.summaries.tick(self.http)
        self.assertEqual(len(self.requests), 1)
        summary = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(summary["status"], "failed")
        self.assertIn("no partial", summary["error"])

    def test_oversized_packet_is_not_sent(self):
        doc = self.document(consent=True)
        with patch("app.summary.MAX_PACKET_BYTES", 10):
            self.summaries.tick(self.http)
        self.assertEqual(self.requests, [])
        summary = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["reserved_microusd"], 0)

    def test_successor_model_has_matching_rates_and_thinking_configuration(self):
        from app.summary import generation_config
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(gemini_model="gemini-3.8-flash")
            settings.validate()
        self.assertEqual((settings.gemini_input_rate, settings.gemini_output_rate), (750000, 3750000))
        config = generation_config(settings.gemini_model, {"evidence": {"p1": {"kind": "draft"}}})
        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": "LOW"})
        self.assertNotIn("thinkingBudget", config["thinkingConfig"])

    def test_flash_lite_default_rates_and_generation_settings(self):
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()
            settings.validate()
        self.assertEqual(settings.gemini_model, "gemini-3.5-flash-lite")
        self.assertEqual((settings.gemini_input_rate, settings.gemini_output_rate), (300000, 2500000))
        config = generation_config(settings.gemini_model, {"evidence": {"p1": {"kind": "draft"}}})
        self.assertEqual(config["temperature"], 1.0)
        self.assertNotIn("thinkingConfig", config)
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["maxOutputTokens"], 2500)

    def test_flash_lite_summary_and_report_use_existing_validated_flow(self):
        self.settings.gemini_model = "gemini-3.5-flash-lite"
        self.settings.validate()
        doc = self.document(consent=True)
        self.assertTrue(self.summaries.tick(self.http))
        response = self.client.post(f"/v1/documents/{doc['id']}/reports")
        self.assertEqual(response.status_code, 200)
        summary = response.json()["document"]["ai_summary"]
        self.assertEqual(summary["status"], "completed", summary)
        self.assertEqual(summary["model"], "gemini-3.5-flash-lite")
        self.assertEqual(summary["usage"]["model_version"], "gemini-3.5-flash-lite")
        self.assertEqual(summary["reserved_microusd"], 25450)
        self.assertEqual(len(self.requests), 2)

    def test_retired_model_is_not_reported_as_network_timeout(self):
        self.response_override = lambda request: httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
        doc = self.document(consent=True)
        self.summaries.tick(self.http)
        result = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(result["status"], "failed")
        self.assertIn("model is unavailable", result["error"])

    def test_provider_overload_is_reported_without_automatic_retry(self):
        self.response_override = lambda request: httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}})
        doc = self.document(consent=True)
        self.summaries.tick(self.http)
        self.summaries.tick(self.http)
        result = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(result["status"], "failed")
        self.assertIn("HTTP 503", result["error"])
        self.assertEqual(len(self.requests), 1)

    def test_queued_old_model_is_not_sent_after_configuration_changes(self):
        doc = self.document(consent=True)
        self.settings.gemini_model = "gemini-3.8-flash"
        self.summaries.tick(self.http)
        result = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(result["status"], "failed")
        self.assertIn("model changed", result["error"])
        self.assertEqual(self.requests, [])

    def test_provider_quota_error_preserves_reservation_and_does_not_retry(self):
        self.response_override = lambda request: httpx.Response(429, json={"error": {"message": "private provider message"}})
        doc = self.document(consent=True)
        self.summaries.tick(self.http)
        self.summaries.tick(self.http)
        summary = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(summary["status"], "failed")
        self.assertNotIn("private provider", summary["error"])
        self.assertEqual(summary["reserved_microusd"], 25450)

    def test_interrupted_job_is_not_replayed(self):
        doc = self.document(consent=True)
        claimed = self.summaries.claim()
        with self.db.transaction() as session:
            session.execute(update(SummaryJobRow).values(lease_until=now()-1))
        self.assertFalse(self.summaries.tick(self.http))
        self.assertEqual(self.requests, [])
        summary = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
        self.assertEqual(summary["status"], "failed")
        self.summaries.finish(claimed[0], doc["id"], claimed[2], output={})
        self.assertEqual(self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]["status"], "failed")

    def test_delete_after_token_count_prevents_generation_and_retains_quota(self):
        doc = self.document(consent=True)
        def delete(request):
            self.assertTrue(request.url.path.endswith(":countTokens"))
            self.app.state.service.mark_deleted("local-development-owner", doc["id"])
            return httpx.Response(200, json={"totalTokens": 300})
        self.response_override = delete
        self.summaries.tick(self.http)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.client.get("/v1/documents/" + doc["id"]).status_code, 404)
        with self.db.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(SummaryJobRow)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(SummaryConsentRow)), 0)
            self.assertEqual(session.get(SummaryQuotaRow, "gemini:account").reserved_microusd, 25450)

    def test_new_analysis_cancels_summary_and_other_owner_cannot_access_it(self):
        doc = self.document(consent=True)
        job_id = doc["ai_summary"]["id"]
        path = self.summary_path(doc) + "/" + job_id
        self.app.dependency_overrides[self.app.state.owner_dependency] = lambda: "different-owner"
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.generate(doc).status_code, 404)
        self.app.dependency_overrides.clear()
        self.assertEqual(self.client.post(f"/v1/documents/{doc['id']}/analyses").status_code, 200)
        self.assertEqual(self.client.get(path).json()["status"], "cancelled")

    def test_request_quota_survives_document_deletion(self):
        for index in range(6):
            doc = self.document(consent=True)
            self.summaries.tick(self.http)
            current = self.client.get("/v1/documents/" + doc["id"]).json()["ai_summary"]
            self.assertEqual(current["status"], "completed" if index < 5 else "failed")
            self.client.delete("/v1/documents/" + doc["id"])
        self.assertEqual(len(self.requests), 10)

    def test_raising_owner_limit_preserves_usage_and_unblocks_next_request(self):
        owner = "local-development-owner"
        for _ in range(5):
            with self.db.transaction() as session:
                self.summaries.reserve(session, owner)
        with self.assertRaisesRegex(ValueError, r"per-user daily request limit reached \(5/5\).*05:30 IST"):
            with self.db.transaction() as session:
                self.summaries.reserve(session, owner)
        self.settings.gemini_owner_daily_requests = 10
        self.settings.validate()
        with self.db.transaction() as session:
            self.assertEqual(self.summaries.reserve(session, owner), 25450)
        with self.db.sessions() as session:
            quota = session.get(SummaryQuotaRow, "gemini:account")
            self.assertEqual(quota.requests, 6)
            self.assertEqual(quota.reserved_microusd, 6 * 25450)

    def test_app_daily_limit_is_distinct_from_owner_limit(self):
        for index in range(20):
            with self.db.transaction() as session:
                self.summaries.reserve(session, f"owner-{index}")
        with self.assertRaisesRegex(ValueError, r"app daily request limit reached \(20/20\)"):
            with self.db.transaction() as session:
                self.summaries.reserve(session, "new-owner")

    def test_allowance_error_includes_amounts_and_no_daily_reset(self):
        self.settings.gemini_budget_microusd = 25450
        with self.db.transaction() as session:
            self.summaries.reserve(session, "owner")
        with self.assertRaisesRegex(ValueError, r"\$0.025450 reserved of \$0.025450.*does not reset daily"):
            with self.db.transaction() as session:
                self.summaries.reserve(session, "owner")
        with self.db.sessions() as session:
            self.assertEqual(session.get(SummaryQuotaRow, "gemini:account").requests, 1)

    def test_owner_limit_configuration_is_bounded(self):
        for invalid in (0, -1, 21, True, 1.5):
            with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, "GEMINI_OWNER_DAILY_REQUESTS"):
                Settings(gemini_owner_daily_requests=invalid).validate()
        with patch.dict("os.environ", {"GEMINI_OWNER_DAILY_REQUESTS": "10"}):
            configured = Settings()
            configured.validate()
            self.assertEqual(configured.gemini_owner_daily_requests, 10)

    def test_budget_reservations_are_atomic(self):
        self.settings.gemini_budget_microusd = 25450
        barrier, outcomes = threading.Barrier(2), []
        def reserve(owner):
            barrier.wait(timeout=5)
            try:
                with self.db.transaction() as session:
                    self.summaries.reserve(session, owner)
                outcomes.append(True)
            except ValueError:
                outcomes.append(False)
        threads = [threading.Thread(target=reserve, args=(f"owner-{i}",)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes), [False, True])
        with self.db.sessions() as session:
            self.assertEqual(session.get(SummaryQuotaRow, "gemini:account").reserved_microusd, 25450)

    def test_file_and_hosted_upload_consent_are_persisted(self):
        response = self.client.post("/v1/documents/file", data={"consent": "true", "ai_summary_consent": "true"},
                                    files={"file": ("sample.txt", DRAFT.encode(), "text/plain")})
        self.assertEqual(response.status_code, 200, response.text)
        self.worker.tick()
        self.assertEqual(self.client.get("/v1/documents/" + response.json()["id"]).json()["ai_summary"]["status"], "queued")
        from unittest.mock import Mock
        storage = Mock()
        storage.sign_upload.return_value = {"upload_url": "https://project.supabase.co/synthetic", "upload_headers": {}}
        storage.download.return_value = DRAFT.encode()
        self.app.state.service.storage = storage
        reservation = self.app.state.service.create("hosted-owner", "Synthetic", "draft.txt", size=len(DRAFT.encode()),
                                                    hosted=True, ai_summary_consent=True)
        with self.db.sessions() as session:
            self.assertIsNotNone(session.get(SummaryConsentRow, reservation["document_id"]))
        self.app.state.service.finalize("hosted-owner", reservation["document_id"])
        self.worker.storage = storage
        self.worker.tick()
        with self.db.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(SummaryJobRow)), 2)
