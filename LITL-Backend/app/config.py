import os
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CHARACTERS = 200_000
MAX_PAGES = 50
MAX_FINDINGS = 50
MAX_SOURCE_REQUESTS = 50


@dataclass
class Settings:
    auth_mode: str = field(default_factory=lambda: os.getenv("AUTH_MODE", "local"))
    storage_mode: str = field(default_factory=lambda: os.getenv("STORAGE_MODE", "local"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///.data/litl.db"))
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_publishable_key: str = field(default_factory=lambda: os.getenv("SUPABASE_PUBLISHABLE_KEY", ""))
    supabase_service_role_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    storage_bucket: str = field(default_factory=lambda: os.getenv("STORAGE_BUCKET", "litl-private"))
    ik_token: str = field(default_factory=lambda: os.getenv("INDIAN_KANOON_API_TOKEN", ""))
    ik_terms_accepted: bool = field(default_factory=lambda: os.getenv("INDIAN_KANOON_TERMS_ACCEPTED", "false").lower() == "true")
    cors_origins: tuple = field(default_factory=lambda: tuple(
        x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()
    ))
    retention_days: int = 7
    max_documents: int = 20
    daily_uploads: int = 20
    daily_analyses: int = 30
    max_runs: int = 5
    worker_enabled: bool = True
    lease_seconds: int = 90
    testing: bool = False

    @property
    def source_lookup_configured(self):
        return bool(self.ik_token and self.ik_terms_accepted)

    def validate(self):
        if self.auth_mode not in {"local", "supabase"} or self.storage_mode not in {"local", "supabase"}:
            raise ValueError("AUTH_MODE and STORAGE_MODE must be local or supabase")
        hosted = any(k in os.environ for k in (
            "RENDER", "RENDER_SERVICE_ID", "VERCEL", "DYNO", "K_SERVICE", "FLY_APP_NAME",
            "AWS_LAMBDA_FUNCTION_NAME", "WEBSITE_SITE_NAME", "GAE_ENV",
        ))
        hosted = hosted or os.getenv("APP_ENV", "local").lower() in {"production", "hosted", "staging"}
        if self.auth_mode == "local" and (hosted or self.storage_mode != "local"):
            raise ValueError("Local authentication is loopback-only and must never be deployed")
        if self.auth_mode == "supabase":
            parsed = urlparse(self.supabase_url)
            if (parsed.scheme != "https" or not parsed.hostname or
                    not parsed.hostname.endswith(".supabase.co") or parsed.path not in {"", "/"} or
                    parsed.username or parsed.port):
                raise ValueError("SUPABASE_URL must be the HTTPS project.supabase.co origin")
            if not self.supabase_publishable_key or not self.supabase_service_role_key:
                raise ValueError("Supabase publishable and server service-role keys are required")
            if self.storage_mode != "supabase":
                raise ValueError("Hosted authentication requires private Supabase Storage")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Hosted mode requires postgresql+psycopg DATABASE_URL")
            if parse_qs(urlparse(self.database_url).query).get("sslmode") != ["verify-full"]:
                raise ValueError("Hosted DATABASE_URL must use sslmode=verify-full")
            if not self.cors_origins or any(not x.startswith("https://") or "*" in x for x in self.cors_origins):
                raise ValueError("Hosted CORS_ORIGINS must list exact HTTPS frontend origins")
        if "/" in self.storage_bucket or not self.storage_bucket:
            raise ValueError("STORAGE_BUCKET must be a bucket name")
        self.supabase_url = self.supabase_url.rstrip("/")

    def public(self):
        return {
            "auth_mode": self.auth_mode, "storage_mode": self.storage_mode,
            "supabase_url": self.supabase_url or None,
            "supabase_publishable_key": self.supabase_publishable_key or None,
            "max_file_bytes": MAX_FILE_BYTES, "max_characters": MAX_CHARACTERS,
            "max_pages": MAX_PAGES, "source_lookup_configured": self.source_lookup_configured,
        }
