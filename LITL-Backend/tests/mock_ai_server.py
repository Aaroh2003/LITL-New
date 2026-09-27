"""Loopback test server; every provider request uses synthetic fixtures."""
import json
import os

import httpx

from app.config import Settings
from app.main import create_app


def transport(request):
    if request.url.host == "api.indiankanoon.org":
        if request.url.path == "/search/":
            is_statute = "CrPC" in request.url.params.get("formInput", "")
            return httpx.Response(200, json={"found": 1, "docs": [{"tid": 456 if is_statute else 123}]})
        if request.url.path == "/doc/456/":
            return httpx.Response(200, json={"title": "Section 41A in The Code of Criminal Procedure, 1973",
                                             "doc": "<p>Synthetic provision fixture, not legal authority.</p>"})
        if request.url.path == "/doc/123/":
            return httpx.Response(200, json={"title": "Arnesh Kumar v. State of Bihar",
                "doc": "<p>Equivalent citations: (2014) 8 SCC 273</p><p>Synthetic source fixture, not legal authority.</p>"})
    if request.url.host == "generativelanguage.googleapis.com":
        if request.url.path.endswith(":countTokens"):
            return httpx.Response(200, json={"totalTokens": 500})
        if request.url.path.endswith(":generateContent"):
            body = json.loads(request.content)
            packet = json.loads(body["contents"][0]["parts"][0]["text"])
            draft = [key for key, value in packet["evidence"].items() if value["kind"] == "draft"]
            sources = [key for key, value in packet["evidence"].items() if value["kind"] == "source"]
            output = {
                "overview": [{"text": "The uploaded synthetic draft contains legal references.", "evidence_ids": draft[-1:]}],
                "key_points": [], "issues": [], "review_questions": [],
                "source_observations": [{"text": "A synthetic source excerpt is available for review.", "evidence_ids": sources[:1]}] if sources else [],
            }
            return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {
                "parts": [{"text": json.dumps(output)}]}}], "usageMetadata": {"totalTokenCount": 650}})
    raise AssertionError("Unexpected request in mock-only server")


database = os.environ["LITL_TEST_DATABASE_URL"]
if not database.startswith("sqlite:///"):
    raise RuntimeError("Mock server requires an explicitly supplied local SQLite test database")
settings = Settings(
    auth_mode="local", storage_mode="local", database_url=database,
    cors_origins=("http://127.0.0.1:15173",), ik_token="mock-only", ik_terms_accepted=True,
    ik_budget_paise=40000, gemini_api_key="mock-only", gemini_enabled=True, gemini_model="gemini-2.5-flash",
    gemini_budget_microusd=1_000_000,
    gemini_input_rate=300000, gemini_output_rate=2500000,
)
app = create_app(settings, httpx.Client(transport=httpx.MockTransport(transport)))


@app.get("/test-mock-mode")
def mock_mode():
    return {"mock_providers": True}
