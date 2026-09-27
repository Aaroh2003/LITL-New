import logging
import threading
import time

from sqlalchemy import func, or_, select, update

from .budget import reserve_source_request
from .config import MAX_SOURCE_REQUESTS
from .extraction import ExtractionError, detect_with_scope, extract_bounded, statutory_details
from .models import DocumentRow, FindingRow, RunRow, RunScopeRow, SourceRequestRow, SourceRow, now, uid
from .network import RemoteError
from .sources import IndianKanoon, MAX_REFERENCE_QUERIES, link_details
from .summary import Summaries


log = logging.getLogger("litl.worker")


class JobLost(Exception):
    pass


class Worker:
    def __init__(self, db, settings, storage, client, service):
        self.db, self.settings, self.storage, self.client, self.service = db, settings, storage, client, service
        self.stop_event = threading.Event()
        self.thread = None
        self.last_cleanup = 0
        self.summaries = Summaries(db, settings, service)

    def start(self):
        self.thread = threading.Thread(target=self.loop, name="litl-durable-worker", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=30)

    def loop(self):
        while not self.stop_event.is_set():
            try:
                if time.monotonic() - self.last_cleanup > 60:
                    self.service.cleanup()
                    self.last_cleanup = time.monotonic()
                worked = self.tick()
                if not self.stop_event.is_set():
                    worked = self.summaries.tick(self.client) or worked
                if not worked:
                    self.stop_event.wait(0.75)
            except Exception as exc:
                log.error("Worker loop failure (%s); retrying without logging private data", type(exc).__name__)
                self.stop_event.wait(2)

    def claim(self):
        timestamp = now()
        with self.db.transaction() as session:
            query = select(RunRow).join(DocumentRow).where(
                DocumentRow.deleted_at.is_(None), DocumentRow.expires_at > timestamp,
                DocumentRow.finalized.is_(True),
                or_(RunRow.status == "queued", (RunRow.status == "processing") & (RunRow.lease_until < timestamp)),
            ).order_by(RunRow.created_at).limit(1).with_for_update(skip_locked=True, of=RunRow)
            run = session.scalar(query)
            if not run:
                return None
            if run.attempts >= 3:
                run.status, run.stage, run.error, run.finished_at = (
                    "failed", "failed", "Processing recovery limit (3 attempts) reached; retry with a new analysis.", timestamp,
                )
                run.lease_token, run.lease_until = None, None
                return None
            run.status, run.stage = "processing", "extracting"
            run.attempts += 1
            run.lease_token, run.lease_until = uid(), timestamp + self.settings.lease_seconds
            return run.id, run.document_id, run.lease_token

    def locked_job(self, session, run_id, document_id, token):
        document = session.scalar(select(DocumentRow).where(
            DocumentRow.id == document_id, DocumentRow.deleted_at.is_(None), DocumentRow.expires_at > now(),
        ).with_for_update())
        if not document:
            raise JobLost()
        run = session.scalar(select(RunRow).where(
            RunRow.id == run_id, RunRow.status == "processing", RunRow.lease_token == token,
            RunRow.lease_until > now(),
        ).with_for_update())
        if not run:
            raise JobLost()
        return document, run

    def heartbeat(self, job, stage=None, reserve=None):
        if self.stop_event.is_set():
            raise JobLost()
        with self.db.transaction() as session:
            document, run = self.locked_job(session, *job)
            run.lease_until = now() + self.settings.lease_seconds
            if stage:
                run.stage = stage
            if reserve:
                if run.source_requests >= MAX_SOURCE_REQUESTS:
                    return False
                if reserve == "search" and session.scalar(select(func.count()).select_from(SourceRequestRow).where(
                    SourceRequestRow.run_id == run.id, SourceRequestRow.operation == "search",
                )) >= MAX_REFERENCE_QUERIES:
                    return False
                if not reserve_source_request(session, self.settings, run, document.owner_id, reserve):
                    return False
                run.source_requests += 1
            return True

    def tick(self):
        job = self.claim()
        if not job:
            return False
        try:
            self.process(job)
        except JobLost:
            pass
        except (ExtractionError, RemoteError) as exc:
            self.fail(job, str(exc))
        except Exception as exc:
            log.error("Analysis failed (%s); document and provider contents omitted", type(exc).__name__)
            self.fail(job, "Unexpected processing error. No result was published; a new analysis may be requested.")
        return True

    def fail(self, job, message):
        try:
            with self.db.transaction() as session:
                _, run = self.locked_job(session, *job)
                run.status, run.stage, run.error, run.finished_at = "failed", "failed", message, now()
                run.lease_token, run.lease_until = None, None
        except JobLost:
            pass

    def process(self, job):
        run_id, document_id, token = job
        self.heartbeat(job, "extracting")
        with self.db.sessions() as session:
            document = session.get(DocumentRow, document_id)
            if not document:
                raise JobLost()
            name, raw, key = document.file_name, document.raw_bytes, document.storage_key
            text, paragraphs = document.text, document.paragraphs
        extraction_warnings = []
        if raw is not None or key or not text:
            if key:
                raw = self.storage.download(key)
            if raw is None:
                raise ExtractionError("Original document bytes are unavailable")
            extracted = extract_bounded(name, raw)
            text, paragraphs = extracted["text"], extracted["paragraphs"]
            extraction_warnings = extracted.get("warnings", [])
        del raw
        self.heartbeat(job, "detecting")
        findings, warnings, scope = detect_with_scope(text, paragraphs)
        connector = IndianKanoon(self.settings, self.client, lambda operation: self.heartbeat(job, reserve=operation))
        self.heartbeat(job, "looking_up_sources")
        for finding in findings:
            self.heartbeat(job)
            if finding["kind"] == "case_citation":
                status, note, sources, checked = connector.resolve(finding)
                finding.update(status=status, note=note, sources=sources, identity_checked=checked)
                finding.update(link_details(status, sources))
                finding["identity_assessment"] = (
                    "matched" if checked and status == "source_found" else "not_matched" if checked else "unknown"
                )
            elif finding["kind"] == "statutory_reference":
                status, note, sources, _ = connector.resolve(finding)
                details = statutory_details(finding["label"])
                finding.update(
                    status="unsupported", sources=sources, **details,
                )
                finding.update(link_details(status, sources))
                if details["statute"]["act"]:
                    finding["note"] = note
                if status == "source_found" and sources[0].get("target_kind") == "statute_act":
                    finding["link_message"] = "Open Act - section-specific link unavailable"
            else:
                finding["sources"] = []
        for finding in findings:
            if finding["kind"] == "quotation":
                candidates = [
                    f for f in findings if f["kind"] == "case_citation" and f["end"] <= finding["start"]
                    and finding["start"] - f["end"] <= 500
                ]
                citation = max(candidates, key=lambda f: f["end"], default=None)
                status, note, sources, checked = connector.check_quote(finding, citation)
                finding.update(status=status, note=note, sources=sources, quote_checked=checked)
                finding.update(link_details(status, sources))
        self.heartbeat(job, "publishing")
        with self.db.transaction() as session:
            document, run = self.locked_job(session, run_id, document_id, token)
            document.text, document.paragraphs = text, paragraphs
            session.add(RunScopeRow(run_id=run_id, data=scope))
            run.parser_version = scope["detector_version"]
            for item in findings:
                sources = item.pop("sources")
                finding = FindingRow(run_id=run_id, data=item)
                finding.sources = [SourceRow(run_id=run_id, data=source) for source in sources]
                session.add(finding)
            run.warnings = list(dict.fromkeys(run.warnings + extraction_warnings + warnings + (
                ["Source lookup unconfigured: no independent external verification took place."]
                if not self.settings.source_lookup_configured else []
            )))
            run.status, run.stage, run.finished_at = "completed", "completed", now()
            run.lease_token, run.lease_until = None, None
            self.summaries.enqueue_auto(session, document, run)
