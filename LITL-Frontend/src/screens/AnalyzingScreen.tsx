import { useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { useDocument } from '@/lib/documents'
import { useAuth } from '@/lib/auth'
import { errorMessage, label, type Run } from '@/lib/api'

export default function AnalyzingScreen() {
  const { doc, reload, updateRun } = useDocument()
  const { api } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const run = doc.latest_run
  if (run?.status === 'completed') return <Navigate to={`/documents/${doc.id}/summary`} replace />
  async function act(action: 'cancel' | 'retry' | 'finalize' | 'delete') {
    if (action === 'delete' && !window.confirm('Delete this document and all associated data?')) return
    setBusy(true); setError('')
    try {
      const path = `/v1/documents/${doc.id}`
      const result = await api<Run>(action === 'delete' ? path : action === 'cancel' ? `${path}/analyses/${run!.id}/cancel` : action === 'finalize' ? `${path}/finalize` : `${path}/analyses`, { method: action === 'delete' ? 'DELETE' : 'POST' })
      if (!alive.current) return
      if (action === 'cancel' || action === 'retry') updateRun(result)
      if (action === 'delete') navigate('/documents'); else reload()
    } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }
  return <AppShell><div className="page narrow"><Card className="stack p-8"><p className="type-overline text-gold-ink">Live analysis status</p><h1 className="type-h2 break-words">{doc.title}</h1><h2 className="type-h3" role="status">{run ? label(run.status) : 'Incomplete upload'}</h2><p>{run ? `Current stage: ${label(run.stage)}` : 'The file upload has not been finalized. If storage upload completed, retry finalization. Otherwise delete this entry and upload again.'}</p>
    {run?.error && <p role="alert" className="notice error">{run.error}</p>}{error && <p role="alert" className="notice error">{error}</p>}
    <div className="row">{run && ['queued', 'processing'].includes(run.status) ? <Button disabled={busy} variant="secondary" onClick={() => void act('cancel')}>Cancel analysis</Button> : <Button disabled={busy} onClick={() => void act(run ? 'retry' : 'finalize')}>{run ? 'Retry analysis' : 'Retry finalization'}</Button>}<Button disabled={busy} variant="danger" onClick={() => void act('delete')}>Delete document</Button><ButtonLink variant="ghost" to="/documents">All documents</ButtonLink></div>
    <p className="text-small text-slate">Status refreshes every 2.5 seconds while queued or processing. No estimated percentage is fabricated. Free hosting can take about a minute to wake up and processing can pause while asleep.</p>
  </Card></div></AppShell>
}
