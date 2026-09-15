import assert from 'node:assert/strict'
import test from 'node:test'
import { documentReadingBlocks } from '../src/lib/documentReading.ts'

test('word-per-line extraction becomes one continuous reading block', () => {
  const text = 'The\napplicant\nrelies\non\nSection\n41A\nCrPC.'
  const blocks = documentReadingBlocks(text)
  assert.equal(blocks.length, 1)
  assert.equal(blocks[0].text, text)
  assert.deepEqual([blocks[0].start, blocks[0].end], [0, text.length])
})

test('blank lines between every word are extraction fragments, not paragraphs', () => {
  const text = ['PUBLIC', 'SAMPLE', '(For', 'layout', 'review', '|', 'Not', 'legal', 'advice)'].join('\n\n')
  const blocks = documentReadingBlocks(text)
  assert.equal(blocks.length, 1)
  assert.deepEqual(blocks[0], { text, start: 0, end: Array.from(text).length })
})

test('word fragments rejoin without flattening surrounding real paragraphs', () => {
  const heading = 'PUBLIC\n\nSAMPLE\n\nNOTICE'
  const paragraph = 'The applicant relies on the cited judgment.'
  const footer = 'For\n \t\nillustration\n\nonly.'
  const blocks = documentReadingBlocks(`${heading}\n\n${paragraph}\n\n${footer}`)
  assert.deepEqual(blocks.map((block) => block.text), [heading, paragraph, footer])
})

test('fragmented citation highlights retain offsets after emoji and blank lines', () => {
  const text = '\u{1f4c4}\n\nSynthetic\n\nSection\n\n41A\n\nCrPC'
  const block = documentReadingBlocks(text)[0]
  const points = Array.from(text)
  const start = points.indexOf('S', 4 + 'Synthetic'.length)
  assert.equal(Array.from(block.text).slice(start - block.start).join(''), 'Section\n\n41A\n\nCrPC')
  assert.equal(block.end, points.length)
})

test('many word fragments are grouped as a single reading block', () => {
  const text = Array(5000).fill('word').join('\n\n')
  const blocks = documentReadingBlocks(text)
  assert.equal(blocks.length, 1)
  assert.equal(blocks[0].text, text)
})

test('only blank lines create natural paragraph spacing', () => {
  const blocks = documentReadingBlocks('First line\ncontinues here.\n\nSecond paragraph.')
  assert.deepEqual(blocks.map((block) => block.text), ['First line\ncontinues here.', 'Second paragraph.'])
})

test('citation offsets stay valid after Unicode and blank-line separators', () => {
  const text = 'Illustration \u{1f4c4}\nfirst line.\n \t\n\nSection 41A\nCrPC applies.'
  const points = Array.from(text)
  const blocks = documentReadingBlocks(text)
  assert.equal(blocks.length, 2)
  for (const block of blocks) {
    assert.equal(points.slice(block.start, block.end).join(''), block.text)
  }
  const start = points.findIndex((_, index) => points.slice(index, index + 7).join('') === 'Section')
  const excerpt = 'Section 41A\nCrPC'
  const block = blocks[1]
  assert.equal(Array.from(block.text).slice(start - block.start, start - block.start + excerpt.length).join(''), excerpt)
})

test('a selection spanning reading blocks retains the original text on each side', () => {
  const text = 'Start citation\n\ncontinues here.'
  const start = 6
  const end = 25
  const selected = documentReadingBlocks(text).filter((block) => start < block.end && end > block.start)
    .map((block) => Array.from(block.text).slice(Math.max(0, start - block.start), Math.min(block.end, end) - block.start).join(''))
  assert.deepEqual(selected, ['citation', 'continues'])
})

test('empty separators do not create labelled or empty blocks', () => {
  assert.deepEqual(documentReadingBlocks(' \n\n\t\n'), [])
  assert.deepEqual(documentReadingBlocks('\n\nText\n\n').map((block) => block.text), ['Text'])
})
