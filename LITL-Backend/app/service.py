from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .extraction import file_kind, paragraphs_for, validate_text
from .metrics import metrics
from .models import DocumentRow, FindingRow, OwnerQuota, ReportRow, ReviewEvent, RunRow, SourceOpen, now, uid
from .network import RemoteError


DISCLAIMER = (
    "Evidence-location and human-review record, not a legal correctness certificate or legal advice. "
    "Metrics cover detected items only. Case identity is not proposition support or good-law status. "
    "Saved corrections are proposals and have NOT been applied to the original document. "
    "Public/synthetic/anonymized beta data only. Indian Kanoon evidence requires powered by IKanoon attribution."
)


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp is not None else None


def run_json(run):
    if run is None:
        return None
    return {
        "id": run.id, "document_id": run.document_id, "status": run.status, "stage": run.stage,
        "error": run.error, "created_at": iso(run.created_at), "finished_at": iso(run.finished_at),
        "warnings": run.warnings,
    }


def finding_json(session, finding):
    opened = list(session.scalars(select(SourceOpen.source_id).where(SourceOpen.finding_id == finding.id)))
    return {
        **finding.data, "id": finding.id, "run_id": finding.run_id,
        "sources": [{"id": s.id, **s.data} for s in finding.sources],
        "decision": finding.decision, "review_note": finding.review_note, "correction": finding.correction,
        "version": finding.version, "source_opened": bool(opened), "opened_source_ids": opened,
    }


def latest_run(session, document_id):
    return session.scalar(select(RunRow).where(RunRow.document_id == document_id).order_by(RunRow.created_at.desc(), RunRow.id.desc()).limit(1))


def document_json(session, document, summary=False):
    run = latest_run(session, document.id)
    result = {
        "id": document.id, "file_name": document.file_name, "title": document.title,
        "created_at": iso(document.created_at), "expires_at": iso(document.expires_at), "latest_run": run_json(run),
    }
    if not summary:
        findings = [] if not run else [
            finding_json(session, f) for f in session.scalars(
                select(FindingRow).where(FindingRow.run_id == run.id)
            )
        ]
        findings.sort(key=lambda f: (f["start"], f["end"]))
        result.update(text=document.text, paragraphs=document.paragraphs, findings=findings, metrics=metrics(findings))
    return result


class Service:
    def __init__(self, db, settings, storage):
        self.db, self.settings, self.storage = db, settings, storage

    def owner_document(self, session, owner, document_id, *, lock=False, allow_deleted=False):
        query = select(DocumentRow).where(DocumentRow.id == document_id, DocumentRow.owner_id == owner)
        if not allow_deleted:
            query = query.where(
                DocumentRow.deleted_at.is_(None), DocumentRow.expires_at > now(),
                DocumentRow.finalized.is_(True) | (DocumentRow.upload_deadline > now()),
            )
        if lock:
            query = query.with_for_update()
        document = session.scalar(query)
        if not document:
            raise HTTPException(404, "Document not found")
        return document

    def quota(self, session, owner):
        day = datetime.now(timezone.utc).date().isoformat()
        insert = sqlite_insert if self.db.engine.dialect.name == "sqlite" else pg_insert
        session.execute(insert(OwnerQuota).values(owner_id=owner, day=day, uploads=0, analyses=0).on_conflict_do_nothing())
        quota = session.scalar(select(OwnerQuota).where(OwnerQuota.owner_id == owner).with_for_update())
        if quota.day != day:
            quota.day, quota.uploads, quota.analyses = day, 0, 0
        return quota

    def new_run(self, session, document, quota):
        if not document.finalized:
            raise HTTPException(409, "Finalize the file upload first")
        runs = list(session.scalars(select(RunRow).where(RunRow.document_id == document.id)))
        if any(r.status in {"queued", "processing"} for r in runs):
            raise HTTPException(409, "An analysis is already active")
        if len(runs) >= self.settings.max_runs:
            raise HTTPException(429, "Maximum analyses per document reached")
        if quota.analyses >= self.settings.daily_analyses:
            raise HTTPException(429, "Daily analysis quota reached")
        quota.analyses += 1
        run = RunRow(document_id=document.id, status="queued", stage="queued", created_at=now(), warnings=[
            "Free hosted processing can pause while the API sleeps; requests wake the durable job loop.",
            "Maximum 50 detected references and 50 external source requests per analysis (including recovery).",
        ])
        session.add(run)
        session.flush()
        return run

    def create(self, owner, title, file_name, *, text=None, data=None, size=0, hosted=False):
        with self.db.transaction() as session:
            quota = self.quota(session, owner)
            count = session.scalar(select(func.count()).select_from(DocumentRow).where(
                DocumentRow.owner_id == owner, DocumentRow.deleted_at.is_(None), DocumentRow.expires_at > now(),
            ))
            if count >= self.settings.max_documents or quota.uploads >= self.settings.daily_uploads:
                raise HTTPException(429, "Document or daily upload quota reached")
            quota.uploads += 1
            timestamp, document_id = now(), uid()
            document = DocumentRow(
                id=document_id, owner_id=owner, file_name=file_name, title=title,
                created_at=timestamp, expires_at=timestamp + self.settings.retention_days * 86400,
                expected_size=size or len(data or b""), raw_bytes=data, finalized=not hosted,
                upload_deadline=timestamp + 3600 if hosted else None,
                upload_token_until=timestamp + 7500 if hosted else None,
                storage_key=f"{uid()}/{document_id}{Path(file_name).suffix.lower()}" if hosted else None,
            )
            if text is not None:
                extracted = paragraphs_for([(validate_text(text), None)])
                document.text, document.paragraphs = extracted["text"], extracted["paragraphs"]
            session.add(document)
            session.flush()
            if not hosted:
                self.new_run(session, document, quota)
            result = document_json(session, document)
            storage_key = document.storage_key
        if hosted:
            try:
                signed = self.storage.sign_upload(storage_key)
            except RemoteError as exc:
                self.mark_deleted(owner, document_id)
                raise HTTPException(503, "Private upload signing unavailable; reservation cancelled") from exc
            return {"document_id": document_id, **signed}
        return result

    def finalize(self, owner, document_id):
        with self.db.sessions() as session:
            document = self.owner_document(session, owner, document_id)
            if document.finalized:
                return document_json(session, document)
            if not document.upload_deadline or document.upload_deadline <= now():
                raise HTTPException(410, "Upload reservation expired")
            key, expected, name = document.storage_key, document.expected_size, document.file_name
        try:
            data = self.storage.download(key)
            if len(data) != expected:
                raise HTTPException(422, "Uploaded file size differs from reservation")
            file_kind(name, data)
        except RemoteError as exc:
            raise HTTPException(503, "Private upload is missing or storage is unavailable; retry finalize") from exc
        with self.db.transaction() as session:
            quota = self.quota(session, owner)
            document = self.owner_document(session, owner, document_id, lock=True)
            if not document.finalized:
                if document.upload_deadline <= now():
                    raise HTTPException(410, "Upload reservation expired")
                document.finalized = True
                self.new_run(session, document, quota)
            return document_json(session, document)

    def analyze(self, owner, document_id):
        with self.db.transaction() as session:
            quota = self.quota(session, owner)
            document = self.owner_document(session, owner, document_id, lock=True)
            return run_json(self.new_run(session, document, quota))

    def cancel(self, owner, document_id, run_id):
        with self.db.transaction() as session:
            self.owner_document(session, owner, document_id, lock=True)
            run = session.scalar(select(RunRow).where(RunRow.id == run_id, RunRow.document_id == document_id).with_for_update())
            if not run:
                raise HTTPException(404, "Analysis not found")
            if run.status in {"queued", "processing"}:
                run.status, run.stage, run.finished_at = "cancelled", "cancelled", now()
                run.lease_token, run.lease_until = None, None
            return run_json(run)

    def owner_finding(self, session, document_id, finding_id):
        finding = session.scalar(select(FindingRow).join(RunRow).where(
            FindingRow.id == finding_id, RunRow.document_id == document_id,
        ))
        if not finding:
            raise HTTPException(404, "Finding not found")
        current = latest_run(session, document_id)
        if not current or current.id != finding.run_id or current.status != "completed":
            raise HTTPException(409, "This finding is not in the latest completed analysis; reload before recording changes")
        return finding

    def review(self, owner, document_id, finding_id, body):
        with self.db.transaction() as session:
            self.owner_document(session, owner, document_id, lock=True)
            finding = self.owner_finding(session, document_id, finding_id)
            if finding.version != body.expected_version:
                raise HTTPException(409, "Review changed since it was loaded; reload before saving")
            before = {"decision": finding.decision, "review_note": finding.review_note, "correction": finding.correction}
            after = {"decision": body.decision, "review_note": body.review_note, "correction": body.correction}
            finding.decision, finding.review_note, finding.correction = body.decision, body.review_note, body.correction
            finding.version += 1
            session.add(ReviewEvent(
                finding_id=finding.id, actor_id=owner, created_at=now(), before=before, after=after, version=finding.version,
            ))
            session.flush()
            return finding_json(session, finding)

    def source_open(self, owner, document_id, finding_id, source_id):
        with self.db.transaction() as session:
            self.owner_document(session, owner, document_id, lock=True)
            finding = self.owner_finding(session, document_id, finding_id)
            if source_id not in {s.id for s in finding.sources}:
                raise HTTPException(404, "Source not found for this finding")
            if not session.get(SourceOpen, (finding_id, source_id)):
                session.add(SourceOpen(finding_id=finding_id, source_id=source_id, created_at=now()))
                session.flush()
            return finding_json(session, finding)

    def report(self, owner, document_id):
        with self.db.transaction() as session:
            document = self.owner_document(session, owner, document_id, lock=True)
            run = latest_run(session, document_id)
            if not run or run.status != "completed":
                raise HTTPException(409, "A report requires the latest analysis to be completed")
            count = session.scalar(select(func.count()).select_from(ReportRow).where(ReportRow.document_id == document_id))
            if count >= 20:
                raise HTTPException(429, "Maximum 20 report snapshots per document reached")
            timestamp, report_id = now(), uid()
            snapshot = {
                "id": report_id, "document_id": document_id, "created_at": iso(timestamp),
                "document": document_json(session, document), "disclaimer": DISCLAIMER,
            }
            session.add(ReportRow(id=report_id, document_id=document_id, created_at=timestamp, snapshot=snapshot))
            return snapshot

    def mark_deleted(self, owner, document_id):
        with self.db.transaction() as session:
            document = self.owner_document(session, owner, document_id, lock=True, allow_deleted=True)
            document.deleted_at = document.deleted_at or now()
            document.text, document.paragraphs, document.raw_bytes = "", [], None
            document.title, document.file_name, document.expected_size = "Deleted document", "deleted", 0
            session.execute(update(RunRow).where(RunRow.document_id == document_id, RunRow.status.in_(["queued", "processing"])).values(
                status="cancelled", stage="cancelled", finished_at=now(), lease_token=None, lease_until=None,
            ))
            session.execute(delete(ReportRow).where(ReportRow.document_id == document_id))
            session.execute(delete(RunRow).where(RunRow.document_id == document_id))
        return self.cleanup_one(document_id)

    def cleanup_one(self, document_id):
        with self.db.sessions() as session:
            document = session.get(DocumentRow, document_id)
            if not document or document.deleted_at is None:
                return True
            key, token_until = document.storage_key, document.upload_token_until
        if key:
            try:
                self.storage.delete(key)
            except RemoteError:
                with self.db.transaction() as session:
                    session.execute(update(DocumentRow).where(DocumentRow.id == document_id).values(cleanup_error=True))
                return False
        with self.db.transaction() as session:
            if key and token_until and token_until > now():
                # A valid old signed token might upload again after deletion.
                # Re-delete on wake and retain this inaccessible tombstone until token expiry.
                session.execute(update(DocumentRow).where(DocumentRow.id == document_id).values(cleanup_error=False))
            else:
                session.execute(delete(DocumentRow).where(DocumentRow.id == document_id, DocumentRow.deleted_at.is_not(None)))
        return True

    def cleanup(self):
        with self.db.sessions() as session:
            expired = list(session.execute(select(DocumentRow.owner_id, DocumentRow.id).where(
                DocumentRow.deleted_at.is_(None),
                (DocumentRow.expires_at <= now()) |
                ((DocumentRow.finalized.is_(False)) & (DocumentRow.upload_deadline <= now())),
            ).limit(100)))
            pending = list(session.scalars(select(DocumentRow.id).where(DocumentRow.deleted_at.is_not(None)).limit(100)))
        for owner, document_id in expired:
            try:
                self.mark_deleted(owner, document_id)
            except HTTPException as exc:
                if exc.status_code != 404:
                    raise
        for document_id in pending:
            self.cleanup_one(document_id)
