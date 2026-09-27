import hashlib
import re
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser

from .extraction import NAME, REPORTER, statutory_details
from .network import RemoteError, request_json


class BudgetExhausted(RemoteError):
    pass


MAX_REFERENCE_QUERIES = 10
ACT_ALIASES = {
    "ipc": "Indian Penal Code", "crpc": "Code of Criminal Procedure",
    "criminal procedure code": "Code of Criminal Procedure",
    "bnss": "Bharatiya Nagarik Suraksha Sanhita", "bns": "Bharatiya Nyaya Sanhita",
    "bsa": "Bharatiya Sakshya Adhiniyam", "constitution": "Constitution of India",
}


def link_details(status, sources):
    state = "matched" if status in {"source_found", "quote_mismatch"} and len(sources) == 1 else (
        "candidates" if sources else status if status in {"not_found", "missing_context", "not_checked"} else "unavailable"
    )
    messages = {
        "matched": "Open Indian Kanoon source", "candidates": "Multiple or unconfirmed matches - review candidates",
        "not_found": "No matching source found", "missing_context": "Act name needed to find this section",
        "unavailable": "Source lookup unavailable", "not_checked": "Not checked - analysis limit or attribution unavailable",
    }
    return {
        "link_state": state, "link_message": messages[state],
        "reference_url": sources[0]["url"] if state == "matched" else None,
    }


def legislation_target(label, title):
    details = statutory_details(label)
    if not details["statute"]["act"]:
        return None
    act = details["statute"]["act"]
    year = re.search(r"(?:18|19|20)\d{2}$", act)
    name = re.sub(r",?\s*(?:18|19|20)\d{2}$", "", act).strip() if year else act
    act_key = re.sub(r"\.", "", name).casefold()
    act = ACT_ALIASES.get(act_key, name) + (" " + year.group() if year else "")
    norm = lambda value: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()
    expected = norm(act).removeprefix("the ")
    candidate = norm(title).removeprefix("the ")
    identifier = norm(details["statute"]["identifier"])
    identifier = re.sub(r"^(?:sec|s|u s) ", "section ", identifier)
    def act_matches(value):
        value = value.removeprefix("the ")
        return value == expected or (
            not re.search(r"\b(?:18|19|20)\d{2}$", expected)
            and re.fullmatch(re.escape(expected) + r" (?:18|19|20)\d{2}", value) is not None
        )
    if act_matches(candidate):
        return "statute_act"
    for connector in (" in ", " of "):
        prefix = identifier + connector
        if candidate.startswith(prefix) and act_matches(candidate[len(prefix):]):
            return "statute_section"
    return None


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
        citation_ok = bool(header and identity_normalize(citation.group()) in {
            identity_normalize(match.group()) for match in re.finditer(REPORTER, header.group(1))
        })
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
        self.resolutions = {}
        self.document_responses = {}
        self.cached_characters = 0
        self.query_count = 0

    def request(self, path, params=None, *, operation):
        if operation == "document" and path in self.document_responses:
            return self.document_responses[path]
        if self.disabled:
            raise RemoteError("Provider unavailable earlier in this run; no further spend attempted")
        if not self.reserve(operation):
            raise BudgetExhausted("Source request or spending limit reached (account, daily, owner or analysis budget)")
        try:
            data = request_json(self.client, "POST", self.BASE + path, headers=self.headers, params=params)
            if data.get("errmsg") or data.get("error"):
                raise RemoteError("Provider returned an error; access or credit may be unavailable")
            if operation == "document":
                size = len(str(data.get("doc", ""))) + len(str(data.get("title", "")))
                if self.cached_characters + size <= 2_000_000:
                    self.document_responses[path] = data
                    self.cached_characters += size
            return data
        except RemoteError:
            self.disabled = True
            raise

    def resolve(self, finding):
        key = (finding.get("kind", "case_citation"), " ".join(finding["label"].split()).casefold())
        if key in self.resolutions:
            return deepcopy(self.resolutions[key])
        if key[0] == "statutory_reference" and not statutory_details(finding["label"])["statute"]["act"]:
            return "missing_context", "Act name needed to find this section.", [], False
        if not self.configured or self.disabled:
            return "unavailable", "Source lookup unavailable; check provider configuration, access and remaining allowance.", [], False
        if len(finding["label"]) > 300:
            return "not_checked", "Reference exceeds the query length limit.", [], False
        if self.query_count >= MAX_REFERENCE_QUERIES:
            return "not_checked", "Not checked - maximum ten distinct reference queries per analysis.", [], False
        self.query_count += 1
        result = self._resolve_statute(finding) if key[0] == "statutory_reference" else self._resolve_case(finding)
        self.resolutions[key] = deepcopy(result)
        return result

    def _resolve_statute(self, finding):
        if not self.configured:
            return "unavailable", "Statute source lookup is not configured.", [], False
        if len(finding["label"]) > 300:
            return "not_checked", "Reference exceeds the query length limit.", [], False
        try:
            data = self.request("/search/", {"formInput": finding["label"], "pagenum": 0}, operation="search")
            docs = data.get("docs")
            if not isinstance(docs, list):
                raise RemoteError("Provider returned no usable search response")
            candidates, matches = [], []
            for entry in docs[:3]:
                if not isinstance(entry, dict) or not re.fullmatch(r"\d{1,20}", str(entry.get("tid", ""))):
                    raise RemoteError("Provider returned invalid candidate data")
                tid = str(entry["tid"])
                document = self.request(f"/doc/{tid}/", operation="document")
                if not isinstance(document.get("doc"), str) or not isinstance(document.get("title"), str):
                    raise RemoteError("Provider returned no full document/title")
                body, title = plain(document["doc"]), plain(document["title"])
                if not body:
                    raise RemoteError("Provider returned empty document text")
                excerpt, locator = passage(body)
                target = legislation_target(finding["label"], title)
                source = {
                    "title": title[:500], "url": f"https://indiankanoon.org/doc/{tid}/",
                    "repository": "Indian Kanoon", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "passage": excerpt, "locator": locator, "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "target_kind": target or "candidate",
                }
                candidates.append(source)
                if target:
                    matches.append(source)
            sections = [s for s in matches if s["target_kind"] == "statute_section"]
            preferred = sections or matches
            if len(preferred) == 1:
                note = "Open Act - section-specific link unavailable." if not sections else "Section source located."
                return "source_found", note + " Amendments, commencement and applicability still require human review.", preferred, False
            if candidates:
                return "ambiguous", "No single legislation target established; review possible matches.", candidates, False
            return "not_found", "No matching source found.", [], False
        except RemoteError as exc:
            self.disabled = True
            return "unavailable", str(exc) + ". No conclusion about validity can be drawn.", [], False

    def _resolve_case(self, finding):
        if not self.configured:
            return "unavailable", (
                "Live source lookup requires a backend API token, terms acceptance and positive spending limits. "
                "No independent source verification was performed."
            ), [], False
        if len(finding["label"]) > 300:
            return "unsupported", "Reference exceeds the external query length limit; not submitted.", [], False
        try:
            result = self.request("/search/", {"formInput": finding["label"], "pagenum": 0}, operation="search")
            docs = result.get("docs")
            if not isinstance(docs, list):
                raise RemoteError("Provider returned no usable search response")
            if not docs:
                return "not_found", "No candidates returned by this repository; this does not prove the reference is invalid.", [], False
            candidates, matched, all_checkable = [], [], True
            for entry in docs[:3]:
                if not isinstance(entry, dict):
                    raise RemoteError("Provider returned invalid candidate data")
                tid = str(entry.get("tid", ""))
                if not re.fullmatch(r"\d{1,20}", tid):
                    continue
                data = self.request(f"/doc/{tid}/", operation="document")
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
                all_checkable = all_checkable and identity_checkable(finding["label"], body)
                if identity_matches(finding["label"], title, body):
                    matched.append(source)
                    if sum(len(text) for text in self.documents.values()) + len(body) <= 2_000_000:
                        self.documents[source["url"]] = body
            if len(matched) == 1 and re.search(REPORTER, finding["label"]):
                return "source_found", (
                    "One examined judgment matched the supplied reporter citation and any supplied party names. "
                    "At most three candidates were examined; this is not an exhaustive search. "
                    "This does not verify proposition support, binding authority or current good law."
                ), matched, True
            if candidates:
                compared_without_match = (
                    not matched and all_checkable and len(candidates) == len(docs) and len(docs) <= 3
                )
                return "ambiguous", (
                    "Candidate documents retrieved, but identity is not uniquely established. "
                    "At most the first three search candidates were examined; snippets alone are not verification. "
                    + ("All returned candidates were compared without an identity match; this does not prove the reference invalid."
                       if compared_without_match else "The identity assessment remains inconclusive.")
                ), candidates, compared_without_match
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
