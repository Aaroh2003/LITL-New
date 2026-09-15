// Uses an already installed Chrome/Chromium via its DevTools pipe. No downloads.
import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import http from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const frontend = process.env.LITL_TEST_FRONTEND_URL || 'http://127.0.0.1:5173'
const api = process.env.LITL_TEST_API_URL || 'http://127.0.0.1:8000'
const chromePath = process.env.LITL_CHROME_PATH ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
for (const origin of [frontend, api]) {
  const url = new URL(origin)
  assert(['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname),
    'Browser smoke tests are restricted to loopback services.')
  assert.equal(url.protocol, 'http:', 'Use a local HTTP development service.')
}

function apiRequest(method, path, data) {
  return new Promise((resolve, reject) => {
    const payload = data === undefined ? undefined : JSON.stringify(data)
    const request = http.request(new URL(path, api), {
      method,
      headers: payload ? {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      } : {},
    }, (response) => {
      let body = ''
      response.setEncoding('utf8')
      response.on('data', (chunk) => { body += chunk })
      response.on('end', () => {
        if (response.statusCode >= 400) {
          reject(new Error(`${method} ${path}: ${response.statusCode} ${body}`))
        } else {
          resolve(body ? JSON.parse(body) : null)
        }
      })
    })
    request.setTimeout(15000, () => request.destroy(new Error('API timeout')))
    request.on('error', reject)
    request.end(payload)
  })
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const config = await apiRequest('GET', '/v1/config')
assert.equal(config.auth_mode, 'local')
assert.equal(config.source_lookup_configured, false,
  'Disable the provider so this test cannot consume API credits.')

const profile = await mkdtemp(join(tmpdir(), 'litl-browser-smoke-'))
const title = `Synthetic browser draft ${Date.now()}`
const draftText = ['Synthetic', 'document', 'illustration', '\u{1f4c4}.', 'PUBLIC', 'SAMPLE', '(For', 'layout', 'review', 'only.)'].join('\n\n') +
  '\n\nSection\n41A\nCrPC\nis\nmentioned.\n\n' +
  'Arnesh Kumar v. State of Bihar, (2014) 8 SCC 273 is cited.'
let browser
let documentId
try {
  browser = spawn(chromePath, [
    '--headless=new', '--remote-debugging-pipe', '--no-first-run',
    '--no-default-browser-check', '--disable-background-networking',
    `--user-data-dir=${profile}`, 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] })

  const pending = new Map()
  const exceptions = []
  let nextId = 0
  let buffered = ''
  browser.on('error', (error) => {
    for (const { reject } of pending.values()) reject(error)
  })
  browser.stdio[4].setEncoding('utf8')
  browser.stdio[4].on('data', (chunk) => {
    buffered += chunk
    let boundary
    while ((boundary = buffered.indexOf('\0')) !== -1) {
      const raw = buffered.slice(0, boundary)
      buffered = buffered.slice(boundary + 1)
      if (!raw) continue
      const message = JSON.parse(raw)
      if (message.id && pending.has(message.id)) {
        const { resolve, reject, timer } = pending.get(message.id)
        pending.delete(message.id)
        clearTimeout(timer)
        if (message.error) reject(new Error(JSON.stringify(message.error)))
        else resolve(message.result)
      }
      if (message.method === 'Runtime.exceptionThrown') {
        exceptions.push(message.params.exceptionDetails)
      }
    }
  })
  function command(method, params = {}, sessionId) {
    return new Promise((resolve, reject) => {
      const id = ++nextId
      const timer = setTimeout(() => {
        pending.delete(id)
        reject(new Error(`Browser command timed out: ${method}`))
      }, 15000)
      pending.set(id, { resolve, reject, timer })
      browser.stdio[3].write(JSON.stringify({ id, method, params, sessionId }) + '\0')
    })
  }

  const { targetId } = await command('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await command('Target.attachToTarget', { targetId, flatten: true })
  await command('Runtime.enable', {}, sessionId)
  await command('Page.enable', {}, sessionId)
  await command('Emulation.setDeviceMetricsOverride', {
    width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false,
  }, sessionId)
  const evaluate = async (expression) => {
    const result = await command('Runtime.evaluate', {
      expression, returnByValue: true, awaitPromise: true,
    }, sessionId)
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
    return result.result.value
  }
  async function visit(path, expectedText) {
    await command('Page.navigate', { url: new URL(path, frontend).href }, sessionId)
    const deadline = Date.now() + 15000
    let text = ''
    while (Date.now() < deadline) {
      text = await evaluate('document.body ? document.body.innerText : ""')
      if (text.includes(expectedText)) {
        assert.equal(exceptions.length, 0, JSON.stringify(exceptions))
        console.log(`Rendered ${path}`)
        return
      }
      await sleep(150)
    }
    throw new Error(`Missing "${expectedText}" on ${path}. Rendered body:\n${text}`)
  }
  async function waitFor(expression) {
    const deadline = Date.now() + 15000
    while (Date.now() < deadline) {
      const value = await evaluate(expression)
      if (value) return value
      await sleep(150)
    }
    throw new Error(`Browser condition did not become true: ${expression}`)
  }
  async function readingLayout(selector) {
    return evaluate(`(() => {
      const article = document.querySelector(${JSON.stringify(selector)});
      const paragraphs = Array.from(article.querySelectorAll('p'));
      const firstText = paragraphs[0].firstChild;
      const firstWord = document.createRange();
      firstWord.setStart(firstText, 0);
      firstWord.setEnd(firstText, 'Synthetic'.length);
      const nextWord = document.createRange();
      const nextStart = firstText.textContent.indexOf('document');
      nextWord.setStart(firstText, nextStart);
      nextWord.setEnd(firstText, nextStart + 'document'.length);
      return {
        blocks: paragraphs.length,
        text: article.innerText,
        whitespace: paragraphs.map(p => getComputedStyle(p).whiteSpace),
        highlight: article.querySelector('[data-selected-reference]')?.textContent,
        firstWordTop: firstWord.getBoundingClientRect().top,
        nextWordTop: nextWord.getBoundingClientRect().top,
        firstParagraphHeight: paragraphs[0].getBoundingClientRect().height,
      };
    })()`)
  }
  function assertReadingLayout(reading) {
    assert.equal(reading.blocks, 3, 'Word fragments separated by blank lines must rejoin.')
    assert(reading.whitespace.every(value => value === 'normal'), 'Extraction line breaks must reflow.')
    assert(reading.text.includes('Synthetic document illustration'), 'Words must read together on a line.')
    assert(Math.abs(reading.firstWordTop - reading.nextWordTop) < 1, 'Consecutive words must visibly sit on the same line.')
    assert(reading.firstParagraphHeight < 120, 'A short sentence must not become a tall word-per-line column.')
    assert(!/Paragraph \d|Page \d/.test(reading.text), 'Repeated location labels must not interrupt the reading view.')
  }

  await visit('/', 'LiTL')
  await visit('/upload', 'Bring the draft')
  await evaluate(`Array.from(document.querySelectorAll('button')).find(button => button.textContent === 'Paste text').click()`)
  await waitFor("document.querySelector('textarea') !== null")
  await evaluate(`(() => {
    const titleInput = document.querySelector('form input:not([type="checkbox"])');
    const textInput = document.querySelector('textarea');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(titleInput, ${JSON.stringify(title)});
    titleInput.dispatchEvent(new Event('input', {bubbles: true}));
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(textInput,
      ${JSON.stringify(draftText)});
    textInput.dispatchEvent(new Event('input', {bubbles: true}));
    document.querySelector('input[type="checkbox"]').click();
  })()`)
  await evaluate("document.querySelector('form').requestSubmit()")
  documentId = await waitFor("location.pathname.match(/^\\/documents\\/([^/]+)\\/(?:analysis|summary)$/)?.[1]")
  let document = await apiRequest('GET', `/v1/documents/${documentId}`)
  const deadline = Date.now() + 30000
  while (document.latest_run?.status !== 'completed' && Date.now() < deadline) {
    assert(!['failed', 'cancelled'].includes(document.latest_run?.status),
      JSON.stringify(document.latest_run))
    await sleep(200)
    document = await apiRequest('GET', `/v1/documents/${documentId}`)
  }
  assert.equal(document.latest_run?.status, 'completed')
  assert(document.findings.length > 0)
  await visit('/documents', title)
  await visit(`/documents/${documentId}/summary`, title)
  await visit(`/documents/${documentId}/review/${document.findings[0].id}`, title)
  await waitFor("document.querySelector('form select') !== null")
  const reading = await readingLayout('article[aria-label="Document reading view"]')
  assertReadingLayout(reading)
  assert.equal(reading.highlight, document.findings[0].excerpt, 'Unicode citation offsets must remain correct.')
  assert.equal(document.text, draftText, 'Reflow must not change the stored source text.')
  if (process.env.LITL_TEST_SCREENSHOT) {
    const screenshot = await command('Page.captureScreenshot', { format: 'png' }, sessionId)
    await writeFile(process.env.LITL_TEST_SCREENSHOT, Buffer.from(screenshot.data, 'base64'))
  }
  await evaluate(`(() => {
    const decision = document.querySelector('form select');
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(decision, 'unresolved');
    decision.dispatchEvent(new Event('change', {bubbles: true}));
    const note = document.querySelectorAll('form textarea')[1];
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(note, 'Synthetic browser review; source unavailable.');
    note.dispatchEvent(new Event('input', {bubbles: true}));
  })()`)
  await evaluate("document.querySelector('form').requestSubmit()")
  await waitFor("document.body.innerText.includes('Review saved.')")
  const reviewed = await apiRequest('GET', `/v1/documents/${documentId}`)
  assert.equal(reviewed.findings[0].decision, 'unresolved')
  assert.equal(reviewed.metrics.review_completion.numerator, 1)
  await visit(`/documents/${documentId}/reports`, title)
  await evaluate(`Array.from(document.querySelectorAll('button')).find(button => button.textContent === 'Save current report snapshot').click()`)
  const reportId = await waitFor("location.pathname.match(/^\\/documents\\/[^/]+\\/reports\\/([^/]+)$/)?.[1]")
  const report = await apiRequest('GET', `/v1/documents/${documentId}/reports/${reportId}`)
  assert.equal(report.document.findings[0].decision, 'unresolved')
  await visit(`/documents/${documentId}/reports/${reportId}`, title)
  const reportSelector = 'article[aria-label="Snapshot document reading view"]'
  assertReadingLayout(await readingLayout(reportSelector))
  await command('Emulation.setEmulatedMedia', { media: 'print' }, sessionId)
  assertReadingLayout(await readingLayout(reportSelector))
  await command('Emulation.setEmulatedMedia', { media: 'screen' }, sessionId)
  assert.deepEqual(await apiRequest('GET', `/v1/documents/${documentId}/reports/${reportId}`), report,
    'Reading-layout changes must not mutate the saved snapshot or JSON export.')
  if (process.env.LITL_TEST_REPORT_SCREENSHOT) {
    await evaluate(`document.querySelector(${JSON.stringify(reportSelector)}).scrollIntoView({block: 'center'})`)
    const screenshot = await command('Page.captureScreenshot', { format: 'png' }, sessionId)
    await writeFile(process.env.LITL_TEST_REPORT_SCREENSHOT, Buffer.from(screenshot.data, 'base64'))
  }

  await command('Emulation.setDeviceMetricsOverride', {
    width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
  }, sessionId)
  await visit(`/documents/${documentId}/review/${document.findings[0].id}`, title)
  const sizes = await evaluate(
    '({scroll: document.documentElement.scrollWidth, viewport: window.innerWidth})',
  )
  assert(sizes.scroll <= sizes.viewport + 2, `Mobile horizontal overflow: ${JSON.stringify(sizes)}`)
  console.log('Local browser smoke flow passed, including narrow-screen review.')
} finally {
  try {
    if (!documentId) {
      const documents = await apiRequest('GET', '/v1/documents')
      documentId = documents.find((document) => document.title === title)?.id
    }
    if (documentId) await apiRequest('DELETE', `/v1/documents/${documentId}`)
  } finally {
    if (browser && browser.exitCode === null) {
      browser.kill('SIGTERM')
      await new Promise((resolve) => {
        browser.once('exit', resolve)
        const timeout = setTimeout(() => {
          browser.kill('SIGKILL')
          resolve()
        }, 5000)
        timeout.unref()
      })
    }
    // Only remove the isolated profile this test created, never a user's profile.
    await rm(profile, { recursive: true, force: true })
  }
}
