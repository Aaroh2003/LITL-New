# LiTL frontend

React 19 / TypeScript / Vite 8 limited-beta client. Reuses the original visual
tokens, cards, buttons, AppShell and responsive three-pane review workspace.
Real routes use the `/v1` API only; the landing reference card is explicitly
illustrative. Old prototype screens are not registered as routes.

## Local development

Use Node **22.12+ in the 22.x series or 24 LTS** (Vite 8 is incompatible with
Node 16). `.nvmrc` records the development runtime version; use an installed
supported Node version on your own machine.

```sh
cp .env.example .env.local
npm ci --ignore-scripts
npm run dev
```

Start the backend separately, following `../LITL-Backend/README.md`.
`VITE_API_URL` defaults to `http://127.0.0.1:8000` in a local browser only.
Hosted browsers reject missing, non-HTTPS or localhost API configuration.
Configuration is loaded from `GET /v1/config`, with retry and cold-start states.

`auth_mode=local` requires no sign-in and displays a conspicuous local-only
warning. There is no local per-user isolation; never expose this mode publicly.
Hosted mode must use `auth_mode=supabase`. Manually provision tester accounts;
the client supports email/password sign-in, automatic SDK token refresh and
sign-out, not signup. Each API request obtains the current access token.
Supabase browser credentials are supplied by the API config. **Never put
service-role keys or source-provider secrets in frontend environment variables.**

## Workflow

- `/documents`: persisted history, title/filename search, status filter, deletion.
- `/upload`: real pasted text or PDF/DOCX/TXT file selection and explicit consent.
  Limits are server-configured. Hosted files go directly to a signed storage
  URL, then finalize through the API; bytes never pass through Vercel functions.
  Incomplete uploads can be deleted or retried; interrupted requests should be
  checked in Documents before resubmitting.
- `/documents/:id/analysis`: real stages, 2.5-second polling, cancel and retry.
- `/documents/:id/summary`: backend-derived metrics, limitations and reanalysis.
  Reanalysis warns that prior human decisions are not transferred.
- `/documents/:id/review/:findingId?`: searchable/filterable references,
  Unicode-code-point highlights, actual source links/passages, separately saved
  human decisions, notes and proposed corrections. HTTP 409 preserves input,
  loads the latest review and requires explicit acknowledgment before saving.
  Link-open activity is best effort; it does not prove reading.
  The document reading view reflows extracted line breaks into continuous text,
  including PDFs with blank lines between individual words. Genuine prose
  paragraphs retain normal spacing instead of labels on each extracted line.
  Stored text, source locations and citation offsets are unchanged.
- `/documents/:id/reports`: immutable snapshot creation and history.
- `/documents/:id/reports/:reportId`: snapshot-only data, JSON download and
  honestly labelled browser **Print / save PDF**. Original documents are not edited.
  Snapshot documents share the review workspace's continuous reading layout,
  including print/PDF output; stored snapshot text and JSON remain unchanged.
- `/help`: scope, provider processing, retention and privacy limitations.

Only public/synthetic/fully anonymized English Indian legal documents are
permitted, including sanitized metadata. Default retention is 7 days, with
user deletion; physical cleanup may pause during free-hosting sleep.
Downloaded reports are outside application retention controls. Hosted backup
and external-provider logs may have separate retention. No confidentiality
guarantee, legal-correctness grade, senior review, teams or public share links.
External lookup is optional: unavailable sources remain explicitly unavailable.
No mocks are substituted into real routes.

Actual Indian Kanoon results display the provider's official, unaltered logo
above each result in both review and report views, using the published desktop
or mobile image at its natural size with `referrerPolicy="no-referrer"`.
The image is loaded only for results whose HTTPS URL is on Indian Kanoon's
canonical domain; no provider HTML is injected. See the
[provider terms](https://api.indiankanoon.org/terms/).

## Validation

```sh
npm run build
npm run lint
npm test
```

The project uses TypeScript/Vite build, Oxlint and Node's built-in test runner
for bounded quotation-word comparisons. No browser automation package is installed.

## Vercel setup (configuration only; not deployed)

Use this directory as the project root, `npm run build`, output `dist`, and a
supported Node LTS runtime. Set `VITE_API_URL` to your HTTPS API origin and
rebuild after changing it. `vercel.json` provides SPA deep-link fallback.
Configure backend CORS to allow the exact frontend origin, and configure
Supabase Auth URL settings for your hosted site. Obtain deployment accounts
and source access separately; no credentials or cloud deployment are included.
