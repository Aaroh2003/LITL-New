# LiTL backend

FastAPI + SQLAlchemy single-service legal-draft review beta. **Public, synthetic
or fully anonymized English Indian-law documents only; never confidential client
or company material.** One owner/reviewer, one or two manually provisioned testers.
Optional consent-bound Gemini summaries; no scraping, automatic purchases,
Redis or fake evidence. Gemini receives extracted text only after separate consent.

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

Environment is read from exported variables. For local key-file configuration,
start Uvicorn with `--env-file .env`; the dotenv loader does not override exported
variables. `.env.example` documents the settings. Do not commit secrets.
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
  in a run, no HTTP retries and no whole-draft source queries. At most ten search
  attempts (including recovery), with up to three candidates per case/statute
  query. Repeated normalized queries and document IDs reuse bounded in-memory
  results within an attempt. Provider failure stops new calls for that run.
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
An exact supplied reporter identity with compatible supplied party names can
establish a primary link among the examined candidates; this is not exhaustive
search. Name-only results remain candidates, regardless of search ranking or
page length. Legislation requires a matching Act/provision title; judgments
merely mentioning a section stay candidates. An exact parent-Act title can get
an explicitly labelled Act link, never a guessed section anchor. Statutory
applicability remains `unsupported` even when a source link is found.

Finding fields `link_state`, `link_message`, and `reference_url` distinguish
matched links, possible matches, missing Act context, not found, unavailable,
and unchecked items independently of legal-verification status.

Quotation comparison uses a preceding case within 500 characters only if uniquely
resolved. The association is disclosed as a nearby case, not definitive attribution.
Unicode punctuation/whitespace normalization preserves numbers, negation and
letter case. Wording absent from that full retrieved text is `quote_mismatch`;
the case source is still linked. Unattributed/unresolved quotes are `not_checked`.
Neither a text match nor a human disposition establishes proposition support,
binding precedent, applicable statutory version or good-law status.

Legacy metrics remain available for API compatibility and old saved snapshots.
Every metric includes `{numerator,denominator,percentage}`; denominator zero
yields `percentage:null`, never a fabricated score:

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

### Versioned report calculations

Live documents and new reports additionally include `metrics.assessment`
(`definition_version: evidence-2`). Its metrics contain labels, formulas,
descriptions and raw counts, frozen in each report. The UI uses these new
definitions when present and preserves legacy snapshot rendering otherwise.

| Metric | Formula |
| --- | --- |
| Identity assessment coverage | assessed case occurrences / processed case occurrences |
| Identity match among assessed | located case occurrences / conclusive bounded-candidate comparisons |
| Located-case coverage | located case occurrences / processed case occurrences |
| Distinct-reference coverage | distinct case labels located at least once / distinct case labels |
| Quote comparison coverage | compared quotations / processed quotations |
| Wording-match rate | normalized wording matches / compared quotations |
| Review completion | any saved decision / processed findings |
| Review disposition | confirmed, corrected or rejected / processed findings |
| Provenance completeness | assessed findings with complete provenance / assessed case and quotation findings |

Each percentage is `100 * numerator / denominator`, rounded to one decimal.
N/A metrics remain visible in the final report. Distinct labels normalize
whitespace/case only, not aliases or different reporter citations. No combined
legal-confidence score or statistical confidence interval is inferred from
these exact within-document counts.

New case findings record `identity_assessment` as `matched`, `not_matched`, or
`unknown`. A fully compared set of at most three returned candidates with no
match can be `not_matched`, but its machine status remains `ambiguous`: the
bounded search does not establish invalidity. Competing matches, skipped
candidates or missing identity metadata are unknown. Old ambiguous findings are
not retroactively treated as conclusive comparisons. Reporter page prefixes do
not count as exact citation matches. Quote attribution remains proximity-based
and provisional; a wording match is not legal-context verification.

New analyses persist pre-limit detection/processed/deferred counts in the
additive `analysis_scopes` table, with the same ownership-through-run, deletion
and hosted RLS protections as other analysis data. No existing columns change.
Old analyses report unknown scope rather than inventing a pre-limit total.

The report endpoint generates schema 2 snapshots with a deterministic overview,
overlapping attention categories, raw calculations, original evidence and
decisions, parser version, extracted-text SHA-256 and per-finding review
versions. Hashes detect changes, not authenticity. Reports may be generated
before human review is complete, with incompleteness explicitly shown.
Open **Generate report** from the analysis or review screen, then generate
the snapshot and download JSON or print/save PDF. Neither step invokes an AI
model or makes new source requests.

### Context-sensitive statutory references

For `Section 335` without an Act in the detected reference, the message asks
the reviewer to identify the Act/Code; it does not assume CrPC or BNSS. A named
Act produces a specific official-text/version-check message. Criminal-procedure
transition guidance appears only for an explicitly named CrPC/BNSS reference.
No applicability, statute identity from section number alone, or official text
is inferred. The missing-passage message follows the reference type and result.

Updated explanations appear on live older statutory findings without paid
reanalysis. Old report snapshots remain unchanged; generate a new report for
updated explanations/formulas. A new analysis is needed only for new detector
scope and case-assessment results; existing results are not silently reverified.

## Indian Kanoon access, terms and attribution

### Enter your key locally

Fill in `INDIAN_KANOON_API_TOKEN=` in the ignored backend `.env` file. If that
file is absent, copy `.env.example` to `.env`. Review the provider terms before
setting `INDIAN_KANOON_TERMS_ACCEPTED=true`, and choose an approved allocation
for `INDIAN_KANOON_BUDGET_PAISE`. The default is `0` (no live spending);
`40000` means INR 400, not a claim about your actual account balance.

From this directory:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 16
```

Restart after editing the file. Exported variables take precedence. Hosted
deployments must use backend dashboard secrets, never frontend `VITE_` variables.
Test commands do not automatically load `.env`.

### Spending limits and report costs

| Variable | Default (paise) | Scope |
| --- | ---: | --- |
| `INDIAN_KANOON_BUDGET_PAISE` | 0 | Cumulative allocation across this app's database |
| `INDIAN_KANOON_RUN_BUDGET_PAISE` | 1100 | Each analysis, including recovery |
| `INDIAN_KANOON_DAILY_BUDGET_PAISE` | 4400 | All owners per UTC day |
| `INDIAN_KANOON_OWNER_DAILY_BUDGET_PAISE` | 2200 | Each owner per UTC day |

All four limits must be positive for lookup to be configured. This configuration
flag does not prove account authorization, available credit, or unspent budget.
Requests reserve 50 paise/search and 20 paise/document before network access
(price schedule `ik-2026-09-25`). Confirm provider rates before activation.
Transactional account locking serializes concurrent spending across owners.
The 50-request/run cap still applies independently of monetary limits.

Failed, interrupted, or uncertain requests retain their reservations; no refunds,
automatic retries, or provider balance API are assumed. Saved reports include
`source_usage`: reserved paise, operation counts, price versions, and unpriced
legacy attempts. Amounts are **unreconciled reservations**, not confirmed charges
or remaining provider credit. Older snapshots still render without usage data.
Opening, downloading, or printing a snapshot does not make paid source requests.

Request-level rows expire/delete with the document. Content-free aggregate
counters, including a pseudonymous hashed owner/day key, survive deletion so
deleting documents does not replenish spending. Token rotation also leaves these
counters intact. Do not reset the database to reset credit.

The lifetime setting is a cumulative allocation, not a remaining-balance field.
Before increasing it, reconcile the dashboard balance, conservative reservations,
outside account usage and current rates. At upgrade, allocate only from verified
remaining credit: old requests have no account-wide ledger. For in-progress
legacy runs, unpriced attempts count at 50 paise each against the run cap.
Separate deployments/databases do not share budgets; partition allocations
manually. Startup adds accounting tables with existing private-table hardening;
it changes no existing columns and preserves prior snapshots/counters.

Persistent cross-user evidence caching remains excluded. Versioned report
metrics are implemented as described above; broader legal-identity and quotation
attribution improvements remain future work. Evidence-only reports and saved
human decisions do not require an AI model or API key.

## Gemini summary setup

Add your key to backend `.env` (never a `VITE_` variable), then explicitly enable:

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_ENABLED=true
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_BUDGET_MICROUSD=1000000
```

The last value is an example **USD 1 cumulative estimated allowance**, not a
provider purchase. The shipped value is zero and the enabled flag is false.
Restart with `--env-file .env`. Existing Indian Kanoon settings are independent.
On hosted services configure the same values in backend secret settings.

`gemini-3.5-flash-lite` is the default lower-cost option, with USD 0.30 per million
input tokens and USD 2.50 per million output tokens at the published rates
checked on 2026-09-26. It uses provider-default thinking settings; the
2.5-specific `thinkingBudget` is not sent. Generation access and free quota
remain project-dependent. `gemini-3.8-flash` is also supported.
Google rejected live 2.5 requests for this API
project as unavailable to new users, despite returning successful model metadata.
`gemini-2.5-flash` remains an explicit option for projects that still have access.
Model metadata success is not proof that generation will succeed.

Standard 3.8 prices checked on 2026-09-26 are USD 0.75 per million input tokens
and USD 3.75 per million output tokens through 2026-12-31, represented by
`GEMINI_INPUT_MICROUSD_PER_MILLION=750000` and
`GEMINI_OUTPUT_MICROUSD_PER_MILLION=3750000`. Reconfirm before activation and when
changing models/dates; the published 3.8 prices increase from 2027-01-01.
The 2.5 rate estimates are USD 0.30/2.50 per million input/output tokens.
Absent explicit rate overrides, validation selects the supported model's rates.
The free tier still uses those conservative estimates for local
allowance accounting; no assertion is made about actual charges.

Upload JSON accepts strict boolean `ai_summary_consent`, default false.
Multipart accepts the literal string `true` or `false`. Consent persists for
that document's subsequent analysis runs, including hosted signed uploads.
Only an opted-in completed analysis queues a summary. Existing documents are
never sent automatically without prior consent.

Owner-authenticated endpoints:

```text
POST /v1/documents/{id}/analyses/{run_id}/summaries
     {"consent":true,"request_key":"unique-client-key"}
GET  /v1/documents/{id}/analyses/{run_id}/summaries/{summary_id}
PUT  /v1/documents/{id}/analyses/{run_id}/summaries/{summary_id}/review
     {"decision":"reviewed"|"rejected","expected_version":0}
```

Repeat request keys reuse the same attempt; concurrent requests reuse an active
job. At most two attempts/run, `GEMINI_OWNER_DAILY_REQUESTS` per owner per UTC
day (default 5; configurable from 1 to 20), and twenty/app/UTC-day. Raising the
owner limit does not clear usage or raise the monetary allowance. Errors
identify whether the owner-day limit, app-day limit or cumulative allowance
blocked a request. Daily limits reset at 00:00 UTC (05:30 IST); the cumulative
monetary allowance does not reset daily. A blocked attempt showing a zero
reservation was not sent to Gemini. Durable
quota counters and cumulative reservations survive document deletion. No
automatic refunds or generation retries; an interrupted lease becomes an
explicit failure rather than replaying an uncertain paid call.

The worker sends a frozen paragraph/reference/source-excerpt packet to Google's
official HTTPS API using `x-goog-api-key`, not query-string credentials. It first
calls `countTokens` for the full request and rejects inputs above 64,000 tokens
without silently truncating the draft. Packets over 1,000,000 UTF-8 bytes are
rejected locally before any request. Output is capped at 2,500 tokens;
3.5 Flash-Lite uses provider defaults, 3.8 uses low thinking, and 2.5 disables
thinking. The output cap includes generated thinking tokens where applicable.
At the documented rates, each attempt reserves USD 0.057375 (3.8) or
USD 0.02545 (3.5 Flash-Lite / 2.5) before network access.
Failed or cancelled attempts
retain this conservative reservation. Google-reported usage and reservations
are not reconciled billing; app caps do not cover other use of the same key.

Gemini must return structured statements with evidence IDs. Prompt/schema
`gemini-summary-2` enumerates the exact evidence-object keys in the response
schema. Tracking IDs in `references[].finding_id` are not evidence IDs.
Source-observation statements are constrained to retrieved-source IDs; when
none are available, that section is constrained to an empty array. The backend
validates the schema, ID membership, source-observation eligibility, exact
reporter citations and quotations, and rejects model-generated HTTP URLs.
These checks do not establish semantic truth. The summary is labelled
unreviewed until a human reviews that exact version; review is not legal
certification. No resolved source means a clearly labelled draft-only summary.
The model does not choose external links or change deterministic metrics.

Post-validation still rejects unknown IDs even if a provider ignores the
generation schema; it never substitutes guessed IDs or publishes unsupported
statements. Reported token usage is retained even when output validation fails.
Already-failed summaries are not repaired or replayed automatically; request a
new summary after updating. Existing snapshots retain their original versions.

New private tables store summary consent, jobs, quota counters and review events.
They use the existing additive schema/RLS setup, run/document deletion cascades
and immutable review-event protections. Reanalysis cancels pending old jobs;
late/deleted/expired jobs cannot publish. Network calls occur outside DB locks.
Original files are never changed.

New schema-3 reports freeze the current summary (including pending/failure
state), source reference index and mathematical report. Existing snapshots are
unchanged. A pending summary prompts the user before saving an evidence-only
report. Viewing/exporting never regenerates a summary or invokes a paid API.

HTTP 404 now reports an unavailable model rather than a generic timeout;
HTTP 503 reports temporary provider overload. Requests are not automatically
replayed. A model change invalidates queued requests for the old model; request
a new summary after restarting. Actual provider charges are not confirmed by
these status codes or conservative reservations.

The frontend also provides Google's first-result redirect (`btnI=1`) for case
citations and statutory references, scoped to
`site:indiankanoon.org/doc/ <reference>`. Google may show a redirect confirmation
or search page; direct navigation is not guaranteed. These links work only when
clicked, with no Gemini Search API, click tracking, result scraping or automatic
evidence import. They do not count as matched sources. Google's
grounding terms restrict automated link collection and caching; that service is
not used to populate reports.

**Data use:** review <https://ai.google.dev/gemini-api/terms>. Unpaid inputs and
outputs may improve Google products and be read by reviewers; do not send
sensitive, confidential or personal information. Paid-tier/region rules differ.
Confirm your account tier, region and Indian Kanoon excerpt-use permissions.
No prompt text, provider response content or key is logged by the summary worker.

Tests use mocked providers. For an isolated browser check including AI and links:

```sh
# Set a NEW disposable SQLite path; never use your normal document database.
LITL_TEST_DATABASE_URL=sqlite:////absolute/path/to/disposable-test.db \
  .venv/bin/uvicorn tests.mock_ai_server:app --host 127.0.0.1 --port 18123
```

Run a frontend at `127.0.0.1:15173` pointed to that API, then run the root browser
smoke with `LITL_TEST_AI_MOCK=1`, `LITL_TEST_API_URL=http://127.0.0.1:18123` and
`LITL_TEST_FRONTEND_URL=http://127.0.0.1:15173`. The script requires the mock-only
server marker before submitting data in AI mode. Never deploy the test server.

Official references inspected:

* <https://api.indiankanoon.org/documentation/>
* <https://api.indiankanoon.org/terms/>
* <https://api.indiankanoon.org/pricing/>

The current **documentation explicitly supports `Authorization: Token YOUR_TOKEN`**
on HTTPS POST requests; the older wording in the terms also discusses signed
public/private-key authentication. The implementation uses the documented token
method, not invented Bearer credentials. Set server-only `INDIAN_KANOON_API_TOKEN`
and `INDIAN_KANOON_TERMS_ACCEPTED=true`, with a positive spending allocation,
only after obtaining access/credit and
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
