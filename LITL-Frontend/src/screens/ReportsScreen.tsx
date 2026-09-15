import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { useDocument, useResource } from '@/lib/documents'
import { useAuth } from '@/lib/auth'
import { date, errorMessage, type Report, type ReportSummary } from '@/lib/api'

export default function ReportsScreen() {
  const { doc } = useDocument()
  const { api } = useAuth()
  const navigate = useNavigate()
  const { data, error, reload } = useResource<ReportSummary[]>(`/v1/documents/${doc.id}/reports`)
  const [busy, setBusy] = useState(false)
  const [saveError, setSaveError] = useState('')
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  async function snapshot() {
    setBusy(true); setSaveError('')
    try {
      const report = await api<Report>(`/v1/documents/${doc.id}/reports`, { method: 'POST' })
      if (alive.current) navigate(`/documents/${doc.id}/reports/${report.id}`)
    } catch (cause) { if (alive.current) setSaveError(errorMessage(cause)) } finally { if (alive.current) setBusy(false) }
  }
  return <AppShell><div className="page"><div className="row"><div><h1 className="type-h2">Saved report snapshots</h1><p className="text-slate break-words">{doc.title}</p></div><Button disabled={busy || doc.latest_run?.status !== 'completed'} onClick={() => void snapshot()}>{busy ? 'Saving snapshot…' : 'Save current report snapshot'}</Button><ButtonLink variant="secondary" to={`/documents/${doc.id}/review`}>Back to review</ButtonLink></div>
    <p className="notice">Each saved report is an immutable snapshot of the analysis, evidence and saved human decisions at that time. Later reviews do not update earlier reports. Unsaved edits are not included. Reports expire with the document and are deleted with it. No public sharing or senior approval is enabled.</p>
    {doc.latest_run?.status !== 'completed' && <p className="notice">Complete the latest analysis before saving a new report. Previously saved snapshots remain available below.</p>}
    {(error || saveError) && <p role="alert" className="notice error">{error || saveError}</p>}
    <Button variant="secondary" onClick={reload}>Refresh report list</Button>
    {!data && !error && <p role="status">Loading report snapshots…</p>}
    {data?.length === 0 && <Card className="p-6">No saved reports yet. Save the current record when you are ready; unresolved and unreviewed references remain visible.</Card>}
    {data?.map((report) => <Card key={report.id} className="row p-5"><div className="grow"><h2 className="font-semibold">Snapshot · {date(report.created_at)}</h2><p className="text-small text-slate break-all">{report.id}</p></div><ButtonLink to={`/documents/${doc.id}/reports/${report.id}`}>View snapshot</ButtonLink></Card>)}
  </div></AppShell>
}
