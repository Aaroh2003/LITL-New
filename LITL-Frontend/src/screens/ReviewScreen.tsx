import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useBlocker, useParams } from 'react-router-dom'
import { Button, ButtonLink } from '@/components/ui/Button'
import { DecisionBadge, MachineBadge } from '@/components/ui/LiveData'
import { WorkspaceLayout, WorkspaceSubHeader, WorkspaceFooterBar, EvidencePane } from '@/components/workspace/WorkspaceLayout'
import { LiveDocumentPane } from '@/components/workspace/LiveDocumentPane'
import { SourceLinks } from '@/components/workspace/SourceLinks'
import { useDocument } from '@/lib/documents'
import { useAuth } from '@/lib/auth'
import { ApiError, errorMessage, label, type Decision, type Document, type Finding, type Source } from '@/lib/api'

function ReviewForm({ finding, setDirty }: { finding: Finding; setDirty: (dirty: boolean) => void }) {
  const { doc, updateFinding } = useDocument()
  const { api } = useAuth()
  const [decision, setDecision] = useState<Decision | ''>(finding.decision || '')
  const [note, setNote] = useState(finding.review_note)
  const [correction, setCorrection] = useState(finding.correction)
  const [version, setVersion] = useState(finding.version)
  const [baseline, setBaseline] = useState({ decision: finding.decision || '', note: finding.review_note, correction: finding.correction })
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [activityError, setActivityError] = useState('')
  const [conflict, setConflict] = useState<Finding | null>(null)
  const [needsRefresh, setNeedsRefresh] = useState(false)
  const alive = useRef(true)
  const operations = useRef(new Set<AbortController>())
  const dirty = decision !== baseline.decision || note !== baseline.note || correction !== baseline.correction
  useEffect(() => { setDirty(dirty) }, [dirty, setDirty])
  useEffect(() => {
    alive.current = true
    const pending = operations.current
    return () => { alive.current = false; pending.forEach((controller) => controller.abort()); setDirty(false) }
  }, [setDirty])
  async function getLatest() {
    const controller = new AbortController()
    operations.current.add(controller)
    try {
      const latestDoc = await api<Document>(`/v1/documents/${doc.id}`, { signal: controller.signal })
      if (!alive.current) return
      const latest = latestDoc.findings.find((item) => item.id === finding.id)
      if (!latest) throw new Error('This finding is no longer in the latest run. Copy your unsaved input before leaving this page.')
      setConflict(latest); setNeedsRefresh(false); updateFinding(latest)
    } catch (cause) { if (alive.current) { setNeedsRefresh(true); setError(`Could not load the latest version: ${errorMessage(cause)}. Your unsaved input is preserved.`) } }
    finally { operations.current.delete(controller) }
  }
  async function save(event: FormEvent) {
    event.preventDefault()
    if (!decision || conflict || needsRefresh) return
    if (decision === 'corrected' && !correction.trim()) { setError('A corrected decision requires a proposed correction.'); return }
    setBusy(true); setError(''); setMessage('')
    const controller = new AbortController()
    operations.current.add(controller)
    try {
      const saved = await api<Finding>(`/v1/documents/${doc.id}/findings/${finding.id}/review`, { method: 'PUT', signal: controller.signal, body: JSON.stringify({ decision, review_note: note, correction, expected_version: version }) })
      if (!alive.current) return
      setVersion(saved.version)
      setBaseline({ decision: saved.decision || '', note: saved.review_note, correction: saved.correction })
      setDecision(saved.decision || ''); setNote(saved.review_note); setCorrection(saved.correction)
      setMessage('Review saved. It will be available when you reopen this document.')
      updateFinding(saved)
    } catch (cause) {
      if (!alive.current) return
      if (cause instanceof ApiError && cause.status === 409) {
        setNeedsRefresh(true)
        setError('This finding changed in another request or tab. Your unsaved input is preserved; compare the latest saved decision below before retrying.')
        await getLatest()
      } else setError(errorMessage(cause))
    } finally { operations.current.delete(controller); if (alive.current) setBusy(false) }
  }
  async function openSource(source: Source) {
    setActivityError('')
    const controller = new AbortController()
    operations.current.add(controller)
    try {
      const next = await api<Finding>(`/v1/documents/${doc.id}/findings/${finding.id}/source-open`, { method: 'POST', signal: controller.signal, body: JSON.stringify({ source_id: source.id }) })
      if (alive.current) updateFinding(next)
    } catch (cause) { if (alive.current) setActivityError(`The source link was opened, but its activity could not be saved: ${errorMessage(cause)}`) }
    finally { operations.current.delete(controller) }
  }
  return <div className="stack">
    <div className="row"><MachineBadge status={finding.status} /><DecisionBadge decision={finding.decision} /></div>
    <p className="text-small">{finding.note}</p>
    <p className="text-small text-slate">{label(finding.kind)} · {finding.page !== null ? `Page ${finding.page}` : finding.paragraph_id ? `Paragraph ${doc.paragraphs.findIndex((p) => p.id === finding.paragraph_id) + 1}` : 'Document location'} · Offsets {finding.start}–{finding.end}</p>
    <blockquote className="whitespace-normal break-words rounded bg-cite-mark p-3 text-small">{finding.excerpt}</blockquote>
    <SourceLinks sources={finding.sources} draftQuote={finding.kind === 'quotation' ? finding.excerpt : undefined} onOpen={(source) => void openSource(source)} />
    <p className="text-small text-slate">Saved link activity: {finding.source_opened ? 'at least one source link opened' : 'no source open recorded'}.</p>
    {activityError && <p role="alert" className="notice error">{activityError} Open the link again to retry recording activity.</p>}
    <form onSubmit={save} className="stack border-t border-mist pt-5">
      <h3 className="type-h3">Your assessment</h3>
      <p className="text-small text-slate">A correction is a saved proposal, not an edit to the original PDF, DOCX or text.</p>
      <label>Human decision<select required value={decision} disabled={busy} onChange={(event) => { setDecision(event.target.value as Decision); setMessage('') }}><option value="">Choose a decision</option>{(['confirmed', 'corrected', 'rejected', 'unresolved'] as const).map((item) => <option value={item} key={item}>{label(item)}</option>)}</select></label>
      <label>Proposed correction {decision === 'corrected' ? '(required)' : '(optional)'}<textarea rows={4} disabled={busy} required={decision === 'corrected'} value={correction} onChange={(event) => { setCorrection(event.target.value); setMessage('') }} /></label>
      <label>Review note<textarea rows={4} disabled={busy} value={note} onChange={(event) => { setNote(event.target.value); setMessage('') }} placeholder="Explain your decision and any unresolved limitation." /></label>
      {error && <p role="alert" className="notice error">{error}</p>}
      {conflict && <div className="notice stack"><h4 className="font-semibold">Latest saved review · version {conflict.version}</h4><p>Decision: {conflict.decision || 'unreviewed'}</p><p className="whitespace-pre-wrap break-words">Correction: {conflict.correction || 'None'}</p><p className="whitespace-pre-wrap break-words">Note: {conflict.review_note || 'None'}</p><Button size="sm" variant="secondary" onClick={() => { setVersion(conflict.version); setConflict(null); setError(''); setMessage('Latest version acknowledged. Your unsaved input remains above; save explicitly to replace that review.') }}>Keep my input and use latest version</Button></div>}
      {needsRefresh && <Button onClick={() => void getLatest()} variant="secondary">Retry loading latest version</Button>}
      {message && <p role="status" className="text-small text-green">{message}</p>}
      <Button type="submit" disabled={busy || !decision || !!conflict || needsRefresh}>{busy ? 'Saving…' : 'Save assessment'}</Button>
      <p className="text-small text-slate">{dirty ? 'Unsaved changes' : `Saved version ${version}`}. Decisions and machine results remain separate.</p>
    </form>
  </div>
}
export default function ReviewScreen() {
  const { doc } = useDocument()
  const { findingId } = useParams()
  const [filter, setFilter] = useState('all')
  const [kind, setKind] = useState('all')
  const [query, setQuery] = useState('')
  const [dirty, setDirty] = useState(false)
  const blocker = useBlocker(dirty)
  useEffect(() => {
    if (blocker.state === 'blocked') {
      if (window.confirm('Leave this review and discard your unsaved changes?')) blocker.proceed()
      else blocker.reset()
    }
  }, [blocker])
  useEffect(() => {
    if (!dirty) return
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', beforeUnload)
    return () => { window.removeEventListener('beforeunload', beforeUnload) }
  }, [dirty])
  if (doc.latest_run?.status !== 'completed') return <Navigate to={`/documents/${doc.id}/analysis`} replace />
  const finding = findingId ? doc.findings.find((item) => item.id === findingId) : doc.findings[0]
  const visible = doc.findings.filter((item) =>
    (kind === 'all' || item.kind === kind) &&
    `${item.label} ${item.excerpt}`.toLowerCase().includes(query.toLowerCase()) &&
    (filter === 'all' || (filter === 'unreviewed' ? !item.decision : filter === 'unresolved' ? item.decision === 'unresolved' : item.status === filter)))
  const progress = doc.metrics.review_completion
  return <WorkspaceLayout
    subHeader={<WorkspaceSubHeader fileName={doc.title} state="Human review" reviewedLabel={`${progress.numerator} / ${progress.denominator} reviewed`} progress={progress.denominator ? progress.numerator / progress.denominator : 0} actionLabel="Saved reports" actionTo={`/documents/${doc.id}/reports`} />}
    rail={<aside aria-label="Detected references" className="flex w-full shrink-0 flex-col border-b border-mist bg-white lg:w-[280px] lg:overflow-y-auto lg:border-r"><div className="stack p-4"><div className="row"><h2 className="type-overline">References · {doc.findings.length}</h2><ButtonLink to={`/documents/${doc.id}/summary`} size="sm" variant="ghost">Summary</ButtonLink></div><label>Search<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label>Review / machine filter<select value={filter} onChange={(event) => setFilter(event.target.value)}>{['all', 'unreviewed', 'unresolved', 'source_found', 'ambiguous', 'not_found', 'unavailable', 'unsupported', 'not_checked', 'quote_mismatch'].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label><label>Reference kind<select value={kind} onChange={(event) => setKind(event.target.value)}>{['all', 'case_citation', 'statutory_reference', 'quotation'].map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label><p className="text-small text-slate">{visible.length} matching references</p></div><div className="max-h-72 overflow-y-auto lg:max-h-none">{visible.map((item) => <Link key={item.id} to={`/documents/${doc.id}/review/${item.id}`} aria-current={finding?.id === item.id ? 'true' : undefined} className={`block border-t border-mist p-4 ${finding?.id === item.id ? 'border-l-4 border-l-yellow-500 bg-yellow-100' : 'hover:bg-paper'}`}><p className="mb-2 text-small font-semibold break-words">{item.label}</p><div className="flex flex-wrap gap-1"><MachineBadge status={item.status} /><DecisionBadge decision={item.decision} /></div></Link>)}{!visible.length && <p className="p-4 text-small text-slate">No references match. Change filters or read the document.</p>}</div></aside>}
    document={<LiveDocumentPane doc={doc} finding={finding} />}
    evidence={<EvidencePane overline="Source evidence / your decision" title={finding?.label || (findingId ? 'Reference not found' : 'No references detected')}><>{finding ? <ReviewForm key={finding.id} finding={finding} setDirty={setDirty} /> : <p className="notice">No selected reference is available. This is not a certification of legal correctness. Read the extracted document and review detection limitations.</p>}</></EvidencePane>}
    footer={<WorkspaceFooterBar status={`${doc.metrics.unreviewed} unreviewed · ${doc.metrics.unresolved} unresolved · ${doc.metrics.unavailable} unavailable`} session={dirty ? 'Unsaved changes — save before leaving' : 'Single-reviewer beta · original document unchanged'} />}
  />
}
