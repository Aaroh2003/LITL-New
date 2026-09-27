import assert from 'node:assert/strict'
import test from 'node:test'
import { googleReferenceFirstResultUrl, referenceSegments, referenceUrl, safeIkUrl } from '../src/lib/referenceLinks.ts'
import type { Finding } from '../src/lib/api.ts'

function finding(start: number, end: number, overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'reference-1', run_id: 'run', kind: 'case_citation', label: 'Citation', excerpt: 'Citation',
    start, end, page: 1, paragraph_id: 'p0', status: 'source_found', note: '', sources: [],
    decision: null, review_note: '', correction: '', version: 0, source_opened: false,
    link_state: 'matched', reference_url: 'https://indiankanoon.org/doc/123/', ...overrides,
  }
}

test('only numeric retrieved Indian Kanoon destinations are accepted', () => {
  assert.equal(safeIkUrl('https://indiankanoon.org/doc/123/'), 'https://indiankanoon.org/doc/123/')
  for (const url of ['javascript:alert(1)', 'http://indiankanoon.org/doc/123/', 'https://attacker.test/doc/123/',
    'https://indiankanoon.org@attacker.test/doc/123/', 'https://indiankanoon.org/doc/123/#invented', null]) {
    assert.equal(safeIkUrl(url), null)
  }
})

test('ambiguous and bare statutory references never get guessed hyperlinks', () => {
  assert.equal(referenceUrl(finding(0, 8, { link_state: 'candidates' })), null)
  assert.equal(referenceUrl(finding(0, 8, { kind: 'statutory_reference', link_state: 'missing_context' })), null)
  assert.equal(referenceUrl(finding(0, 8)), 'https://indiankanoon.org/doc/123/')
})

test('Unicode code-point offsets and selected reference are preserved', () => {
  const text = '😀 Alpha v. Beta, then Section 335.'
  const refs = [finding(2, 15), finding(22, 33, { id: 'reference-2', kind: 'statutory_reference', link_state: 'missing_context' })]
  const segments = referenceSegments(text, 0, refs, refs[0])
  assert.equal(segments.map(s => s.text).join(''), text)
  assert.equal(segments.filter(s => s.selected).map(s => s.text).join(''), 'Alpha v. Beta')
  assert.equal(segments.find(s => s.finding?.id === 'reference-2')?.text, 'Section 335')
})

test('overlapping references are rendered as flat segments without losing text', () => {
  const text = 'Alpha v. Beta'
  const refs = [finding(0, 13), finding(0, 13, { id: 'quote', kind: 'quotation' })]
  const segments = referenceSegments(text, 0, refs)
  assert.equal(segments.map(s => s.text).join(''), text)
  assert(segments.every(s => s.finding?.id === 'reference-1'))
})

test('references crossing reading blocks retain local offsets', () => {
  const ref = finding(4, 18)
  const segments = referenceSegments('v. Beta rest', 11, [ref])
  assert.equal(segments[0].text, 'v. Beta')
  assert.equal(segments[0].finding?.id, ref.id)
})

test('Google fallback requests the first result without claiming a verified evidence URL', () => {
  const value = 'Alpha & Beta\nv. State (2014) 8 SCC 273'
  const result = googleReferenceFirstResultUrl(value)
  assert(result)
  const url = new URL(result)
  assert.equal(url.origin, 'https://www.google.com')
  assert.equal(url.pathname, '/search')
  assert.equal(url.searchParams.get('q'), 'site:indiankanoon.org/doc/ Alpha & Beta v. State (2014) 8 SCC 273')
  assert.equal(url.searchParams.get('btnI'), '1')
  assert.equal([...url.searchParams.keys()].length, 2)
  assert.equal(safeIkUrl(result), null)
  assert.equal(googleReferenceFirstResultUrl('  '), null)
  assert.equal(googleReferenceFirstResultUrl('a'.repeat(301)), null)
})
