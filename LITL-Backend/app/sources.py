import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser

from .extraction import NAME, REPORTER
from .network import RemoteError, request_json


class BudgetExhausted(RemoteError):
    pass


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.suppressed += 1
        if tag in {"p", "div", "br", "h1", "h2", "h3", "li"} and not self.suppressed:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)
        elif tag in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def plain(value):
    parser = PlainHTML()
    parser.feed(str(value))
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def normalize_quote(value):
    value = unicodedata.normalize("NFKC", value).translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
    return " ".join(value.split())


def identity_normalize(value):
    value = re.sub(r"\b(?:versus|vs\.?|v\.?)\b", " v ", value.lower())
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def identity_matches(label, title, body):
    name = re.search(NAME, label)
    citation = re.search(REPORTER, label)
    name_ok = name is None or identity_normalize(name.group()) == identity_normalize(
        re.split(r"\s+on\s+\d", title, flags=re.I)[0]
    )
    citation_ok = citation is None
    if citation:
        # A citation in a judgment's reasoning could cite a *different* case.
        # Only the explicitly identified equivalent-citations header is identity evidence.
        header = re.search(r"Equivalent citations?\s*:\s*([^\n]{1,1000})", body[:5000], re.I)
        citation_ok = bool(header and identity_normalize(citation.group()) in identity_normalize(header.group(1)))
    return bool((name or citation) and name_ok and citation_ok)


def identity_checkable(label, body):
    """Missing reporter metadata is unknown, not an adverse identity comparison."""
    return not re.search(REPORTER, label) or bool(
        re.search(r"Equivalent citations?\s*:\s*([^\n]{1,1000})", body[:5000], re.I)
    )


def passage(body, needle=None):
    lines = body.splitlines()
    selected = 0
    if needle:
        selected = next((i for i, line in enumerate(lines) if normalize_quote(needle) in normalize_quote(line)), 0)
    text = "\n".join(lines[selected:selected + 3])[:1600]
    return text, f"Retrieved text paragraph {selected + 1}" if lines else None


class IndianKanoon:
    BASE = "https://api.indiankanoon.org"

    def __init__(self, settings, client, reserve):
        self.configured = settings.source_lookup_configured
        self.client = client
        self.reserve = reserve
        self.headers = {"Accept": "application/json", "Authorization": "Token " + settings.ik_token}
        self.documents = {}
        self.disabled = False

    def request(self, path, params=None):
        if self.disabled:
            raise RemoteError("Provider unavailable earlier in this run; no further spend attempted")
        if not self.reserve():
            raise BudgetExhausted("Source request budget exhausted")
        try:
            data = request_json(self.client, "POST", self.BASE + path, headers=self.headers, params=params)
            if data.get("errmsg") or data.get("error"):
                raise RemoteError("Provider returned an error; access or credit may be unavailable")
            return data
        except RemoteError:
            self.disabled = True
            raise

    def resolve(self, finding):
        if not self.configured:
            return "unavailable", "Live source lookup is not configured. No independent source verification was performed.", [], False
        if len(finding["label"]) > 300:
            return "unsupported", "Reference exceeds the external query length limit; not submitted.", [], False
        try:
            result = self.request("/search/", {"formInput": finding["label"], "pagenum": 0})
            docs = result.get("docs")
            if not isinstance(docs, list):
                raise RemoteError("Provider returned no usable search response")
            if not docs:
                return "not_found", "No candidates returned by this repository; this does not prove the reference is invalid.", [], False
            candidates, matched, checkable = [], [], False
            for entry in docs[:3]:
                if not isinstance(entry, dict):
                    raise RemoteError("Provider returned invalid candidate data")
                tid = str(entry.get("tid", ""))
                if not re.fullmatch(r"\d{1,20}", tid):
                    continue
                data = self.request(f"/doc/{tid}/")
                if not isinstance(data.get("doc"), str) or not isinstance(data.get("title"), str):
                    raise RemoteError("Provider returned no full document/title for identity checking")
                body = plain(data["doc"])
                title = plain(data["title"])
                if not body:
                    continue
                source_passage, locator = passage(body)
                source = {
                    "title": title[:500], "url": f"https://indiankanoon.org/doc/{tid}/",
                    "repository": "Indian Kanoon", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "passage": source_passage, "locator": locator,
                    "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
                }
                candidates.append(source)
                checkable = checkable or identity_checkable(finding["label"], body)
                if identity_matches(finding["label"], title, body):
                    matched.append(source)
                    if sum(len(text) for text in self.documents.values()) + len(body) <= 2_000_000:
                        self.documents[source["url"]] = body
            if len(matched) == 1 and len(docs) <= 3:
                return "source_found", (
                    "Reference identity matched retrieved title and any explicit equivalent-citations header. "
                    "This does not verify proposition support, binding authority or current good law."
                ), matched, True
            if candidates:
                return "ambiguous", (
                    "Candidate documents retrieved, but identity is not uniquely established. "
                    "Only the first three search candidates were examined; snippets alone are not verification."
                ), candidates, checkable
            return "unavailable", "Search returned candidates but no usable full source documents; identity was not checked.", [], False
        except RemoteError as exc:
            self.disabled = True
            return "unavailable", str(exc) + ". No negative inference about the reference is justified.", [], False

    def check_quote(self, finding, citation):
        if not citation or citation["status"] != "source_found" or len(citation.get("sources", [])) != 1:
            return "not_checked", "Quotation has no uniquely resolved nearby attributed case. Wording was not compared.", [], False
        source = dict(citation["sources"][0])
        body = self.documents.get(source["url"])
        if not body:
            return "not_checked", "Full retrieved case text is unavailable or exceeds the in-memory quote-comparison budget.", [source], False
        needle = finding["excerpt"][1:-1]
        matches = normalize_quote(needle) in normalize_quote(body)
        source["passage"], source["locator"] = passage(body, needle if matches else None)
        if matches:
            # If the quote crosses paragraphs, return its normalized wording as an explicitly normalized locator.
            if normalize_quote(needle) not in normalize_quote(source["passage"]):
                source["passage"] = normalize_quote(needle)
                source["locator"] = "Normalized exact-text match in retrieved document"
            return "source_found", (
                "Quotation wording found in the nearby resolved case after Unicode punctuation and whitespace normalization. "
                "Numbers, negation and letter case are preserved. Attribution and legal context still require human review."
            ), [source], True
        return "quote_mismatch", (
            "Quotation wording was not found in the full retrieved text of the nearby resolved case. "
            "This is a text comparison, not proof of fabrication; formatting and attribution need human review."
        ), [source], True
