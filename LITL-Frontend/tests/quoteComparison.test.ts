import assert from 'node:assert/strict'
import test from 'node:test'
import { compareQuoteWords } from '../src/lib/quoteComparison.ts'

test('identical quotations have no changed words', () => {
  const result = compareQuoteWords('Bail is the rule.', 'Bail is the rule.')
  assert(result.draft.every((word) => !word.changed))
  assert(result.source.every((word) => !word.changed))
})

test('negation and numeric changes remain visible', () => {
  const result = compareQuoteWords('Arrest is mandatory within 7 days.', 'Arrest is not mandatory within 14 days.')
  assert.deepEqual(result.draft.filter((word) => word.changed).map((word) => word.text), ['7'])
  assert.deepEqual(result.source.filter((word) => word.changed).map((word) => word.text), ['not', '14'])
})

test('reordering is not treated as identical wording', () => {
  const result = compareQuoteWords('A precedes B', 'B precedes A')
  assert(result.draft.some((word) => word.changed))
  assert(result.source.some((word) => word.changed))
})

test('whitespace differences do not hide changed punctuation', () => {
  const result = compareQuoteWords('Bail\nis  permitted.', 'Bail is permitted!')
  assert.deepEqual(result.draft.filter((word) => word.changed).map((word) => word.text), ['permitted.'])
})

test('empty and Unicode input are supported', () => {
  assert.deepEqual(compareQuoteWords('', '').draft, [])
  const result = compareQuoteWords('Liberty 📄 matters', 'Liberty 📄 matters')
  assert(result.draft.every((word) => !word.changed))
})

test('long comparisons are bounded and disclose truncation', () => {
  const result = compareQuoteWords(Array(400).fill('word').join(' '), 'word')
  assert.equal(result.truncated, true)
  assert.equal(result.draft.length, 300)
})
