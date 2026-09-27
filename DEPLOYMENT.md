# Deploying the two-tester beta

This is a free-tier deployment guide, not an always-on production setup.
Do not upload confidential, client or company information. A publicly reachable
frontend does not mean uploads or reports should be publicly readable.

## 1. Prepare the accounts and source

Use accounts you own for Vercel, Render, Supabase and optionally Indian Kanoon.
Do not send any passwords, database URLs containing passwords, provider tokens,
service-role keys or private keys through chat.

The project folder currently contains separate frontend/backend directories.
For a single repository containing both, the Render service root is
`LITL-Backend` and the Vercel project root is `LITL-Frontend`. If you publish each
folder as its own repository, select that repository's root instead and adjust
the Render Blueprint's `rootDir` accordingly.

Do not publish `.env` files, `.venv`, databases, uploaded files or private keys.
The ignore files and environment examples are intended to help, but inspect
the proposed commit before pushing.

## 2. Create Supabase

1. Create a free Supabase project in an appropriate region.
2. Get the **session pooler** Postgres connection string from the Connect dialog.
   Render needs an accessible endpoint; the IPv4 session pooler is generally
   preferable to an IPv6-only direct database address. Require verified TLS.
   Download your project's database CA certificate from the dashboard.
   URL-encode special characters in the password when constructing a connection URI.
3. Follow the schema setup instructions in
   [the backend README](LITL-Backend/README.md), including `supabase.sql` in the
   backend directory. Backend application tables must
   not be readable or writable through public Supabase REST roles.
4. Create the backend's configured **private** storage bucket. It must not be a
   public bucket. Set the file-size ceiling to 10 MB and use the allowed MIME
   types documented by the backend.
5. In Authentication, disable public signup. Manually create two tester users
   with email/password credentials in the Supabase dashboard. Use the dashboard
   option to confirm those test users rather than relying on production email
   delivery. Give credentials directly to the intended testers, not in source.

Keep the database connection and service-role key on Render only. The Supabase
project URL and publishable/anon key are intended for browser use, but that does
not replace database/storage access controls.

## 3. Create the Render API service

Deploy the root `render.yaml` Blueprint, or create a Python web service using the
same configuration. Select the Free instance type. The Blueprint deliberately
does not create a paid background worker, Render database or Redis instance.

Configure these values through Render's dashboard/Blueprint prompt:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `hosted` |
| `AUTH_MODE`, `STORAGE_MODE` | `supabase` |
| `DATABASE_URL` | Session-pooler URI using `postgresql+psycopg://`, `sslmode=verify-full` and `sslrootcert=/etc/secrets/supabase-ca.cer` |
| `SUPABASE_URL` | Your `https://PROJECT.supabase.co` origin |
| `SUPABASE_PUBLISHABLE_KEY` | Browser-safe publishable or anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only legacy service-role JWT from Supabase API settings |
| `STORAGE_BUCKET` | `litl-private` |
| `CORS_ORIGINS` | Exact frontend origins, comma-separated; no wildcard |
| `INDIAN_KANOON_API_TOKEN` | Optional server-only token once authorized API access is obtained |
| `INDIAN_KANOON_TERMS_ACCEPTED` | `true` only after reviewing the provider's terms; defaults to `false` |
| `INDIAN_KANOON_BUDGET_PAISE` | Approved cumulative allocation in paise; defaults to `0` (disabled); `40000` is INR 400 |
| `INDIAN_KANOON_RUN_BUDGET_PAISE` | Per-analysis limit including recovery; defaults to `1100` (INR 11) |
| `INDIAN_KANOON_DAILY_BUDGET_PAISE` | Shared UTC-day limit; defaults to `4400` (INR 44) |
| `INDIAN_KANOON_OWNER_DAILY_BUDGET_PAISE` | Per-owner UTC-day limit; defaults to `2200` (INR 22) |
| `GEMINI_API_KEY` | Optional server-only Google Gemini API key |
| `GEMINI_ENABLED` | `true` only after data-use and account review; defaults to `false` |
| `GEMINI_MODEL` | Defaults to `gemini-3.5-flash-lite`; also supports `gemini-3.8-flash` and legacy `gemini-2.5-flash`; no silent model substitution |
| `GEMINI_BUDGET_MICROUSD` | Cumulative estimated Gemini allowance; defaults to `0` (disabled); `1000000` is USD 1 |
| `GEMINI_OWNER_DAILY_REQUESTS` | Per-user attempts per UTC day; default `5`, configurable `1`–`20`; app-wide cap stays `20` |
| `GEMINI_INPUT_MICROUSD_PER_MILLION` | Model-specific estimate; 3.5 Flash-Lite default `300000` (USD 0.30/million) |
| `GEMINI_OUTPUT_MICROUSD_PER_MILLION` | Model-specific estimate; 3.5 Flash-Lite default `2500000` (USD 2.50/million) |

In Render's **Secret Files**, upload the Supabase database CA as
`supabase-ca.cer`; Render makes it available at `/etc/secrets/supabase-ca.cer`.
This file must exist before schema setup can connect to Postgres. If the
Blueprint's initial deployment starts before the secret file is configured, it
will fail closed; add the file and redeploy. Do not weaken TLS to bypass that
failure. The certificate is not a private key.

The start command runs the backend's idempotent greenfield schema setup before
starting Uvicorn. It is not a general-purpose migration system for later schema
changes. Use one process; the Blueprint supplies the required concurrency bound.

The Blueprint omits the optional provider variables, so source lookup defaults
to disabled. To enable it later, set the token, terms flag and positive allocation above in the Render
environment and restart the service.

Gemini is independently optional and requires its key, enabled flag, positive
budget and per-document consent. Confirm the model's current prices, account
tier, data-use/region rules and IK excerpt-use permissions first. AI generation
uses durable jobs and may pause on free hosting. Additive summary tables receive
the same private RLS/grant hardening as other backend tables. No frontend key,
public summary sharing or automatic purchase is introduced.

Requests reserve 50 paise/search and 20 paise/document (schedule
`ik-2026-09-25`); confirm current prices before activation. Reservations survive
failures/restarts, and aggregate spending survives deletion. This is not a
provider balance sync. Reconcile outside account usage manually, and allocate
only from verified remaining credit at upgrade; prior requests have no
account-wide price ledger. Separate databases need separately partitioned
allocations. New accounting tables receive existing RLS/grant hardening;
existing columns, saved reports and previously recorded counters are unchanged.

**Never deploy the local, unauthenticated development mode.** Hosted deployment
must reject a missing Supabase configuration instead of silently falling back
to a shared local user or an ephemeral SQLite database.

The health endpoint is `/healthz`; the Blueprint uses `/readyz`. Cold starts may take
about a minute. Once available, inspect `/v1/config`: it may expose only public
configuration and must report hosted authentication/storage modes, not secrets.

## 4. Connect Vercel

Keep the existing Vite project and set its production `VITE_API_URL` to the HTTPS
Render API origin, without a trailing `/v1`. Redeploy the frontend: Vite embeds
these values during the build.

Use a Node runtime matching the frontend's declared requirements, not Node 16.
The frontend's `vercel.json` supplies SPA routing so document/report deep links
work after refresh.

For preview deployments, explicitly allow the chosen preview frontend origin on
the backend, or use an isolated preview backend. Do not expose the shared tester
API to arbitrary preview origins for convenience.

## 5. Exercise the hosted flow

Use only a small synthetic document for the first pass:

- Sign in as tester A, upload/paste, wait for real analysis and save a review.
- Reopen the same URL and confirm that content and decisions persist.
- Generate a snapshot and download/print it. Make a later review change and
  confirm the old snapshot remains unchanged.
- Sign in as tester B in a separate browser profile. A copied tester-A document,
  source or report URL must not expose A's data.
- Confirm the storage bucket cannot be listed or downloaded anonymously.
- Delete the document and ensure its API/report URLs no longer return content.
- When source lookup is configured, open the actual linked source and confirm
  the provider attribution is visible. A homepage or invented passage is not
  a successful lookup.

The repository's local HTTP smoke tests intentionally refuse a hosted API.
Do not point automated destructive tests at a shared environment.

## Free-tier and privacy limits

Render may restart or sleep. The database-backed job state is intended to
survive that; processing resumes when the service wakes, rather than relying
on a browser timer. There is no guarantee of completion while everyone is away.
Do not use artificial traffic to defeat the hosting provider's free-tier policy.

Supabase Free has finite storage/egress and can pause inactive projects. Monitor
usage, remove unused test documents and do not assume unlimited free capacity.

Retention is seven days by default. Expired documents must be inaccessible
immediately; physical deletion may be delayed while the service is asleep or a
provider is unavailable. Provider backups/retention are separate from deleting
the live app's copy. Use the application's delete action for early removal.

Indian Kanoon credits are separate from hosting quotas. The connector sends
reference queries to that provider. Its source content is subject to its terms,
including attribution, and cannot be treated as an authoritative determination
of legal correctness.

## What cannot be completed without your account configuration

Source code and local workflows do not create provider accounts or authorize
charges. A live public URL, hosted Supabase isolation and real Indian Kanoon
retrieval still require the account setup above and a hosted acceptance pass.
