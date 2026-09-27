import type { AnalysisScope, AssessmentMetrics, Metrics } from '@/lib/api'
import { label } from '@/lib/api'
import { Card } from './Card'

const metricNames = {
  source_coverage: 'Source location coverage',
  citation_consistency: 'Citation identity consistency',
  quotation_fidelity: 'Quotation fidelity',
  review_completion: 'Review completion',
  resolution_coverage: 'Resolution coverage',
  source_activity: 'Source-link activity',
  evidence_provenance: 'Evidence provenance',
} as const
const metricDescriptions: Record<keyof typeof metricNames, string> = {
  source_coverage: 'Uniquely located sources / detected references. Location does not establish support for an argument.',
  citation_consistency: 'Consistent case identities / identities actually checked. Missing metadata is not a failed check.',
  quotation_fidelity: 'Normalized wording matches / quotations actually compared. Read the source context too.',
  review_completion: 'Any saved human decision / detected references, including decisions left unresolved.',
  resolution_coverage: 'Confirmed, corrected or rejected / detected references. Rejection is a disposition, not validation.',
  source_activity: 'Distinct source URLs with a recorded open action / distinct linked source URLs.',
  evidence_provenance: 'Checked references with complete source URLs, timestamps and locators / checked references.',
}
function AssessmentCards({ assessment, scope, showAll }: { assessment: AssessmentMetrics; scope?: AnalysisScope | null; showAll: boolean }) {
  const counts = assessment.counts
  const cards = Object.entries(assessment.metrics).filter(([, metric]) => showAll || metric.denominator > 0)
  return <div className="stack">
    <div>
      <h2 className="type-h3">Evidence and review calculations</h2>
      <p className="text-small text-slate">Formula version: {assessment.definition_version}. Percentages = 100 × numerator / denominator; no denominator means N/A, not zero or full verification.</p>
    </div>
    <p className="text-small">{counts.processed} processed findings: {counts.case_citations} case citations ({counts.distinct_case_labels} distinct labels), {counts.quotations} quotations, {counts.statutory_references} statutory references.</p>
    {scope ? <p className="notice">{scope.detected} detected before the processing limit · {scope.processed} processed · {scope.deferred} deferred. Selection: {scope.selection}; limit {scope.processing_limit}. Undetected references are not measured.</p> : <p className="notice">The pre-limit detection count was not recorded for this older analysis. Metrics cover processed findings only; run a new analysis to record detection and deferral counts.</p>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{cards.map(([key, metric]) => <Card key={key} className="stack break-inside-avoid p-4">
      <h3 className="text-small text-slate">{metric.label}</h3>
      <p className="font-display text-h2">{metric.denominator === 0 || metric.percentage === null ? 'N/A' : `${metric.percentage}%`}</p>
      <p className="text-small">{metric.numerator} / {metric.denominator}</p>
      <p className="text-small"><code>100 × ({metric.formula})</code></p>
      <p className="text-small text-slate">{metric.description}</p>
    </Card>)}</div>
    <p className="text-small">{counts.unreviewed} unreviewed · {counts.unresolved} unresolved · {counts.case_citations - counts.assessed_identities} inconclusive case assessments · {counts.quotations - counts.compared_quotes} quotations not compared.</p>
    <p className="text-small text-slate">Statutes are detected but not independently verified. Metrics are exact counts of these processed findings, not sample-based accuracy estimates, confidence intervals, or a combined legal-correctness score. Source-link activity records clicks, not reading.</p>
  </div>
}

export function MetricCards({ metrics, scope, showAll = false }: { metrics: Metrics; scope?: AnalysisScope | null; showAll?: boolean }) {
  if (metrics.assessment) return <AssessmentCards assessment={metrics.assessment} scope={scope} showAll={showAll} />
  const cards = (Object.keys(metricNames) as Array<keyof typeof metricNames>).filter((key) => {
    const metric = metrics[key]
    return showAll || (metric.denominator > 0 && metric.percentage !== null)
  })
  return <div>
    {cards.length > 0 && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map((key) => {
      const metric = metrics[key]
      return <Card key={key} className="p-4"><p className="text-small text-slate">{metricNames[key]}</p><p className="mt-2 font-display text-h2">{metric.denominator === 0 || metric.percentage === null ? 'N/A' : `${metric.percentage}%`}</p><p className="text-small">{metric.numerator} / {metric.denominator}</p><p className="mt-2 text-small text-slate">{metricDescriptions[key]}</p></Card>
    })}</div>}
    <p className="mt-3 text-small text-slate">Metrics cover detected references only, not all legal claims. Source-link activity records clicks, not reading. No metric is a legal-correctness grade.</p>
    <p className="mt-2 text-small">{metrics.total} detected · {metrics.unreviewed} unreviewed · {metrics.unresolved} unresolved · {metrics.ambiguous} ambiguous · {metrics.unavailable} unavailable</p>
    <p className="mt-2 text-small">{(['unsupported', 'not_found', 'not_checked', 'quote_mismatch'] as const).filter((key) => metrics[key] !== undefined).map((key) => `${metrics[key]} ${label(key)}`).join(' · ')}</p>
  </div>
}
export function MachineBadge({ status }: { status: string }) {
  return <span className={`badge ${status === 'source_found' ? 'bg-blue-tint text-blue' : status === 'quote_mismatch' ? 'bg-red-tint text-red' : 'bg-amber-tint text-amber'}`}>Machine: {label(status)}</span>
}
export function DecisionBadge({ decision }: { decision: string | null }) {
  return <span className="badge bg-neutral-tint text-ink">Human: {decision ? label(decision) : 'unreviewed'}</span>
}
