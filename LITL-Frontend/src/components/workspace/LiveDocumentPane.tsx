import { useEffect, useRef, useState } from 'react'
import { errorMessage, type Document, type Finding } from '@/lib/api'
import { DocumentReadingText } from './DocumentReadingText'
import { useAuth } from '@/lib/auth'
import { referenceUrl } from '@/lib/referenceLinks'
import { useDocument } from '@/lib/documents'
import { IndianKanoonAttribution } from './SourceLinks'

export function LiveDocumentPane({ doc, finding }: { doc: Document; finding?: Finding }) {
  const container = useRef<HTMLDivElement>(null)
  const { api } = useAuth()
  const { reload } = useDocument()
  const [activityError, setActivityError] = useState('')
  async function open(finding: Finding) {
    const source = finding.sources.find(s => s.url === referenceUrl(finding))
    if (!source) return
    try {
      await api(`/v1/documents/${doc.id}/findings/${finding.id}/source-open`, {
        method: 'POST', body: JSON.stringify({ source_id: source.id }),
      })
      setActivityError('')
      reload()
    } catch (cause) { setActivityError(`Source opened, but activity could not be recorded: ${errorMessage(cause)}`) }
  }
  useEffect(() => {
    container.current?.querySelector('[data-selected-reference]')?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [finding?.id])
  return <section aria-label="Extracted document" className="min-w-0 flex-1 overflow-y-auto bg-paper p-5 lg:p-7" ref={container}>
    <div className="mb-5">
      <h2 className="type-h3">Document</h2>
      <p className="text-small text-slate break-words">{doc.file_name}</p>
      <p className="mt-1 text-small text-slate">Click a matched reference to open Indian Kanoon. Dotted links open its review panel. Selected citation highlighted.</p>
      {doc.findings.some(f => referenceUrl(f)) && <IndianKanoonAttribution />}
      {activityError && <p role="alert" className="notice error">{activityError}</p>}
    </div>
    <article aria-label="Document reading view" className="mx-auto max-w-[72ch] rounded-card border border-mist bg-white p-5 font-serif text-[16px] leading-[1.85] shadow-card lg:p-6">
      <DocumentReadingText text={doc.text} highlight={finding} references={doc.findings} documentId={doc.id} onOpen={finding => void open(finding)} />
    </article>
  </section>
}
