import { useParams } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { DecisionBadge, MachineBadge, MetricCards } from '@/components/ui/LiveData'
import { IndianKanoonAttribution, SourceLinks } from '@/components/workspace/SourceLinks'
import { DocumentReadingText } from '@/components/workspace/DocumentReadingText'
import { useResource } from '@/lib/documents'
import { date, label, type Report } from '@/lib/api'
import { AiSummaryContent } from '@/components/workspace/AiSummaryPanel'
import { googleReferenceFirstResultUrl, referenceUrl } from '@/lib/referenceLinks'

function Snapshot({ documentId, reportId }: { documentId: string; reportId: string }) {
  const { data: report, error, reload } = useResource<Report>(`/v1/documents/${encodeURIComponent(documentId)}/reports/${encodeURIComponent(reportId)}`)
  const usage = report?.document.latest_run?.source_usage
  function download() {
    if (!report) return
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `litl-report-${report.id}.json`; anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <AppShell><div className="page report-page">
    <div className="row no-print"><ButtonLink to={`/documents/${documentId}/reports`} variant="secondary">All snapshots</ButtonLink>{report && <><Button onClick={download}>Download JSON</Button><Button variant="secondary" onClick={() => window.print()}>Print / save PDF</Button></>}</div>
    {error && <p role="alert" className="notice error">{error} <Button onClick={reload}>Retry</Button></p>}
    {!report && !error && <p role="status">Loading saved report…</p>}
    {report && <><header className="stack"><p className="type-overline text-gold-ink">LiTL · immutable review snapshot</p><h1 className="type-h2 break-words">{report.document.title}</h1><p>Saved {date(report.created_at)}</p><p className="text-small text-slate break-all">Report {report.id} · Analysis {report.document.latest_run?.id || 'not recorded'} · Document {report.document.id}</p></header>
      <p className="text-small text-slate">Single-reviewer record. No overall legal-correctness grade, senior approval or modification of the original file. This snapshot reflects saved decisions only.</p>
      {report.overview && <Card className="stack p-6">
        <h2 className="type-h3">{report.overview.title}</h2>
        <p>{report.overview.text}</p>
        {report.overview.attention.length > 0 && <><h3 className="font-semibold">Items needing attention</h3><ul className="list-disc pl-5">{report.overview.attention.map((item) => <li key={item.label}>{item.count} · {item.label}</li>)}</ul><p className="text-small text-slate">Attention categories overlap and must not be added into a risk score.</p></>}
        <p className="text-small text-slate">Generated from saved counts and decisions, not by an AI model.</p>
      </Card>}
      {usage && <Card className="stack p-6">
        <h2 className="type-h3">Indian Kanoon usage at snapshot</h2>
        <p><strong>{new Intl.NumberFormat('en-IN', { style: 'currency', currency: usage.currency }).format(usage.reserved_paise / 100)}</strong> reserved for {usage.priced_requests} priced request attempts.</p>
        <p className="text-small text-slate">{usage.requests_by_operation.search ?? 0} search requests · {usage.requests_by_operation.document ?? 0} document requests{usage.price_versions.length > 0 && ` · Price schedule: ${usage.price_versions.join(', ')}`}</p>
        <p className="text-small">Conservative reservation, not a confirmed provider charge or remaining account balance. Failed or uncertain requests keep their reservation. Reopening, downloading and printing this snapshot do not make paid API calls.</p>
        {usage.unpriced_requests > 0 && <p className="notice">{usage.unpriced_requests} older request attempts have no price records. The amount above is incomplete and excludes them.</p>}
      </Card>}
      <MetricCards metrics={report.document.metrics} scope={report.document.analysis_scope} showAll />
      {report.document.ai_summary ? <AiSummaryContent summary={report.document.ai_summary} snapshot /> : <p className="text-small text-slate">No AI summary was included in this snapshot.</p>}
      <h2 className="type-h3">Reference index</h2>
      <p className="text-small text-slate">Google fallback links request the first Indian Kanoon result. Google may require confirmation or show search results instead. These unverified links do not change verification metrics.</p>
      {report.document.findings.some(f => referenceUrl(f)) && <IndianKanoonAttribution />}
      <div className="stack">{report.document.findings.map(finding => {
        const url = referenceUrl(finding)
        const search = finding.kind !== 'quotation' ? googleReferenceFirstResultUrl(finding.label) : null
        return <p key={finding.id} className="text-small break-words">{url
          ? <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue underline">{finding.label} — {finding.link_message || 'Open source'}</a>
          : <a href={`#finding-${finding.id}`} className="underline decoration-dotted">{finding.label} — {finding.link_message || 'Inspect source status'}</a>}{search && <> · <a href={search} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" className="text-blue underline">First Google result (unverified)</a></>}</p>
      })}</div>
      <h2 className="type-h3">References, evidence and saved decisions</h2>
      {!report.document.findings.length && <p className="notice">No references were detected. This does not establish that the document is legally correct or free of references.</p>}
      {report.document.findings.map((finding, index) => <Card id={`finding-${finding.id}`} key={finding.id} className="stack p-6 report-finding">
        <h3 className="type-h3">{index + 1}. {finding.label}</h3>
        <div className="row"><MachineBadge status={finding.status} /><DecisionBadge decision={finding.decision} /></div>
        <p className="text-small">{label(finding.kind)} · {finding.page !== null ? `Page ${finding.page}` : finding.paragraph_id ? `Paragraph ${report.document.paragraphs.findIndex((p) => p.id === finding.paragraph_id) + 1}` : 'Document'} · Character offsets {finding.start}–{finding.end}</p>
        <blockquote className="whitespace-normal break-words rounded bg-cite-mark p-3">{finding.excerpt}</blockquote>
        <p><strong>Machine note:</strong> {finding.note}</p>
        <p className="whitespace-pre-wrap break-words"><strong>Proposed correction:</strong> {finding.correction || 'None recorded'}</p>
        <p className="whitespace-pre-wrap break-words"><strong>Human note:</strong> {finding.review_note || 'None recorded'}</p>
        <p className="text-small text-slate">Saved review version {finding.version} · Source-open activity at snapshot: {finding.source_opened ? 'recorded' : 'not recorded'}</p>
        <SourceLinks sources={finding.sources} searchQuery={finding.kind !== 'quotation' ? finding.label : undefined} candidates={finding.link_state === 'candidates'} emptyMessage={finding.evidence_message} draftQuote={finding.kind === 'quotation' ? finding.excerpt : undefined} />
      </Card>)}
      <h2 className="type-h3">Extracted document at snapshot</h2>
      <Card className="p-6">
        <article aria-label="Snapshot document reading view" className="mx-auto max-w-[72ch] font-serif text-[16px] leading-[1.85]">
          <DocumentReadingText text={report.document.text} references={report.document.findings} documentId={report.document.id} snapshot />
        </article>
      </Card>
      <h2 className="type-h3">Scope and limitations</h2>
      {report.schema_version && <p className="text-small text-slate">Report schema {report.schema_version} · Parser {report.parser_version} · Review versions and formulas frozen at snapshot creation.</p>}
      {report.input_sha256 && <p className="text-small text-slate break-all">Extracted-text SHA-256: {report.input_sha256}. A reproducibility identifier, not a certificate of authenticity.</p>}
      <p className="text-small text-slate">{report.disclaimer}</p>
      {report.document.latest_run?.warnings.map((warning, index) => <p className="text-small text-slate" key={index}>{warning}</p>)}
      <p className="text-small text-slate">Source links in this immutable report do not change saved activity. Downloaded reports are outside application retention/deletion controls; store and remove your copies responsibly.</p>
    </>}
  </div></AppShell>
}
export default function VerificationReportScreen() {
  const { documentId = '', reportId = '' } = useParams()
  return <Snapshot key={`${documentId}/${reportId}`} documentId={documentId} reportId={reportId} />
}
