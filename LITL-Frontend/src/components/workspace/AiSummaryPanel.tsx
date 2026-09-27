import { useRef, useState } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/lib/auth'
import { useDocument } from '@/lib/documents'
import { date, errorMessage, type AiSummary } from '@/lib/api'
import { safeIkUrl } from '@/lib/referenceLinks'
import { IndianKanoonAttribution } from './SourceLinks'

const headings = {
  overview: 'Overview of the draft', key_points: 'Key facts and requested relief',
  issues: 'Issues raised', source_observations: 'Retrieved-source observations',
  review_questions: 'Questions for human review',
} as const

export function AiSummaryContent({ summary, snapshot = false }: { summary: AiSummary; snapshot?: boolean }) {
  return <Card className="stack p-6">
    <h2 className="type-h3">AI summary</h2>
    <p className="notice">{summary.status === 'completed'
      ? `AI-generated draft summary · ${summary.review_state === 'reviewed' ? 'Human review recorded (not legal certification)' : summary.review_state === 'rejected' ? 'Rejected by reviewer — do not rely on this summary' : 'Not reviewed — verify statements against the document and sources'}.`
      : `Summary ${summary.status}; no AI-written summary is available in this record.`}</p>
    <p className="text-small text-slate">{summary.model} · {summary.prompt_version} · {summary.finished_at ? `${summary.status === 'completed' ? 'Generated' : 'Finished'} ${date(summary.finished_at)}` : `Requested ${date(summary.created_at)}`}</p>
    {Object.values(summary.evidence).some(e => safeIkUrl(e.url)) && <IndianKanoonAttribution />}
    {summary.status !== 'completed' && <p role={summary.error ? 'alert' : 'status'}>{summary.error || (
      snapshot ? 'AI summary was still pending when this report was saved. Generate a new report after completion.' :
        summary.status === 'queued' ? 'AI summary queued. Free hosting may pause processing.' : 'Generating AI summary…'
    )}</p>}
    {summary.output && Object.entries(headings).map(([key, heading]) => {
      const statements = summary.output?.[key as keyof typeof headings] || []
      return statements.length > 0 && <section key={key} className="stack">
        <h3 className="font-semibold">{heading}</h3>
        {statements.map((statement, index) => <div key={index} className="stack">
          <p className="whitespace-pre-wrap break-words">{statement.text}</p>
          <details className="text-small"><summary className="cursor-pointer text-blue underline">Supporting text ({statement.evidence_ids.length})</summary>
            {statement.evidence_ids.map(id => {
              const evidence = summary.evidence[id]
              if (!evidence) return <p key={id} className="notice">Evidence not available in this snapshot.</p>
              const url = safeIkUrl(evidence.url)
              return <div key={id} className="my-2 border-l-2 border-mist pl-3">
                <p>{url ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue underline">{evidence.title} — Indian Kanoon</a> : evidence.title}{evidence.page != null && ` · Page ${evidence.page}`}</p>
                <blockquote className="whitespace-pre-wrap break-words">{evidence.text}{evidence.truncated && ' [Display excerpt truncated]'}</blockquote>
              </div>
            })}
          </details>
        </div>)}
      </section>
    })}
    {summary.output && summary.output.source_observations.length === 0 && <p className="text-small">No source-backed observations were generated. The draft summary is not independent legal verification.</p>}
    {summary.limitations.map(item => <p className="text-small text-slate" key={item}>{item}</p>)}
    <p className="text-small text-slate">Gemini allowance reserved: ${(summary.reserved_microusd / 1_000_000).toFixed(5)} USD (conservative estimate, not a confirmed charge). {summary.usage?.counted_input_tokens != null && `${summary.usage.counted_input_tokens} input tokens counted. `}{summary.usage?.totalTokenCount != null && `${summary.usage.totalTokenCount} total tokens reported.`}</p>
    {summary.input_sha256 && <p className="text-small text-slate break-all">Evidence packet SHA-256: {summary.input_sha256}</p>}
  </Card>
}

export function AiSummaryPanel() {
  const { doc, reload } = useDocument()
  const { api, config } = useAuth()
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const requestKey = useRef<string | null>(null)
  const summary = doc.ai_summary
  const active = summary?.status === 'queued' || summary?.status === 'processing'
  async function generate() {
    if (!consent || !doc.latest_run) return
    setBusy(true); setError('')
    requestKey.current ||= crypto.randomUUID()
    try {
      await api(`/v1/documents/${doc.id}/analyses/${doc.latest_run.id}/summaries`, {
        method: 'POST', body: JSON.stringify({ consent: true, request_key: requestKey.current }),
      })
      requestKey.current = null
      reload()
    } catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  async function review(decision: 'reviewed' | 'rejected') {
    if (!summary) return
    setBusy(true); setError('')
    try {
      await api(`/v1/documents/${doc.id}/analyses/${summary.run_id}/summaries/${summary.id}/review`, {
        method: 'PUT', body: JSON.stringify({ decision, expected_version: summary.review_version }),
      })
      reload()
    } catch (cause) { setError(errorMessage(cause)) }
    finally { setBusy(false) }
  }
  return <section className="stack">
    {summary ? <AiSummaryContent summary={summary} /> : <h2 className="type-h3">AI summary of your document</h2>}
    {!config?.ai_summary_configured && <p className="notice">Gemini is not enabled with a backend key and positive budget. Evidence review and reports still work.</p>}
    {config?.ai_summary_configured && !active && <div className="stack">
      <label className="flex items-start gap-3"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} /><span>I consent to sending this document’s extracted text and selected source excerpts to Google Gemini. This contains no confidential, sensitive or personal information. Unpaid Gemini inputs/outputs may be used to improve Google products. Gemini usage is separate from Indian Kanoon credits.</span></label>
      <Button disabled={busy || !consent || doc.latest_run?.status !== 'completed'} onClick={() => void generate()}>{busy ? 'Working…' : summary ? 'Regenerate AI summary' : 'Generate AI summary'}</Button>
    </div>}
    {summary?.status === 'completed' && <div className="row no-print">
      <Button disabled={busy} variant="secondary" onClick={() => void review('reviewed')}>Mark summary reviewed</Button>
      <Button disabled={busy} variant="secondary" onClick={() => void review('rejected')}>Reject summary</Button>
      <span className="text-small text-slate">Review version {summary.review_version}. Save a new report to include this version.</span>
    </div>}
    {error && <p role="alert" className="notice error">{error}</p>}
  </section>
}
