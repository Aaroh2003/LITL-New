import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { useAuth } from '@/lib/auth'
import { errorMessage, type Document } from '@/lib/api'

export default function UploadScreen() {
  const { api, config } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'file' | 'text'>('file')
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState('')
  const [error, setError] = useState('')
  const [pendingId, setPendingId] = useState('')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  if (!config) return null
  const count = Array.from(text).length
  async function discard() {
    if (!pendingId || !window.confirm('Delete the incomplete upload?')) return
    setBusy(true); setError('')
    try { await api(`/v1/documents/${pendingId}`, { method: 'DELETE' }); setPendingId(''); setStage('Incomplete upload deleted.') } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!config || !consent) return
    setError('')
    if (mode === 'text' && (!text.trim() || count > config.max_characters)) { setError('Enter non-empty text within the character limit.'); return }
    if (mode === 'file' && (!file || file.size === 0 || file.size > config.max_file_bytes || !/\.(pdf|docx|txt)$/i.test(file.name))) { setError('Choose a non-empty PDF, DOCX or TXT within the file size limit.'); return }
    const operation = new AbortController()
    controller.current = operation
    setBusy(true)
    try {
      let doc: Document
      if (mode === 'text') {
        setStage('Submitting text…')
        doc = await api<Document>('/v1/documents/text', { method: 'POST', signal: operation.signal, body: JSON.stringify({ title: title.trim() || 'Untitled document', text, consent: true }) })
      } else if (config.storage_mode === 'local') {
        setStage('Uploading file to your local API…')
        const body = new FormData()
        body.set('file', file!); body.set('consent', 'true')
        doc = await api<Document>('/v1/documents/file', { method: 'POST', signal: operation.signal, body })
      } else {
        if (pendingId) {
          const existing = await api<Document>(`/v1/documents/${pendingId}`, { signal: operation.signal })
          if (existing.latest_run) {
            if (!operation.signal.aborted) navigate(`/documents/${existing.id}/analysis`)
            return
          }
          setStage('Removing the previous incomplete upload before retry…')
          await api(`/v1/documents/${pendingId}`, { method: 'DELETE', signal: operation.signal })
          setPendingId('')
        }
        setStage('Preparing private storage upload…')
        const upload = await api<{ document_id: string; upload_url: string; upload_headers: Record<string, string> }>('/v1/uploads', { method: 'POST', signal: operation.signal, body: JSON.stringify({ file_name: file!.name, size: file!.size, consent: true }) })
        if (operation.signal.aborted) return
        setPendingId(upload.document_id)
        setStage('Uploading directly to private storage…')
        const uploadUrl = new URL(upload.upload_url)
        if (uploadUrl.protocol !== 'https:') throw new Error('The API returned an unsafe storage URL. Upload stopped.')
        const result = await fetch(uploadUrl, { method: 'PUT', headers: upload.upload_headers, body: file!, signal: operation.signal })
        if (!result.ok) throw new Error(`Storage upload failed (${result.status}). Retry or delete the incomplete upload.`)
        setStage('Finalizing upload and queuing analysis…')
        doc = await api<Document>(`/v1/documents/${upload.document_id}/finalize`, { method: 'POST', signal: operation.signal })
      }
      if (!operation.signal.aborted) navigate(`/documents/${doc.id}/analysis`)
    } catch (cause) {
      if (!operation.signal.aborted) setError(`${errorMessage(cause)} If a request was interrupted after reaching the server, check Documents before resubmitting.`)
    } finally { if (!operation.signal.aborted) { setBusy(false); controller.current = null } }
  }
  return <AppShell><div className="page narrow"><h1 className="type-h2">Bring the draft. Keep the judgment.</h1><p className="text-slate">English Indian legal documents. Deterministic detection of case citations, statutory references and quotations; not comprehensive legal analysis.</p>
    <Card className="p-6"><div className="row mb-5"><Button variant={mode === 'file' ? 'primary' : 'secondary'} disabled={busy || !!pendingId} onClick={() => setMode('file')}>Upload file</Button><Button variant={mode === 'text' ? 'primary' : 'secondary'} disabled={busy || !!pendingId} onClick={() => setMode('text')}>Paste text</Button></div>
      <form onSubmit={submit} className="stack">
        {mode === 'file' ? <label>PDF, DOCX or TXT<input type="file" accept=".pdf,.docx,.txt" disabled={busy || !!pendingId} onChange={(event) => setFile(event.target.files?.[0] || null)} /><span className="text-small text-slate">{file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : 'Choose a text-based document.'}</span></label> : <><label>Document title<input value={title} maxLength={200} disabled={busy} onChange={(event) => setTitle(event.target.value)} /></label><label>Document text<textarea rows={12} required disabled={busy} value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste public, synthetic or fully anonymized legal text…" /><span className={count > config.max_characters ? 'text-red text-small' : 'text-small text-slate'}>{count.toLocaleString()} / {config.max_characters.toLocaleString()} characters</span></label></>}
        <p className="text-small text-slate">Maximum {(config.max_file_bytes / 1024 / 1024).toFixed(0)} MB, {config.max_pages} extracted pages, {config.max_characters.toLocaleString()} characters. Scanned/image-only or encrypted PDFs and OCR are unsupported. Original files are never edited.</p>
        {!config.source_lookup_configured && <p className="notice">External source lookup is not configured. References can be detected and reviewed, but unavailable sources are not verified.</p>}
        <label className="flex items-start gap-3"><input className="mt-1 shrink-0" type="checkbox" checked={consent} disabled={busy} required onChange={(event) => setConsent(event.target.checked)} /><span>I confirm this is public, synthetic or fully anonymized content, including metadata and embedded content — not confidential client/company data. I consent to storage and processing by the configured hosting providers, and sending detected references/quotations to legal-source providers when enabled. Default retention is 7 days; cleanup can pause during hosting sleep. <ButtonLink to="/help" size="sm" variant="ghost">Read data limitations</ButtonLink></span></label>
        {error && <p className="notice error" role="alert">{error}</p>}
        {stage && <p role="status">{stage}</p>}
        <div className="row"><Button type="submit" disabled={busy || !consent}>{busy ? 'Working…' : pendingId ? 'Retry upload' : 'Upload and analyze'}</Button>{busy && <Button variant="secondary" onClick={() => { controller.current?.abort(); setBusy(false); setStage('Request cancelled. The server may already have accepted it; check Documents before retrying.') }}>Cancel request</Button>}{pendingId && !busy && <Button variant="danger" onClick={() => void discard()}>Delete incomplete upload</Button>}<ButtonLink to="/documents" variant="ghost">Documents</ButtonLink></div>
      </form>
    </Card><p className="text-small text-slate">Free API cold starts may take about a minute. Processing may pause when hosting sleeps. No background completion guarantee.</p>
  </div></AppShell>
}
