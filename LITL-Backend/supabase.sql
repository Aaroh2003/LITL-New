-- Run after `python -m app.setup_db`, using the database owner in Supabase SQL Editor.
-- The application also applies table RLS/grants atomically during setup.
BEGIN;
DO $$
DECLARE name text;
BEGIN
  FOREACH name IN ARRAY ARRAY[
    'owner_quotas', 'documents', 'analysis_runs', 'findings', 'sources',
    'finding_sources', 'review_events', 'source_opens', 'report_snapshots'
  ]
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', name);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', name);
  END LOOP;
END $$;

-- Private bucket, strict provider-side bound before the backend downloads/parses.
-- Use a fresh bucket; audit existing storage.objects policies for broad grants.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'litl-private', 'litl-private', false, 10485760,
  ARRAY[
    'application/octet-stream', 'application/pdf', 'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
ON CONFLICT (id) DO UPDATE SET
  public = false,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- No anon/authenticated policies are added for backend tables or this bucket.
-- Only server-held service_role accesses storage; clients have object-scoped,
-- non-upsert signed upload tokens. Do not give users direct bucket listing/read.
COMMIT;

-- Deployment inspection (all backend rows should have relrowsecurity = true):
SELECT c.relname, c.relrowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname IN (
  'owner_quotas', 'documents', 'analysis_runs', 'findings', 'sources',
  'finding_sources', 'review_events', 'source_opens', 'report_snapshots'
);
