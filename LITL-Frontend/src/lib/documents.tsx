import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { Outlet, useParams } from 'react-router-dom'
import { useAuth } from './auth'
import { ApiError, errorMessage, type Document, type Finding, type Run } from './api'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'

export function useResource<T>(path: string, poll?: (value: T) => boolean) {
  const { api } = useAuth()
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const reload = useCallback(() => setRevision((n) => n + 1), [])
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    setError('')
    api<T>(path, { signal: controller.signal }).then((value) => {
      if (controller.signal.aborted) return
      setData(value)
      if (poll?.(value)) timer = setTimeout(reload, 2500)
    }).catch((cause) => {
      if (!controller.signal.aborted) {
        if (cause instanceof ApiError && [401, 403, 404, 410].includes(cause.status)) setData(null)
        setError(errorMessage(cause))
      }
    })
    return () => { controller.abort(); clearTimeout(timer) }
  }, [api, path, revision, poll, reload])
  return { data, setData, error, reload }
}
const active = (doc: Document) => ['queued', 'processing'].includes(doc.latest_run?.status || '') ||
  ['queued', 'processing'].includes(doc.ai_summary?.status || '') ||
  doc.findings.some((finding) => finding.ai_explanation?.status === 'processing' &&
    finding.ai_explanation.started_at * 1000 + 120000 > Date.now())
type DocumentState = { doc: Document; reload: () => void; updateFinding: (finding: Finding) => void; updateRun: (run: Run) => void }
const DocumentContext = createContext<DocumentState | null>(null)
function DocumentLoader({ documentId }: { documentId: string }) {
  const { data: doc, setData, error, reload } = useResource<Document>(`/v1/documents/${encodeURIComponent(documentId)}`, active)
  if (!doc) return <AppShell><div className="page"><h1 className="type-h2">Document</h1><p role={error ? 'alert' : 'status'}>{error || 'Loading document… Free hosting can take about a minute to wake up.'}</p>{error && <Button onClick={reload}>Retry</Button>}<ButtonLink to="/documents" variant="secondary">All documents</ButtonLink></div></AppShell>
  return <DocumentContext.Provider value={{ doc, reload, updateRun: (run) => {
    setData((current) => current ? { ...current, latest_run: run } : current)
    reload()
  }, updateFinding: (finding) => {
    setData((current) => current ? { ...current, findings: current.findings.map((item) => item.id === finding.id ? finding : item) } : current)
    reload()
  } }}>
    {error && <div className="notice error" role="alert">{error} <Button size="sm" onClick={reload}>Retry refresh</Button></div>}
    <Outlet />
  </DocumentContext.Provider>
}
export function DocumentRoutes() {
  const { documentId = '' } = useParams()
  return <DocumentLoader key={documentId} documentId={documentId} />
}
export function useDocument() {
  const value = useContext(DocumentContext)
  if (!value) throw new Error('Document provider missing')
  return value
}
