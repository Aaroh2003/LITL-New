import io
import json
import shutil
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from uvicorn import Config as UvicornConfig

from app.config import MAX_CHARACTERS, MAX_FILE_BYTES, Settings
from app.db import Database
from app.extraction import ExtractionError, detect, extract, extract_bounded, paragraphs_for
from app.main import create_app
from app.models import Base, DocumentRow, FindingRow, ReportRow, ReviewEvent, RunRow, RunScopeRow, SourceBudgetRow, SourceOpen, SourceRequestRow, now, uid
from app.network import RemoteError, bounded_request
from app.sources import IndianKanoon, identity_matches, normalize_quote
from app.storage import SupabaseStorage
from app.worker import JobLost, Worker


SAMPLE = 'Alpha v. Beta, (2020) 1 SCC 100 stated: “Bail shall not be refused solely on suspicion.”\nSection 41 of CrPC'
BODY = "<h2>Alpha v. Beta on 1 January, 2020</h2><div>Equivalent citations: (2020) 1 SCC 100</div><p>Bail shall not be refused solely on suspicion.</p>"


def source_http(request):
    if request.url.path == "/search/":
        return httpx.Response(200, json={"docs": [{"tid": 123, "title": "Alpha v. Beta"}]})
    if request.url.path == "/doc/123/":
        return httpx.Response(200, json={"title": "Alpha v. Beta on 1 January, 2020", "doc": BODY})
    raise AssertionError(f"Unexpected outbound request: {request.url.host}{request.url.path}")


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(".test-data") / uid()
        self.directory.mkdir(parents=True)
        self.settings = Settings(
            database_url=f"sqlite:///{self.directory}/test.db", worker_enabled=False, testing=True,
            ik_token="", ik_terms_accepted=False, ik_budget_paise=10000, ik_run_budget_paise=5000,
            ik_daily_budget_paise=10000, ik_owner_daily_budget_paise=10000,
        )
        self.http = httpx.Client(transport=httpx.MockTransport(source_http), follow_redirects=False)
        self.app = create_app(self.settings, self.http)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.db = self.app.state.db
        self.worker = self.app.state.worker

    def tearDown(self):
        self.client.__exit__(None, None, None)
        shutil.rmtree(self.directory)

    def create(self, text=SAMPLE):
        response = self.client.post("/v1/documents/text", json={"title": "Synthetic test", "text": text, "consent": True})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def complete(self, live=False, text=SAMPLE):
        if live:
            self.settings.ik_token, self.settings.ik_terms_accepted = "synthetic-token", True
        document = self.create(text)
        self.assertTrue(self.worker.tick())
        return self.client.get("/v1/documents/" + document["id"]).json()

    def test_public_config_and_health(self):
        config = self.client.get("/v1/config").json()
        self.assertEqual(config["max_file_bytes"], 10485760)
        self.assertFalse(config["source_lookup_configured"])
        self.assertNotIn("ik_token", config)
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/readyz").status_code, 200)

    def test_local_env_file_and_exported_precedence(self):
        env_file = self.directory / ".env"
        env_file.write_text(
            "INDIAN_KANOON_API_TOKEN=file-token\nINDIAN_KANOON_TERMS_ACCEPTED=true\n"
            "INDIAN_KANOON_BUDGET_PAISE=40000\n"
        )
        with patch.dict("os.environ", {"INDIAN_KANOON_API_TOKEN": "exported-token"}, clear=True):
            UvicornConfig("app.main:app", env_file=str(env_file), log_config=None)
            settings = Settings()
            settings.validate()
            self.assertEqual(settings.ik_token, "exported-token")
            self.assertTrue(settings.source_lookup_configured)
            self.assertEqual(settings.ik_budget_paise, 40000)
            self.assertNotIn("exported-token", repr(settings))
            self.assertNotIn("exported-token", json.dumps(settings.public()))

    def test_zero_budget_prevents_network_calls(self):
        self.settings.ik_budget_paise = 0
        with patch.object(self.http, "stream", side_effect=AssertionError("Must not contact provider")):
            document = self.complete(live=True)
            self.client.get("/healthz")
            self.client.get("/readyz")
            self.client.get("/v1/config")
        self.assertEqual(document["findings"][0]["status"], "unavailable")
        self.assertEqual(document["latest_run"]["source_usage"]["reserved_paise"], 0)

    def test_source_spending_limits_and_partial_report(self):
        for limit in ("ik_budget_paise", "ik_run_budget_paise", "ik_daily_budget_paise", "ik_owner_daily_budget_paise"):
            with self.subTest(limit=limit):
                original = getattr(self.settings, limit)
                with self.db.sessions() as session:
                    spent = session.get(SourceBudgetRow, "ik:account")
                    current = spent.reserved_paise if spent else 0
                setattr(self.settings, limit, 50 if limit == "ik_run_budget_paise" else current + 50)
                document = self.complete(live=True)
                self.assertEqual(document["findings"][0]["status"], "unavailable")
                self.assertIn("spending limit", document["findings"][0]["note"])
                usage = document["latest_run"]["source_usage"]
                self.assertEqual(usage["reserved_paise"], 50)
                self.assertEqual(usage["requests_by_operation"], {"search": 1})
                report = self.client.post(f"/v1/documents/{document['id']}/reports")
                self.assertEqual(report.status_code, 200)
                self.assertEqual(report.json()["document"]["latest_run"]["source_usage"], usage)
                setattr(self.settings, limit, original)

    def test_exact_budget_allows_request_then_refuses_more(self):
        self.settings.ik_budget_paise = 70
        document = self.complete(live=True)
        self.assertEqual(document["findings"][0]["status"], "source_found")
        self.assertEqual(document["latest_run"]["source_usage"]["reserved_paise"], 70)
        second = self.complete(live=True)
        self.assertEqual(second["findings"][0]["status"], "unavailable")
        self.assertEqual(second["latest_run"]["source_usage"]["reserved_paise"], 0)
        with self.db.sessions() as session:
            self.assertEqual(session.get(SourceBudgetRow, "ik:account").reserved_paise, 70)

    def test_cost_snapshot_survives_later_analysis_and_no_read_spend(self):
        document = self.complete(live=True, text=SAMPLE.split("\n")[0])
        base = f"/v1/documents/{document['id']}"
        with patch.object(self.http, "stream", side_effect=AssertionError("Reads must not contact provider")):
            report = self.client.post(base + "/reports").json()
            self.assertEqual(report["document"]["latest_run"]["source_usage"]["reserved_paise"], 70)
            self.assertEqual(report["document"]["latest_run"]["source_usage"]["billing_status"], "unreconciled")
            self.assertEqual(self.client.get(base + "/reports/" + report["id"]).json(), report)
        self.assertEqual(self.client.post(base + "/analyses").status_code, 200)
        self.worker.tick()
        self.assertEqual(self.client.get(base + "/reports/" + report["id"]).json(), report)
        with self.db.sessions() as session:
            self.assertEqual(session.get(SourceBudgetRow, "ik:account").reserved_paise, 140)

    def test_uncertain_requests_remain_reserved_after_recovery_and_deletion(self):
        self.settings.ik_token, self.settings.ik_terms_accepted = "synthetic-token", True
        document = self.create(text=SAMPLE.split("\n")[0])
        job = self.worker.claim()
        self.assertTrue(self.worker.heartbeat(job, reserve="search"))
        with self.db.transaction() as session:
            session.execute(update(RunRow).values(lease_until=now() - 1))
        replacement_db = Database(self.settings.database_url)
        try:
            replacement = Worker(replacement_db, self.settings, None, self.http, self.app.state.service)
            self.assertTrue(replacement.tick())
        finally:
            replacement_db.engine.dispose()
        result = self.client.get(f"/v1/documents/{document['id']}").json()
        self.assertEqual(result["latest_run"]["source_usage"]["reserved_paise"], 120)
        self.assertEqual(self.client.delete(f"/v1/documents/{document['id']}").status_code, 204)
        with self.db.sessions() as session:
            self.assertEqual(session.get(SourceBudgetRow, "ik:account").reserved_paise, 120)
            self.assertEqual(session.scalar(select(func.count()).select_from(SourceRequestRow)), 0)

    def test_concurrent_account_reservations_across_owners(self):
        self.settings.ik_budget_paise = 50
        for owner in ("owner-a", "owner-b"):
            self.app.state.service.create(owner, "Synthetic", "text.txt", text=SAMPLE)
        jobs = [self.worker.claim(), self.worker.claim()]
        barrier, results, errors = threading.Barrier(2), [], []
        def reserve(job):
            try:
                barrier.wait(timeout=5)
                results.append(self.worker.heartbeat(job, reserve="search"))
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=reserve, args=(job,)) for job in jobs]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sorted(results), [False, True])
        with self.db.sessions() as session:
            self.assertEqual(session.get(SourceBudgetRow, "ik:account").reserved_paise, 50)
            self.assertEqual(session.scalar(select(func.count()).select_from(SourceRequestRow)), 1)

    def test_daily_budget_resets_without_resetting_lifetime(self):
        from datetime import datetime, timezone
        self.settings.ik_daily_budget_paise = 50
        document = self.create()
        job = self.worker.claim()
        with patch("app.budget.datetime") as clock:
            clock.now.return_value = datetime(2026, 9, 25, 23, 59, tzinfo=timezone.utc)
            self.assertTrue(self.worker.heartbeat(job, reserve="search"))
            self.assertFalse(self.worker.heartbeat(job, reserve="search"))
            clock.now.return_value = datetime(2026, 9, 26, 0, 0, tzinfo=timezone.utc)
            self.assertTrue(self.worker.heartbeat(job, reserve="search"))
        with self.db.sessions() as session:
            self.assertEqual(session.get(SourceBudgetRow, "ik:account").reserved_paise, 100)
        result = self.client.get(f"/v1/documents/{document['id']}").json()
        self.assertEqual(result["latest_run"]["source_usage"]["reserved_paise"], 100)

    def test_cost_accounting_handles_legacy_unpriced_runs(self):
        document = self.create()
        with self.db.transaction() as session:
            session.execute(update(RunRow).values(source_requests=2))
        result = self.client.get(f"/v1/documents/{document['id']}").json()
        self.assertEqual(result["latest_run"]["source_usage"]["unpriced_requests"], 2)
        self.settings.ik_run_budget_paise = 149
        job = self.worker.claim()
        self.assertFalse(self.worker.heartbeat(job, reserve="search"))

    def test_source_failure_still_consumes_reserved_budget(self):
        def timeout(request):
            raise httpx.ReadTimeout("synthetic timeout")
        with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
            self.worker.client = client
            document = self.complete(live=True)
        self.assertEqual(document["findings"][0]["status"], "unavailable")
        self.assertEqual(document["latest_run"]["source_usage"]["reserved_paise"], 50)

    def test_source_request_records_are_immutable(self):
        self.complete(live=True)
        with self.assertRaises(IntegrityError):
            with self.db.transaction() as session:
                session.execute(update(SourceRequestRow).values(cost_paise=0))

    def test_existing_schema_upgrade_preserves_saved_report(self):
        document = self.complete()
        snapshot = self.client.post(f"/v1/documents/{document['id']}/reports").json()
        # Simulate a pre-accounting deployment without replacing its existing tables.
        with self.db.engine.begin() as connection:
            Base.metadata.tables["source_requests"].drop(connection)
            Base.metadata.tables["source_budgets"].drop(connection)
        self.db.setup()
        self.db.setup()
        self.assertEqual(
            self.client.get(f"/v1/documents/{document['id']}/reports/{snapshot['id']}").json(), snapshot,
        )
        with self.db.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(SourceRequestRow)), 0)

    def test_durable_create_and_unconfigured_evidence(self):
        document = self.create()
        self.assertEqual(document["latest_run"]["status"], "queued")
        self.assertEqual(self.client.get("/v1/documents").json()[0]["id"], document["id"])
        self.worker.tick()
        reopened = self.client.get("/v1/documents/" + document["id"]).json()
        self.assertEqual(reopened["latest_run"]["status"], "completed")
        statuses = {f["kind"]: f["status"] for f in reopened["findings"]}
        self.assertEqual(statuses, {"case_citation": "unavailable", "quotation": "not_checked", "statutory_reference": "unsupported"})
        self.assertEqual(reopened["metrics"]["source_coverage"]["numerator"], 0)
        self.assertIsNone(reopened["metrics"]["quotation_fidelity"]["percentage"])
        self.assertTrue(all(not f["sources"] and f["decision"] is None for f in reopened["findings"]))

    def test_mock_source_identity_quote_and_offsets(self):
        document = self.complete(live=True)
        case, quote, statute = document["findings"]
        self.assertEqual(case["status"], "source_found")
        self.assertEqual(quote["status"], "source_found")
        self.assertTrue(quote["quote_checked"])
        self.assertEqual(case["sources"][0]["url"], "https://indiankanoon.org/doc/123/")
        for finding in document["findings"]:
            self.assertEqual(document["text"][finding["start"]:finding["end"]], finding["excerpt"])
        self.assertEqual(document["metrics"]["quotation_fidelity"]["percentage"], 100)
        self.assertEqual(document["metrics"]["review_completion"]["numerator"], 0)

    def test_changed_negation_is_quote_mismatch(self):
        document = self.complete(live=True, text=SAMPLE.replace("shall not", "shall"))
        quote = next(f for f in document["findings"] if f["kind"] == "quotation")
        self.assertEqual(quote["status"], "quote_mismatch")
        self.assertTrue(quote["sources"])
        self.assertEqual(document["metrics"]["quotation_fidelity"]["percentage"], 0)

    def test_no_reference_document(self):
        document = self.complete(text="This anonymized application requests a hearing.")
        self.assertEqual(document["findings"], [])
        self.assertEqual(document["metrics"]["total"], 0)
        self.assertIsNone(document["metrics"]["source_coverage"]["percentage"])

    def test_dynamic_statute_and_formula_report_without_source_spending(self):
        with patch.object(self.http, "stream", side_effect=AssertionError("No statute API calls")):
            document = self.complete(live=True, text="Section 335")
        item = document["findings"][0]
        self.assertIsNone(item["statute"]["act"])
        self.assertIn("Act or Code", item["note"])
        self.assertNotIn("CrPC/BNSS", item["note"])
        self.assertEqual(document["analysis_scope"]["detected"], 1)
        base = f"/v1/documents/{document['id']}"
        snapshot = self.client.post(base + "/reports").json()
        self.assertEqual(snapshot["schema_version"], 3)
        self.assertEqual(snapshot["overview"]["state"], "review_incomplete")
        self.assertEqual(snapshot["document"]["metrics"]["assessment"]["definition_version"], "evidence-2")
        self.assertEqual(snapshot["review_versions"], {item["id"]: 0})
        self.assertEqual(len(snapshot["input_sha256"]), 64)
        self.assertEqual(snapshot["parser_version"], "deterministic-2")
        reviewed = self.client.put(base + f"/findings/{item['id']}/review", json={
            "decision": "unresolved", "review_note": "Act needs identifying", "correction": "", "expected_version": 0,
        })
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(self.client.get(base + "/reports/" + snapshot["id"]).json(), snapshot)
        newer = self.client.post(base + "/reports").json()
        self.assertEqual(newer["overview"]["state"], "reviewed_with_unresolved")
        self.assertEqual(newer["document"]["metrics"]["assessment"]["metrics"]["review_completion"]["percentage"], 100)
        self.assertEqual(newer["document"]["metrics"]["assessment"]["metrics"]["review_disposition"]["percentage"], 0)

    def test_old_live_statutes_get_context_but_old_snapshots_are_unchanged(self):
        document = self.complete(text="Section 335")
        base = f"/v1/documents/{document['id']}"
        legacy = {"document": document, "disclaimer": "Original saved disclaimer"}
        legacy["document"]["findings"][0]["note"] = "Original saved generic note"
        legacy["document"]["metrics"].pop("assessment")
        with self.db.transaction() as session:
            item = session.scalar(select(FindingRow))
            item.data = {**{key: value for key, value in item.data.items() if key not in {
                "link_state", "link_message", "reference_url",
            }}, "note": "Old generic note"}
            session.delete(session.get(RunScopeRow, document["latest_run"]["id"]))
            report = ReportRow(id=uid(), document_id=document["id"], created_at=now(), snapshot=legacy)
            session.add(report)
            report_id = report.id
        live = self.client.get(base).json()
        self.assertIn("not identified in this reference", live["findings"][0]["note"])
        self.assertIsNone(live["analysis_scope"])
        self.assertEqual(self.client.get(base + "/reports/" + report_id).json(), legacy)

    def test_identity_metric_excludes_competing_matches(self):
        def competing(request):
            if request.url.path == "/search/":
                return httpx.Response(200, json={"docs": [{"tid": 123}, {"tid": 456}]})
            return httpx.Response(200, json={"title": "Alpha v. Beta", "doc": BODY})
        with httpx.Client(transport=httpx.MockTransport(competing)) as client:
            self.worker.client = client
            document = self.complete(live=True)
        self.assertEqual(document["findings"][0]["identity_assessment"], "unknown")
        self.assertEqual(document["metrics"]["assessment"]["counts"]["assessed_identities"], 0)

    def test_compared_nonmatching_candidate_is_scoped_not_invalid(self):
        def different(request):
            if request.url.path == "/search/":
                return httpx.Response(200, json={"docs": [{"tid": 456}]})
            return httpx.Response(200, json={"title": "Gamma v. Delta", "doc": "Equivalent citations: (2021) 1 SCC 200"})
        with httpx.Client(transport=httpx.MockTransport(different)) as client:
            self.worker.client = client
            document = self.complete(live=True)
        self.assertEqual(document["findings"][0]["status"], "ambiguous")
        self.assertEqual(document["findings"][0]["identity_assessment"], "not_matched")
        self.assertEqual(document["metrics"]["assessment"]["metrics"]["identity_match"]["percentage"], 0)
        self.assertIn("does not prove the reference invalid", document["findings"][0]["note"])

    def test_unicode_offsets_and_reference_limit(self):
        document = self.complete(text="😀 Context.\n" + "\n".join(f"Section {n} of CrPC" for n in range(1, 55)))
        self.assertEqual(len(document["findings"]), 50)
        self.assertEqual(document["findings"][0]["start"], 11)
        self.assertTrue(any("first 50" in w for w in document["latest_run"]["warnings"]))

    def test_consent_and_limits(self):
        for consent in (False, None, 1, "true"):
            self.assertEqual(self.client.post("/v1/documents/text", json={"title": "x", "text": SAMPLE, "consent": consent}).status_code, 422)
        self.assertEqual(self.client.post("/v1/documents/text", json={"title": "x", "text": "a" * (MAX_CHARACTERS + 1), "consent": True}).status_code, 422)
        self.assertEqual(self.client.post("/v1/documents/text", json={"title": "x", "text": " \n", "consent": True}).status_code, 422)
        self.assertEqual(self.client.post("/v1/documents/text", content=b"x", headers={"Content-Length": str(MAX_FILE_BYTES)}).status_code, 413)

    def test_multipart_txt_is_real_queued_input(self):
        response = self.client.post("/v1/documents/file", data={"consent": "true"},
                                    files={"file": ("anonymized.txt", SAMPLE.encode(), "text/plain")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["latest_run"]["status"], "queued")
        self.worker.tick()
        document = self.client.get("/v1/documents/" + response.json()["id"]).json()
        self.assertEqual(document["text"], SAMPLE)
        self.assertEqual(len(document["findings"]), 3)

    def test_bad_file_signature_and_binary_txt(self):
        for name, content in (("fake.pdf", b"not pdf"), ("macro.exe", b"abc"), ("file.txt", b"\x00abc"), ("a.docx", b"bad")):
            response = self.client.post("/v1/documents/file", data={"consent": "true"},
                                        files={"file": (name, content)})
            self.assertEqual(response.status_code, 422, response.text)

    def test_oversize_file_never_parsed(self):
        with patch("app.main.file_kind") as parser:
            response = self.client.post("/v1/documents/file", data={"consent": "true"},
                                        files={"file": ("big.txt", b"x" * (MAX_FILE_BYTES + 1))})
            self.assertEqual(response.status_code, 413)
            parser.assert_not_called()

    def test_review_optimistic_version_and_audit(self):
        document = self.complete()
        finding = document["findings"][0]
        url = f"/v1/documents/{document['id']}/findings/{finding['id']}/review"
        review = {"decision": "confirmed", "review_note": "Human checked separately", "correction": "", "expected_version": 0}
        response = self.client.put(url, json=review)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["version"], 1)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertEqual(response.json()["sources"], [])
        self.assertEqual(self.client.put(url, json=review).status_code, 409)
        with self.db.sessions() as session:
            event = session.scalar(select(ReviewEvent))
            self.assertEqual(event.before["decision"], None)
            self.assertEqual(event.after["decision"], "confirmed")
        review.update(decision="corrected", expected_version=1)
        self.assertEqual(self.client.put(url, json=review).status_code, 422)

    def test_concurrent_review_only_one_wins(self):
        document = self.complete()
        finding = document["findings"][0]
        from app.main import ReviewInput
        body = ReviewInput(decision="unresolved", review_note="", correction="", expected_version=0)
        outcomes = []
        def save():
            try:
                self.app.state.service.review("local-development-owner", document["id"], finding["id"], body)
                outcomes.append(200)
            except Exception as exc:
                outcomes.append(exc.status_code)
        threads = [threading.Thread(target=save) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), [200, 409])

    def test_snapshot_immutable_across_review_and_reanalysis(self):
        document = self.complete()
        base = "/v1/documents/" + document["id"]
        snapshot = self.client.post(base + "/reports").json()
        finding = document["findings"][0]
        self.client.put(base + f"/findings/{finding['id']}/review", json={
            "decision": "rejected", "review_note": "Review record", "correction": "", "expected_version": 0,
        })
        self.assertEqual(self.client.get(base + "/reports/" + snapshot["id"]).json(), snapshot)
        self.assertEqual(len(self.client.get(base + "/reports").json()), 1)
        self.assertEqual(self.client.post(base + "/analyses").status_code, 200)
        self.assertEqual(self.client.post(base + "/reports").status_code, 409)
        self.worker.tick()
        reopened = self.client.get(base).json()
        self.assertTrue(all(f["decision"] is None for f in reopened["findings"]))
        self.assertEqual(self.client.get(base + "/reports/" + snapshot["id"]).json(), snapshot)
        with self.assertRaises(IntegrityError):
            with self.db.transaction() as session:
                session.execute(update(ReportRow).values(snapshot={}))

    def test_source_open_is_idempotent_does_not_bump_review_version(self):
        document = self.complete(live=True)
        finding = document["findings"][0]
        base = f"/v1/documents/{document['id']}/findings/{finding['id']}/source-open"
        for _ in range(2):
            response = self.client.post(base, json={"source_id": finding["sources"][0]["id"]})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["source_opened"])
            self.assertEqual(response.json()["version"], 0)
        with self.db.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(SourceOpen)), 1)
        self.assertEqual(self.client.post(base, json={"source_id": uid()}).status_code, 404)

    def test_old_analysis_cannot_accept_review_or_source_activity(self):
        document = self.complete(live=True)
        base = "/v1/documents/" + document["id"]
        finding = document["findings"][0]
        snapshot = self.client.post(base + "/reports").json()
        self.assertEqual(self.client.post(base + "/analyses").status_code, 200)
        review_path = base + f"/findings/{finding['id']}/review"
        activity_path = base + f"/findings/{finding['id']}/source-open"
        review = {
            "decision": "confirmed", "review_note": "Stale tab",
            "correction": "", "expected_version": finding["version"],
        }
        for complete_new_run in (False, True):
            if complete_new_run:
                self.worker.tick()
            self.assertEqual(self.client.put(review_path, json=review).status_code, 409)
            self.assertEqual(self.client.post(activity_path, json={"source_id": finding["sources"][0]["id"]}).status_code, 409)
        self.assertEqual(self.client.get(base + "/reports/" + snapshot["id"]).json(), snapshot)
        with self.db.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ReviewEvent)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(SourceOpen)), 0)

    def test_owner_isolation_on_all_private_resources(self):
        document = self.complete(live=True)
        base = "/v1/documents/" + document["id"]
        report = self.client.post(base + "/reports").json()
        finding = document["findings"][0]
        self.app.dependency_overrides[self.app.state.owner_dependency] = lambda: "other-owner"
        self.assertEqual(self.client.get("/v1/documents").json(), [])
        operations = [
            ("get", base, None), ("delete", base, None), ("post", base + "/analyses", None),
            ("get", base + "/analyses/" + document["latest_run"]["id"], None),
            ("post", base + "/reports", None), ("get", base + "/reports", None),
            ("get", base + "/reports/" + report["id"], None),
            ("put", base + f"/findings/{finding['id']}/review", {"decision": "confirmed", "review_note": "", "correction": "", "expected_version": 0}),
            ("post", base + f"/findings/{finding['id']}/source-open", {"source_id": finding["sources"][0]["id"]}),
        ]
        for method, url, body in operations:
            self.assertEqual(self.client.request(method, url, json=body).status_code, 404, url)

    def test_cancel_and_active_run_guard(self):
        document = self.create()
        base = "/v1/documents/" + document["id"]
        self.assertEqual(self.client.post(base + "/analyses").status_code, 409)
        run = self.client.post(base + "/analyses/" + document["latest_run"]["id"] + "/cancel").json()
        self.assertEqual(run["status"], "cancelled")
        self.assertFalse(self.worker.tick())
        self.assertEqual(self.client.post(base + "/analyses").status_code, 200)

    def test_delete_cascades_and_prevents_worker_publication(self):
        document = self.create()
        job = self.worker.claim()
        self.assertEqual(self.client.delete("/v1/documents/" + document["id"]).status_code, 204)
        self.assertEqual(self.client.get("/v1/documents/" + document["id"]).status_code, 404)
        with self.assertRaises(JobLost):
            self.worker.process(job)
        with self.db.sessions() as session:
            for model in (DocumentRow, RunRow, FindingRow, ReportRow, ReviewEvent):
                self.assertEqual(session.scalar(select(func.count()).select_from(model)), 0)

    def test_delete_during_source_network_work_cannot_publish(self):
        self.settings.ik_token, self.settings.ik_terms_accepted = "test", True
        document = self.create()
        original = IndianKanoon.resolve
        def deleting(connector, finding):
            result = original(connector, finding)
            self.app.state.service.mark_deleted("local-development-owner", document["id"])
            return result
        with patch.object(IndianKanoon, "resolve", deleting):
            self.worker.tick()
        with self.db.sessions() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(FindingRow)), 0)

    def test_expiry_is_inaccessible_before_cleanup(self):
        document = self.complete()
        base = "/v1/documents/" + document["id"]
        report = self.client.post(base + "/reports").json()
        with self.db.transaction() as session:
            session.execute(update(DocumentRow).values(expires_at=now() - 1))
        self.assertEqual(self.client.get(base).status_code, 404)
        self.assertEqual(self.client.get(base + "/reports/" + report["id"]).status_code, 404)
        self.assertEqual(self.client.get("/v1/documents").json(), [])
        self.app.state.service.cleanup()
        with self.db.sessions() as session:
            self.assertIsNone(session.get(DocumentRow, document["id"]))

    def test_restart_reclaims_lease_and_invalidates_old_token(self):
        document = self.create()
        old = self.worker.claim()
        with self.db.transaction() as session:
            session.execute(update(RunRow).values(lease_until=now() - 1))
        replacement = Worker(self.db, self.settings, None, self.http, self.app.state.service)
        new = replacement.claim()
        self.assertNotEqual(old[2], new[2])
        with self.assertRaises(JobLost):
            self.worker.heartbeat(old)
        replacement.process(new)
        self.assertEqual(self.client.get("/v1/documents/" + document["id"]).json()["latest_run"]["status"], "completed")

    def test_fresh_database_connection_recovers_persisted_job(self):
        document = self.create()
        replacement_db = Database(self.settings.database_url)
        replacement = Worker(replacement_db, self.settings, None, self.http, self.app.state.service)
        self.assertTrue(replacement.tick())
        replacement_db.engine.dispose()
        self.assertEqual(self.client.get("/v1/documents/" + document["id"]).json()["latest_run"]["status"], "completed")

    def test_recovery_and_provider_budget_are_bounded(self):
        document = self.create()
        job = self.worker.claim()
        with self.db.transaction() as session:
            session.execute(update(RunRow).values(source_requests=50))
        self.assertFalse(self.worker.heartbeat(job, reserve="search"))
        with self.db.transaction() as session:
            session.execute(update(RunRow).values(attempts=3, lease_until=now() - 1))
        self.assertFalse(self.worker.tick())
        self.assertEqual(self.client.get("/v1/documents/" + document["id"]).json()["latest_run"]["status"], "failed")

    def test_duplicate_references_reuse_one_lookup(self):
        requests = []
        def counting(request):
            requests.append(request)
            return source_http(request)
        with httpx.Client(transport=httpx.MockTransport(counting)) as client:
            self.worker.client = client
            document = self.complete(live=True, text="\n".join(["(2020) 1 SCC 100"] * 50))
        self.assertEqual(len(requests), 2)
        self.assertEqual(document["metrics"]["source_coverage"]["numerator"], 50)
        self.assertEqual(document["metrics"]["unavailable"], 0)
        with self.db.sessions() as session:
            self.assertEqual(session.scalar(select(RunRow.source_requests)), 2)

    def test_distinct_query_limit_is_ten_and_survives_recovery(self):
        document = self.complete(live=True, text="\n".join(f"(2020) 1 SCC {100+i}" for i in range(50)))
        self.assertEqual(sum(f["status"] == "not_checked" for f in document["findings"]), 40)
        self.assertEqual(document["latest_run"]["source_usage"]["requests_by_operation"]["search"], 10)
        new = self.create()
        job = self.worker.claim()
        for _ in range(10):
            self.assertTrue(self.worker.heartbeat(job, reserve="search"))
        with self.db.transaction() as session:
            session.execute(update(RunRow).where(RunRow.id == new["latest_run"]["id"]).values(lease_until=now()-1))
        replacement = self.worker.claim()
        self.assertFalse(self.worker.heartbeat(replacement, reserve="search"))

    def test_daily_and_concurrent_owner_quotas(self):
        self.settings.max_documents = 1
        results = []
        def submit():
            try:
                self.app.state.service.create("quota-owner", "test", "text.txt", text="Synthetic data.")
                results.append(200)
            except Exception as exc:
                results.append(exc.status_code)
        threads = [threading.Thread(target=submit) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), [200, 429])
        self.settings.daily_analyses = 1
        document = self.complete()
        while self.worker.tick():
            pass
        self.assertEqual(self.client.post("/v1/documents/" + document["id"] + "/analyses").status_code, 429)

    def test_source_timeouts_do_not_become_not_found(self):
        self.settings.ik_token, self.settings.ik_terms_accepted = "test", True
        def timeout(request):
            raise httpx.ReadTimeout("synthetic timeout")
        self.worker.client = httpx.Client(transport=httpx.MockTransport(timeout))
        document = self.complete()
        self.assertEqual(document["findings"][0]["status"], "unavailable")
        self.assertEqual(document["latest_run"]["status"], "completed")
        self.worker.client.close()

    def test_hosted_storage_lifecycle_and_retryable_delete(self):
        storage = Mock()
        storage.sign_upload.return_value = {"upload_url": "https://project.supabase.co/upload?token=synthetic", "upload_headers": {}}
        storage.download.return_value = SAMPLE.encode()
        self.app.state.service.storage = storage
        result = self.app.state.service.create("local-development-owner", "Hosted", "hosted.txt", size=len(SAMPLE.encode()), hosted=True)
        document_id = result["document_id"]
        self.assertIsNone(self.client.get("/v1/documents/" + document_id).json()["latest_run"])
        finalized = self.app.state.service.finalize("local-development-owner", document_id)
        self.assertEqual(finalized["latest_run"]["status"], "queued")
        storage.delete.side_effect = RemoteError("unavailable")
        self.assertEqual(self.client.delete("/v1/documents/" + document_id).status_code, 503)
        self.assertEqual(self.client.get("/v1/documents/" + document_id).status_code, 404)
        storage.delete.side_effect = None
        self.assertEqual(self.client.delete("/v1/documents/" + document_id).status_code, 204)
        with self.db.sessions() as session:
            self.assertIsNotNone(session.get(DocumentRow, document_id), "Token-expiry tombstone must survive deletion")
        with self.db.transaction() as session:
            session.execute(update(DocumentRow).values(upload_token_until=now() - 1))
        self.app.state.service.cleanup()
        with self.db.sessions() as session:
            self.assertIsNone(session.get(DocumentRow, document_id))

    def test_hosted_storage_size_mismatch(self):
        storage = Mock()
        storage.sign_upload.return_value = {"upload_url": "https://project.supabase.co/upload", "upload_headers": {}}
        storage.download.return_value = b"changed size"
        self.app.state.service.storage = storage
        result = self.app.state.service.create("local-development-owner", "Hosted", "hosted.txt", size=5, hosted=True)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            self.app.state.service.finalize("local-development-owner", result["document_id"])
        self.assertEqual(error.exception.status_code, 422)

    def test_abandoned_upload_inaccessible_and_cleaned(self):
        storage = Mock()
        storage.sign_upload.return_value = {"upload_url": "https://project.supabase.co/upload", "upload_headers": {}}
        self.app.state.service.storage = storage
        result = self.app.state.service.create("local-development-owner", "Hosted", "hosted.txt", size=5, hosted=True)
        with self.db.transaction() as session:
            session.execute(update(DocumentRow).values(upload_deadline=now() - 1, upload_token_until=now() - 1))
        self.assertEqual(self.client.get("/v1/documents/" + result["document_id"]).status_code, 404)
        self.assertEqual(self.client.get("/v1/documents").json(), [])
        self.app.state.service.cleanup()
        storage.delete.assert_called_once()
        with self.db.sessions() as session:
            self.assertIsNone(session.get(DocumentRow, result["document_id"]))

    def test_malformed_pdf_is_failed_run_not_success(self):
        response = self.client.post("/v1/documents/file", data={"consent": "true"},
                                    files={"file": ("broken.pdf", b"%PDF-1.7\nbroken")})
        self.assertEqual(response.status_code, 200)
        self.worker.tick()
        document = self.client.get("/v1/documents/" + response.json()["id"]).json()
        self.assertEqual(document["latest_run"]["status"], "failed")
        self.assertTrue(document["latest_run"]["error"])
        self.assertEqual(document["findings"], [])
        self.assertEqual(self.client.post("/v1/documents/" + document["id"] + "/reports").status_code, 409)

    def test_auth_uses_supabase_user_endpoint_not_decode_only(self):
        owner_id = uid()
        self.settings.auth_mode = "supabase"
        self.settings.supabase_url = "https://project.supabase.co"
        with patch("app.main.request_json", return_value={"id": owner_id}) as remote:
            self.assertEqual(self.client.get("/v1/documents", headers={"Authorization": "Bearer synthetic.jwt"}).status_code, 200)
            self.assertEqual(remote.call_args.args[2], "https://project.supabase.co/auth/v1/user")
        self.assertEqual(self.client.get("/v1/documents").status_code, 401)
        with patch("app.main.request_json", side_effect=RemoteError("unauthorized")):
            self.assertEqual(self.client.get("/v1/documents", headers={"Authorization": "Bearer fake.jwt"}).status_code, 401)

    def test_signup_creates_confirmed_user_and_returns_session(self):
        owner_id = uid()
        self.settings.auth_mode = "supabase"
        self.settings.supabase_url = "https://project.supabase.co"
        self.settings.supabase_publishable_key = "anon-key"
        self.settings.supabase_service_role_key = "service-key"
        created = {"id": owner_id}
        token = {"access_token": "access-token", "refresh_token": "refresh-token", "expires_in": 3600}

        def remote(_client, method, url, **kwargs):
            if url.endswith("/auth/v1/admin/users"):
                self.assertEqual(method, "POST")
                self.assertEqual(kwargs["headers"]["Authorization"], "Bearer service-key")
                self.assertEqual(kwargs["json"]["email"], "tester@example.com")
                self.assertTrue(kwargs["json"]["email_confirm"])
                return created
            if "/auth/v1/token" in url:
                self.assertEqual(method, "POST")
                self.assertEqual(kwargs["headers"]["Authorization"], "Bearer anon-key")
                self.assertEqual(kwargs["json"]["password"], "secret12")
                return token
            raise AssertionError(url)

        with patch("app.main.request_json", side_effect=remote):
            response = self.client.post("/v1/signup", json={"email": "tester@example.com", "password": "secret12"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["user_id"], owner_id)
        self.assertEqual(body["session"]["access_token"], "access-token")
        self.assertEqual(body["session"]["refresh_token"], "refresh-token")

    def test_signup_rejects_local_mode_duplicates_and_invalid_input(self):
        response = self.client.post("/v1/signup", json={"email": "tester@example.com", "password": "secret12"})
        self.assertEqual(response.status_code, 409)
        self.settings.auth_mode = "supabase"
        self.settings.supabase_url = "https://project.supabase.co"
        self.settings.supabase_publishable_key = "anon-key"
        self.settings.supabase_service_role_key = "service-key"
        self.assertEqual(self.client.post("/v1/signup", json={"email": "not-an-email", "password": "secret12"}).status_code, 422)
        self.assertEqual(self.client.post("/v1/signup", json={"email": "tester@example.com", "password": "ab"}).status_code, 422)
        duplicate = RemoteError("Remote service returned HTTP 422", status=422, payload={"msg": "User already registered"})
        with patch("app.main.request_json", side_effect=duplicate):
            response = self.client.post("/v1/signup", json={"email": "tester@example.com", "password": "secret12"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.json()["detail"])

    def test_loopback_host_restriction(self):
        self.assertEqual(self.client.get("/v1/documents", headers={"Host": "evil.example"}).status_code, 403)

    def test_local_rejects_non_loopback_peer(self):
        remote_client = TestClient(self.app, client=("192.0.2.10", 54321))
        self.assertEqual(remote_client.get("/v1/documents", headers={"Host": "localhost"}).status_code, 403)
        remote_client.close()

    def test_local_mutations_require_allowlisted_origin_if_present(self):
        body = {"title": "Synthetic origin test", "text": "No references.", "consent": True}
        for origin in ("https://malicious.example", "null", "http://localhost:5173.evil.example"):
            response = self.client.post("/v1/documents/text", json=body, headers={"Origin": origin})
            self.assertEqual(response.status_code, 403)
        for origin in ("http://127.0.0.1:5173", "http://localhost:5173"):
            response = self.client.post("/v1/documents/text", json=body, headers={"Origin": origin})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.post("/v1/documents/text", json=body).status_code, 200)

    def test_multipart_csrf_and_cross_origin_delete_are_rejected(self):
        response = self.client.post(
            "/v1/documents/file", data={"consent": "true"},
            files={"file": ("synthetic.txt", b"No references.")},
            headers={"Origin": "https://malicious.example"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/v1/documents").json(), [])
        document = self.create()
        base = "/v1/documents/" + document["id"]
        self.assertEqual(self.client.delete(base, headers={"Origin": "https://malicious.example"}).status_code, 403)
        self.assertEqual(self.client.get(base).status_code, 200)
        self.assertEqual(self.client.delete(base).status_code, 204)


class ExtractionTests(unittest.TestCase):
    def test_docx_body_tables_offsets_and_no_fake_pages(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>😀 Section 41 of CrPC</w:t></w:r></w:p></w:body></w:document>')
        result = extract_bounded("test.docx", data.getvalue())
        self.assertEqual(result["text"], "😀 Section 41 of CrPC")
        self.assertIsNone(result["paragraphs"][0]["page"])

    def test_docx_compression_bomb_and_malformed(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", "x" * 1_000_000)
        with self.assertRaises(ExtractionError):
            extract("bomb.docx", data.getvalue())
        with self.assertRaises(ExtractionError):
            extract("malformed.docx", b"PK\x03\x04junk")

    def test_encrypted_scanned_and_over_page_limit_pdf(self):
        for kind in ("encrypted", "scanned", "many"):
            writer = PdfWriter()
            for _ in range(51 if kind == "many" else 1):
                writer.add_blank_page(width=300, height=300)
            if kind == "encrypted":
                writer.encrypt("synthetic-password")
            data = io.BytesIO()
            writer.write(data)
            with self.assertRaises(ExtractionError):
                extract("test.pdf", data.getvalue())

    def test_text_pdf_extracts_page_locations(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 10 250 Td (Section 41 of CrPC) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        data = io.BytesIO()
        writer.write(data)
        result = extract_bounded("text.pdf", data.getvalue())
        self.assertIn("Section 41", result["text"])
        self.assertEqual(result["paragraphs"][0]["page"], 1)

    def test_quote_normalization_preserves_numbers_and_negation(self):
        self.assertEqual(normalize_quote("bail\nshall   not"), "bail shall not")
        self.assertNotEqual(normalize_quote("bail shall not"), normalize_quote("bail shall"))
        self.assertNotEqual(normalize_quote("within 60 days"), normalize_quote("within 90 days"))


class ConnectorTests(unittest.TestCase):
    def settings(self):
        return Settings(ik_token="test-secret", ik_terms_accepted=True, ik_budget_paise=40000)

    def test_budget_configuration_fails_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(Settings(ik_token="test", ik_terms_accepted=True).source_lookup_configured)
            for value in ("-1", "1.50", "NaN", "400 rupees", "", " ", "1" * 5000):
                with self.subTest(value=value[:30]), patch.dict("os.environ", {"INDIAN_KANOON_BUDGET_PAISE": value}):
                    with self.assertRaisesRegex(ValueError, "paise"):
                        Settings()
            for value in (-1, 1.5, True, 2_000_000_001):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    Settings(ik_budget_paise=value).validate()
            for value in ("key\nheader", "key with spaces", "non-ascii-\u00e9"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    Settings(ik_token=value).validate()

    def test_document_body_citation_does_not_establish_identity(self):
        self.assertFalse(identity_matches("(2020) 1 SCC 100", "Other v. Case", "The applicant cited (2020) 1 SCC 100."))
        self.assertTrue(identity_matches("Alpha v. Beta, (2020) 1 SCC 100", "Alpha v. Beta on 1 January 2020",
                                         "Equivalent citations: (2020) 1 SCC 100\nJudgment"))

    def test_auth_method_fixed_host_and_only_reference_query(self):
        requests = []
        def transport(request):
            requests.append(request)
            return source_http(request)
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            connector = IndianKanoon(self.settings(), client, lambda operation: True)
            result = connector.resolve({"label": "Alpha v. Beta, (2020) 1 SCC 100"})
        self.assertEqual(result[0], "source_found")
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(r.method == "POST" and r.url.host == "api.indiankanoon.org" and r.url.scheme == "https" for r in requests))
        self.assertEqual(requests[0].headers["Authorization"], "Token test-secret")

    def test_multiple_identity_candidates_remain_ambiguous(self):
        def transport(request):
            if request.url.path == "/search/":
                return httpx.Response(200, json={"docs": [{"tid": 123}, {"tid": 456}]})
            return httpx.Response(200, json={"title": "Alpha v. Beta", "doc": BODY})
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            result = IndianKanoon(self.settings(), client, lambda operation: True).resolve({"label": "Alpha v. Beta"})
        self.assertEqual(result[0], "ambiguous")
        self.assertEqual(len(result[2]), 2)

    def test_empty_search_is_not_found_and_credit_errors_unavailable(self):
        for status, data, expected in ((200, {"docs": []}, "not_found"), (403, {}, "unavailable"), (200, {"errmsg": "No credit"}, "unavailable")):
            with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=data))) as client:
                result = IndianKanoon(self.settings(), client, lambda operation: True).resolve({"label": "(2020) 1 SCC 100"})
                self.assertEqual(result[0], expected)

    def test_budget_and_unsafe_candidate_ids(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"docs": [{"tid": "https://127.0.0.1/"}]}))) as client:
            result = IndianKanoon(self.settings(), client, lambda operation: True).resolve({"label": "Alpha v. Beta"})
            self.assertEqual(result[0], "unavailable")
        client = Mock()
        result = IndianKanoon(self.settings(), client, lambda operation: False).resolve({"label": "Alpha v. Beta"})
        self.assertEqual(result[0], "unavailable")
        client.stream.assert_not_called()

    def test_redirects_and_oversized_responses_rejected(self):
        for response in (httpx.Response(302, headers={"location": "http://127.0.0.1/"}),
                         httpx.Response(200, content=b"a" * 20)):
            with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
                with self.assertRaises(RemoteError):
                    bounded_request(client, "GET", "https://api.indiankanoon.org/search/", limit=10)

    def test_storage_signing_uses_official_endpoint_and_rejects_external_url(self):
        settings = Settings(supabase_url="https://project.supabase.co", supabase_service_role_key="synthetic")
        key = uid() + "/" + uid() + ".txt"
        expected = "/object/upload/sign/litl-private/" + key
        for signed, valid in ((expected + "?token=synthetic", True), ("https://attacker.test/upload?token=synthetic", False)):
            with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"url": signed}))) as client:
                storage = SupabaseStorage(settings, client)
                if valid:
                    result = storage.sign_upload(key)
                    self.assertEqual(result["upload_url"], settings.supabase_url + "/storage/v1" + signed)
                    self.assertNotIn("Authorization", result["upload_headers"])
                else:
                    with self.assertRaises(RemoteError):
                        storage.sign_upload(key)

    def test_local_auth_cannot_start_hosted(self):
        for value in ("true", ""):
            with patch.dict("os.environ", {"RENDER": value}):
                with self.assertRaises(ValueError):
                    Settings().validate()

    def test_private_bucket_configuration_is_verified(self):
        settings = Settings(supabase_url="https://project.supabase.co", supabase_service_role_key="synthetic")
        for data, valid in (
            ({"public": False, "file_size_limit": MAX_FILE_BYTES}, True),
            ({"public": True, "file_size_limit": MAX_FILE_BYTES}, False),
            ({"public": False, "file_size_limit": None}, False),
        ):
            with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=data))) as client:
                storage = SupabaseStorage(settings, client)
                if valid:
                    storage.validate_bucket()
                else:
                    with self.assertRaises(RemoteError):
                        storage.validate_bucket()


if __name__ == "__main__":
    unittest.main()
