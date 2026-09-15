import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  AssessmentNote,
  ClaimRail,
  DecisionRow,
  DocumentPane,
  EvidencePane,
  MachineStatement,
  WorkspaceFooterBar,
  WorkspaceLayout,
  WorkspaceSubHeader,
  type DecisionAction,
  type MachineRow,
  type RailFilter,
} from '@/components/workspace/WorkspaceLayout'
import { Divider } from '@/components/ui/Card'
import { CLAIMS, CLAIM_COUNTS, DOCUMENT, type Claim } from '@/data/claims'
import type { VerificationStatus } from '@/components/ui/StatusPill'
import { DRAFT_PARAGRAPHS } from '@/data/draft'
import { cn } from '@/lib/cn'

/**
 * Figma: 07 · Workspace — Could Not Be Verified (node 27:63).
 * Same three-pane workspace as 05, in the state where no source could be located
 * for the active reference — LiTL says so plainly and records where it looked.
 */

/** The active reference is the one the dataset marks as unlocatable (node 27:137). */
const ACTIVE_CLAIM: Claim =
  CLAIMS.find((claim) => claim.status === 'Could not be verified') ?? CLAIMS[0]

const REVIEWED = 7

/** Decisions already recorded in this session, as the rail shows them (node 27:106). */
const RECORDED: Partial<Record<string, VerificationStatus>> = {
  '05': 'Confirmed',
}

const NEEDS_REVIEW = CLAIM_COUNTS['Requires review'] + CLAIM_COUNTS['Could not be verified']

const FILTERS: RailFilter[] = [
  { label: `All · ${CLAIMS.length}`, active: true },
  { label: `Needs review · ${NEEDS_REVIEW}` },
  { label: `Done · ${REVIEWED}` },
]

/** The record of where LiTL searched, and what it did and did not match (node 27:228). */
const MACHINE_ROWS: MachineRow[] = [
  { label: 'Searched:', value: 'Indian Kanoon · connected repositories' },
  { label: 'Case name:', value: 'match found (2021 SCC OnLine SC 3302)' },
  { label: 'Reporter:', value: '(2022) 10 SCC 51 — no consistent match' },
]

/** Retry affordances on the carbon block (nodes 27:230, 27:232). */
const RETRY_ACTIONS = ['Search again', 'Edit citation'] as const

/** The two bordered decisions of the action row (nodes 27:243, 27:245). */
const DECISIONS: DecisionAction[] = [
  { label: '✎  Correct citation', tone: 'correct', to: '/workspace/complete' },
  { label: '✕  Reject', tone: 'reject', to: '/workspace/complete' },
]

/** Each claim opens the workspace variant that matches its verification state. */
function routeForClaim(claim: Claim): string {
  const status = RECORDED[claim.id] ?? claim.status
  if (status === 'Could not be verified') return '/workspace/unverified'
  if (status === 'Requires review') return '/workspace/quote-mismatch'
  return '/workspace/evidence'
}

/**
 * Figma: "Honest Note" (node 27:234) — the caution that a null result is not a
 * finding of falsity. Local to this frame; the shared callout has no rule or tone.
 */
function HonestNote({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex w-full shrink-0 flex-col gap-[6px] rounded-[8px] border-l-[3px] border-red bg-paper py-[12px] pr-[12px] pl-[14px]">
      <p className="text-[9.5px] font-semibold tracking-[1.14px] whitespace-nowrap text-red">
        {label}
      </p>
      <p className="text-[12px] leading-[1.55] text-ink">{children}</p>
    </div>
  )
}

/** Figma: node 27:229 — the machine block's paired retry links. */
function RetryRow() {
  return (
    <div className="flex shrink-0 flex-wrap items-start gap-[10px]">
      {RETRY_ACTIONS.map((label) => (
        <button
          key={label}
          type="button"
          className="inline-flex cursor-pointer items-center rounded-[6px] border border-yellow-500/60 px-[12px] py-[7px] font-mono text-[11.5px] font-bold text-yellow-500 transition-colors hover:bg-yellow-500/10"
        >
          {label}
        </button>
      ))}
    </div>
  )
}

/** Figma: node 27:248 — the full-width filled "leave unresolved" decision. */
function LeaveUnresolvedAction({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className={cn(
        'flex w-full shrink-0 items-center justify-center rounded-[8px] bg-slate py-[11px]',
        'text-center text-[12.5px] font-semibold text-white transition-colors hover:bg-carbon-700',
      )}
    >
      {label}
    </Link>
  )
}

export function WorkspaceUnverifiedScreen() {
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
          activeId={ACTIVE_CLAIM.id}
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
          overline={`REFERENCE ${ACTIVE_CLAIM.id} · ${ACTIVE_CLAIM.kind.toUpperCase()}`}
          title="Satender Kumar Antil v. CBI"
          subtitle={ACTIVE_CLAIM.source}
          closeTo="/summary"
        >
          <MachineStatement tone="unverified" label="COULD NOT BE VERIFIED" rows={MACHINE_ROWS}>
            <RetryRow />
          </MachineStatement>

          <HonestNote label="WHAT THIS MEANS">
            “Could not be verified” is not “fake.” Older judgments, unreported decisions, tribunal
            orders and regional sources may simply be unavailable to LiTL. The item stays visible
            either way.
          </HonestNote>

          <Divider className="shrink-0" />

          <AssessmentNote label="LAWYER ASSESSMENT — PENDING">
            You may know this authority from practice. Verify it your own way, correct the citation,
            or leave it unresolved — it will be flagged in the report.
          </AssessmentNote>

          {/* Decisions — node 27:241: two bordered choices, then one full-width. */}
          <div className="flex w-full shrink-0 flex-col gap-[10px]">
            <DecisionRow actions={DECISIONS} />
            <LeaveUnresolvedAction
              to="/workspace/complete"
              label="◌  Leave unresolved — flag in report"
            />
          </div>
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

export default WorkspaceUnverifiedScreen
