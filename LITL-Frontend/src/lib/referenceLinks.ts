import type { Finding } from './api.ts'

export function googleReferenceFirstResultUrl(reference: string): string | null {
  const query = reference.trim().replace(/\s+/g, ' ')
  if (!query || Array.from(query).length > 300) return null
  const url = new URL('https://www.google.com/search')
  url.searchParams.set('q', `site:indiankanoon.org/doc/ ${query}`)
  url.searchParams.set('btnI', '1')
  return url.href
}

export function safeIkUrl(url: string | null | undefined): string | null {
  return url && /^https:\/\/indiankanoon\.org\/doc\/\d{1,20}\/$/.test(url) ? url : null
}

export function referenceUrl(finding: Finding): string | null {
  if (finding.link_state) return finding.link_state === 'matched' ? safeIkUrl(finding.reference_url) : null
  return ['source_found', 'quote_mismatch'].includes(finding.status) && finding.sources.length === 1
    ? safeIkUrl(finding.sources[0].url) : null
}

export function referenceSegments(text: string, blockStart: number, findings: Finding[], highlight?: { start: number; end: number }) {
  const points = Array.from(text)
  const blockEnd = blockStart + points.length
  const priority = { case_citation: 0, statutory_reference: 1, quotation: 2 }
  const relevant = findings.filter(f => f.start < blockEnd && f.end > blockStart && f.end > f.start)
    .sort((a, b) => priority[a.kind] - priority[b.kind] || a.start - b.start || a.end - b.end)
  const boundaries = new Set([0, points.length])
  for (const span of [...relevant, ...(highlight ? [highlight] : [])]) {
    if (span.start < blockEnd && span.end > blockStart) {
      boundaries.add(Math.max(0, span.start - blockStart))
      boundaries.add(Math.min(points.length, span.end - blockStart))
    }
  }
  const ordered = [...boundaries].sort((a, b) => a - b)
  return ordered.slice(0, -1).map((start, i) => {
    const end = ordered[i + 1]
    return {
      start, text: points.slice(start, end).join(''),
      finding: relevant.find(f => f.start <= blockStart + start && f.end >= blockStart + end),
      selected: !!highlight && highlight.start < blockStart + end && highlight.end > blockStart + start,
    }
  })
}
