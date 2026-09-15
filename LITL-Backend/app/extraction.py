import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from defusedxml import ElementTree
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .config import MAX_CHARACTERS, MAX_FILE_BYTES, MAX_FINDINGS, MAX_PAGES


class ExtractionError(ValueError):
    pass


def validate_text(text):
    if len(text) > MAX_CHARACTERS:
        raise ExtractionError(f"Document exceeds {MAX_CHARACTERS:,} extracted characters")
    if not text.strip():
        raise ExtractionError("No readable text. Scanned/image-only files need OCR, which is not supported")
    if any(ord(c) < 32 and c not in "\n\r\t\f" for c in text):
        raise ExtractionError("Binary/control characters are not supported")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def file_kind(name, data=None):
    suffix = Path(name).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise ExtractionError("Only text-based PDF, DOCX and UTF-8 TXT are supported")
    if data is not None:
        if len(data) > MAX_FILE_BYTES:
            raise ExtractionError("File exceeds 10 MB")
        if not data:
            raise ExtractionError("Empty files are not supported")
        if suffix == ".pdf" and not data.startswith(b"%PDF-"):
            raise ExtractionError("File signature does not match PDF")
        if suffix == ".docx" and not data.startswith(b"PK\x03\x04"):
            raise ExtractionError("File signature does not match DOCX")
        if suffix == ".txt":
            try:
                validate_text(data.decode("utf-8-sig"))
            except UnicodeDecodeError as exc:
                raise ExtractionError("TXT files must use UTF-8 encoding") from exc
    return suffix


def paragraphs_for(pages):
    parts, paragraphs, position = [], [], 0
    for index, (page_text, page_number) in enumerate(pages):
        if index:
            parts.append("\n\n")
            position += 2
        parts.append(page_text)
        for match in re.finditer(r"[^\n]+", page_text):
            if match.group().strip():
                paragraphs.append({
                    "id": f"p{len(paragraphs) + 1}", "text": match.group(),
                    "start": position + match.start(), "end": position + match.end(), "page": page_number,
                })
        position += len(page_text)
    text = "".join(parts)
    validate_text(text)
    return {"text": text, "paragraphs": paragraphs}


def extract(name, data):
    kind = file_kind(name, data)
    if kind == ".txt":
        return paragraphs_for([(validate_text(data.decode("utf-8-sig")), None)])
    if kind == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ExtractionError("Encrypted PDFs are not supported; provide an unencrypted anonymized copy")
            if len(reader.pages) > MAX_PAGES:
                raise ExtractionError("PDF exceeds 50 pages")
            pages, total = [], 0
            for number, page in enumerate(reader.pages, 1):
                text = (page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n")
                total += len(text) + 2
                if total > MAX_CHARACTERS:
                    raise ExtractionError("PDF exceeds 200,000 extracted characters")
                pages.append((text, number))
            result = paragraphs_for(pages)
            result["warnings"] = (
                ["Some PDF pages have no extractable text. OCR is unavailable; detection covers extracted text only."]
                if any(not t.strip() for t, _ in pages) else []
            )
            return result
        except (PdfReadError, KeyError, TypeError, IndexError, ValueError) as exc:
            if isinstance(exc, ExtractionError):
                raise
            raise ExtractionError("PDF is malformed or cannot be read safely") from exc
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(i.file_size for i in entries) > 30 * 1024 * 1024:
                raise ExtractionError("DOCX decompression limit exceeded")
            if any(i.flag_bits & 1 or i.file_size > 20 * 1024 * 1024 or
                   i.file_size > max(i.compress_size, 1) * 200 for i in entries):
                raise ExtractionError("DOCX is encrypted or exceeds safe compression limits")
            names = [i.filename for i in entries]
            if len(set(names)) != len(names) or "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ExtractionError("Not a supported DOCX document")
            if any("vbaproject" in n.lower() for n in names):
                raise ExtractionError("Macro-enabled documents are not supported")
            root = ElementTree.fromstring(archive.read("word/document.xml"))
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            lines = []
            for paragraph in root.iter(ns + "p"):
                line = "".join(
                    node.text or "" if node.tag == ns + "t" else
                    "\t" if node.tag == ns + "tab" else "\n"
                    for node in paragraph.iter() if node.tag in {ns + "t", ns + "tab", ns + "br"}
                )
                lines.append(line)
            result = paragraphs_for([(validate_text("\n".join(lines)), None)])
            result["warnings"] = ["DOCX body/table text only; headers, footnotes, comments, images and metadata are not analyzed. Page numbers are unavailable."]
            return result
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ExtractionError("DOCX is malformed or cannot be read safely") from exc


def extract_bounded(name, data):
    file_kind(name, data)
    try:
        process = subprocess.run(
            [sys.executable, "-m", "app.extract_cli", name], input=data,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=25, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError("Extraction exceeded the 25 second safety limit") from exc
    if process.returncode or not process.stdout:
        raise ExtractionError("Extraction failed or exceeded memory/CPU limits")
    result = json.loads(process.stdout)
    if "error" in result:
        raise ExtractionError(result["error"])
    return result


REPORTER = r"(?:\(\d{4}\)\s*\d{1,2}\s+SCC(?:\s*\((?:Cri|Civ)\))?\s+\d{1,6}|AIR\s+\d{4}\s+(?:SC|[A-Z][A-Za-z]{1,15})\s+\d{1,6})"
NAME = r"\b[A-Z][A-Za-z.&'-]*(?:[ \t]+(?:[A-Z][A-Za-z.&'-]*|of|and|the)){0,5}[ \t]+(?i:v\.?|vs\.?|versus)[ \t]+[A-Z][A-Za-z.&'-]*(?:[ \t]+(?:[A-Z][A-Za-z.&'-]*|of|and|the)){0,6}"
STATUTE = (
    r"\b(?:[Ss]ections?|[Ss]ec\.?|[Ss]\.|[Aa]rticles?|[Uu]/[Ss])\s+\d+[A-Za-z]?(?:\([0-9A-Za-z]+\))*"
    r"(?:\s*(?:,|and|&|to|-)\s*\d+[A-Za-z]?(?:\([0-9A-Za-z]+\))*){0,6}"
    r"(?:\s+(?:of\s+)?(?:the\s+)?)?"
    r"(?:(?:Code of Criminal Procedure|Criminal Procedure Code|Indian Penal Code|Indian Evidence Act|"
    r"Bharatiya Nagarik Suraksha Sanhita|Bharatiya Nyaya Sanhita|Bharatiya Sakshya Adhiniyam|"
    r"Constitution(?: of India)?|[A-Z][A-Za-z ]{2,55}Act|Cr\.?P\.?C\.?|IPC|BNSS|BNS|BSA)"
    r"(?:,?\s*(?:18|19|20)\d{2})?)?"
)


def detect(text, paragraphs):
    spans = []
    for pattern in (REPORTER, NAME):
        spans.extend((m.start(), m.end(), "case_citation") for m in re.finditer(pattern, text))
    spans.sort()
    merged = []
    for start, end, kind in spans:
        if merged and start >= merged[-1][1] and start - merged[-1][1] < 35:
            previous = text[merged[-1][0]:merged[-1][1]]
            between = text[merged[-1][1]:start]
            if re.search(NAME, previous) and re.fullmatch(REPORTER, text[start:end]) and "\n" not in between:
                merged[-1] = (merged[-1][0], end, kind)
                continue
        merged.append((start, end, kind))
    spans = merged
    spans.extend((m.start(), m.end(), "statutory_reference") for m in re.finditer(STATUTE, text))
    spans.extend((m.start(), m.end(), "quotation") for m in re.finditer(r'“[^”\n]{10,1200}”|"[^"\n]{10,1200}"|‘[^’\n]{10,1200}’', text))
    spans.sort()
    findings = []
    for start, end, kind in spans[:MAX_FINDINGS]:
        paragraph = next((p for p in paragraphs if p["start"] <= start < p["end"]), None)
        findings.append({
            "kind": kind, "label": text[start:end], "excerpt": text[start:end], "start": start, "end": end,
            "paragraph_id": paragraph["id"] if paragraph else None, "page": paragraph["page"] if paragraph else None,
            "status": "not_checked", "note": "", "identity_checked": False, "quote_checked": False,
        })
    warnings = ["Deterministic English pattern detection is incomplete; undetected references and legal propositions are not assessed."]
    if len(spans) > MAX_FINDINGS:
        warnings.append(f"Detected {len(spans)} references; only the first {MAX_FINDINGS} are processed due to the safety budget.")
    return findings, warnings
