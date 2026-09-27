import os
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CHARACTERS = 200_000
MAX_PAGES = 50
MAX_FINDINGS = 50
MAX_SOURCE_REQUESTS = 50
GEMINI_APP_DAILY_REQUESTS = 20
GEMINI_RATES = {
    "gemini-2.5-flash": (300000, 2500000),
    "gemini-3.5-flash-lite": (300000, 2500000),
    "gemini-3.8-flash": (750000, 3750000),
}


def env_integer(name, default, unit=""):
    raw = os.getenv(name, str(default))
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 10:
        raise ValueError(f"{name} must be a nonnegative integer" + (f" number of {unit}" if unit else ""))
    return int(raw)


def env_paise(name, default):
    return env_integer(name, default, "paise")


@dataclass
class Settings:
    auth_mode: str = field(default_factory=lambda: os.getenv("AUTH_MODE", "local"))
    storage_mode: str = field(default_factory=lambda: os.getenv("STORAGE_MODE", "local"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///.data/litl.db"))
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_publishable_key: str = field(default_factory=lambda: os.getenv("SUPABASE_PUBLISHABLE_KEY", ""))
    supabase_service_role_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))
    storage_bucket: str = field(default_factory=lambda: os.getenv("STORAGE_BUCKET", "litl-private"))
    ik_token: str = field(default_factory=lambda: os.getenv("INDIAN_KANOON_API_TOKEN", ""), repr=False)
    ik_terms_accepted: bool = field(default_factory=lambda: os.getenv("INDIAN_KANOON_TERMS_ACCEPTED", "false").lower() == "true")
    ik_budget_paise: int = field(default_factory=lambda: env_paise("INDIAN_KANOON_BUDGET_PAISE", 0))
    ik_run_budget_paise: int = field(default_factory=lambda: env_paise("INDIAN_KANOON_RUN_BUDGET_PAISE", 1100))
    ik_daily_budget_paise: int = field(default_factory=lambda: env_paise("INDIAN_KANOON_DAILY_BUDGET_PAISE", 4400))
    ik_owner_daily_budget_paise: int = field(default_factory=lambda: env_paise("INDIAN_KANOON_OWNER_DAILY_BUDGET_PAISE", 2200))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""), repr=False)
    gemini_enabled: bool = field(default_factory=lambda: os.getenv("GEMINI_ENABLED", "false").lower() == "true")
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
    gemini_budget_microusd: int = field(default_factory=lambda: env_integer("GEMINI_BUDGET_MICROUSD", 0))
    gemini_owner_daily_requests: int = field(default_factory=lambda: env_integer("GEMINI_OWNER_DAILY_REQUESTS", 5))
    gemini_input_rate: int | None = field(default_factory=lambda: env_integer("GEMINI_INPUT_MICROUSD_PER_MILLION", 0)
                                       if "GEMINI_INPUT_MICROUSD_PER_MILLION" in os.environ else None)
    gemini_output_rate: int | None = field(default_factory=lambda: env_integer("GEMINI_OUTPUT_MICROUSD_PER_MILLION", 0)
                                        if "GEMINI_OUTPUT_MICROUSD_PER_MILLION" in os.environ else None)
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
    def ai_summary_configured(self):
        return bool(self.gemini_api_key and self.gemini_enabled and self.gemini_budget_microusd > 0)

    @property
    def source_lookup_configured(self):
        return bool(self.ik_token and self.ik_terms_accepted and all(value > 0 for value in (
            self.ik_budget_paise, self.ik_run_budget_paise,
            self.ik_daily_budget_paise, self.ik_owner_daily_budget_paise,
        )))

    def validate(self):
        if type(self.gemini_owner_daily_requests) is not int or not 1 <= self.gemini_owner_daily_requests <= GEMINI_APP_DAILY_REQUESTS:
            raise ValueError(f"GEMINI_OWNER_DAILY_REQUESTS must be an integer between 1 and {GEMINI_APP_DAILY_REQUESTS}")
        self.gemini_api_key = self.gemini_api_key.strip()
        if any(not 33 <= ord(c) <= 126 for c in self.gemini_api_key):
            raise ValueError("GEMINI_API_KEY must not contain whitespace or non-ASCII characters")
        if self.gemini_model not in GEMINI_RATES:
            raise ValueError("GEMINI_MODEL must be one of: " + ", ".join(GEMINI_RATES) + "; other models require reviewed token/pricing limits")
        if self.gemini_input_rate is None:
            self.gemini_input_rate = GEMINI_RATES[self.gemini_model][0]
        if self.gemini_output_rate is None:
            self.gemini_output_rate = GEMINI_RATES[self.gemini_model][1]
        for name in ("gemini_budget_microusd", "gemini_input_rate", "gemini_output_rate"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 2_000_000_000:
                raise ValueError(f"{name} must be an integer between 0 and 2000000000")
        if self.gemini_input_rate == 0 or self.gemini_output_rate == 0:
            raise ValueError("Configure positive Gemini rate estimates even for free-tier quota")
        self.ik_token = self.ik_token.strip()
        if any(not 33 <= ord(character) <= 126 for character in self.ik_token):
            raise ValueError("INDIAN_KANOON_API_TOKEN must not contain whitespace or non-ASCII characters")
        for name in ("ik_budget_paise", "ik_run_budget_paise", "ik_daily_budget_paise", "ik_owner_daily_budget_paise"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 2_000_000_000:
                raise ValueError(f"{name} must be an integer between 0 and 2000000000 paise")
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
            "ai_summary_configured": self.ai_summary_configured,
            "ai_summary_model": self.gemini_model,
        }
