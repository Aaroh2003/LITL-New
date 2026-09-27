# Indian Kanoon integration and evidence-report MVP plan

Date: 2026-09-25
Status: Proposed implementation plan; no credentials configured or credits spent.

Implementation milestone (2026-09-25): backend `.env` key placeholder and explicit
Uvicorn dotenv loading, fail-closed monetary configuration, durable conservative
account/day/owner/run reservations, and source-usage reporting are implemented.
No credentials have been entered or live requests made by this work. AI summaries,
evidence deduplication/resume, and revised identity/metric rules remain planned.
Accounting currently retains every request reservation without automatic
settlement/refund; reports explicitly label amounts unreconciled. See the backend
README for activation and reconciliation boundaries.

Reapplication (2026-09-26): restored the non-AI milestone against the replaced
workspace, preserving the updated upload UX. Local `.env` and dependencies had
been removed; the key placeholder is blank and must be filled again. Account
budgets default to zero. AI summaries are explicitly deferred at the user's
request; the AI sections below describe future scope, not enabled functionality.

Report milestone (2026-09-26): context-sensitive statutory messages, schema-2
count-based reports, versioned coverage/match/review/provenance formulas, distinct
reference-label coverage, pre-limit detection scope for new runs, and explicit
N/A values in exported reports are implemented. Existing snapshots remain
unchanged. Candidate comparisons are bounded, not proof of invalidity; quotation
attribution remains provisional. AI summaries remain deferred.

Subsequent approved implementation (2026-09-26): Gemini summary jobs and
schema-3 report inclusion are now implemented, together with clickable case and
legislation references. See `GEMINI_SUMMARY_LINKS_PLAN.md` and backend setup for
the current scope, separate consent and budgets. Earlier deferral notes describe
past milestones. Live Gemini activation remains off until explicitly configured.

## 1. Outcome and scope

Activate the existing Indian Kanoon (IK) integration, protect the shared prepaid
balance, and produce a reproducible evidence report with an optional AI-written
legal research summary. The summary covers retrieved authorities associated with
the uploaded draft, not exhaustive independent legal research.

User-confirmed planning inputs:

- Actual credit balance and expiry are unknown. INR 500 is an illustration only.
- Include citation/quotation evidence, human decisions, JSON, print-to-PDF, and
  an AI-written summary.

MVP exclusions: predictions of litigation outcomes, a legal-correctness score,
automatic good-law certification, exhaustive precedent search, statute-version
verification, OCR, automatic changes to the uploaded document, and public sharing.
Keep the existing public/synthetic/anonymized-beta restriction. An external AI
provider must not receive confidential client information.

## 2. What already exists

This is an extension of working code paths, not a greenfield API integration.
The observations below are from source inspection, not a live provider test.

| Surface | Existing implementation | Work needed |
|---|---|---|
| Backend configuration | `LITL-Backend/app/config.py`: token and terms gate | Backend secret setup, explicit spending configuration |
| IK client | `app/sources.py`: authenticated POST search and full-document retrieval | Typed failures, deduplication, conservative identity handling |
| Processing | `app/worker.py`: durable runs, leases, up to 50 external requests across recovery | Account-wide monetary reservations and resumable evidence |
| Evidence | Source URL, timestamp, passage, locator, normalized-text hash | Stable source IDs, exact evidence spans, versioned provenance |
| Metrics | `app/metrics.py`: counts, percentages, zero denominator as null | Separate eligibility, attempts, successful comparisons, and outcomes |
| Reports | `app/service.py`, `app/main.py`, `ReportRow` | Versioned report contract, cost/review cutoff, AI supplement |
| Frontend reports | `ReportsScreen.tsx`, `VerificationReportScreen.tsx` | Extend existing JSON and browser print/PDF, not a second renderer |
| Attribution | `SourceLinks.tsx`: provider logo above evidence | Preserve attribution in summary and printed output |
| Tests | Backend mocked-provider tests and frontend/workflow tests | Cost invariants, summary grounding, report parity |

Important current limitations:

- The 50-call limit is per analysis, not a shared-account credit limit. Different
  users/runs can collectively exhaust the same token's balance.
- Repeated references can trigger repeated search/document requests.
- `len(docs) <= 3` is not proof that the whole search result set contains at most
  three results. Inspect provider result-count/pagination semantics before using
  completeness as an identity gate.
- Quote attribution currently selects the nearest preceding case within 500
  characters. Proximity alone is not reliable attribution.
- `identity_checked` can be true when one candidate is checkable but the final
  identity is ambiguous. It is not a clean denominator for identity accuracy.
- Only short passages are persisted; full case text is held in memory. The first
  few lines of a judgment are not sufficient input for a legal research summary.
- Report snapshots already exist and should remain immutable under later edits.

## 3. Provider contract and activation

Official pages inspected on the plan date:

- Documentation: https://api.indiankanoon.org/documentation/
- Pricing: https://api.indiankanoon.org/pricing/
- Terms: https://api.indiankanoon.org/terms/

Published prices, in INR per request:

| Operation | Endpoint | Price |
|---|---|---:|
| Search | `/search/?formInput=...&pagenum=0` | 0.50 |
| Full document | `/doc/{id}/` | 0.20 |
| Document metadata | `/docmeta/{id}/` | 0.02 |
| Fragment | `/docfragment/{id}/?formInput=...` | 0.05 |
| Original court copy | `/origdoc/{id}/` | 0.50 |

The pricing page advertises INR 500 signup credit. A separately approved
non-commercial allowance is not assumed for this app. Rates can change; record a
price-schedule version and reconfirm before activation.

Activation sequence:

1. In the user's IK account, verify usable balance, expiry, account authorization,
   and any applicable restrictions. Credits remain in that provider account;
   the app accesses them through the account's API token.
2. Confirm caching, evidence retention, and use with the chosen AI provider are
   permitted. Attribution requirements are explicit; blanket caching rights
   should not be inferred. Preserve the required unaltered provider graphic.
3. Configure `INDIAN_KANOON_API_TOKEN` in the backend environment/secret manager.
   Set `INDIAN_KANOON_TERMS_ACCEPTED=true` only after the terms review.
   Never use a `VITE_` variable for this token, place it in source control,
   paste it into chat, or include it in reports/logs.
4. Configure the monetary limits described below before enabling multi-user use.
   Local environment injection is sufficient; do not assume `.env` auto-loading
   exists in the backend.
5. Restart the backend; configuration readiness means "configured", not "balance
   or account access verified." Health/readiness checks must not spend credits.
6. Run one explicitly authorized public-case smoke check: one search plus up to
   three document fetches, estimated maximum INR 1.10 at these rates. Reconcile
   the actual debit in the account. No automatic retry.

Use HTTPS and `Authorization: Token <server-secret>` with JSON responses.
The documentation explicitly supports token authentication even though parts of
the terms describe public/private-key authentication.

## 4. Mathematically bounded spending

### 4.1 Cost model

Let S, D, M, F, O be counts of potentially billable search, document, metadata,
fragment, and original-copy attempts, including retries:

    C_IK = 0.50 S + 0.20 D + 0.02 M + 0.05 F + 0.50 O

Count uncertain requests conservatively: a timeout does not prove the provider
did not process or bill a request. Use integer paise in storage, not floating
point currency. Record estimated debits separately from reconciled charges.

For the MVP, use only search and full documents. Metadata is an optional later
optimization, not an extra compulsory call. A fragment cannot establish absence
of a quotation from an entire judgment.

Let U be distinct reference queries selected for lookup and k <= 3 be candidate
documents examined per query. With no cache and no retries:

    S <= U
    D <= kU
    requests <= (1 + k)U
    C_IK <= U(0.50 + 0.20k)

Proposed pilot limits: at most 10 distinct reference queries, 3 candidate fetches
per query, 40 requests, and INR 11 per analysis. Every limit applies across
recovery, not independently to each worker attempt. Retain the existing
50-request ceiling as a secondary absolute safety limit.

Documents may still contain up to 50 processed findings. Deduplicated references
reuse evidence; remaining unselected references are visibly "not checked:
budget/selection limit", not omitted or declared invalid. Selection is stable by
first occurrence; disclose the resulting sampling bias. Any future prioritizing
heuristic must be versioned and must not be called a probability of relevance.

### 4.2 Illustrative credit runway

Let B be verified remaining account balance and rho the reserve fraction:

    B_work = floor((1 - rho) B)     [rounded down to paise]
    n_full = floor(B_work / C_run_max)

For B = INR 500, rho = 0.20, and C_run_max = INR 11:

    B_work = INR 400
    n_full = floor(400 / 11) = 36 worst-case pilot analyses

These are 36 budget allocations, not guaranteed successful reports. Smoke tests,
other consumers of the token, failed calls, and evaluation traffic reduce the
remaining allocation. A user may generate additional snapshots of an existing
analysis without further IK calls.

If only one candidate is fetched per selected reference, ten references cost
at most INR 7 and INR 400 covers 57 such allocations. This is a conditional
scenario, not grounds to fetch less evidence and weaken identity checks.

For forecasting only:

    E[C] = 0.50 U(1-h_s) + 0.20 V(1-h_d) + E[retry_cost]

Here V is the planned number of document fetch opportunities and h_s/h_d are
measured cache-hit fractions. Never use expected cost instead of the hard
reservation limit.

### 4.3 Atomic reservation invariant

Maintain an account-level ledger across all owners, workers, and restarts:

    settled_or_conservatively_charged + outstanding_reservations <= B_work

Before each external request, atomically check and reserve its price against
account, UTC-day, owner-day, and run budgets. Commit the reservation before
network I/O; do not hold a database transaction open during the request.
Transition the reservation exactly once to charged, uncertain, or released.

- Release only when it is certain the request was not sent, or the provider
  confirms it was not billed.
- Keep a lost/expired in-flight request charged or reserved until reconciliation.
- Persist a request-attempt ID, endpoint class, price version, run ID, timestamps,
  response category, and reservation state. Never persist tokens or raw private
  query text in operational logs.
- Provider requests are not assumed idempotent. Local idempotency prevents
  duplicate scheduling, not duplicate billing after an uncertain network result.
- No automatic retries for the first MVP. Explicit retries use new reservations
  within the original run limits. Never reset counters on worker recovery.
- Reconcile balance manually against the provider dashboard until an official
  balance API is established; no such endpoint was verified during this plan.
- The local invariant bounds app-authorized spending at configured prices, not
  unrelated usage of the same provider account. Use a dedicated token where
  supported and reconcile outside usage; pause on unexplained differences.

Suggested configurable pilot caps: INR 11/run, INR 22/owner/day,
INR 44/account/day, and INR 400 lifetime allocation for the illustrative account.
These are product defaults, not provider rate limits. Account limits still apply
when an owner creates multiple accounts.

### 4.4 Separate AI budget

IK credits do not pay for a separate language model. Select an approved model,
hosting arrangement, and privacy policy before enabling generation.

For model prices p_in and p_out per million tokens:

    C_AI = (T_in p_in + T_out p_out) / 1,000,000
    C_total = C_IK + FX * C_AI + allocated_hosting_cost

Use a conservative FX conversion if prices use different currencies. Provider
billing can include reasoning or other tokens: include those components and
reserve the provider-specific upper bound, not just visible output tokens.

Initial proposal: <= 12,000 total input tokens and <= 1,500 generated output
tokens, one generation per evidence snapshot, no hidden retries. Validate these
limits against the selected model before enabling it; record truncation and
omitted sources. Do not claim an INR price until the model is selected.

When AI is unavailable, over budget, or fails validation, the evidence report
still works. Display "AI summary unavailable" with a reason; do not substitute
template text labelled as AI-generated.

## 5. Evidence pipeline and decision rules

    Upload -> extract -> detect -> deduplicate -> reserve spend
           -> search -> fetch full candidates -> identity decisions
           -> quotation comparison -> evidence snapshot
           -> optional AI summary -> human review -> report snapshot

Keep backend authority over credentials, decisions, metrics, and report content.

### Identity

Separate retrieval from confirmation. Search ranking, snippets, similar names,
and a reference inside another judgment's reasoning do not verify case identity.

For citation i and candidate j, define:

    E_ij = exact structured reporter/neutral identifier match in identity metadata
    N_ij = normalized party-name match
    X_ij = contradiction in any supplied identity field

A candidate can be auto-resolved only with E_ij = 1 and X_ij = 0, with name
agreement required when the draft supplies a name, and no unresolved competing
identity evidence in the examined candidate set. Parse identifiers as structured
tuples rather than loose substrings: page 12 must not match page 123.

Missing required metadata means unknown. Name-only matches remain candidates for
human review. Record search scope and truncation; this gate establishes a
source-identity match from supplied evidence, not uniqueness across all law.
Multiple competing candidates, incomplete required fetches, and contradictions
must not become automatic matches.

Keep machine outcome separate from human decision. "Not found" means this bounded
search returned no candidates, not that a citation is fabricated. API errors,
credit depletion, and network failures mean unavailable, never not found.

### Quotation

Record attribution separately: explicit attribution, reviewer-confirmed
attribution, or proximity-only candidate. Do not elevate proximity-only
attribution to a verified quotation.

Let n(q) be a versioned normalization of whitespace and equivalent quotation
marks. Preserve digits, negation, words, case, and substantive punctuation.
Audit the current NFKC normalization: compatibility transformations may change
legally meaningful symbols, so limit transformations or flag them for review.

    wording_match(q, d) = 1 if n(q) is a contiguous substring of n(d), else 0

Only compare against a complete retrieved document with resolved attribution.
Truncated text, missing text, or ambiguous attribution means not checked.
Mismatch means wording not located under this normalization, not fabrication.
Ellipses, editorial brackets, translations, and OCR differences require review.

Persist the actual matched span and surrounding context. For mismatches, label
any displayed contextual passage as a candidate, not a match. Distinguish
provider paragraph anchors from local extracted-paragraph numbers.

### Deduplication and retention

Deduplicate identical normalized queries within a run without discarding
identity-bearing year, court, volume, or page fields; share fetched document IDs
and snapshot hashes across findings. Persist progress for safe recovery.

Start with private run-scoped evidence storage and existing seven-day document
retention, subject to provider permission. Defer shared cross-user caches.
Delete evidence and AI artifacts with the parent document. Do not retain
document content in a billing ledger that survives deletion; retain only
minimal accounting aggregates/identifiers permitted by the retention policy.

## 6. AI-written legal research summary

Treat generation as an optional evidence-bound feature, never as the verifier.
No autonomous browsing, new case discovery, or model-selected extra IK calls.

Build an evidence packet from the frozen analysis:

- Only identity-resolved authorities for affirmative case-law summaries.
- Issue-relevant passages plus context, source ID, title, URL, retrieval time,
  locator, and content hash.
- Explicit limitations: candidate-search cap, unsupported statutes, omitted
  passages, ambiguous attribution, and unverified current treatment.
- Public/synthetic issue description; do not send the entire uploaded draft.

The current first-three-lines passage helper is insufficient. Select passages
from the already fetched document using deterministic issue-term matching and
nearby context, with a bounded text budget. This selection ranks text, not legal
authority. Record omitted/truncated material and abstain when no useful passage
supports a requested section. Avoid additional paid retrieval in the MVP.

Require structured output:

    schema_version
    scope_and_limitations
    issues[]:
      issue_text
      observations[]:
        text
        source_ids[]
        evidence_span_ids[]
    unresolved_questions[]
    suggested_human_checks[]

Validate schema, ownership of every source/span ID, source eligibility, and
verbatim quotations against saved spans. Reject invented citations, dates,
numerical claims without evidence, and unsupported definitive good-law or
litigation-outcome claims. Treat source text as untrusted data, not instructions.

For substantive AI statements:

    traceability = statements_with_valid_evidence_links / substantive_statements

Require traceability = 1 for a structurally accepted draft. If there are no
substantive statements, report N/A and "insufficient evidence", not 100%.
Valid links do NOT prove that the cited text entails the statement. Human review
is mandatory before the AI section can be labelled reviewed.

Track two separate states: generation (`queued`, `processing`, `completed`,
`failed`, `unavailable`) and human review (`unreviewed`, `reviewed`, `rejected`).
Default label: "AI-generated research draft - not reviewed". Save reviewer,
timestamp, and exact generation version on acceptance; editing creates a new
version and resets review. A reviewed summary is not legal certification.

## 7. Report contract and defensible metrics

### Report contents

Reuse the existing immutable snapshot mechanism and endpoints:

    POST /v1/documents/{document_id}/reports
    GET  /v1/documents/{document_id}/reports
    GET  /v1/documents/{document_id}/reports/{report_id}

Add a versioned report payload containing:

- Report/document/run IDs, creation time, extracted-input hash, parser,
  normalization, identity-rule, metric, and report-schema versions.
- Per-finding review versions and event cutoff captured consistently.
- Scope: detected/processed/deferred counts, distinct reference counts,
  selection policy, searched candidate limits, unsupported reference types.
- Evidence and exact passages with locators, source hashes, retrieval times,
  machine results, saved human decisions, proposed corrections, unresolved items.
- Endpoint request counts, reserved/estimated/reconciled cost distinctions,
  configured budget, currency, and price-schedule version.
- Optional AI summary, model identifier, prompt-template version, token usage,
  evidence-packet hash, generation ID, human-review state, and limitations.
- Required attribution and clear statement that identity/wording checks do not
  establish legal applicability, binding authority, or current good law.

Snapshot AI content only if it belongs to the exact selected run and evidence
version. If generation is pending, explicitly save an evidence-only snapshot;
later completion must not mutate it. Create a new report to include the summary.
Download/reopen/reprint must not call IK or the AI provider.

Provide JSON and the existing browser "Print / save PDF" first. A server-generated
PDF is not required for this MVP. Make the text, warnings, attribution, and
unreviewed labels survive printing and narrow-screen rendering.

Hashes support reproducibility and change detection, not authenticity or legal
certification. Version the canonical serialization used for payload hashes.
Retain backward rendering of old snapshots; never recompute their metrics under
new definitions.

### Metric definitions

Use disjoint sets and explicit denominators:

- N: all processed findings; also show pre-cap detected count and deferred count.
- C: processed case-citation occurrences; U: distinct case references in C.
- A subset of C: identities with sufficient evidence for a conclusive comparison.
- R subset of A: resolved matching identities.
- Q: detected/processed quotations.
- K subset of Q: quotations actually compared against complete, attributed text.
- W subset of K: normalized wording matches.
- H subset of N: findings with any saved human decision.
- Z subset of H: confirmed, corrected, or rejected (not unresolved).
- P subset of (A union K): items with complete required provenance.

| Metric | Formula | What it does not mean |
|---|---|---|
| Identity coverage | `|A| / |C|` | Not all citations in the document were necessarily detected |
| Identity match among assessed | `|R| / |A|` | Not model accuracy; assessment is selectively possible |
| Located-case coverage | `|R| / |C|` | Not proposition support |
| Quote comparison coverage | `|K| / |Q|` | Not attribution accuracy |
| Wording-match rate | `|W| / |K|` | Not contextual correctness |
| Review completion | `|H| / |N|` | An unresolved decision still counts as reviewed |
| Review disposition | `|Z| / |N|` | Rejection is not verification |
| Provenance completeness | `|P| / |A union K|` | Not source authority |

For every metric, return numerator, denominator, percentage, and definition
version; denominator zero produces null/N/A. Show unique-reference coverage
alongside occurrence coverage so one repeated case cannot inflate apparent
research breadth. Track lookup attempts separately from conclusive assessments.
Do not create a weighted "legal confidence" average.

Example: 10 case references, 6 conclusively assessed, 5 matched, 8 quotations,
4 compared, 3 wording matches:

    Identity coverage = 6/10 = 60%
    Identity match among assessed = 5/6 = 83.3%
    Located-case coverage = 5/10 = 50%
    Quote comparison coverage = 4/8 = 50%
    Wording-match rate = 3/4 = 75%

The honest result is those five statements, not "83% legally correct."
No sampling confidence interval is needed for exact counts within one report.

## 8. Quality evaluation and mathematical release gates

Build a human-labelled public/synthetic evaluation set, separate from examples
used to tune detection/normalization. Label extraction spans, identity, attribution,
quotation wording, and statement-to-source support independently. Split by case
and document family to prevent repeated authorities leaking across splits.

Measure detection precision/recall by reference type:

    precision = TP / (TP + FP)
    recall    = TP / (TP + FN)

Specify matching rules before testing: identity-bearing tokens and offsets must
be captured; report strict span matches separately from acceptable boundary
variations. Undetected references are false negatives in evaluation even though
they are invisible to per-report denominators.

For automatic identity resolution, measure precision over auto-resolved cases
and coverage over all labelled eligible cases. For summary support, use human
labels: evidence links alone cannot measure factual support.

For x correct independent decisions out of n, report a binomial confidence
interval (e.g. exact Clopper-Pearson). In the zero-error case, a one-sided 95%
lower bound for correctness is:

    L = 0.05^(1/n)

Thus 100/100 correct implies L approximately 97.05%, not proven 100% accuracy.
At least 299/299 correct independent cases are needed for L >= 99%.
This is a conditional statistical bound, not a guarantee on future legal work.
Correlated decisions from the same case require cluster-aware evaluation rather
than pretending each occurrence is independent.

Proposed gates:

1. No unauthorized provider calls; spending invariant holds under concurrent
   workers, crashes, timeouts, cancellations, and restarts.
2. Zero false automatic confirmations on explicit adversarial fixtures:
   near-identical case names, differing years/pages, citations in reasoning,
   incomplete metadata, conflicting candidates, altered negation/numbers.
3. Detection precision/recall and resolver coverage reported by type with sample
   sizes; no launch claim of "99% accuracy" without the corresponding evidence.
4. Public MVP remains human-review-required. An unattended automation claim is
   deferred until an agreed statistical precision gate is met; a small successful
   smoke test cannot meet it.
5. Every accepted AI draft has structurally valid evidence links for every
   substantive statement. Pilot summaries receive human support review;
   unsupported statements must be removed/revised before marking reviewed.
6. Evidence-only reports remain available when IK is unconfigured, exhausted,
   or unavailable and when the AI provider fails. Warnings must survive export.

Do not spend the small live trial credit on all benchmark cases. Use permitted
recorded fixtures and mocked failures for development; reserve a separately
approved small live budget for contract checks. Synthetic tests establish
behavior on fixtures, not representative real-world precision.

## 9. Implementation sequence

Dependencies:

    account/contract -> schema + budgets -> retrieval/evidence -> metrics/report
                                           |
                                           +-> AI draft/review
    metrics/report + AI draft/review -> frontend -> end-to-end pilot

Each step is additive. A step is complete only when its acceptance conditions
are demonstrated, not merely when its files exist.

| Step | Files/surfaces | Deliverable and completion condition |
|---|---|---|
| 1. Contract and activation preparation | `DEPLOYMENT.md`, backend configuration | Verified balance/rates/terms, selected AI deployment or explicitly disabled AI; backend-only secrets; no metered health calls |
| 2. Schema and budget accounting | `app/models.py`, `app/db.py`, new `app/budget.py`, `app/config.py` | Account budget and request ledger; integer paise; atomic scoped limits; uncertain-charge recovery; owner isolation |
| 3. Retrieval and evidence | `app/sources.py`, `app/network.py`, `app/worker.py`, `app/extraction.py` | Deduplicated queries/documents, structured identity rules, attribution state, stable spans and progress, typed failure reasons |
| 4. Report v2 and metrics | `app/metrics.py`, `app/service.py`, `app/main.py` | Explicit denominators, versioned immutable snapshot, costs/cutoff/provenance, compatible old-report reads |
| 5. AI generation and review | new `app/summary.py`, `app/models.py`, `app/worker.py`, `app/main.py`, `app/service.py` | Durable generation job, separate budget, evidence-only prompt, validation, versioned review, no mutation of old reports |
| 6. Frontend wiring | `src/lib/api.ts`, `ReportsScreen.tsx`, `VerificationReportScreen.tsx`, `LiveData.tsx`, `SourceLinks.tsx`, related print CSS | Typed report v2, summary generation/review UI, partial/unavailable states, identical saved JSON and displayed data |
| 7. Release checks and deployment docs | `LITL-Backend/tests/test_backend.py`, frontend tests, `tests/browser_smoke.mjs`, component READMEs, `DEPLOYMENT.md` | Budget/concurrency/isolation/immutability scenarios, real print artifact, approved bounded live check and reconciliation |

Suggested new persistence entities:

- `ProviderBudget`: provider/account key, configured allocation, reserved/charged
  paise, price version and reconciliation timestamp.
- `ProviderRequest`: durable request-attempt and reservation state; indexed by
  account/owner/run/day for enforcement and inspection.
- `EvidenceDocument`: private run-linked document ID, text/spans, normalization
  version, hash, retrieval status/time; indexed for run-scoped deduplication.
- `SummaryGeneration`: immutable input snapshot plus durable job status/lease,
  model/prompt metadata, output, failure reason and usage.
- `SummaryReviewEvent`: reviewer, generation ID, timestamp, expected version and
  decision; no possibility of reviewing a different generation accidentally.

Use the existing SQLAlchemy and database transaction patterns. The backend uses
`create_all`, which does not alter existing tables: add an explicit versioned
upgrade/backfill for any changes to existing tables and test fresh and existing
SQLite/Postgres databases. New hosted tables must receive the same RLS and grant
hardening as existing private tables, atomically during creation.

Proposed owner-authenticated summary API:

    POST /v1/documents/{document_id}/analyses/{run_id}/summaries
    GET  /v1/documents/{document_id}/analyses/{run_id}/summaries/{summary_id}
    PUT  /v1/documents/{document_id}/analyses/{run_id}/summaries/{summary_id}/review

POST accepts a client idempotency key scoped to owner/run/evidence/prompt version.
Review requires the expected version. Pin immutable input before network work;
check deletion/cancellation and job lease before publishing. Changes to a newer
analysis or summary must never silently update old reports.

Validation commands for implementation:

```sh
cd LITL-Backend
.venv/bin/python -m unittest discover -v

cd ../LITL-Frontend
npm test
npm run lint
npm run build
```

With isolated local servers running and live source lookup disabled:

```sh
python3 -m unittest discover -s tests -v
node tests/browser_smoke.mjs
```

Add dedicated mocked-provider end-to-end scenarios for the configured-source
path; existing local workflow tests deliberately reject a live-configured source.
Exercise account-budget races on Postgres as well as serialized local SQLite.
Verify printed output contains the report ID, complete findings, warnings,
unreviewed AI marker, and attribution. Verify no provider calls on report reads.

## 10. Rollout, estimates, and unresolved inputs

Suggested sequence: internal synthetic documents -> invited users with public
documents -> measured pilot. Keep independent switches for IK lookup and AI
generation. Turning either off preserves existing snapshots and evidence-only
report generation; no destructive rollback of stored reviews.

Planning estimate for one engineer familiar with this codebase: 7-12 working
days including integration and report checks, excluding provider approval,
terms clarification, and the time for legal-domain evaluation. This is an
estimate, not a deadline commitment.

Before enabling live usage, resolve:

- Real IK balance, expiry, permissions, and any other consumers of that balance.
- Approved AI provider/model, token pricing, separate spending ceiling, retention
  and data-use policy. Until resolved, generation remains explicitly unavailable.
- Named human reviewer and representative public-document evaluation set.

MVP acceptance: a user can upload a permitted document, see bounded evidence
lookup and honest unknowns, optionally generate/review an evidence-linked AI
draft, and save/reopen/export a report whose metrics, citations, costs, and
limitations are traceable to a frozen analysis. No component claims that source
retrieval or fluent AI prose proves legal correctness.
