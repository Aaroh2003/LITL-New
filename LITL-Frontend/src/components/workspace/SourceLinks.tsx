import type { Source } from '@/lib/api'
import { date, safeSourceUrl } from '@/lib/api'
import { compareQuoteWords } from '@/lib/quoteComparison'
import { googleReferenceFirstResultUrl } from '@/lib/referenceLinks'

export function GoogleReferenceSearch({ query }: { query: string }) {
  const href = googleReferenceFirstResultUrl(query)
  return href ? <p className="text-small">
    <a href={href} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" className="text-blue underline">Open first Google result (unverified) ↗</a>
    <span className="block text-slate">Requests the first Indian Kanoon result. Google may show a redirect confirmation or search page. Ranking is not verification; no Gemini API call is made.</span>
  </p> : null
}

export function IndianKanoonAttribution() {
  return <a href="https://indiankanoon.org/" target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" className="self-start" aria-label="powered by IKanoon">
    <picture>
      <source media="(max-width: 640px)" srcSet="https://api.indiankanoon.org/static/pics/ikanoon_mobile_powered_transparent.png" />
      <img src="https://api.indiankanoon.org/static/pics/ikanoon6_powered_transparent.png" alt="powered by IKanoon" referrerPolicy="no-referrer" className="max-w-none" />
    </picture>
  </a>
}

function QuoteComparison({ draft, source }: { draft: string; source: string }) {
  const comparison = compareQuoteWords(draft, source)
  return <details className="text-small">
    <summary className="cursor-pointer font-semibold">Compare quotation wording</summary>
    <p className="my-2 text-slate">Word-order comparison against this retrieved passage, not a judgment of meaning. Whitespace is normalized; numbers, negation and punctuation are preserved.</p>
    <p className="font-semibold">Draft — changed or missing words highlighted</p>
    <p className="my-2 break-words">{comparison.draft.map((word, index) => <span key={index} className={word.changed ? 'bg-amber-tint text-ink underline decoration-amber' : undefined}>{word.text}{' '}</span>)}</p>
    <p className="font-semibold">Source — different or additional words highlighted</p>
    <p className="my-2 break-words">{comparison.source.map((word, index) => <span key={index} className={word.changed ? 'bg-blue-tint text-ink underline decoration-blue' : undefined}>{word.text}{' '}</span>)}</p>
    {comparison.truncated && <p className="notice">Comparison limited to the first 300 words on each side. Read the full excerpts and original source for the remaining context.</p>}
  </details>
}

export function SourceLinks({ sources, onOpen, draftQuote, emptyMessage, candidates = false, searchQuery }: { sources: Source[]; onOpen?: (source: Source) => void; draftQuote?: string; emptyMessage?: string; candidates?: boolean; searchQuery?: string }) {
  const search = searchQuery ? <GoogleReferenceSearch query={searchQuery} /> : null
  if (!sources.length) return <div className="stack"><p className="notice">{emptyMessage || 'No source passage is available. An unavailable or unchecked source is not evidence of a fabricated citation.'}</p>{search}</div>
  return <div className="stack">{search}{candidates && <p className="notice">Possible matches only — no single source has been established for this reference.</p>}{sources.map((source) => {
    const href = safeSourceUrl(source.url)
    const isIndianKanoon = href && ['indiankanoon.org', 'www.indiankanoon.org'].includes(new URL(href).hostname)
    return <section key={source.id} className="stack rounded-card border border-mist p-4">
      {isIndianKanoon && <IndianKanoonAttribution />}
      <h3 className="font-semibold break-words">{source.title}</h3>
      <p className="text-small text-slate">{source.repository} · {source.locator || 'No passage locator supplied'}<br />Retrieved {date(source.retrieved_at)}</p>
      <blockquote className="whitespace-pre-wrap break-words rounded bg-passage-mark p-3 text-small">{source.passage || 'No passage available.'}</blockquote>
      {draftQuote && source.passage && <QuoteComparison draft={draftQuote} source={source.passage} />}
      {href ? <a className="source-link break-all text-small font-semibold text-blue underline" href={href} target="_blank" rel="noopener noreferrer" onClick={() => onOpen?.(source)} onAuxClick={(event) => { if (event.button === 1) onOpen?.(source) }}>Open judgment source ↗<span className="block font-normal">{href}</span></a> : <p className="text-small text-red">Source URL is missing or is not a safe HTTPS link.</p>}
    </section>
  })}<p className="text-small text-slate">{onOpen ? 'Opening a link records source-link activity, not reading, comprehension or agreement. Browser context-menu actions may not be recorded.' : 'These snapshot links do not update recorded source-link activity. Recorded activity does not prove reading or agreement.'}</p></div>
}
