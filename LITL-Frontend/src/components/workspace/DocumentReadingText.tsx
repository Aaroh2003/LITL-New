import { useMemo } from 'react'
import { documentReadingBlocks } from '@/lib/documentReading'

type Highlight = { start: number; end: number }

function HighlightedText({ text, start, end }: { text: string } & Highlight) {
  const points = Array.from(text)
  if (start < 0 || end <= start || end > points.length) return <>{text}</>
  return <>{points.slice(0, start).join('')}<mark className="rounded bg-cite-mark px-0.5" data-selected-reference>{points.slice(start, end).join('')}</mark>{points.slice(end).join('')}</>
}

export function DocumentReadingText({ text, highlight }: { text: string; highlight?: Highlight }) {
  const blocks = useMemo(() => documentReadingBlocks(text), [text])
  return <div className="space-y-5">
    {blocks.length ? blocks.map((block) => (
      <p key={block.start} className="whitespace-normal break-words">
        {highlight && highlight.start < block.end && highlight.end > block.start
          ? <HighlightedText text={block.text} start={Math.max(0, highlight.start - block.start)} end={Math.min(block.end, highlight.end) - block.start} />
          : block.text}
      </p>
    )) : <p className="text-slate">No extracted text available.</p>}
  </div>
}
