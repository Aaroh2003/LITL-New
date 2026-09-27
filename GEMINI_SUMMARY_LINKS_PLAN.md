# Gemini summaries and Indian Kanoon reference links

Date: 2026-09-26
Status: Approved by the user and implemented. Example configuration ships
disabled; activation is operator-controlled. Initial validation used mocks.
Subsequent live diagnostics identified retirement of Gemini 2.5 for new users
and high-demand errors on Gemini 3.8. The user selected Gemini 3.5 Flash-Lite
as the new default, with corresponding rates and provider-default thinking.
Flash-Lite integration has been validated with mocks; live access still needs
confirmation for the user's project.

## 1. User-visible outcome

For each uploaded document:

1. Show an AI-written summary of the uploaded text.
2. Make detected citations and statutory references clickable in the reading view.
3. Open the corresponding Indian Kanoon document when its identity is established.
4. Where the correct target cannot be established, show a short, accurate message
   and any explicitly labelled candidate links.
5. Include the saved AI summary, reference links and existing mathematical
   coverage/review calculations in the final JSON/PDF report.

Gemini writes the summary. Indian Kanoon supplies reference targets. Gemini must
not invent links, choose a source purely from memory, or change verification
metrics. A link to a judgment does not prove the draft's argument or current law.

OCR, chat, automatic document rewriting, exhaustive legal research, litigation
predictions and good-law certification are outside this change.

## 2. Existing code to extend

The app already has bounded text extraction, detected reference offsets,
Indian Kanoon search/document retrieval, prepaid request reservations, human
review, schema-2 reports and immutable snapshots.

The remaining gaps are:

- No Gemini client, summary job or summary UI.
- `sources.py` resolves cases, but statutory references never receive lookups.
- Repeated references can cause repeated paid requests.
- `DocumentReadingText.tsx` highlights only the selected reference; it does not
  render source hyperlinks across all detected spans.
- Existing matching may leave a useful result ambiguous. Better candidate
  handling must not be replaced with "always choose the first search hit".

Preserve the updated upload UI, signup changes, existing review decisions,
spending counters and all previously saved report snapshots.

## 3. Proposed experience

### Upload and summary

Add an unchecked option:

    Generate an AI summary using Gemini
    Sends extracted document text and selected source excerpts to Google.

After the user opts in, the existing analysis runs first, followed by a durable
summary job. The app shows source-lookup progress and summary-generation progress
separately. Failure of either provider does not discard the other results.

For existing documents, add a "Generate AI summary" button with the same consent.
Do not automatically send previously uploaded documents to Google.

The summary has:

- A short overview of what the draft says.
- Key facts and requested relief, when present.
- Issues raised by the draft.
- References and available source-linked observations.
- Missing information and questions for human review.

Label the output "AI-generated draft summary - not reviewed". Statements about
the uploaded document are not independently verified facts. When no Indian
Kanoon source is resolved, generate a draft-only summary and explicitly say so.

Allow a reviewer to mark an exact summary version reviewed or rejected. A
regenerated summary starts unreviewed. Review never implies legal certification.

### Reference links

| Reference state | Inline action / message |
| --- | --- |
| One established matching case | Click citation to open its Indian Kanoon judgment |
| Established Act and section target | Click section to open that provision |
| Only the parent Act is established | "Open Act - section-specific link unavailable" |
| Several plausible results | "Multiple possible matches - review candidates" |
| Successful lookup with no matching source | "No matching source found" |
| Section number without an identifiable Act | "Act name needed to find this section" |
| Provider/key/budget failure | "Source lookup unavailable" with expandable details |
| Not processed because of limits | "Not checked - analysis limit reached" where a deferred span is retained; otherwise disclose deferred counts |

Every processed reference is interactive: a resolved reference opens an external
source; an unresolved one opens its internal evidence panel. Do not manufacture
an external hyperlink merely to make every reference look resolved.

Candidate URLs are labelled "Possible match", never "Verified source". The MVP
will show up to three candidate documents when relevant. It will not silently
pick search rank 1 or rely on a model confidence percentage.

## 4. Indian Kanoon linking rules

### Cases

Reuse the server-only API client:

    POST /search/?formInput=<citation>&pagenum=0
    POST /doc/<returned_numeric_id>/

Normalize queries conservatively, retaining years, reporter volumes, pages,
court qualifiers and party names. Reuse results for identical normalized
references within the same run, subject to permitted retention.

Prefer structured reporter/neutral-citation identity evidence and compatible
title metadata. A mention of the draft's citation in another judgment's
reasoning is not identity evidence. Conflicting fields prevent automatic
selection. Identical party names alone do not establish a unique case.

Separate the candidate list from the established primary source. Record examined
candidate count and search truncation. Correct the existing page-length-based
uniqueness assumption; search pagination/counts must be interpreted from actual
provider responses, not inferred from `len(docs)`.

Only build direct URLs using numeric IDs actually returned by the API:

    https://indiankanoon.org/doc/<id>/

Do not use model-generated URLs or guess provider paragraph/section anchors.

### Statutory sections and articles

Use `statutory_details` as the starting point. For a reference with an explicitly
identified Act, search using the section/article plus Act name and year when
present. Distinguish legislation from judgments merely discussing that section.

Auto-link a provision only when retrieved document metadata/text identifies the
same Act and provision. If only the parent legislation is established, label it
as an Act link, not a section-specific target. Neither link verifies amendments,
commencement, transitional rules or applicability.

For "Section 335" without an Act, do not assume IPC, CrPC, BNSS or another law.
Show "Act name needed". An Act named elsewhere may be offered as context for
review, but proximity or Gemini inference alone cannot establish the target.
Interactive Act correction and a new paid lookup are follow-up scope, not an
implicit extra step in this MVP.

### Budget and caching

Keep the existing account/day/owner/run monetary limits. Case and statute lookups
share the same IK budget. Reuse fetched document IDs and successful resolutions
within the run so repeated references do not repeatedly spend credits.

Initial proposed lookup cap: ten distinct case/statute queries, up to three
document fetches each, within the existing request and monetary ceilings. Leave
unprocessed references visibly unchecked. The first version uses no separate
metadata/fragment/original-copy calls.

Using the currently configured price schedule:

    C_IK = 0.50 * searches + 0.20 * document_fetches
    C_IK <= 10 * (0.50 + 3 * 0.20) = INR 11 per analysis

That bound assumes at most the stated attempts. Recovery and retries consume
the same durable run allocation; they do not reset it. Unknown request outcomes
retain conservative reservations. Confirm provider prices before enabling use.

Reopening summaries, source panels and reports makes no paid retrieval calls.
Clicking an external link opens the website; it does not invoke the paid API.

## 5. Gemini summary implementation

### Configuration

Add backend-only settings, without replacing existing keys:

    GEMINI_API_KEY=
    GEMINI_ENABLED=false
    GEMINI_MODEL=gemini-3.5-flash-lite

The model above is a proposed documented Flash model, not a promise of account
availability. Confirm its availability and current pricing during activation.
Do not silently switch models on failures.

Never expose the key through `/v1/config`, frontend `VITE_` variables, logs,
reports or query-string URLs. Use the official HTTPS API and API-key header.

### Evidence and input

Use extracted text, not raw uploaded file bytes. Pin a packet to one completed
analysis containing:

- Document paragraphs with stable IDs and page/character locations.
- Detected reference IDs and their actual retrieval states.
- Established source IDs, relevant retrieved excerpts and provenance.
- Explicit missing-source and scope limitations.

A short stored source passage is not an entire judgment. Observations based on
an excerpt must be labelled as such; do not synthesize the whole case's holding
from its title or first lines. Source excerpts and draft text are untrusted input,
not executable instructions.

Request structured JSON with sections for overview, key points, issues,
source-backed observations, review questions and limitations. Each substantive
statement must cite allowed draft-paragraph IDs or source-evidence IDs.
Gemini returns IDs, not external hyperlinks. The backend maps valid source IDs
to stored URLs.

Validate schema, referenced IDs, source eligibility and quoted text before
publishing. Invalid IDs, invented URLs, incomplete output, provider safety blocks
or malformed JSON produce an explicit failed summary; never a fake success.
Structural validation cannot guarantee semantic faithfulness. Human review
remains necessary, and the UI must say so.

### Bounded processing

Proposed defaults for approval:

- One summary automatically queued per opted-in analysis.
- At most one explicit regeneration: two generation attempts per run.
- At most five attempts per owner per UTC day and twenty across the app per day.
- At most 64,000 input tokens and 2,500 visible output tokens per generation.
- A bounded worker execution deadline; no automatic generation retries.

Use the selected model's documented token-counting mechanism and account for the
complete prompt/schema/context. Do not assume four characters per token as a
hard bound. If the input exceeds the limit, disclose the limitation instead of
silently summarizing only the beginning. Multi-pass chunk summarization is
deferred unless separately approved.

Gemini billing is separate from IK credits:

    C_Gemini = (T_in * p_in + T_out * p_out + other_billed_token_costs) / 1,000,000

Record actual available token usage, model/version and generation timestamps.
Configure a separate cost ceiling using current model prices before enabling
paid usage; account for any model-specific thinking tokens in its upper bound.
If reliable rate/billing metadata is absent, show token usage and "cost unknown",
not an invented INR amount. Request quotas are not provider billing guarantees.

### Durable jobs and retention

Add a run-linked summary job/result table and review events. Persist consent,
input/evidence hash, prompt/model version, state, lease, error category, output
and usage. Existing `create_all` does not migrate columns: prefer additive tables,
and add an explicit upgrade if an existing table must change.

Use the existing durable worker pattern, with Gemini timeouts separate from the
shorter lookup timeouts. No model request inside a database transaction. Check
job ownership, run identity, cancellation and document deletion before publishing.
Do not replay an uncertain provider request automatically after a crash.

Summaries and packet content expire/delete with the parent document. Minimal
quota aggregates survive deletion so deleting/reuploading cannot bypass limits.
No cross-user cache or public sharing is added.

## 6. Frontend and final report

Add an AI summary panel to the analysis page and report-generation page, with
queued/generating/completed/failed states and explicit retry controls.

Extend the reading renderer to wrap all non-overlapping detected spans:

- Preserve Python Unicode-code-point offsets and reflowed text.
- Preserve selected-reference highlighting and keyboard accessibility.
- Do not create nested anchors for overlapping detections.
- Use safe HTTPS destinations, a new tab, and `noopener noreferrer`.
- For unresolved references, navigate to the reference's internal evidence panel.
- In saved reports, use frozen URLs and local finding anchors rather than
  changing live review state.

A new report schema includes:

- The AI summary version, review state, model and generation timestamp.
- Summary input/evidence hash and any coverage limitations.
- A reference index: original citation/section, source title, link, match state.
- Existing formulas, decisions, cost reservations and disclaimers.
- Required Indian Kanoon attribution.

Report generation stays available if summary generation fails. If it is still
pending, clearly offer an evidence-only report; do not silently imply the AI
summary was included. Later summary completion never changes an old snapshot.
Generate a new report to include it. JSON and print/PDF use the same saved data.

## 7. Implementation order

| Step | Main files | Completion condition |
| --- | --- | --- |
| 1. Contracts/configuration | `app/config.py`, `.env.example`, `app/models.py`, `app/db.py`, API types | Protected Gemini configuration and additive private summary/link data; old snapshots still readable |
| 2. Reference resolution | `app/extraction.py`, `app/sources.py`, `app/budget.py`, `app/worker.py` | Distinct-query reuse, case/statute link rules, bounded candidate handling, short explicit failure states |
| 3. Gemini jobs | New `app/summary.py`, `app/worker.py`, `app/service.py`, `app/main.py` | Consent-bound durable generation, validated JSON, separate quotas, failure/recovery/deletion behavior |
| 4. Interactive references | `DocumentReadingText.tsx`, `LiveDocumentPane.tsx`, `SourceLinks.tsx`, reference screens | Clickable matched references, candidate/missing-context panels, unchanged text/offsets and accessibility |
| 5. Summary/report UI | Upload/analysis/reports screens, `VerificationReportScreen.tsx`, API types | Automatic opt-in flow, existing-document action, saved summary review state, hyperlinks in JSON/PDF |
| 6. Validation and activation | Backend/frontend tests, browser smoke, component READMEs, `DEPLOYMENT.md` | Mocked regression gates plus explicitly authorized live smoke calls after keys are configured |

Dependencies: contracts -> resolver and Gemini jobs -> UI -> final report -> activation.

Proposed summary endpoints:

    POST /v1/documents/{id}/analyses/{run_id}/summaries
    GET  /v1/documents/{id}/analyses/{run_id}/summaries/{summary_id}
    PUT  /v1/documents/{id}/analyses/{run_id}/summaries/{summary_id}/review

POST requires explicit consent and an idempotency key. Repeat requests reuse an
existing attempt rather than double-charge. Review requires an expected version.
Automatic upload consent must be persisted for local text/file and hosted
signed-upload flows, with the same behavior on recovery.

## 8. Acceptance criteria

1. An opted-in upload produces a real Gemini summary or an explicit failure;
   uploading without AI consent makes no Gemini request.
2. An existing document can request a summary with new consent.
3. A known case with sufficient matching evidence receives the correct returned
   IK document URL; a contradictory or ambiguous result is not auto-selected.
4. A named Act/section can receive a checked provision target or a clearly
   labelled parent-Act link. Bare sections show "Act name needed".
5. Empty results, failed lookups and exhausted budgets remain distinct.
6. Repeated references reuse a lookup within the run; all limits apply across
   recovery and concurrent users.
7. Every rendered external reference URL comes from validated IK retrieval data,
   not model memory. Unsupported references remain interactive via their panel.
8. Structured summary statements carry valid permitted evidence IDs; no claim
   that this alone proves factual correctness.
9. Unicode offsets, overlapping spans, long references and narrow-screen layout
   remain correct. Source opening does not alter review decisions.
10. New report JSON and actual generated PDF retain summary labels, hyperlinks,
    reference states, mathematical denominators and attribution.
11. Reanalysis/regeneration/review never mutates old reports; deletion and expiry
    prevent stale job publication or cross-owner access.
12. Gemini failure does not prevent source review or an evidence-only report.

Use existing unittest, frontend test/lint/build, and browser/PDF checks. Test
known-source fixtures, ambiguous cases, incorrect reporter pages, missing Acts,
same-number sections in different Acts, incomplete Gemini output, fake source
IDs, prompt injection text, timeouts, duplicate submissions and deletion races.
Use mocks for development; do not spend API credit without explicit activation.

## 9. Data-use and approval boundary

Google's terms distinguish unpaid and paid Gemini services. Unpaid inputs/outputs
may be used to improve products and may be reviewed by people; they explicitly
prohibit submitting sensitive, confidential or personal information. Confirm the
account tier and applicable regional restrictions before enabling this feature.
Keep this MVP restricted to permitted non-sensitive/synthetic/appropriately
anonymized material; consent is not a substitute for provider-policy compliance.

Confirm IK permissions for retaining excerpts and including them in Gemini
context, and retain the required attribution. No credentials need to be supplied
in chat; key variables will be added only during implementation.

References reviewed:

- Gemini models: https://ai.google.dev/gemini-api/docs/models
- Structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini terms: https://ai.google.dev/gemini-api/terms
- IK documentation: https://api.indiankanoon.org/documentation/
- IK pricing: https://api.indiankanoon.org/pricing/
- IK terms: https://api.indiankanoon.org/terms/

Approval covers the automatic-after-opt-in summary flow, the direct
source versus candidate-link distinction, the requirement for an Act before
auto-linking bare section numbers, and the initial quotas. Implementation is
complete with mocked-provider validation. Live activation and any paid smoke calls remain a separate
explicit step after backend credentials and provider permissions are confirmed.

Approved troubleshooting follow-up: ordinary Google search links are available
for individual case/statute references. Gemini Google Search grounding is NOT
used to automatically collect/cache source URLs into reports, because its terms
restrict that use. Manual search links do not change source verification metrics
or consume Gemini search quota.
