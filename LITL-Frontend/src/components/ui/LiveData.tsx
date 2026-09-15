import type { Metrics } from '@/lib/api'
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
export function MetricCards({ metrics }: { metrics: Metrics }) {
  return <div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Object.entries(metricNames).map(([key, title]) => {
      const metric = metrics[key as keyof typeof metricNames]
      return <Card key={key} className="p-4"><p className="text-small text-slate">{title}</p><p className="mt-2 font-display text-h2">{metric.denominator === 0 || metric.percentage === null ? 'N/A' : `${Math.round(metric.percentage * 10) / 10}%`}</p><p className="text-small">{metric.numerator} / {metric.denominator}</p><p className="mt-2 text-small text-slate">{metricDescriptions[key as keyof typeof metricNames]}</p></Card>
    })}</div>
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
