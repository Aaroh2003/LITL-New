# LiTL MVP implementation plan

Status: Local MVP implemented on 2026-09-14. Hosted deployment and live-source acceptance pending.
Date: 2026-09-14

## Goal

Turn the existing Lawyer in the Loop prototype into a publicly accessible,
evidence-backed legal-document review application. Preserve the current design
and its core boundary: the system locates and compares evidence; a human records
the final assessment. Do not sell a score as a certificate of legal correctness.

## Starting point (before implementation)

- `LITL-Frontend` is React 19, TypeScript, Vite and Tailwind, with ten routes.
- `LITL-Backend` is empty.
- `src/screens/UploadScreen.tsx` retains a filename, not file contents.
  Paste text does not collect text, and the advertised 25 MB limit is not enforced.
- `src/screens/AnalyzingScreen.tsx` advances on a six-second timer.
- `src/data/claims.ts` and `src/data/draft.ts` supply a fixed bail application.
- The workspace screens select fixed references and navigate on review actions;
  decisions, edits and review events are not persisted.
- Source excerpts are fixtures. The evidence screen links to a repository
  homepage, not the judgment being discussed.
- Report figures and senior-review queues are fabricated demonstration data.
  The PDF button invokes browser printing; sharing just changes routes.
- No real authentication, document history, source retrieval or application API
  was found in the inspected frontend.
- Sample citations differ across screens: the landing page uses
  `(2014) 8 SCC 273` for Arnesh Kumar while the mock dataset uses
  `(2014) 8 SCC 469`. Neither fixture is a source of verified legal truth.

Reuse the design tokens, shared UI components and three-pane review layout.
Replace the simulated workflow and hard-coded data, not the whole frontend.

## Proposed first-release scope

Confirmed scope:

- Indian law, English-language bail applications, legal notices and written
  submissions; initially case citations, statutory references and attributed quotations.
- One or two testers, no initial budget, public/synthetic/anonymized documents only.
- One owner/reviewer per document; senior approval is deferred.

Proposed implementation defaults:

- Public sample walkthrough without an account; two manually provisioned
  Supabase email/password accounts for private test uploads. Defer public signup
  and production email delivery configuration.
- Text-based PDF, DOCX, TXT and pasted text. Initially cap at 10 MB and
  50 extracted pages, with a separate character and reference-processing budget.
  Update the upload copy to reflect enforced limits.
- Scanned/image-only PDFs, encrypted PDFs and unsupported documents receive an
  explicit explanation. OCR and multilingual support are subsequent work.
- Hide senior approval and sharing until real permissions and collaboration exist.
- Draft and findings can be reopened after refresh. Corrections are saved review
  proposals, not silent edits to the original document.
- Start with non-confidential demo documents; confidential-client use is blocked
  pending a suitable hosting, retention and external-provider policy.

### End-to-end user journey

Sign in -> upload or paste -> see real processing stages -> inspect findings ->
select a reference -> view its document context and linked source passage ->
confirm, correct, reject or leave unresolved -> save -> reopen or export report ->
delete document and associated private data.

The first implementation milestone is a complete TXT/pasted-text version of this
journey using one real source connector. Add PDF/DOCX and richer metrics only
after that vertical slice works.

## Hosting and architecture

Zero-budget test baseline: keep Vercel for the existing frontend, use one free
Python FastAPI Render web service, and Supabase Free for Postgres, Auth and
private object storage. Python suits document parsing; no frontend rewrite or
Next.js migration is needed. This is a limited tester deployment, not an
always-on production architecture.

```text
Vercel React frontend
  |-- Supabase Auth: user identity
  |-- Private storage: authorized direct upload/download
  `-- Render FastAPI: document, analysis, findings and review API
        |-- Supabase Postgres: application records and durable jobs
        `-- In-service job processor (one concurrent job, while awake)
              |-- Parse files and locate reference spans
              |-- Query permitted legal-source connectors
              |-- Compare retrieved evidence
              `-- Optional approved LLM for structured assistance
```

- Upload directly to private storage using short-lived authorization; do not
  route document bytes through the frontend host's function request body.
- API returns a job ID immediately. Frontend polls durable job state instead of
  keeping one long request open or simulating percentage completion.
- Use a Postgres-backed jobs table with atomic claiming, leases, heartbeats,
  bounded retries and idempotent writes. A restarted worker resumes safely.
  This avoids adding Redis solely for a small MVP.
- The free API service runs a lifecycle-managed job loop, with expensive parsing
  offloaded from the HTTP event loop and bounded resource use. Persistent files
  live in object storage, not a Render filesystem. Persist jobs before scheduling;
  do not rely solely on an in-memory background task.
- Active analysis screens poll for progress; closing the browser may allow the
  service to sleep. Processing can pause on sleep/restart and resumes after a
  request wakes the service and expired leases are reclaimed. Tell users this;
  do not promise unattended completion or use artificial keep-alive traffic.
- Later, move the same processor to a paid Render background worker when
  unattended processing or more users justify it.
- Choose compatible regions based on the confirmed data policy. Store privileged
  keys only on the backend; enforce owner access even when using a database role
  that bypasses RLS.
- Render Free sleeps after 15 minutes without inbound traffic and cold starts
  take about a minute. Supabase Free currently includes 500 MB database storage
  and 1 GB file storage, and pauses inactive projects after one week.
- Use deterministic extraction/matching initially: no paid LLM is required.
  This limits free-form claim understanding and detection recall, which the UI
  must disclose. An approved model integration can be added behind a flag later.
- Indian Kanoon's published pricing offers Rs 500 signup credit for integration
  development/testing. Account access and credit must actually be obtained before
  claiming live external lookup works.
- Its published request prices are Rs 0.50/search, Rs 0.20/document and
  Rs 0.05/fragment. A simple one-search, one-document, one-fragment lookup costs
  Rs 0.75; 20 such lookups cost Rs 15. Ambiguities, retries and additional
  requests increase this. Trial credit is finite, not an ongoing free tier.
- The provider also advertises Rs 10,000/month for administrator-approved
  non-commercial use. Do not assume this project qualifies.
- Initial cash requirement can therefore be Rs 0 within hosting quotas and
  available trial credit. After credit exhaustion, top-up requirements must be
  confirmed with the provider; there is no verified minimum top-up here.
- Enforce conservative request budgets, cache only as permitted, expose credit
  exhaustion honestly, and disable paid model use. Never initiate purchases.
- Hosting choices are proposals, not confirmation that these services are
  approved for LinkedIn or confidential legal data.

## Evidence and verification approach

1. Extract text with stable character offsets, paragraph IDs and PDF page
   locations. For DOCX/TXT, show paragraph locations rather than inventing page
   numbers. Keep the original file unchanged.
2. Detect citations, statutes and quotation spans using deterministic patterns
   plus an optional schema-constrained model. Validate every detected span
   against the actual extracted text and record parser/model versions.
3. Resolve references through permitted connectors. Indian Kanoon has an API
   for search, documents and fragments; published pricing and terms have been
   reviewed, but account access and credits remain prerequisites. Include its
   required "powered by IKanoon" attribution in accordance with its terms.
   Assess official court and India Code access separately;
   do not assume an unrestricted scraping API exists.
4. Store candidate identity, canonical URL, repository, retrieved timestamp,
   relevant passage and source locator, plus a content hash where permitted.
   Respect licensing restrictions on retained or exported source text.
5. Compare names, citation/year/court metadata, statute identifiers and quotation
   wording. Retain ambiguity when multiple candidates match. Finding the case
   does not establish that it supports the proposition in the draft.
6. Keep retrieval results separate from human decisions. Distinguish found,
   ambiguous, not found, provider unavailable, unsupported and not checked.
   A failed provider call must not be reported as a fabricated citation.
7. Models may suggest passage relevance only against retrieved evidence, with
   explicit uncertainty. They cannot invent authorities, URLs or source quotes;
   model output alone never establishes a source match.

If a source provider is unavailable, show that limitation. A sample or
user-supplied source comparison can remain useful, but it is not equivalent to
independent external verification. Never silently substitute mock evidence.

## Metrics

Show counts and denominators alongside percentages. Metrics apply only to
detected items, not to every possible claim in the document. Display N/A when
the denominator is zero and surface extraction/processing coverage limitations.

| Metric | Definition and interpretation | Release |
| --- | --- | --- |
| Source location coverage | Detected references with an identified source / detected references requiring a source; separate ambiguous and unavailable counts | MVP |
| Citation identity consistency | References with consistent available identity fields / references whose metadata was actually checked; display fields missing or conflicting | MVP |
| Quotation fidelity | Exact or explicitly normalized matches / quotations checked against retrieved passages; show word-level differences and unchecked count | MVP |
| Review completion | References with any saved human decision, including unresolved / detected references | MVP |
| Resolution coverage | Confirmed, corrected or rejected references / detected references; rejected is a recorded disposition, not a valid claim | MVP |
| Open issues | Counts of unreviewed, unresolved, ambiguous, inaccessible and conflicting items, with drill-down | MVP |
| Source-link activity | Distinct sources with a recorded open-link action / located sources; does not prove reading or comprehension | MVP |
| Evidence provenance | Checked findings with repository, URL, timestamp and a passage locator / checked findings | MVP |
| Proposition support | Evidence-linked supported/partial/contradicted/insufficient-evidence suggestions; requires human confirmation and evaluation | Later |
| Statutory applicability | Potential repeals/amendments and date-sensitive references; needs applicable-date facts and authoritative version data | Later |
| Authority fit | Court/jurisdiction mismatch warnings; not a blanket binding-precedent score | Later |
| Internal consistency | Conflicting dates, amounts, party names or cross-references within the draft | Later |

Do not add an AI-authorship score, unsupported "hallucination probability" or
overall legal-correctness score. Do not claim a case remains good law without a
reliable treatment-history source. CrPC/BNSS applicability in particular cannot
be decided by replacing old section numbers based on upload date alone.

## Implementation sequence

### 1. Confirm scope and prove source access

Jurisdiction, permitted data, zero-budget target and single-reviewer scope are
confirmed. Obtain authorized API access and trial credit through the provider
dashboard, not pasted credentials.
Use a small public/synthetic fixture set with known correct and incorrect
citations, altered quotes and unlocatable references. Prove retrieval of exact
document URLs and passages before building a polished analysis pipeline.

Exit: an approved source connector can resolve representative references, or
the reduced source coverage is explicitly agreed before implementation continues.

### 2. Backend foundation and private document lifecycle

Create `LITL-Backend/app/`, dependency configuration, migrations, environment
example, backend tests and single-service deployment configuration.

Tables: documents, analysis_runs, findings, sources, finding_sources,
review_events and report_snapshots. Analysis runs also carry durable job state.
Each private record is tied to an owner and document/run version. Human review
events record actor, timestamp, old/new decision, note and proposed correction.

API surface under `/v1`: create/list/get/delete documents, initialize and
finalize uploads, create/get/cancel analysis runs, retrieve findings and sources,
save review events with an expected version, and generate/get report snapshots.
Add `/healthz` and readiness reporting.

Enforce authentication, ownership, file-signature/size validation and budget
limits server-side. Detect concurrent updates rather than overwriting them.
Document deletion cancels jobs and prevents workers recreating deleted data.

Exit: two users cannot access each other's records; private documents survive
process restarts and can be deleted.

### 3. First working evidence/review slice

Implement TXT/paste extraction, reference detection, one source connector,
durable jobs and evidence comparisons. Save immutable analysis versions;
reanalysis does not silently transfer old decisions onto changed evidence.

Add a typed frontend API layer and real document/run state. Change routes to
include document IDs, e.g. `/documents/:documentId/analysis`,
`/documents/:documentId/review/:findingId` and document-specific reports.
Consolidate the fixed evidence/mismatch/unverified screens into one data-driven
workspace using `WorkspaceLayout.tsx`.

Exit: a user can submit new text, inspect real sources, save a decision and
refresh without losing the document or review.

### 4. File formats and usable frontend states

Extend parsing to text PDFs and DOCX. Bound decompression, extraction time,
page/text volume and memory consumption. Handle empty, corrupt, encrypted and
image-only files explicitly; sanitize rendered document and source content.

Wire `UploadScreen`, `AnalyzingScreen`, `DetectionSummaryScreen`, `DocumentPane`
and `ClaimRail` to live data. Add document history, functional filters, selected
reference highlights, correction forms, notes, cancellation and retry controls.
Provide loading, empty, partial-success and failure states; support keyboard use
and a stacked small-screen workspace.

Exit: every supported input produces its own content/findings; unsupported or
failed input never routes to a successful sample report.

### 5. Reports and honest metrics

Derive all MVP metrics from persisted findings/events, with one shared definition
per metric. Snapshot reports against an analysis version and review-event cutoff.
Show original reference, evidence link/locator, machine result, human decision,
correction note and unresolved limitations.

Retain print-to-PDF initially, correctly labelled "Print / save PDF"; add a
downloadable structured report. Do not imply the original DOCX was modified.
Hide fake senior queues, reviewer identities and team-sharing controls unless
collaboration is explicitly added to scope.

Exit: workspace and report agree; prior report snapshots do not silently change
after later review events.

### 6. Public-beta protection and deployment

Add user/IP rate limits, upload/job/concurrency quotas, provider timeouts,
retry limits and spend controls. Restrict outbound retrieval to approved
connectors; block private-network/metadata targets and unsafe redirects.
Treat uploaded documents and fetched source text as untrusted data, not model
instructions. Never let document text initiate arbitrary tool calls.

Define consent, external processing disclosures, retention and deletion before
enabling uploads. Default demo proposal: automatic removal after seven days,
plus immediate user-triggered deletion of files, findings and reports.
Document actual backup/provider retention exceptions; avoid raw document text
in application logs. No public buckets or publicly shareable report URLs.

Add Render free API/in-service processor configuration, Supabase migration/storage/RLS
instructions, Vercel SPA deep-link routing and an environment-variable guide.
Deploy to user-owned accounts only after approval, with local development kept
separate from the shared tester data, restricted CORS and source/model keys held
server-side. Use the two tester accounts rather than unrestricted public signup.
For scheduled deletion, use an available database scheduler to enqueue expiration
work and run cleanup on wake; reject access to expired data immediately. Clearly
disclose that physical cleanup may be delayed while free compute is asleep.

Exit: the public URL supports upload -> real evidence -> review -> persistent
report, and job recovery, isolation, limits and deletion behave as documented.

## Validation and launch criteria

- Extend the existing frontend build and lint commands. Add backend unit/API
  tests and a small end-to-end suite as part of implementation; no tools or
  dependencies are installed during planning.
- Cover extraction locations, citation ambiguity, quote normalization without
  hiding changed numbers/negation, no-reference documents, malformed files,
  source timeouts, stale decisions, job restarts and deletion during processing.
- Evaluate detection precision/recall and source-resolution accuracy separately
  on human-labelled public/synthetic fixtures; report sample size and misses.
  Agree numeric launch thresholds after choosing the source corpus, rather than
  claiming accuracy from mock data.
- Exercise two isolated users and verify refresh/deep-link behavior.
- Measure latency and cost on a representative 10-page document; set a public
  latency expectation from measured performance, not the current fake 42 seconds.
- Keep mock examples explicitly labelled as samples and separate from real uploads.
- No deployment, provider purchase, source scraping or external submission of
  local documents is part of this planning task.

## Deferred work

OCR, Hindi/regional languages, jurisdiction expansion, comprehensive
statute-version/treatment-history checks, senior-review roles, shared workspaces,
public share links, billing, annotated original-document exports and semantic
claim verification beyond the scoped legal references.

## Remaining prerequisites

- Implementation approved; hosted deployment still needs user-owned accounts
  and configuration.
- User-owned Render and Supabase accounts plus existing Vercel project access
  for deployment. No account access is needed to begin local implementation.
- Indian Kanoon API signup/trial access, subject to its terms, for the live
  retrieval milestone. Without this, free hosting is still feasible but broad
  automatic source lookup is not yet established.
- No confidential/client or company data is permitted in this beta. Anonymization
  must include document metadata and embedded content, not just visible names.

## Implementation handoff

The repository now contains the persistent FastAPI backend, live frontend
workflow, schema/private-storage setup, Render Free Blueprint and deployment
guide. Local uploads, deterministic reference detection, saved review decisions,
optimistic concurrency, report snapshots and quotation-word comparisons are
implemented. Older analyses cannot accept new review decisions after reanalysis.

The local app can run without cloud credentials. In that mode, case-source
lookup is explicitly unavailable, authoritative statute checks are unsupported,
and unattributed quotations are unchecked. No source evidence is fabricated.
Indian Kanoon integration is implemented against its documented API and covered
with synthetic mocked responses, but no live provider-account request or hosted
deployment has been performed. See `README.md` and `DEPLOYMENT.md`.

## Hosting/source references

- Render background workers: https://render.com/docs/background-workers
- Render free-service limitations: https://render.com/docs/free
- Supabase storage access controls:
  https://supabase.com/docs/guides/storage/security/access-control
- Supabase pricing: https://supabase.com/pricing
- Vercel function limits: https://vercel.com/docs/functions/limitations
- Indian Kanoon API: https://api.indiankanoon.org/
- Indian Kanoon pricing: https://api.indiankanoon.org/pricing/
- Indian Kanoon API terms: https://api.indiankanoon.org/terms/
