import asyncio
import ipaddress
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, text as sql_text
from starlette.formparsers import MultiPartParser
from starlette.datastructures import UploadFile

from .config import MAX_CHARACTERS, MAX_FILE_BYTES, Settings
from .db import Database
from .extraction import ExtractionError, file_kind
from .models import DocumentRow, ReportRow, RunRow
from .network import RemoteError, http_client, request_json
from .service import Service, document_json, iso, run_json
from .storage import SupabaseStorage
from .worker import Worker


MAX_BODY = MAX_FILE_BYTES + 65536
# Never spool files into an OS temporary directory. The ASGI guard enforces a
# smaller request bound before Starlette's multipart parser sees the request.
MultiPartParser.spool_max_size = MAX_BODY + 1


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class TextInput(Input):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=MAX_CHARACTERS)
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Consent must be the JSON boolean true")
        return value


class UploadInput(Input):
    file_name: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0, le=MAX_FILE_BYTES, strict=True)
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Consent must be the JSON boolean true")
        return value


class ReviewInput(Input):
    decision: Literal["confirmed", "corrected", "rejected", "unresolved"]
    review_note: str = Field(max_length=4000)
    correction: str = Field(max_length=4000)
    expected_version: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def correction_required(self):
        if self.decision == "corrected" and not self.correction.strip():
            raise ValueError("A corrected decision requires a nonempty proposed correction")
        return self


class SourceOpenInput(Input):
    source_id: str = Field(max_length=36)


class SignupInput(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=72)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if value.count("@") != 1 or " " in value:
            raise ValueError("Enter a valid email address")
        local, domain = value.split("@")
        if not local or not domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Enter a valid email address")
        return value


def supabase_headers(key):
    return {"apikey": key, "Authorization": "Bearer " + key}


def signup_conflict_message(exc: RemoteError):
    payload = exc.payload or {}
    text = " ".join(str(payload.get(key) or "") for key in ("msg", "error_description", "error", "error_code", "code")).lower()
    if "already" in text or "exists" in text:
        return "An account with this email already exists. Sign in instead."
    if "password" in text:
        return "Choose a stronger password with at least 6 characters."
    if exc.status in {400, 422}:
        return "Could not create the account with the details provided."
    return None


class RequestGuard:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.rates, self.signups, self.lock = {}, {}, threading.Lock()
        self.active_uploads = 0

    async def __call__(self, scope, receive, send):
        is_file = scope["type"] == "http" and scope["path"] == "/v1/documents/file" and scope["method"] == "POST"
        if not is_file:
            return await self.dispatch(scope, receive, send)
        with self.lock:
            allowed = self.active_uploads < 2
            if allowed:
                self.active_uploads += 1
        if not allowed:
            return await JSONResponse({"detail": "Too many concurrent file uploads; retry shortly"}, status_code=429)(scope, receive, send)
        try:
            return await self.dispatch(scope, receive, send)
        finally:
            with self.lock:
                self.active_uploads -= 1

    async def dispatch(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        ip = (scope.get("client") or ("", 0))[0]
        if self.settings.auth_mode == "local":
            try:
                loopback = ipaddress.ip_address(ip).is_loopback
            except ValueError:
                loopback = self.settings.testing and ip == "testclient"
            try:
                host = urlsplit("//" + headers.get(b"host", b"").decode("ascii")).hostname
            except (ValueError, UnicodeDecodeError):
                host = None
            if not loopback or host not in {"localhost", "127.0.0.1", "::1", "testserver" if self.settings.testing else "localhost"}:
                return await JSONResponse({"detail": "Local development is loopback-only"}, status_code=403)(scope, receive, send)
            if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"} and b"origin" in headers:
                origin = headers[b"origin"].decode("latin-1")
                if origin not in self.settings.cors_origins:
                    return await JSONResponse({"detail": "Origin is not allowed for local mutations"}, status_code=403)(scope, receive, send)
        if scope["path"] not in {"/healthz", "/readyz"}:
            clock = time.monotonic()
            signup = scope["path"] == "/v1/signup" and scope["method"] == "POST"
            with self.lock:
                if len(self.rates) > 2048:
                    self.rates = {key: value for key, value in self.rates.items() if clock - value[0] < 60}
                if len(self.signups) > 2048:
                    self.signups = {key: value for key, value in self.signups.items() if clock - value[0] < 60}
                start, count = self.rates.get(ip, (clock, 0))
                if clock - start >= 60:
                    start, count = clock, 0
                if len(self.rates) > 2048 and ip not in self.rates:
                    count = 180
                else:
                    self.rates[ip] = (start, count + 1)
                if signup:
                    signup_start, signup_count = self.signups.get(ip, (clock, 0))
                    if clock - signup_start >= 60:
                        signup_start, signup_count = clock, 0
                    self.signups[ip] = (signup_start, signup_count + 1)
                    if signup_count >= 8:
                        count = 180
            if count >= 180:
                return await JSONResponse({"detail": "Request rate limit reached; retry in a minute"}, status_code=429)(scope, receive, send)
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            try:
                length = int(headers.get(b"content-length", b"0"))
            except ValueError:
                return await JSONResponse({"detail": "Invalid content length"}, status_code=400)(scope, receive, send)
            limit = MAX_BODY if scope["path"] == "/v1/documents/file" else 2 * 1024 * 1024
            if length > limit or length < 0:
                return await JSONResponse({"detail": "Request exceeds size limit"}, status_code=413)(scope, receive, send)
            body = bytearray()
            deadline = time.monotonic() + 30
            while True:
                try:
                    message = await asyncio.wait_for(receive(), timeout=max(0, min(15, deadline - time.monotonic())))
                except TimeoutError:
                    return await JSONResponse({"detail": "Request body timed out"}, status_code=408)(scope, receive, send)
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    return await JSONResponse({"detail": "Request exceeds size limit"}, status_code=413)(scope, receive, send)
                if not message.get("more_body"):
                    break
            sent = False

            async def limited_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            return await self.app(scope, limited_receive, send)
        return await self.app(scope, receive, send)


def create_app(settings=None, client=None):
    settings = settings or Settings()
    settings.validate()
    db = Database(settings.database_url)
    client = client or http_client()
    storage = SupabaseStorage(settings, client) if settings.storage_mode == "supabase" else None
    service = Service(db, settings, storage)
    worker = Worker(db, settings, storage, client, service)

    @asynccontextmanager
    async def lifespan(app):
        db.setup()
        if storage:
            await asyncio.to_thread(storage.validate_bucket)
        if settings.auth_mode == "local":
            logging.getLogger("litl").warning("LOCAL MODE: fixed development owner; bind only 127.0.0.1. Never deploy local mode.")
        if settings.worker_enabled:
            worker.start()
        yield
        await asyncio.to_thread(worker.stop)
        client.close()
        db.engine.dispose()

    app = FastAPI(title="LiTL API", version="1.0.0", lifespan=lifespan)
    app.state.db, app.state.service, app.state.worker, app.state.settings = db, service, worker, settings
    app.add_middleware(RequestGuard, settings=settings)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(ExtractionError)
    async def extraction_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    def owner(authorization: str | None = Header(default=None)):
        if settings.auth_mode == "local":
            return "local-development-owner"
        if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 8192:
            raise HTTPException(401, "A Supabase bearer session is required")
        try:
            data = request_json(
                client, "GET", settings.supabase_url + "/auth/v1/user", limit=65536,
                headers={"apikey": settings.supabase_publishable_key, "Authorization": authorization},
            )
            # /auth/v1/user verifies the bearer token server-side. Never decode JWTs without validation.
            return str(UUID(data["id"]))
        except (RemoteError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(401, "Session is invalid, expired, or authentication service is unavailable") from exc

    app.state.owner_dependency = owner

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/readyz")
    def ready():
        try:
            with db.sessions() as session:
                session.execute(sql_text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(503, "Database is unavailable") from exc
        if settings.worker_enabled and (not worker.thread or not worker.thread.is_alive()):
            raise HTTPException(503, "Job processor is not running")
        return {"status": "ready"}

    @app.get("/v1/config")
    def config():
        return settings.public()

    @app.post("/v1/signup")
    def signup(body: SignupInput):
        if settings.auth_mode != "supabase":
            raise HTTPException(409, "Local mode has no accounts. Sign-in is not required.")
        try:
            created = request_json(
                client, "POST", settings.supabase_url + "/auth/v1/admin/users", limit=65536,
                headers=supabase_headers(settings.supabase_service_role_key),
                json={"email": body.email, "password": body.password, "email_confirm": True},
            )
            user = created["user"] if isinstance(created.get("user"), dict) else created
            user_id = str(UUID(user["id"]))
        except (RemoteError, ValueError, KeyError, TypeError) as exc:
            conflict = signup_conflict_message(exc) if isinstance(exc, RemoteError) else None
            if conflict:
                raise HTTPException(409 if "already exists" in conflict else 422, conflict) from exc
            raise HTTPException(502, "Could not create the account. Retry shortly.") from exc
        try:
            token = request_json(
                client, "POST", settings.supabase_url + "/auth/v1/token?grant_type=password", limit=65536,
                headers=supabase_headers(settings.supabase_publishable_key),
                json={"email": body.email, "password": body.password},
            )
            access, refresh = token["access_token"], token["refresh_token"]
            if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
                raise KeyError("session")
            return {
                "user_id": user_id,
                "session": {
                    "access_token": access,
                    "refresh_token": refresh,
                    "expires_in": int(token.get("expires_in") or 3600),
                    "token_type": "bearer",
                },
            }
        except (RemoteError, ValueError, KeyError, TypeError) as exc:
            text = " ".join(str((getattr(exc, "payload", None) or {}).get(key) or "") for key in ("msg", "error_description", "error")).lower() if isinstance(exc, RemoteError) else ""
            if "confirm" in text:
                return {"user_id": user_id, "session": None}
            raise HTTPException(502, "Account was created. Sign in to continue.") from exc

    @app.post("/v1/documents/text")
    def create_text(body: TextInput, actor=Depends(owner)):
        if not body.title.strip():
            raise HTTPException(422, "Title cannot be blank")
        return service.create(actor, body.title.strip(), "pasted-text.txt", text=body.text)

    @app.post("/v1/documents/file")
    async def create_file(request: Request, actor=Depends(owner)):
        if settings.storage_mode != "local":
            raise HTTPException(409, "Use the signed private-storage upload flow")
        async with request.form(max_files=1, max_fields=1, max_part_size=MAX_BODY) as form:
            file = form.get("file")
            if form.get("consent") != "true":
                raise HTTPException(422, "Explicit anonymized-data and external-query consent is required")
            if not isinstance(file, UploadFile) or len(form.multi_items()) != 2:
                raise HTTPException(422, "Supply exactly one file and consent")
            name = Path((file.filename or "").replace("\\", "/")).name
            if not name or len(name) > 255:
                raise HTTPException(422, "Invalid filename")
            data = bytearray()
            while chunk := await file.read(65536):
                data.extend(chunk)
                if len(data) > MAX_FILE_BYTES:
                    raise HTTPException(413, "File exceeds 10 MB")
            file_kind(name, bytes(data))
            return await asyncio.to_thread(service.create, actor, name[:200], name, data=bytes(data))

    @app.post("/v1/uploads")
    def upload(body: UploadInput, actor=Depends(owner)):
        if settings.storage_mode != "supabase":
            raise HTTPException(409, "Local mode uses the multipart file endpoint")
        name = Path(body.file_name.replace("\\", "/")).name
        file_kind(name)
        return service.create(actor, name[:200], name, size=body.size, hosted=True)

    @app.post("/v1/documents/{document_id}/finalize")
    def finalize(document_id: str, actor=Depends(owner)):
        if settings.storage_mode != "supabase":
            raise HTTPException(409, "Local documents are finalized at creation")
        return service.finalize(actor, document_id)

    @app.get("/v1/documents")
    def documents(actor=Depends(owner)):
        from .models import now
        with db.sessions() as session:
            rows = session.scalars(select(DocumentRow).where(
                DocumentRow.owner_id == actor, DocumentRow.deleted_at.is_(None), DocumentRow.expires_at > now(),
                DocumentRow.finalized.is_(True) | (DocumentRow.upload_deadline > now()),
            ).order_by(DocumentRow.created_at.desc()))
            return [document_json(session, d, summary=True) for d in rows]

    @app.get("/v1/documents/{document_id}")
    def document(document_id: str, actor=Depends(owner)):
        with db.sessions() as session:
            return document_json(session, service.owner_document(session, actor, document_id))

    @app.post("/v1/documents/{document_id}/analyses")
    def analyze(document_id: str, actor=Depends(owner)):
        return service.analyze(actor, document_id)

    @app.get("/v1/documents/{document_id}/analyses/{run_id}")
    def analysis(document_id: str, run_id: str, actor=Depends(owner)):
        with db.sessions() as session:
            service.owner_document(session, actor, document_id)
            run = session.scalar(select(RunRow).where(RunRow.id == run_id, RunRow.document_id == document_id))
            if not run:
                raise HTTPException(404, "Analysis not found")
            return run_json(run)

    @app.post("/v1/documents/{document_id}/analyses/{run_id}/cancel")
    def cancel(document_id: str, run_id: str, actor=Depends(owner)):
        return service.cancel(actor, document_id, run_id)

    @app.put("/v1/documents/{document_id}/findings/{finding_id}/review")
    def review(document_id: str, finding_id: str, body: ReviewInput, actor=Depends(owner)):
        return service.review(actor, document_id, finding_id, body)

    @app.post("/v1/documents/{document_id}/findings/{finding_id}/source-open")
    def source_open(document_id: str, finding_id: str, body: SourceOpenInput, actor=Depends(owner)):
        return service.source_open(actor, document_id, finding_id, body.source_id)

    @app.delete("/v1/documents/{document_id}", status_code=204)
    def remove(document_id: str, actor=Depends(owner)):
        if not service.mark_deleted(actor, document_id):
            raise HTTPException(503, "Document is inaccessible and database contents removed; private-storage deletion pending. Retry DELETE.")
        return Response(status_code=204)

    @app.post("/v1/documents/{document_id}/reports")
    def report(document_id: str, actor=Depends(owner)):
        return service.report(actor, document_id)

    @app.get("/v1/documents/{document_id}/reports")
    def reports(document_id: str, actor=Depends(owner)):
        with db.sessions() as session:
            service.owner_document(session, actor, document_id)
            return [
                {"id": r.id, "document_id": document_id, "created_at": iso(r.created_at)}
                for r in session.scalars(select(ReportRow).where(ReportRow.document_id == document_id).order_by(ReportRow.created_at.desc()))
            ]

    @app.get("/v1/documents/{document_id}/reports/{report_id}")
    def get_report(document_id: str, report_id: str, actor=Depends(owner)):
        with db.sessions() as session:
            service.owner_document(session, actor, document_id)
            report = session.scalar(select(ReportRow).where(ReportRow.id == report_id, ReportRow.document_id == document_id))
            if not report:
                raise HTTPException(404, "Report not found")
            return report.snapshot

    return app


app = create_app()
