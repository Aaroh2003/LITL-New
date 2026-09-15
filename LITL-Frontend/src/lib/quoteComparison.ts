export type ComparedWord = { text: string; changed: boolean }

const MAX_WORDS = 300

export function compareQuoteWords(draft: string, source: string) {
  const draftWords = draft.trim().split(/\s+/u).filter(Boolean)
  const sourceWords = source.trim().split(/\s+/u).filter(Boolean)
  const left = draftWords.slice(0, MAX_WORDS)
  const right = sourceWords.slice(0, MAX_WORDS)
  const lengths = Array.from({ length: left.length + 1 }, () => new Uint16Array(right.length + 1))
  for (let i = left.length - 1; i >= 0; i--) {
    for (let j = right.length - 1; j >= 0; j--) {
      lengths[i][j] = left[i] === right[j]
        ? lengths[i + 1][j + 1] + 1
        : Math.max(lengths[i + 1][j], lengths[i][j + 1])
    }
  }
  const draftResult: ComparedWord[] = left.map((text) => ({ text, changed: true }))
  const sourceResult: ComparedWord[] = right.map((text) => ({ text, changed: true }))
  let i = 0
  let j = 0
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) {
      draftResult[i++].changed = false
      sourceResult[j++].changed = false
    } else if (lengths[i + 1][j] >= lengths[i][j + 1]) {
      i++
    } else {
      j++
    }
  }
  return {
    draft: draftResult,
    source: sourceResult,
    truncated: draftWords.length > MAX_WORDS || sourceWords.length > MAX_WORDS,
  }
}
