import type { SupabaseClient } from '@supabase/supabase-js'

export type Config = {
  auth_mode: 'local' | 'supabase'
  storage_mode: 'local' | 'supabase'
  supabase_url: string | null
  supabase_publishable_key: string | null
  max_file_bytes: number
  max_characters: number
  max_pages: number
  source_lookup_configured: boolean
}
export type Run = {
  id: string; document_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  stage: string; error: string | null; created_at: string; finished_at: string | null; warnings: string[]
}
export type Source = {
  id: string; title: string; url: string; repository: string
  retrieved_at: string; passage: string; locator: string | null
}
export type Decision = 'confirmed' | 'corrected' | 'rejected' | 'unresolved'
export type Finding = {
  id: string; run_id: string; kind: 'case_citation' | 'statutory_reference' | 'quotation'
  label: string; excerpt: string; start: number; end: number; paragraph_id: string | null; page: number | null
  status: 'source_found' | 'ambiguous' | 'not_found' | 'unavailable' | 'unsupported' | 'not_checked' | 'quote_mismatch'
  note: string; sources: Source[]; decision: Decision | null; review_note: string; correction: string
  version: number; source_opened: boolean
}
export type Metric = { numerator: number; denominator: number; percentage: number | null }
export type Metrics = {
  source_coverage: Metric; citation_consistency: Metric; quotation_fidelity: Metric
  review_completion: Metric; resolution_coverage: Metric; source_activity: Metric; evidence_provenance: Metric
  total: number; unreviewed: number; unresolved: number; ambiguous: number; unavailable: number
  unsupported?: number; not_found?: number; not_checked?: number; quote_mismatch?: number
}
export type DocumentSummary = {
  id: string; file_name: string; title: string; created_at: string; expires_at: string; latest_run: Run | null
}
export type Document = DocumentSummary & {
  text: string; paragraphs: { id: string; text: string; start: number; end: number; page: number | null }[]
  findings: Finding[]; metrics: Metrics
}
export type ReportSummary = { id: string; document_id: string; created_at: string }
export type Report = ReportSummary & { document: Document; disclaimer: string }

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}
export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'An unexpected error occurred. Please retry.'
}
export function apiBase() {
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname)
  const configured = import.meta.env.VITE_API_URL?.trim()
  if (!configured && !local) throw new Error('Setup required: set VITE_API_URL to your hosted HTTPS API, then rebuild the frontend.')
  const url = new URL(configured || 'http://127.0.0.1:8000')
  if (!local && (url.protocol !== 'https:' || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) {
    throw new Error('Setup required: a hosted browser must use a hosted HTTPS API, not localhost.')
  }
  return url.href.replace(/\/$/, '')
}
export async function request<T>(path: string, options: RequestInit = {}, client: SupabaseClient | null = null): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (client) {
    const { data, error } = await client.auth.getSession()
    if (error) throw error
    if (!data.session) throw new ApiError('Your session has expired. Please sign in again.', 401)
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }
  let response: Response
  try {
    response = await fetch(`${apiBase()}${path}`, { ...options, headers })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new Error('Cannot reach the API. Check your connection and API configuration. Free hosting may take about a minute to wake up.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.join('.') || 'Input'}: ${item.msg || 'invalid'}`).join('; ')
      : `Request failed (${response.status}). Please retry.`
    throw new ApiError(message, response.status)
  }
  return response.status === 204 ? undefined as T : response.json()
}
export const label = (value: string) => value.replaceAll('_', ' ')
export const date = (value: string) => new Date(value).toLocaleString()
export function safeSourceUrl(value: string) {
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : null } catch { return null }
}
