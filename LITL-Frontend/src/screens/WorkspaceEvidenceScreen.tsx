import {
  AssessmentNote,
  ClaimRail,
  DocumentPane,
  EvidenceCallout,
  EvidencePane,
  EvidenceQuote,
  MachineStatement,
  WorkspaceFooterBar,
  WorkspaceLayout,
  WorkspaceSubHeader,
  type DecisionAction,
  type RailFilter,
} from '@/components/workspace/WorkspaceLayout'
import { Divider } from '@/components/ui/Card'
import { DRAFT_PARAGRAPHS } from '@/data/draft'
import { CLAIMS, CLAIM_COUNTS, DOCUMENT, type Claim } from '@/data/claims'
import type { VerificationStatus } from '@/components/ui/StatusPill'

/** Figma: 05 · Workspace — Evidence (node 17:43) — happy path, source found. */

const ACTIVE_ID = '07'
const REVIEWED = 7

/** Decisions already recorded in this session, as the rail shows them (node 17:114). */
const RECORDED: Partial<Record<string, VerificationStatus>> = {
  '05': 'Confirmed',
}

const NEEDS_REVIEW = CLAIM_COUNTS['Requires review'] + CLAIM_COUNTS['Could not be verified']

const FILTERS: RailFilter[] = [
  { label: `All · ${CLAIMS.length}`, active: true },
  { label: `Needs review · ${NEEDS_REVIEW}` },
  { label: `Done · ${REVIEWED}` },
]


/** Machine statement rows for reference 07 (node 23:67). */
const MACHINE_ROWS = [
  { label: 'Repository:', value: 'Indian Kanoon' },
  { label: 'Bench:', value: 'Supreme Court · 02 Jul 2014' },
  { label: 'Match:', value: 'case name and reporter citation consistent' },
]

const DECISIONS: DecisionAction[] = [
  { label: '✓  Confirm', tone: 'confirm', to: '/workspace/quote-mismatch' },
  { label: '✎  Correct', tone: 'correct', to: '/workspace/quote-mismatch' },
  { label: '✕  Reject', tone: 'reject', to: '/workspace/quote-mismatch' },
  { label: '◌  Leave unresolved', tone: 'unresolved', to: '/workspace/quote-mismatch' },
]

/** Each claim opens the workspace variant that matches its verification state. */
function routeForClaim(claim: Claim): string {
  const status = RECORDED[claim.id] ?? claim.status
  if (status === 'Could not be verified') return '/workspace/unverified'
  if (status === 'Requires review') return '/workspace/quote-mismatch'
  return '/workspace/evidence'
}

export function WorkspaceEvidenceScreen() {
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
          overline="REFERENCE 07 · CASE CITATION"
          title="Arnesh Kumar v. State of Bihar"
          subtitle="(2014) 8 SCC 469"
          closeTo="/summary"
          actions={DECISIONS}
        >
          <EvidenceCallout label="CITED IN SUPPORT OF">
            Notice under s.41A CrPC ought ordinarily to precede arrest for offences punishable up to
            seven years.
          </EvidenceCallout>

          <MachineStatement
            tone="found"
            label="SOURCE FOUND — MACHINE STATEMENT"
            rows={MACHINE_ROWS}
            action={{ label: 'Open source ↗', href: 'https://indiankanoon.org/' }}
          />

          <EvidenceQuote
            quote="“Arrest brings humiliation, curtails freedom… The attitude to arrest first and then proceed with the rest is despicable.”"
            attribution="— Arnesh Kumar judgment, para 13"
          />

          <Divider className="shrink-0" />

          <AssessmentNote label="LAWYER ASSESSMENT — PENDING">
            The system reports a source was located. Only you can mark this reference verified.
          </AssessmentNote>
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

export default WorkspaceEvidenceScreen
