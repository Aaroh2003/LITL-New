import {
  ClaimRail,
  DocumentPane,
  WorkspaceFooterBar,
  WorkspaceLayout,
  type RailFilter,
} from '@/components/workspace/WorkspaceLayout'
import { ButtonLink } from '@/components/ui/Button'
import type { VerificationStatus } from '@/components/ui/StatusPill'
import { CLAIMS, DOCUMENT, type Claim } from '@/data/claims'
import { DRAFT_PARAGRAPHS } from '@/data/draft'
import { cn } from '@/lib/cn'

/**
 * Figma: 08 · Workspace — Review Complete (node 29:73).
 * Every verification point has been decided; the evidence pane is replaced by the
 * completion panel and the sub-header state pill turns green.
 */

/** Node 29:78 — the context-bar pill for this variant. */
const STATE = 'Review complete'

/** The single reference the reviewer rejected (node 29:213 tallies 1 rejected). */
const REJECTED_ID = '12'

/**
 * The decision recorded against every reference at the end of the session
 * (rail items 29:101 – 29:163): quotations flagged for review were corrected,
 * the citation that could not be verified was left unresolved, one located
 * source was rejected, and the rest were confirmed.
 */
const DECISIONS: Partial<Record<string, VerificationStatus>> = Object.fromEntries(
  CLAIMS.map((claim): [string, VerificationStatus] => {
    if (claim.id === REJECTED_ID) return [claim.id, 'Rejected']
    if (claim.status === 'Requires review') return [claim.id, 'Corrected']
    if (claim.status === 'Could not be verified') return [claim.id, 'Unresolved']
    return [claim.id, 'Confirmed']
  }),
)

function tally(status: VerificationStatus): number {
  return CLAIMS.filter((claim) => DECISIONS[claim.id] === status).length
}

const CONFIRMED = tally('Confirmed')
const CORRECTED = tally('Corrected')
const REJECTED = tally('Rejected')
const UNRESOLVED = tally('Unresolved')

const OUTCOME_LINE = `${CONFIRMED} confirmed · ${CORRECTED} corrected · ${REJECTED} rejected · ${UNRESOLVED} unresolved`
const REVIEWED_LABEL = `${DOCUMENT.referenceCount} of ${DOCUMENT.referenceCount} reviewed`

const FILTERS: RailFilter[] = [
  { label: `All · ${DOCUMENT.referenceCount}`, active: true },
  { label: 'Needs review · 0' },
  { label: `Done · ${DOCUMENT.referenceCount}` },
]

/** The reference still open at the end of the review (node 29:233). */
const OPEN_ITEM: Claim | undefined = CLAIMS.find((claim) => DECISIONS[claim.id] === 'Unresolved')

/** Node 29:234 — the tail of the recorded event log. */
const EVENTS: Array<{ time: string; detail: string }> = [
  { time: '14:32:11', detail: 'Ref 07 · Confirmed · source opened · 2m 41s' },
  { time: '14:29:40', detail: 'Ref 06 · Corrected · quote aligned to para 8' },
  { time: '14:27:03', detail: 'Ref 09 · Left unresolved · flagged for report' },
]

/** The yellow glow the Figma CTAs carry (nodes 29:83, 29:245). */
const GLOW = 'shadow-[0px_4px_22px_0px] shadow-yellow-500/40'

/* -------------------------------------------------------------------------- */
/* Screen-local sub-header — node 29:75                                        */
/* -------------------------------------------------------------------------- */

/**
 * Same shape as the shared `WorkspaceSubHeader`, but this frame states a
 * completed review: a green state pill and a filled yellow report action.
 */
function CompleteSubHeader() {
  return (
    <div className="flex w-full shrink-0 flex-wrap items-center gap-[10px] border-b border-mist bg-white px-[16px] py-[12px] sm:gap-[14px] sm:px-[24px] lg:px-[40px]">
      <p className="min-w-0 max-w-full truncate text-[14px] font-semibold text-ink sm:max-w-[360px]">{DOCUMENT.fileName}</p>
      <span className="rounded-pill bg-green-tint px-[10px] py-[3px] text-[11px] font-semibold whitespace-nowrap text-green">
        {STATE}
      </span>
      <div className="hidden min-w-px flex-1 sm:block" />
      <p className="text-[13px] font-medium whitespace-nowrap text-slate">{REVIEWED_LABEL}</p>
      <div className="h-[6px] w-[80px] shrink-0 overflow-hidden rounded-[3px] bg-mist sm:w-[120px]">
        <div className="h-full w-full rounded-[3px] bg-yellow-500" />
      </div>
      <ButtonLink
        to="/report"
        size="sm"
        className={cn(
          'bg-yellow-500! px-[16px]! py-[8px]! text-[12.5px]! text-carbon-900! hover:bg-yellow-500/90',
          GLOW,
        )}
      >
        Generate report
      </ButtonLink>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Screen-local completion panel — node 29:176                                 */
/* -------------------------------------------------------------------------- */

function ReviewCompletePanel() {
  return (
    <section className="flex h-auto min-h-[420px] w-full shrink-0 flex-col items-center gap-[11px] overflow-y-auto border-t border-mist bg-white px-[16px] py-[18px] sm:px-[26px] lg:h-full lg:min-h-0 lg:w-[408px] lg:border-t-0 lg:border-l">
      <p className="text-[10.5px] font-semibold tracking-[1.47px] whitespace-nowrap text-green">
        REVIEW COMPLETE
      </p>

      {/* Check — node 29:227 */}
      <div className="flex size-[64px] shrink-0 items-center justify-center rounded-pill bg-green-tint">
        <span className="text-[26px] font-semibold text-green" aria-hidden>
          ✓
        </span>
      </div>

      <h2 className="shrink-0 text-center font-display text-[21px] font-bold text-carbon-900">
        All {DOCUMENT.referenceCount} references reviewed.
      </h2>
      <p className="shrink-0 text-center font-mono text-[12px] text-slate">{OUTCOME_LINE}</p>

      {/* Unresolved Warning — node 29:231 */}
      {OPEN_ITEM ? (
        <div className="flex w-full shrink-0 flex-col gap-[5px] rounded-[8px] bg-red-tint py-[12px] pr-[12px] pl-[14px]">
          <p className="text-[10px] font-semibold tracking-[0.8px] whitespace-pre text-red">
            {`⚠  ${UNRESOLVED} ITEM REMAINS UNRESOLVED`}
          </p>
          <p className="text-[11.5px] leading-[1.5] text-ink">
            Ref {OPEN_ITEM.id} · {OPEN_ITEM.label} — reporter citation could not be matched. It will
            appear prominently in the report, not in a footnote.
          </p>
        </div>
      ) : null}

      {/* Recorded Events — node 29:234 */}
      <div className="flex w-full shrink-0 flex-col gap-[8px] rounded-[8px] bg-paper py-[14px] pr-[12px] pl-[14px]">
        <p className="text-[9.5px] font-semibold tracking-[1.14px] whitespace-nowrap text-slate-soft">
          RECORDED EVENTS — LATEST
        </p>
        {EVENTS.map((event) => (
          <div key={event.time} className="flex shrink-0 items-start gap-[10px] font-mono text-[10.5px]">
            <span className="whitespace-nowrap text-slate-soft">{event.time}</span>
            <span className="text-ink">{event.detail}</span>
          </div>
        ))}
      </div>

      {/* Generate CTA — node 29:245 */}
      <ButtonLink
        to="/report"
        className={cn(
          'w-full shrink-0 rounded-[8px]! bg-yellow-500! py-[13px]! text-[14px]! text-carbon-900! hover:bg-yellow-500/90',
          GLOW,
        )}
      >
        {'Generate Verification Report  →'}
      </ButtonLink>

      <p className="w-full max-w-[330px] shrink-0 text-center text-[11px] leading-[1.45] text-slate-soft">
        The report records the process. It does not certify legal correctness.
      </p>
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* Screen                                                                      */
/* -------------------------------------------------------------------------- */

export function WorkspaceCompleteScreen() {
  return (
    <WorkspaceLayout
      subHeader={<CompleteSubHeader />}
      rail={
        <ClaimRail
          claims={CLAIMS}
          activeId=""
          decisions={DECISIONS}
          filters={FILTERS}
          count={DOCUMENT.referenceCount}
        />
      }
      document={
        <DocumentPane
          court={DOCUMENT.court}
          title={DOCUMENT.title}
          paragraphs={DRAFT_PARAGRAPHS}
          footnote={`Page ${DOCUMENT.currentPage} of ${DOCUMENT.pageCount} · highlighted spans are detected references`}
        />
      }
      evidence={<ReviewCompletePanel />}
      footer={
        <WorkspaceFooterBar
          status={`${REVIEWED_LABEL} · ${OUTCOME_LINE}`}
          session={`Review session 15:12 · ${DOCUMENT.reviewer}`}
        />
      }
    />
  )
}

export default WorkspaceCompleteScreen
