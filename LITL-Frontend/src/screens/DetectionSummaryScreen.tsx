import { useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { MetricCards, MachineBadge, DecisionBadge } from '@/components/ui/LiveData'
import { useDocument } from '@/lib/documents'
import { useAuth } from '@/lib/auth'
import { date, errorMessage, type Run } from '@/lib/api'
import { AiSummaryPanel } from '@/components/workspace/AiSummaryPanel'

export default function DetectionSummaryScreen() {
  const { doc, updateRun } = useDocument()
  const { api } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  if (doc.latest_run?.status !== 'completed') return <Navigate to={`/documents/${doc.id}/analysis`} replace />
  async function reanalyze() {
    if (!window.confirm('Start a new analysis? Existing human decisions are NOT transferred to the new run. Save a report snapshot first if you need the current review record.')) return
    setBusy(true); setError('')
    try { const run = await api<Run>(`/v1/documents/${doc.id}/analyses`, { method: 'POST' }); if (!alive.current) return; updateRun(run); navigate(`/documents/${doc.id}/analysis`) } catch (cause) { if (alive.current) setError(errorMessage(cause)) } finally { if (alive.current) setBusy(false) }
  }
  return <AppShell><div className="page"><div className="row"><div><p className="type-overline text-gold-ink">Analysis summary</p><h1 className="type-h2 break-words">{doc.title}</h1><p className="text-small text-slate">Expires {date(doc.expires_at)} · Original document unchanged</p></div><ButtonLink to={`/documents/${doc.id}/review`}>Review references</ButtonLink><ButtonLink to={`/documents/${doc.id}/reports`} variant="secondary">Generate report</ButtonLink></div>
    <MetricCards metrics={doc.metrics} scope={doc.analysis_scope} />
    <AiSummaryPanel />
    {doc.findings.length === 0 ? <Card className="p-6"><h2 className="type-h3">No references detected</h2><p>This does not mean the document is legally correct or contains no references. Read the extracted document and account for detection limitations.</p></Card> : <div className="grid gap-3 md:grid-cols-2">{doc.findings.map((finding) => <Card className="stack p-5" key={finding.id}><h2 className="font-semibold">{finding.label}</h2><div className="row"><MachineBadge status={finding.status} /><DecisionBadge decision={finding.decision} /></div><p className="text-small text-slate">{finding.note}</p><ButtonLink variant="ghost" size="sm" to={`/documents/${doc.id}/review/${finding.id}`}>Inspect document and evidence →</ButtonLink></Card>)}</div>}
    {error && <p role="alert" className="notice error">{error}</p>}<div className="row"><Button variant="secondary" disabled={busy} onClick={() => void reanalyze()}>{busy ? 'Starting…' : 'Run a new analysis'}</Button><ButtonLink to="/documents" variant="ghost">All documents / delete</ButtonLink></div>
  </div></AppShell>
}
