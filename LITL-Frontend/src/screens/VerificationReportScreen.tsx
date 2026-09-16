import { useParams } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { DecisionBadge, MachineBadge, MetricCards } from '@/components/ui/LiveData'
import { SourceLinks } from '@/components/workspace/SourceLinks'
import { DocumentReadingText } from '@/components/workspace/DocumentReadingText'
import { useResource } from '@/lib/documents'
import { date, label, type Report } from '@/lib/api'

function Snapshot({ documentId, reportId }: { documentId: string; reportId: string }) {
  const { data: report, error, reload } = useResource<Report>(`/v1/documents/${encodeURIComponent(documentId)}/reports/${encodeURIComponent(reportId)}`)
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
      <MetricCards metrics={report.document.metrics} />
      <h2 className="type-h3">References, evidence and saved decisions</h2>
      {!report.document.findings.length && <p className="notice">No references were detected. This does not establish that the document is legally correct or free of references.</p>}
      {report.document.findings.map((finding, index) => <Card key={finding.id} className="stack p-6 report-finding"><h3 className="type-h3">{index + 1}. {finding.label}</h3><div className="row"><MachineBadge status={finding.status} /><DecisionBadge decision={finding.decision} /></div><p className="text-small">{label(finding.kind)} · {finding.page !== null ? `Page ${finding.page}` : finding.paragraph_id ? `Paragraph ${report.document.paragraphs.findIndex((p) => p.id === finding.paragraph_id) + 1}` : 'Document'} · Character offsets {finding.start}–{finding.end}</p><blockquote className="whitespace-normal break-words rounded bg-cite-mark p-3">{finding.excerpt}</blockquote><p><strong>Machine note:</strong> {finding.note}</p><p className="whitespace-pre-wrap break-words"><strong>Proposed correction:</strong> {finding.correction || 'None recorded'}</p><p className="whitespace-pre-wrap break-words"><strong>Human note:</strong> {finding.review_note || 'None recorded'}</p><p className="text-small text-slate">Saved review version {finding.version} · Source-open activity at snapshot: {finding.source_opened ? 'recorded' : 'not recorded'}</p><SourceLinks sources={finding.sources} draftQuote={finding.kind === 'quotation' ? finding.excerpt : undefined} /></Card>)}
      <h2 className="type-h3">Extracted document at snapshot</h2>
      <Card className="p-6">
        <article aria-label="Snapshot document reading view" className="mx-auto max-w-[72ch] font-serif text-[16px] leading-[1.85]">
          <DocumentReadingText text={report.document.text} />
        </article>
      </Card>
      <p className="text-small text-slate">Source links in this immutable report do not change saved activity. Downloaded reports are outside application retention/deletion controls; store and remove your copies responsibly.</p>
    </>}
  </div></AppShell>
}
export default function VerificationReportScreen() {
  const { documentId = '', reportId = '' } = useParams()
  return <Snapshot key={`${documentId}/${reportId}`} documentId={documentId} reportId={reportId} />
}
