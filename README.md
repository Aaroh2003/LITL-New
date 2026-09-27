# LiTL - Lawyer in the Loop

A small legal-document review app for English-language Indian legal drafts.
Upload a text-based PDF, DOCX or TXT, or paste a draft; inspect detected legal
references and available source evidence; record your own assessment; export a
report of the review.

**For public, synthetic or properly anonymized documents only.** Do not use this
beta for confidential client files, company information or personal data.
LiTL does not certify legal correctness, and finding a judgment does not prove
that the judgment supports the draft's argument.

## Start here: source handoff

This is the source project to push to GitHub and deploy. Dependency folders,
compiled builds and Python caches are deliberately not included: install the
dependencies using the commands below. **Keep `package-lock.json` and
`requirements.txt`**; they describe what must be installed.

If you received `LITL-source.zip`, extract it and use the enclosed `LITL/` folder
as the repository root. The ZIP excludes local databases/uploaded documents,
real environment files, private keys, dependency folders, builds and AI-tool
logs. Do not send a ZIP of an existing developer's entire working directory
instead: `LITL-Backend/.data/` can contain uploaded document bytes and reviews.

For the quickest deployment, keep the frontend and backend in **one GitHub
repository with the folder structure below unchanged**. Do not flatten or rename
the folders without also updating the hosting root-directory settings.

## Project layout

| Path | Purpose |
| --- | --- |
| `LITL-Frontend/` | React, TypeScript, Vite and Tailwind application |
| `LITL-Backend/` | FastAPI, persistent document/review storage and analysis jobs |
| `render.yaml` | Free Render API service configuration; points to `LITL-Backend` |
| `DEPLOYMENT.md` | Supabase, database TLS, private storage and hosting setup |
| `tests/test_local_workflow.py` | Local HTTP workflow smoke tests using synthetic input |
| `MVP_PLAN.md` | Approved scope and implementation sequence |

The frontend and backend can remain in separate repositories. The root deployment
instructions assume both folders are committed in a single repository; see the
deployment notes for the separate-repository adjustment.

## How the app works

```text
Browser: React frontend on Vercel
  -> VITE_API_URL + /v1/config: load public configuration
  -> Supabase Auth: sign in when hosted
  -> VITE_API_URL + /v1/...: authenticated document/review/report requests
       -> FastAPI on Render
       -> Postgres: documents, queued analysis jobs, findings and reviews
       -> Private Supabase Storage: original uploaded files
       -> Indian Kanoon API: optional external reference lookup
```

The backend extracts text, detects citations/statutes/quotations and records real
job stages. The frontend polls for results, highlights selected citations and
lets a human save an assessment. Reports are immutable snapshots of the saved
analysis and review state. Reading layouts reflow extracted word/line breaks;
they do not change the stored original or citation offsets.

Local development substitutes SQLite and a fixed local identity for the hosted
database/authentication setup. Uploaded file bytes are also stored in local
SQLite. Local mode must not be exposed to online users.

## Where to set the backend URL

**Set `VITE_API_URL` in the frontend's environment. Do not edit URLs in individual
screens or put a deployed site's backend URL to `localhost`.**

| Setting | Where to change it | Example |
| --- | --- | --- |
| Frontend API base URL | Vercel project -> Settings -> Environment Variables -> `VITE_API_URL` | `https://your-litl-api.onrender.com` |
| Local frontend API base URL | `LITL-Frontend/.env.local` (copy `.env.example`) | `http://127.0.0.1:8000` |
| Allowed browser origins | Render API -> Environment -> `CORS_ORIGINS` | `https://your-litl-frontend.vercel.app` |
| API URL reader and HTTP client | `LITL-Frontend/src/lib/api.ts`: `apiBase()` and `request()` | Usually no source change needed |
| Frontend session/auth wrapper | `LITL-Frontend/src/lib/auth.tsx` | Adds the current Supabase session |
| Backend route definitions | `LITL-Backend/app/main.py` | Endpoints under `/v1` |
| Backend environment settings | `LITL-Backend/app/config.py` and `.env.example` | Server-side configuration |

For an online frontend, use your actual HTTPS backend origin, **without `/v1` or
an endpoint path**:

```dotenv
VITE_API_URL=https://your-litl-api.onrender.com
```

Requests already include paths such as `/v1/documents`; the client combines them
with the configured origin. A missing hosted URL, an HTTP URL or localhost URL is
rejected rather than trying to contact each visitor's own computer.

**Redeploy/rebuild the frontend after changing `VITE_API_URL`.** Vite embeds this
value into the browser bundle at build time. Set the value for the Vercel
Production environment, and explicitly configure Preview values if needed.
Restart the Vite development server after changing `.env.local`.

On the backend, set the matching frontend origin:

```dotenv
CORS_ORIGINS=https://your-litl-frontend.vercel.app
```

Use exact origins without paths or trailing slashes. Multiple approved origins
can be comma-separated; never use `*`. Restart/redeploy the API after changing
its environment. Do not broadly allow every Vercel preview domain.

**Never put `DATABASE_URL`, a Supabase service-role key or the Indian Kanoon token
in a `VITE_` variable.** Every `VITE_` value is public browser configuration.
The frontend receives only the Supabase project URL and browser-safe key through
`GET /v1/config`; privileged keys stay on Render.

## Run locally

Use Python 3.12 and Node 24 LTS (or Node 22.12+ in the 22.x series).
`LITL-Frontend/.nvmrc` records the development Node version. Vite 8 does **not**
support Node 16. The backend commands below are for macOS/Linux; use WSL on
Windows.

In the first terminal:

```sh
cd LITL-Backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.setup_db
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 16
```

In the second terminal:

```sh
cd LITL-Frontend
cp .env.example .env.local
npm ci --ignore-scripts
npm run dev -- --host 127.0.0.1
```

Open the frontend address printed by Vite. Local development requires no cloud
credentials. It uses a local development identity, local files and SQLite:
**never expose this mode using a tunnel or bind it to a public network.**

Source lookup remains explicitly unavailable until Indian Kanoon API access is
configured. You can still exercise real uploads, reference detection, saved
review decisions and report generation. Local source-unavailable results are not
an external verification demo.

See [backend setup](LITL-Backend/README.md) and
[frontend setup](LITL-Frontend/README.md) for environment configuration.
Environment examples contain placeholders only; never commit real credentials,
private keys, uploaded files or local databases.
The backend does not automatically load `.env`; configure its environment
through exported shell variables locally or the Render dashboard when hosted.

## First use

1. Open Upload and confirm that the draft is public, synthetic or anonymized.
2. Paste a short draft or choose a PDF, DOCX or TXT. The input limit is 10 MB,
   50 extracted PDF pages and 200,000 text characters.
3. Wait for the actual job stages. A document without detectable references is
   a valid empty result, not a 100% verification score.
4. In the review workspace, select a reference and inspect its machine result,
   evidence and source location. A provider error is not a finding of falsity.
5. Confirm, correct, reject or leave unresolved, with a note as appropriate.
   A correction records a proposal; it does not rewrite your original file.
6. Generate a report snapshot, download its structured data, or print/save PDF.
   Later review edits do not silently alter an earlier report.
7. Delete test documents from document history when finished.

Case citations, statutory references and quotations are detected using bounded
patterns. This is not comprehensive free-form claim extraction. Scanned,
encrypted or unsupported files should receive an explicit error; OCR is not
part of this release.

## Live source lookup

Create your own [Indian Kanoon API account](https://api.indiankanoon.org/).
Read the provider's documentation and terms, obtain API credentials and place
them in **backend-only** environment configuration. Do not send credentials in
chat or put them in any `VITE_` variable.

For local use, enter your key in `LITL-Backend/.env` as
`INDIAN_KANOON_API_TOKEN=...`. After reviewing the terms, set
`INDIAN_KANOON_TERMS_ACCEPTED=true` and an approved
`INDIAN_KANOON_BUDGET_PAISE` allocation. Units are integer paise: `40000` means
INR 400, an example only. The default is zero, preventing live spending.
From `LITL-Backend`, start:

```sh
.venv/bin/uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 16
```

Restart after editing the file. Exported variables override it. See the
[backend spending limits](LITL-Backend/README.md#spending-limits-and-report-costs).
Reports include reserved request costs, not confirmed billing or account balance.
Reopening/exporting reports does not make paid source requests. Optional Gemini
summaries require a separate backend key, budget and explicit document consent;
evidence-only reports do not require an AI provider.

From the analysis or review screen, choose **Generate report**, then generate
a saved snapshot. The final report includes a count-based overview, items needing
attention, versioned formulas with numerators/denominators, source passages,
saved decisions and JSON/PDF export. Coverage and match rates are separate;
zero-denominator metrics show N/A, not a legal-correctness score.
Statutory messages use the detected provision and explicitly named Act. A bare
`Section 335` asks the reviewer to identify its Act instead of assuming CrPC/BNSS.
Older saved reports are never rewritten; generate a new snapshot to include
the current explanations and formulas.

## Optional Gemini summaries and clickable references

In `LITL-Backend/.env`, set `GEMINI_API_KEY`, `GEMINI_ENABLED=true` and a positive
`GEMINI_BUDGET_MICROUSD` (for example `1000000` is a USD 1 estimated cumulative
allowance). The default model is `gemini-3.5-flash-lite`; `gemini-3.8-flash` is
also supported, while `gemini-2.5-flash` is retained
only for projects that still have access. Defaults leave generation
disabled. Restart the backend after editing. See
[Gemini setup and safeguards](LITL-Backend/README.md#gemini-summary-setup).

Opt in during upload for a summary after analysis, or choose **Generate AI
summary** on an existing document's summary/reports page. Review its evidence
references, mark it reviewed or rejected, and generate a new report to include
that summary version. Unpaid Gemini may use prompts/responses to improve Google
products; never send sensitive, confidential or personal data.

Matched citations and named legislation targets open Indian Kanoon directly.
Dotted references open the review panel, where possible matches or simple
missing-source messages are shown. Bare sections require an Act name. A source
link is not proof of legal applicability; AI does not invent URLs or alter
the mathematical verification results.

Each case/statute panel and report also offers **Open first Google result
(unverified)**, using Google's first-result redirect for Indian Kanoon pages.
Google may show a redirect confirmation or search page rather than navigating
directly. Clicking sends only that reference; it makes no Gemini Search API
call and does not import the result as verified evidence.

The provider's [published pricing](https://api.indiankanoon.org/pricing/) currently
advertises Rs 500 development/testing signup credit. Account approval, actual
credit availability and any later top-up are the provider's responsibility.
Do not assume a trial credit is a permanent free tier.

Only detected reference queries are intended for the connector, not the whole
draft. Even a citation may contain party names, so anonymize input appropriately.
The app must retain the distinction between unavailable lookup, no match,
ambiguous candidates and a conservatively identified source.

Source results require the provider's attribution, including its unmodified
"powered by IKanoon" graphic. Review the
[API terms](https://api.indiankanoon.org/terms/) before deploying.

## Zero-budget tester hosting

Keep the frontend on Vercel. Use Supabase Free for authentication, Postgres and
private file storage, and one Render Free web service for FastAPI and its
in-service job processor. Configure two tester accounts; open signup and
junior/senior collaboration are intentionally deferred.

### Deployment order for your friend

1. Push the extracted source folder to a GitHub repository, including the root
   README, `render.yaml`, both application folders, lockfile and environment
   examples. Do not commit actual credentials or local data.
2. Create Supabase and configure its Postgres connection, private `litl-private`
   storage bucket, schema/RLS and two manually provisioned tester accounts.
   Disable public signup. Follow `DEPLOYMENT.md` for the database CA certificate
   and `sslmode=verify-full` setup.
3. Create the Render API using `render.yaml`, with repository root
   `LITL-Backend`. Hosted mode requires `APP_ENV=hosted`, `AUTH_MODE=supabase`,
   `STORAGE_MODE=supabase` and all Supabase/database settings from the deployment
   guide. Do not deploy SQLite or local authentication.
4. Create/import the Vercel project with root directory `LITL-Frontend`, build
   command `npm run build`, output directory `dist`, and supported Node LTS.
   Set `VITE_API_URL` to the new Render HTTPS origin before building.
5. Set Render's `CORS_ORIGINS` to the final Vercel origin. Set Supabase Auth's Site
   URL to the frontend URL. Redeploy as necessary; verify `/readyz` and sign in
   with a tester account before trying a synthetic upload.
6. If external source lookup is needed, obtain your own Indian Kanoon token and
   configure `INDIAN_KANOON_API_TOKEN` plus
   `INDIAN_KANOON_TERMS_ACCEPTED=true` and a positive
   `INDIAN_KANOON_BUDGET_PAISE` allocation on the **backend only**. Source lookup is
   otherwise explicitly unavailable; no fake evidence or paid LLM is substituted.

Deploy only into accounts you own and have permission to use. These hosting
choices are not a claim of approval for LinkedIn or confidential legal data.

- Render Free can sleep after 15 minutes without traffic and take about a minute
  to wake. Jobs can pause while asleep and resume on wake.
- Supabase Free projects can pause after one week of inactivity.
- Files must live in private Supabase Storage in hosted mode. Render's local
  filesystem is ephemeral; do not use hosted SQLite.
- Expired records become inaccessible even if physical cleanup is delayed
  because the free service is asleep. Backup/provider retention is separate.
- No paid LLM is required. Metered source lookup stops being free once credits
  run out, and quotas can interrupt hosting.
- No service is deployed or paid account created by the source code itself.

See [deployment instructions](DEPLOYMENT.md) for the account configuration and
environment variables needed to make the application publicly reachable.

### Common deployment problems

| Symptom | What to check |
| --- | --- |
| Frontend says API setup is missing | Set `VITE_API_URL` in Vercel, then redeploy; editing a local `.env` does not update an existing deployment |
| Browser requests go to localhost | Replace the production API URL with the HTTPS Render origin and rebuild |
| Requests fail with CORS errors | `CORS_ORIGINS` must exactly match the browser's frontend origin; restart the API |
| API refuses to start | Hosted auth/storage/DB settings, CA secret file and private bucket must all be configured; local fallback is intentionally forbidden |
| Initial request is slow | Render Free can take about a minute to wake; check `/readyz` |
| Sources show unavailable | Configure the backend token, terms flag and positive allocation; check unspent app limits and provider credit/access |
| Refreshing a document URL gives 404 | Use the supplied frontend `vercel.json` SPA rewrite and correct Vercel project root |

## Local workflow checks

With the local API running and source lookup disabled:

```sh
python3 -m unittest discover -s tests -v
```

These checks refuse non-loopback URLs, hosted authentication and a configured
source provider. They create synthetic documents and delete only those records;
they do not send documents to legal repositories or consume API credit.
They do consume local upload/analysis quotas. For repeated runs, start the API
with an isolated database, e.g. export
`DATABASE_URL=sqlite:///.data/smoke.db` in its terminal before starting it, then
return to the normal database for manual use.

For backend tests and frontend build/lint commands, see the component READMEs.

With both development servers running and Chrome already installed, the browser
smoke test also exercises document/report deep links and a narrow-screen review:

```sh
node tests/browser_smoke.mjs
```

On systems without Chrome at the default macOS path, set `LITL_CHROME_PATH` to an
existing Chrome/Chromium executable. The test does not install or download a
browser. It uses an isolated temporary browser profile and removes it afterwards.
