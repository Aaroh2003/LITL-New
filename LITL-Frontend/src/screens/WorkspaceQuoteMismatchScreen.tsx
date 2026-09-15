import {
  AssessmentNote,
  ClaimRail,
  DocumentPane,
  EvidencePane,
  MachineStatement,
  WorkspaceFooterBar,
  WorkspaceLayout,
  WorkspaceSubHeader,
  type DecisionAction,
  type RailFilter,
} from '@/components/workspace/WorkspaceLayout'
import { Divider } from '@/components/ui/Card'
import { CLAIMS, CLAIM_COUNTS, DOCUMENT, type Claim } from '@/data/claims'
import type { VerificationStatus } from '@/components/ui/StatusPill'
import { DRAFT_PARAGRAPHS } from '@/data/draft'
import { cn } from '@/lib/cn'

/**
 * Figma: 06 · Workspace — Quote Mismatch (node 25:53).
 * Same three-pane workspace as 05, but the active reference is a quotation
 * whose wording does not match the located source passage.
 */

const ACTIVE_ID = '06'
const REVIEWED = 7

/** Decisions already recorded in this session, as the rail shows them (node 25:96). */
const RECORDED: Partial<Record<string, VerificationStatus>> = {
  '05': 'Confirmed',
}

const NEEDS_REVIEW = CLAIM_COUNTS['Requires review'] + CLAIM_COUNTS['Could not be verified']

const FILTERS: RailFilter[] = [
  { label: `All · ${CLAIMS.length}`, active: true },
  { label: `Needs review · ${NEEDS_REVIEW}` },
  { label: `Done · ${REVIEWED}` },
]

/** Reference 06 — the quotation under review (rail row 25:99, panel 25:211). */
const ACTIVE_CLAIM: Claim = CLAIMS.find((claim) => claim.id === ACTIVE_ID) ?? CLAIMS[0]

/** The source passage the system located for the quotation (node 25:224). */
const SOURCE_PASSAGE =
  '“No arrest should be made only because the offence is non-bailable and cognizable and therefore, lawful for the police officers to do so.”'

const DECISIONS: DecisionAction[] = [
  { label: '✓  Confirm', tone: 'confirm', to: '/workspace/unverified' },
  { label: '✎  Correct quote', tone: 'correct', to: '/workspace/unverified' },
  { label: '✕  Reject', tone: 'reject', to: '/workspace/unverified' },
  { label: '◌  Leave unresolved', tone: 'unresolved', to: '/workspace/unverified' },
]

/** Each claim opens the workspace variant that matches its verification state. */
function routeForClaim(claim: Claim): string {
  const status = RECORDED[claim.id] ?? claim.status
  if (status === 'Could not be verified') return '/workspace/unverified'
  if (status === 'Requires review') return '/workspace/quote-mismatch'
  return '/workspace/evidence'
}

/**
 * Figma: "Comparison" (node 25:218) — one half of the drafted-vs-source pair.
 * The rule and the overline carry the diff signal: amber for the draft's
 * wording, green for the wording the source actually uses.
 */
function ComparisonQuote({
  label,
  quote,
  tone,
}: {
  label: string
  quote: string
  tone: 'draft' | 'source'
}) {
  return (
    <div
      className={cn(
        'flex w-full shrink-0 flex-col gap-[5px] rounded-[8px] border-l-[3px] bg-paper py-[11px] pr-[12px] pl-[14px]',
        tone === 'draft' ? 'border-amber' : 'border-green',
      )}
    >
      <p
        className={cn(
          'text-[9.5px] font-semibold tracking-[1.14px] whitespace-nowrap',
          tone === 'draft' ? 'text-amber' : 'text-green',
        )}
      >
        {label}
      </p>
      <p className="font-mono text-[11.5px] leading-[1.5] italic text-ink">{quote}</p>
    </div>
  )
}

/** Figma: "Review Signal" (node 25:225) — the non-blocking review-time observation. */
function ReviewSignal({ label, children }: { label: string; children: string }) {
  return (
    <div className="flex w-full shrink-0 flex-col gap-[6px] rounded-[8px] bg-amber-tint py-[12px] pr-[12px] pl-[14px]">
      <p className="text-[10px] font-semibold tracking-[0.8px] whitespace-pre text-amber">{label}</p>
      <p className="text-[11.5px] leading-[1.5] text-gold-ink">{children}</p>
    </div>
  )
}

export function WorkspaceQuoteMismatchScreen() {
  return (
    <WorkspaceLayout
      subHeader={
        <WorkspaceSubHeader
          fileName={DOCUMENT.fileName}
          state={DOCUMENT.state}
          reviewedLabel={`${REVIEWED} of ${DOCUMENT.referenceCount} reviewed`}
          progress={REVIEWED / DOCUMENT.referenceCount}
          actionLabel="Generate report"
          actionTo="/report"
        />
      }
      rail={
        <ClaimRail
          claims={CLAIMS}
          activeId={ACTIVE_ID}
          decisions={RECORDED}
          filters={FILTERS}
          linkForClaim={routeForClaim}
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
      evidence={
        <EvidencePane
          overline="REFERENCE 06 · QUOTATION"
          title={ACTIVE_CLAIM.excerpt}
          subtitle={ACTIVE_CLAIM.source}
          closeTo="/summary"
          actions={DECISIONS}
          /* Node 25:211 sets this quotation title at 16.5px with an Inter attribution line. */
          className="[&_h2]:text-[16.5px]! [&_h2]:leading-[1.35]! [&_h2+p]:font-sans! [&_h2+p]:text-[11.5px]!"
        >
          <MachineStatement tone="review" label="SOURCE LOCATED — WORDING DIFFERS">
            <p className="font-mono text-[11.5px] leading-[1.65] text-slate-soft">
              {ACTIVE_CLAIM.note}
            </p>
          </MachineStatement>

          <div className="flex w-full shrink-0 flex-col gap-[8px]">
            <ComparisonQuote
              tone="draft"
              label="THE DRAFT QUOTES"
              quote={ACTIVE_CLAIM.excerpt}
            />
            <ComparisonQuote
              tone="source"
              label="THE SOURCE SAYS · PARA 8"
              quote={SOURCE_PASSAGE}
            />
          </div>

          <ReviewSignal label="⚠  QUICK REVIEW — OBSERVATION">
            Review time: 2.4s · Source opened: no. Consider opening the source before confirming.
            Nothing is blocked — this observation is recorded beside your decision.
          </ReviewSignal>

          <Divider className="shrink-0" />

          <AssessmentNote label="LAWYER ASSESSMENT — PENDING">{null}</AssessmentNote>
        </EvidencePane>
      }
      footer={
        <WorkspaceFooterBar
          status={`${REVIEWED} of ${DOCUMENT.referenceCount} reviewed · 1 left unresolved so far`}
          session={`Review session 08:41 · ${DOCUMENT.reviewer}`}
        />
      }
    />
  )
}

export default WorkspaceQuoteMismatchScreen
