import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { useAuth } from '@/lib/auth'
import { useResource } from '@/lib/documents'
import { date, errorMessage, type DocumentSummary } from '@/lib/api'

export default function DocumentsScreen() {
  const { api } = useAuth()
  const { data, error, reload } = useResource<DocumentSummary[]>('/v1/documents')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [pending, setPending] = useState('')
  const [actionError, setActionError] = useState('')
  async function remove(doc: DocumentSummary) {
    if (!window.confirm(`Delete “${doc.title}” and its files, reviews and reports? This cannot be undone.`)) return
    setPending(doc.id); setActionError('')
    try { await api(`/v1/documents/${doc.id}`, { method: 'DELETE' }); reload() } catch (cause) { setActionError(errorMessage(cause)) } finally { setPending('') }
  }
  const visible = data?.filter((doc) => `${doc.title} ${doc.file_name}`.toLowerCase().includes(query.toLowerCase()) && (!status || (doc.latest_run?.status || 'pending') === status))
  return <AppShell><div className="page"><div className="row"><div><h1 className="type-h2">Your documents</h1><p className="text-slate">One reviewer. Real documents, saved decisions and immutable report snapshots.</p></div><ButtonLink to="/upload">Upload or paste</ButtonLink></div>
    <p className="notice">Public, synthetic or fully anonymized documents only. Default retention is 7 days; delete any document below. Physical cleanup can be delayed while free hosting sleeps.</p>
    <div className="row"><label className="grow">Search documents<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Title or filename" /></label><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{['pending', 'queued', 'processing', 'completed', 'failed', 'cancelled'].map((item) => <option key={item}>{item}</option>)}</select></label><Button variant="secondary" onClick={reload}>Refresh</Button></div>
    {(error || actionError) && <p role="alert" className="notice error">{error || actionError}</p>}
    {!data && !error && <p role="status">Loading documents… The API can take about a minute to wake up.</p>}
    {visible?.length === 0 && <Card className="p-8"><h2 className="type-h3">{data?.length ? 'No documents match these filters.' : 'Your first review starts here.'}</h2><p>Upload a supported document or paste English Indian legal text. Nothing is pre-populated.</p></Card>}
    <div className="stack">{visible?.map((doc) => <Card key={doc.id} className="row p-5"><div className="min-w-0 grow"><h2 className="type-h3 break-words">{doc.title}</h2><p className="text-small text-slate break-words">{doc.file_name} · {doc.latest_run?.status || 'pending upload'}</p><p className="text-small text-slate">Created {date(doc.created_at)} · Expires {date(doc.expires_at)}</p></div><div className="row"><ButtonLink size="sm" to={`/documents/${doc.id}/${doc.latest_run?.status === 'completed' ? 'summary' : 'analysis'}`}>Open</ButtonLink><ButtonLink size="sm" variant="secondary" to={`/documents/${doc.id}/reports`}>Reports</ButtonLink><Button size="sm" variant="danger" disabled={!!pending} onClick={() => void remove(doc)}>{pending === doc.id ? 'Deleting…' : 'Delete'}</Button></div></Card>)}</div>
  </div></AppShell>
}
