from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, LargeBinary, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).timestamp()


class Base(DeclarativeBase):
    pass


class OwnerQuota(Base):
    __tablename__ = "owner_quotas"
    owner_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    day: Mapped[str] = mapped_column(String(10))
    uploads: Mapped[int] = mapped_column(default=0)
    analyses: Mapped[int] = mapped_column(default=0)


class DocumentRow(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(String(128), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[float]
    expires_at: Mapped[float] = mapped_column(index=True)
    deleted_at: Mapped[float | None]
    upload_deadline: Mapped[float | None]
    # Signed upload tokens cannot be revoked; retain a tombstone until they expire.
    upload_token_until: Mapped[float | None]
    storage_key: Mapped[str | None] = mapped_column(String(400))
    expected_size: Mapped[int]
    raw_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    text: Mapped[str] = mapped_column(Text, default="")
    paragraphs: Mapped[list] = mapped_column(JSON, default=list)
    finalized: Mapped[bool] = mapped_column(Boolean, default=False)
    cleanup_error: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str] = mapped_column(String(40), default="anonymized-external-query-v1")
    runs: Mapped[list["RunRow"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class RunRow(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    stage: Mapped[str] = mapped_column(String(80))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[float]
    finished_at: Mapped[float | None]
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[float | None]
    lease_token: Mapped[str | None] = mapped_column(String(36))
    source_requests: Mapped[int] = mapped_column(default=0)
    parser_version: Mapped[str] = mapped_column(String(40), default="deterministic-1")


class SourceBudgetRow(Base):
    __tablename__ = "source_budgets"
    scope: Mapped[str] = mapped_column(String(100), primary_key=True)
    reserved_paise: Mapped[int] = mapped_column(default=0)


class RunScopeRow(Base):
    __tablename__ = "analysis_scopes"
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class SourceRequestRow(Base):
    __tablename__ = "source_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    operation: Mapped[str] = mapped_column(String(20))
    cost_paise: Mapped[int]
    price_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[float]


finding_sources = Table(
    "finding_sources", Base.metadata,
    Column("finding_id", ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id", ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True),
)


class FindingRow(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[str | None] = mapped_column(String(16))
    review_note: Mapped[str] = mapped_column(Text, default="")
    correction: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(default=0)
    sources: Mapped[list["SourceRow"]] = relationship(secondary=finding_sources, lazy="selectin")


class SourceRow(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[float]
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int]


class SourceOpen(Base):
    __tablename__ = "source_opens"
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[float]


class ReportRow(Base):
    __tablename__ = "report_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[float]
    snapshot: Mapped[dict] = mapped_column(JSON)


class SummaryConsentRow(Base):
    __tablename__ = "summary_consents"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    accepted_at: Mapped[float]
    version: Mapped[str] = mapped_column(String(40), default="gemini-summary-1")


class SummaryJobRow(Base):
    __tablename__ = "summary_jobs"
    __table_args__ = (UniqueConstraint("run_id", "request_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    request_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[float]
    consent_at: Mapped[float]
    finished_at: Mapped[float | None]
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[float | None]
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40), default="gemini-summary-2")
    input_packet: Mapped[dict | None] = mapped_column(JSON)
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    output: Mapped[dict | None] = mapped_column(JSON)
    usage: Mapped[dict | None] = mapped_column(JSON)
    reserved_microusd: Mapped[int] = mapped_column(default=0)
    review_state: Mapped[str] = mapped_column(String(16), default="unreviewed")
    review_version: Mapped[int] = mapped_column(default=0)


class SummaryQuotaRow(Base):
    __tablename__ = "summary_quotas"
    scope: Mapped[str] = mapped_column(String(100), primary_key=True)
    requests: Mapped[int] = mapped_column(default=0)
    reserved_microusd: Mapped[int] = mapped_column(default=0)


class SummaryReviewEvent(Base):
    __tablename__ = "summary_review_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    summary_id: Mapped[str] = mapped_column(ForeignKey("summary_jobs.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[float]
    decision: Mapped[str] = mapped_column(String(16))
    version: Mapped[int]
