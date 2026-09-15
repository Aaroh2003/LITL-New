export type ReadingBlock = { text: string; start: number; end: number }

export function documentReadingBlocks(text: string): ReadingBlock[] {
  const blocks: ReadingBlock[] = []
  let position = 0
  // Keep source offsets intact: reflow affects presentation, not saved evidence.
  for (const part of text.split(/(\n[ \t]*\n(?:[ \t]*\n)*)/u)) {
    const end = position + Array.from(part).length
    if (part.trim()) blocks.push({ text: part, start: position, end })
    position = end
  }
  const points = Array.from(text)
  const reading: ReadingBlock[] = []
  for (let index = 0; index < blocks.length;) {
    const first = blocks[index]
    let next = index
    // Some PDFs put a blank line between every word, not just every paragraph.
    while (next < blocks.length && !/\s/u.test(blocks[next].text.trim())) next++
    if (next - index > 1) {
      const end = blocks[next - 1].end
      reading.push({ text: points.slice(first.start, end).join(''), start: first.start, end })
      index = next
    } else {
      reading.push(first)
      index++
    }
  }
  return reading
}
