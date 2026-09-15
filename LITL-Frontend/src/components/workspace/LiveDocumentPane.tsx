import { useEffect, useRef } from 'react'
import type { Document, Finding } from '@/lib/api'
import { DocumentReadingText } from './DocumentReadingText'

export function LiveDocumentPane({ doc, finding }: { doc: Document; finding?: Finding }) {
  const container = useRef<HTMLDivElement>(null)
  useEffect(() => {
    container.current?.querySelector('[data-selected-reference]')?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [finding?.id])
  return <section aria-label="Extracted document" className="min-w-0 flex-1 overflow-y-auto bg-paper p-5 lg:p-7" ref={container}>
    <div className="mb-5">
      <h2 className="type-h3">Document</h2>
      <p className="text-small text-slate break-words">{doc.file_name}</p>
      <p className="mt-1 text-small text-slate">Reading view · selected citation highlighted</p>
    </div>
    <article aria-label="Document reading view" className="mx-auto max-w-[72ch] rounded-card border border-mist bg-white p-5 font-serif text-[16px] leading-[1.85] shadow-card lg:p-6">
      <DocumentReadingText text={doc.text} highlight={finding} />
    </article>
  </section>
}
