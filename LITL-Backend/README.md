# LiTL backend

FastAPI + SQLAlchemy single-service legal-draft review beta. **Public, synthetic
or fully anonymized English Indian-law documents only; never confidential client
or company material.** One owner/reviewer, one or two manually provisioned testers.
No LLM, scraping, purchases, external document submissions, Redis or fake evidence.

## Run locally (no credentials)

Python 3.12 recommended; Python 3.10+ on macOS/Linux. From this directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
.venv/bin/python -m app.setup_db
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 16
```

Open <http://127.0.0.1:8000/docs> for the API explorer. Frontend development origins
`http://localhost:5173` and `http://127.0.0.1:5173` are allowed by default.
`/healthz`, `/readyz` and `/v1/config` require no session.

SQLite `.data/litl.db` stores original local file bytes, extracted text, queued
jobs, reviews and reports. This is persistent local storage, not a temporary
upload folder. Back up/protect it like the original documents. Never expose
local mode over a tunnel or bind it to `0.0.0.0`; every request shares the fixed
`local-development-owner`. Startup refuses known hosted environments or
`APP_ENV=hosted|production|staging`; local requests also require a loopback peer
and localhost Host header. **Never deploy with `AUTH_MODE=local`.**
Local mutations also reject any supplied `Origin` outside `CORS_ORIGINS`,
including `Origin: null`: CORS response headers alone do not prevent multipart
CSRF. Both default development origins are accepted; loopback CLI requests without
an Origin remain valid. Merely setting the `RENDER` environment variable, even
to an empty value, forbids local authentication at startup.

Environment is read from exported variables, not automatically from `.env`.
`.env.example` describes every supported environment setting. Do not commit secrets.
Dependencies are exact direct-dependency releases reviewed against their official
PyPI metadata and upstream projects on 2026-09-14; normal pip resolves transitives.

## Working API

The frontend contract is under `/v1`:

* `GET /config`
* `POST /documents/text` — `{title, text, consent:true}`
* `POST /documents/file` — local multipart `file` and `consent="true"`
* `POST /uploads` — hosted `{file_name,size,consent:true}`; returns document ID,
  private signed upload URL and required headers. PUT raw bytes, then
  `POST /documents/{id}/finalize`. Multipart is intentionally denied in hosted mode.
* `GET /documents`, `GET /documents/{id}`, `DELETE /documents/{id}`
* `POST /documents/{id}/analyses`, `GET /documents/{id}/analyses/{run_id}`,
  `POST /documents/{id}/analyses/{run_id}/cancel`
* `PUT /documents/{id}/findings/{finding_id}/review` — decision, review_note,
  correction and expected_version. Stale writes return 409; corrected requires
  a nonempty correction. Reviews/source activity on an older analysis also
  return 409, including while a new analysis is queued. Decisions are never
  filled by a machine.
* `POST /documents/{id}/findings/{finding_id}/source-open` — `{source_id}`;
  idempotent activity, no decision-version increment.
* `POST /documents/{id}/reports`, `GET /documents/{id}/reports`,
  `GET /documents/{id}/reports/{report_id}` — immutable JSON snapshots, only after
  the latest analysis completes. The frontend can print/save PDF or download JSON.

Creation persists a queued run before returning. File extraction takes place in
the durable worker, so corrupt-but-signature-valid files become explicit failed
runs. Initial file responses can have empty text/paragraphs until completion.
All offsets use **Python Unicode code points**, not UTF-16 offsets. Paragraph
IDs and text spans are stable in each extracted document. PDF page numbers are
one-based; DOCX/TXT have `page:null`. Reports include proposed corrections; they
do **not** modify the original uploaded file.

Additional backward-compatible fields: finding `identity_checked`, `quote_checked`
and `opened_source_ids`; source `content_sha256`; metrics per-status counts.
Machine status/provenance never changes when a human confirms unavailable evidence.
Reports and review events reject SQL UPDATEs; owner deletion/expiry can erase them.

## Boundaries and quotas

* 10 MiB original file, 200,000 extracted characters, 50 PDF pages.
* TXT is UTF-8 (optional BOM), nonempty, no binary control characters.
* PDF must be text-based, unencrypted and readable. Scanned PDFs explicitly fail;
  mixed image/text PDFs warn about missing pages. No OCR.
* DOCX ZIP signatures, member count (1,000), total expanded bytes (30 MiB),
  member size (20 MiB), compression ratio (200:1), duplicate entries, encryption
  and macros are checked. XML uses defusedxml. Body/table text only; no footnotes,
  headers, comments, images or metadata. Anonymize those before uploading, too.
* Extraction runs in a killed-on-timeout subprocess: 25 seconds wall time,
  20 CPU seconds, 256 MiB address-space limit on Linux (macOS lacks reliable
  equivalent address-space enforcement). Nothing is unpacked to disk.
* At most 50 detected spans; truncation is disclosed. Deterministic SCC/AIR,
  selected case-name, section/article and quotation patterns are incomplete.
  Statutes are detected but **unsupported for authoritative version/applicability
  checks**. No automated CrPC-to-BNSS conversion or proposition verification.
* Per owner: 20 active documents, 20 new uploads/day UTC, 30 analyses/day UTC,
  five total runs/document, one active run/document, 20 report snapshots/document.
  Quotas are transactional and durable; concurrent submissions cannot overrun them.
* 180 HTTP requests/minute per direct peer; health/readiness excluded. This
  in-memory network backstop complements durable authenticated-owner budgets.
  Behind Render's proxy the peer limit may be shared; do not trust arbitrary
  forwarded headers. Run one process and the documented concurrency limit.
* Bodies are bounded before multipart parsing (10 MiB + 64 KiB framing);
  no multipart spill to OS temporary directories. Other bodies cap at 2 MiB.
  At most two local multipart uploads are buffered concurrently.
  Request bodies have a 30-second overall/15-second idle read deadline.
* Outbound source traffic is HTTPS only to fixed `api.indiankanoon.org`, POST,
  no redirects or environment proxy inheritance, verified TLS, short connect/read
  timeouts, uncompressed bounded response bytes, maximum 50 requests across all lease recoveries
  in a run, no HTTP retries and no full document queries. Up to three candidates
  per case are fetched. Provider failure stops further calls for that run.
  Full matched-case text used for quote comparisons has an aggregate two-million
  character in-memory budget; additional quotations remain explicitly unchecked.
* Supabase API calls only use the configured `https://PROJECT.supabase.co` origin.
  No document-supplied URLs, local network targets, arbitrary URL fetching or HTML
  execution. Stored passages are plain text.

## Honest evidence and metrics

Indian Kanoon is optional. With no token/terms approval, cases are `unavailable`,
statutes are `unsupported`, and quotations are `not_checked`; no fixtures or
invented URLs are returned. An empty successful search is `not_found`, not proof
of fabrication. Provider auth, credit, timeout or malformed response problems
are `unavailable`.

Search snippets alone never establish identity. The connector fetches full
candidate documents, compares the actual title to detected party names, and
checks reporter citations only against an explicit equivalent-citations header
(not incidental citations in reasoning). It conservatively retains ambiguity
when candidates or identity fields cannot be uniquely resolved. Only canonical
`https://indiankanoon.org/doc/NUMERIC_ID/` source links are emitted.

Quotation comparison uses a preceding case within 500 characters only if uniquely
resolved. The association is disclosed as a nearby case, not definitive attribution.
Unicode punctuation/whitespace normalization preserves numbers, negation and
letter case. Wording absent from that full retrieved text is `quote_mismatch`;
the case source is still linked. Unattributed/unresolved quotes are `not_checked`.
Neither a text match nor a human disposition establishes proposition support,
binding precedent, applicable statutory version or good-law status.

Every metric is `{numerator,denominator,percentage}`; denominator zero yields
`percentage:null`, never a fabricated score:

| Metric | Numerator / denominator |
| --- | --- |
| Source coverage | uniquely located references (including quote mismatches with a located case) / all detected findings |
| Citation consistency | consistent identity checks / case findings whose required identity metadata was actually checked |
| Quotation fidelity | normalized wording matches / quotations actually compared with retrieved full text |
| Review completion | any saved human decision, including unresolved / detected findings |
| Resolution coverage | confirmed, corrected or rejected / detected findings; rejection is a disposition, not validation |
| Source activity | distinct canonical URLs with recorded open-link action / distinct located candidate URLs; not proof of reading |
| Evidence provenance | checked findings with URL, repository, timestamp and locator for every linked source / identity-or-quote checked findings |

Counts for unreviewed, unresolved, ambiguous, unavailable, unsupported, not found,
not checked and quote mismatches are separate. All coverage applies only to
detected references, never every claim in the original document.

## Indian Kanoon access, terms and attribution

Official references inspected:

* <https://api.indiankanoon.org/documentation/>
* <https://api.indiankanoon.org/terms/>
* <https://api.indiankanoon.org/pricing/>

The current **documentation explicitly supports `Authorization: Token YOUR_TOKEN`**
on HTTPS POST requests; the older wording in the terms also discusses signed
public/private-key authentication. The implementation uses the documented token
method, not invented Bearer credentials. Set server-only `INDIAN_KANOON_API_TOKEN`
and `INDIAN_KANOON_TERMS_ACCEPTED=true` only after obtaining access/credit and
reviewing permitted display/retention. No account, trial credit or continued free
access is assumed. Trial exhaustion means unavailable, not permission to purchase.

Their terms require the **authentic “powered by IKanoon” logo above directly
displayed results**, complete, unobscured and **not altered or resized**:

* Desktop: <https://api.indiankanoon.org/static/pics/ikanoon6_powered_transparent.png>
* Mobile: <https://api.indiankanoon.org/static/pics/ikanoon_mobile_powered_transparent.png>

Frontend evidence and reports must display these assets at their natural size
(choose the appropriate official variant). Do not substitute plain text or invent
a logo. Include attribution when printing/exporting evidence. Terms permit API
information display, but do not establish confidential-client data approval.
Only limited passages (at most 1,600 characters/source), content hashes and
provenance are persisted; full fetched judgments live only in worker memory.
Provider query/account logs and its own retention remain outside LiTL deletion.

## Hosted setup: Render + Supabase

No deployment is performed by this repository. Use user-owned accounts, select
appropriate regions, provision only the approved two testers, and disable public
signups in Supabase Auth.

1. Create Supabase project and save its server Postgres connection string.
   Use direct or **session pooler** connection (not transaction mode).
2. Download the database CA certificate through the Supabase dashboard into a
   backend-relative protected location (for example `certs/prod-supabase.cer`).
   Use `postgresql+psycopg://...?...sslmode=verify-full&sslrootcert=...`.
   URL-encode password punctuation. Never turn off certificate/hostname checks.
3. Set `AUTH_MODE=supabase`, `STORAGE_MODE=supabase`, `APP_ENV=hosted`,
   `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
   `SUPABASE_SERVICE_ROLE_KEY`, `STORAGE_BUCKET=litl-private`,
   and `CORS_ORIGINS=https://YOUR_FRONTEND_HOST` (comma-separated exact origins).
   Only the project URL and publishable/anon key are returned to the frontend.
4. Run `python -m app.setup_db` with the backend database owner. This is the
   greenfield **schema-v1 setup command**, idempotent for an unchanged schema;
   it does not auto-migrate future column changes. Take backups and write a
   reviewed forward migration before changing a deployed schema.
5. Run `supabase.sql` in Supabase SQL Editor. It creates/hardens the **private**
   10 MiB bucket and revokes anonymous/authenticated access to every backend
   public-schema table. The application applies table RLS and revocation
   atomically with schema creation. No backend-table REST policies are granted.
   Use a fresh bucket and audit existing `storage.objects` policies: no broad
   authenticated/public policy may permit access to `litl-private`.
   API startup verifies that the bucket is private and its provider-side file
   limit is at most 10 MiB; it fails closed if that check is unavailable or unsafe.
6. Supabase authentication is validated using `/auth/v1/user` on every private
   request with strict timeouts. JWT payload decoding alone is never trusted.
   Backend Postgres and storage credentials are server-only; every document,
   finding, source action and report checks ownership before privileged access.
7. Render build command: `pip install --no-cache-dir -r requirements.txt`.
   Start command:
   `python -m app.setup_db && uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1 --limit-concurrency 16 --no-proxy-headers`.
   Configure health check `/readyz`. Never run multiple Uvicorn workers for this
   single-loop free-tier configuration. Provider and storage network calls happen
   outside DB transactions. SQLite is refused in hosted mode.

Signed uploads are object-scoped, non-upsert, and expire after Supabase's two-hour
token lifetime. Reservations must finalize within one hour. Tokens are bearer
capabilities: never log/share them. Storage enforces the 10 MiB limit even when
a client lies about size; finalization downloads with a hard byte bound and checks
declared size/signature. The worker validates full format again. Original hosted
bytes remain in private storage; Render's filesystem is never the source of truth.

## Recovery, expiry and deletion

SQLAlchemy tables include documents, runs/jobs, findings, sources, associations,
immutable review events, source-open activity, report snapshots and owner quotas.
Postgres claims use `FOR UPDATE SKIP LOCKED`; SQLite uses `BEGIN IMMEDIATE`.
Each claimed run has an ownership token, 90-second lease and at most three
recovery attempts. Heartbeats and provider-request reservations are durable;
old/cancelled workers cannot publish. Final findings and completion are published
in one short transaction, after rechecking document expiry/deletion and lease.
Restart recovery redoes an interrupted run, not human decisions from an older run.

Data expires seven days after creation; unfinished uploads expire after one hour.
Expired documents and reports are denied immediately, before cleanup. The worker
cleans on wake and approximately every minute while awake. Free Render may sleep:
physical deletion/processing is delayed until the service wakes, and is **not**
promised as unattended/always-on. There is no artificial keep-alive traffic.

DELETE first tombstones the document and erases original local bytes, extracted
text, runs/findings/sources/reviews/reports transactionally; stale worker output
cannot resurrect them. It then deletes the private object. A storage failure
returns **503 with an explicit pending-deletion message** while all owner reads
remain 404. Retry DELETE; the worker also retries. Inaccessible upload tombstones
survive until outstanding signed tokens expire (two hours plus five-minute
margin), and re-delete their object on subsequent cleanup to catch late uploads.
After token expiry the row itself is erased. Pending tombstones retain only the
owner/random storage identifier and cleanup metadata; filenames/titles are scrubbed.
Provider logs, hosting backups and database backups have separate retention;
physical media erasure and third-party retention are not promised.

## Validation

```sh
.venv/bin/python -m unittest discover -v
.venv/bin/python -m pip check
```

Tests use stdlib unittest, FastAPI TestClient and **mocked source HTTP only**.
They cover owner isolation, real text/multipart flows, PDF/DOCX/TXT limits,
Unicode offsets, empty detections, identity ambiguity, quote negation/number
preservation, unavailable/credit errors, quotas, concurrent review, immutable
snapshots, cancellation, restart leases, delete-during-processing and storage
deletion retries. Scratch databases are only in backend `.test-data/` and are
removed after tests. No legal document is submitted to an external service.

Mock tests do not prove live provider credentials, hosted Postgres connectivity,
Supabase policies, account setup or measured legal detection accuracy. Before
public beta, validate those with user-owned credentials and a labelled
public/synthetic corpus, inspect the logo, verify two-account isolation in the
deployed environment, and measure representative 10-page latency/cost. No accuracy
or legal correctness score is claimed from these synthetic tests.
