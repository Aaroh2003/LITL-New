import { Fragment, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { documentReadingBlocks } from '@/lib/documentReading'
import { referenceSegments, referenceUrl } from '@/lib/referenceLinks'
import type { Finding } from '@/lib/api'

type Highlight = { start: number; end: number }

function HighlightedText({ text, start, end }: { text: string } & Highlight) {
  const points = Array.from(text)
  if (start < 0 || end <= start || end > points.length) return <>{text}</>
  return <>{points.slice(0, start).join('')}<mark className="rounded bg-cite-mark px-0.5" data-selected-reference>{points.slice(start, end).join('')}</mark>{points.slice(end).join('')}</>
}

export function DocumentReadingText({ text, highlight, references, documentId, snapshot = false, onOpen }: {
  text: string; highlight?: Highlight; references?: Finding[]; documentId?: string; snapshot?: boolean
  onOpen?: (finding: Finding) => void
}) {
  const blocks = useMemo(() => documentReadingBlocks(text), [text])
  return <div className="space-y-5">
    {blocks.length ? blocks.map((block) => (
      <p key={block.start} className="whitespace-normal break-words">
        {references && documentId ? referenceSegments(block.text, block.start, references, highlight).map(segment => {
          const finding = segment.finding
          const selected = segment.selected
          const className = selected ? 'rounded bg-cite-mark px-0.5' : undefined
          if (!finding) return selected
            ? <mark key={segment.start} className={className} data-selected-reference>{segment.text}</mark>
            : <Fragment key={segment.start}>{segment.text}</Fragment>
          const url = referenceUrl(finding)
          return url
            ? <a key={segment.start} href={url} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer"
                data-selected-reference={selected || undefined} className={`${className || ''} text-blue underline`}
                title={finding.link_message || 'Open matched Indian Kanoon source'}
                onClick={() => onOpen?.(finding)} onAuxClick={event => { if (event.button === 1) onOpen?.(finding) }}>{segment.text}</a>
            : <Link key={segment.start} to={snapshot ? `#finding-${finding.id}` : `/documents/${encodeURIComponent(documentId)}/review/${finding.id}`}
                data-selected-reference={selected || undefined} className={`${className || ''} underline decoration-dotted`}
                title={finding.link_message || 'Inspect reference and source status'}>{segment.text}</Link>
        }) : highlight && highlight.start < block.end && highlight.end > block.start
          ? <HighlightedText text={block.text} start={Math.max(0, highlight.start - block.start)} end={Math.min(block.end, highlight.end) - block.start} />
          : block.text}
      </p>
    )) : <p className="text-slate">No extracted text available.</p>}
  </div>
}
