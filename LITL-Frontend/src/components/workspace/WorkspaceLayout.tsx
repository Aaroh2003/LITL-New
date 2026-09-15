import { useEffect, useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { RAIL_LABELS, StatusPill, type VerificationStatus } from '@/components/ui/StatusPill'
import { Card } from '@/components/ui/Card'
import type { Claim } from '@/data/claims'
import { cn } from '@/lib/cn'

/**
 * Shared shell for the four review-workspace frames
 * (05 · Evidence 17:43, 06 · Quote Mismatch 25:53, 07 · Could Not Be Verified 27:63,
 * 08 · Review Complete 29:73). Screen files supply the slot content only.
 */

/* -------------------------------------------------------------------------- */
/* Sub-header                                                                  */
/* -------------------------------------------------------------------------- */

/** Figma: "Context Bar" (node 17:55) — file name, state pill, review progress, report action. */
export function WorkspaceSubHeader({
  fileName,
  state,
  reviewedLabel,
  /** 0 → 1; drives the yellow progress fill (node 17:62). */
  progress,
  actionLabel = 'Generate report',
  actionTo,
  onAction,
  className,
}: {
  fileName: string
  state: string
  reviewedLabel: string
  progress: number
  actionLabel?: string
  actionTo?: string
  onAction?: () => void
  className?: string
}) {
  const pct = Math.max(0, Math.min(1, progress)) * 100

  return (
    <div
      className={cn(
        'flex w-full shrink-0 flex-wrap items-center gap-[10px] border-b border-mist bg-white px-[16px] py-[12px] sm:gap-[14px] sm:px-[24px] lg:px-[40px]',
        className,
      )}
    >
      <p className="min-w-0 max-w-full truncate text-[14px] font-semibold text-ink sm:max-w-[360px]">
        {fileName}
      </p>
      <span className="rounded-pill bg-yellow-100 px-[10px] py-[3px] text-[11px] font-semibold whitespace-nowrap text-gold-ink">
        {state}
      </span>
      <div className="hidden min-w-px flex-1 sm:block" />
      <p className="text-[13px] font-medium whitespace-nowrap text-slate">{reviewedLabel}</p>
      <div className="h-[6px] w-[80px] shrink-0 overflow-hidden rounded-[3px] bg-mist sm:w-[120px]">
        <div className="h-full rounded-[3px] bg-yellow-500" style={{ width: `${pct}%` }} />
      </div>
      {actionTo ? (
        <ButtonLink to={actionTo} variant="secondary" size="sm">
          {actionLabel}
        </ButtonLink>
      ) : (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Claim rail                                                                  */
/* -------------------------------------------------------------------------- */

/** One chip in the rail's filter row (nodes 17:97 – 17:102). */
export type RailFilter = { label: string; active?: boolean }

/** Figma: "Items Rail" (node 17:66) — every verification point, one row each. */
export function ClaimRail({
  claims,
  activeId,
  /** Route for a claim row; return undefined to render a plain button instead of a link. */
  linkForClaim,
  onSelectClaim,
  /** Per-claim status overrides, for variants where decisions have been recorded. */
  decisions,
  title = 'REFERENCES',
  count = claims.length,
  filters,
  className,
}: {
  claims: Claim[]
  activeId: string
  linkForClaim?: (claim: Claim) => string | undefined
  onSelectClaim?: (claim: Claim) => void
  decisions?: Partial<Record<string, VerificationStatus>>
  title?: string
  count?: number
  filters?: RailFilter[]
  className?: string
}) {
  const listRef = useRef<HTMLDivElement>(null)

  // Keep the claim under review visible without the reviewer hunting for it.
  useEffect(() => {
    const row = listRef.current?.querySelector(`[data-claim-id="${activeId}"]`)
    row?.scrollIntoView({ block: 'center' })
  }, [activeId])

  return (
    <aside
      className={cn(
        'flex h-auto max-h-[280px] w-full shrink-0 flex-col border-b border-mist bg-white lg:h-full lg:max-h-none lg:w-[320px] lg:border-r lg:border-b-0',
        className,
      )}
    >
      {/* Rail Head — node 17:91 */}
      <div className="flex w-full shrink-0 flex-col gap-[12px] px-[20px] pt-[20px] pb-[14px]">
        <div className="flex w-full items-center">
          <p className="text-[11px] font-semibold tracking-[1.32px] whitespace-nowrap text-slate">
            {title}
          </p>
          <div className="min-w-px flex-1" />
          <p className="text-[11px] font-semibold text-slate-soft">{count}</p>
        </div>
        {filters && filters.length > 0 ? (
          <div className="flex flex-wrap items-start gap-[8px]">
            {filters.map((filter) => (
              <span
                key={filter.label}
                className={cn(
                  'rounded-pill px-[11px] py-[5px] text-[11px] font-semibold whitespace-nowrap',
                  filter.active ? 'bg-carbon-900 text-white' : 'bg-mist/50 text-slate',
                )}
              >
                {filter.label}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="h-px w-full shrink-0 bg-mist" aria-hidden />

      {/* List — node 17:104 */}
      <div ref={listRef} className="flex min-h-0 w-full flex-1 flex-col overflow-y-auto">
        {claims.map((claim) => {
          const status = decisions?.[claim.id] ?? claim.status
          const isActive = claim.id === activeId
          const to = linkForClaim?.(claim)

          const inner = (
            <>
              {isActive ? (
                <span
                  className={cn(
                    'absolute top-1/2 left-0 h-[40px] w-[3px] -translate-y-1/2',
                    status === 'Could not be verified' ? 'bg-red' : 'bg-yellow-500',
                  )}
                  aria-hidden
                />
              ) : null}
              <span className="flex min-w-px flex-1 flex-col items-start gap-[3px] overflow-hidden text-left">
                <span className="flex items-center gap-[6px]">
                  <span
                    className={cn(
                      'font-mono text-[11px] font-medium',
                      !isActive
                        ? 'text-slate-soft'
                        : status === 'Could not be verified'
                          ? 'text-red'
                          : 'text-gold-ink',
                    )}
                  >
                    {claim.id}
                  </span>
                  <span
                    className={cn(
                      'truncate text-[12.5px] text-ink',
                      isActive ? 'font-semibold' : 'font-medium',
                    )}
                  >
                    {claim.label}
                  </span>
                </span>
                <span className="text-[10.5px] text-slate-soft">{claim.kind}</span>
              </span>
              {/* Compact rail variant of the shared pill (nodes 17:111 – 17:167). */}
              <StatusPill
                status={status}
                label={RAIL_LABELS[status]}
                showDot={false}
                className="px-[9px]! py-[3px]! text-[10px]!"
              />
            </>
          )

          const rowClass = cn(
            'relative flex w-full items-center gap-[10px] border-b border-mist/60 py-[13px] pr-[16px] pl-[20px] text-left transition-colors',
            isActive
              ? status === 'Could not be verified'
                ? 'bg-red-tint/55'
                : 'bg-yellow-100'
              : 'bg-white hover:bg-paper',
          )

          return to ? (
            <Link
              key={claim.id}
              to={to}
              data-claim-id={claim.id}
              className={rowClass}
              aria-current={isActive ? 'true' : undefined}
            >
              {inner}
            </Link>
          ) : (
            <button
              key={claim.id}
              type="button"
              data-claim-id={claim.id}
              onClick={() => onSelectClaim?.(claim)}
              className={cn(rowClass, 'cursor-pointer')}
              aria-current={isActive ? 'true' : undefined}
            >
              {inner}
            </button>
          )
        })}
      </div>
    </aside>
  )
}

/* -------------------------------------------------------------------------- */
/* Document pane                                                               */
/* -------------------------------------------------------------------------- */

/** How a detected span is painted inside the draft (nodes 21:57 – 21:60). */
export type PassageTone = 'plain' | 'found' | 'review' | 'unverified' | 'active'

const PASSAGE_TONES: Record<PassageTone, string> = {
  plain: 'text-ink',
  found: 'text-green underline decoration-solid',
  review: 'text-amber underline decoration-solid',
  unverified: 'text-red underline decoration-solid',
  active: 'font-bold text-gold-ink underline decoration-solid',
}

/** A run of draft text; `tone` marks it as a detected reference. */
export type DocumentSegment = { text: string; tone?: PassageTone }

/** One numbered paragraph of the draft. */
export type DocumentParagraph = { id: string; segments: DocumentSegment[] }

/** Figma: "Doc Column" / "Doc Page" (nodes 17:67, 21:53) — the draft with highlighted spans. */
export function DocumentPane({
  court,
  title,
  paragraphs,
  footnote,
  className,
}: {
  court: string
  title: string
  paragraphs: DocumentParagraph[]
  footnote?: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex min-w-px flex-1 flex-col overflow-y-auto px-[36px] py-[28px]',
        className,
      )}
    >
      <Card
        tone="flat"
        className="flex min-h-full flex-1 flex-col items-center gap-[22px] rounded-[6px]! px-[20px] py-[28px] shadow-card sm:px-[32px] sm:py-[36px] lg:px-[48px] lg:py-[44px]"
      >
        <p className="text-center text-[11px] font-semibold tracking-[1.1px] text-slate">{court}</p>
        <h1 className="text-center font-display text-[19px] font-bold text-carbon-900">{title}</h1>
        <div className="h-px w-full max-w-[560px] shrink-0 bg-mist" aria-hidden />

        {paragraphs.map((paragraph) => (
          <p
            key={paragraph.id}
            className="w-full max-w-[560px] font-display text-[14px] leading-[1.78] text-ink"
          >
            {paragraph.segments.map((segment, i) => (
              <span key={i} className={PASSAGE_TONES[segment.tone ?? 'plain']}>
                {segment.text}
              </span>
            ))}
          </p>
        ))}

        <div className="min-h-[8px] flex-1" />
        {footnote ? (
          <p className="text-center text-[11.5px] text-slate-soft">{footnote}</p>
        ) : null}
      </Card>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Evidence pane                                                               */
/* -------------------------------------------------------------------------- */

/** Verdict tone for the machine statement / assessment blocks. */
export type EvidenceTone = 'found' | 'review' | 'unverified'

const MACHINE_TONES: Record<EvidenceTone, { dot: string; text: string }> = {
  found: { dot: 'bg-green-bright', text: 'text-green-bright' },
  review: { dot: 'bg-amber-bright', text: 'text-amber-bright' },
  unverified: { dot: 'bg-red-bright', text: 'text-red-bright' },
}

/** A `label: value` line inside the machine statement (node 23:67). */
export type MachineRow = { label: string; value: string }

/** Figma: "Machine Statement" (node 23:63) — the carbon block stating what the system found. */
export function MachineStatement({
  tone,
  label,
  rows,
  action,
  children,
  className,
}: {
  tone: EvidenceTone
  label: string
  rows?: MachineRow[]
  /** The bordered yellow link at the foot of the block (node 23:68). */
  action?: { label: string; href?: string; to?: string; onClick?: () => void }
  children?: ReactNode
  className?: string
}) {
  const style = MACHINE_TONES[tone]
  const actionClass =
    'inline-flex items-center rounded-[6px] border border-yellow-500/60 px-[12px] py-[7px] font-mono text-[11.5px] font-bold text-yellow-500 transition-colors hover:bg-yellow-500/10'

  return (
    <div
      className={cn(
        'flex w-full shrink-0 flex-col gap-[10px] rounded-[10px] bg-carbon-900 p-[16px]',
        className,
      )}
    >
      <div className="flex items-center gap-[8px]">
        <span className={cn('size-[7px] shrink-0 rounded-full', style.dot)} aria-hidden />
        <p
          className={cn(
            'font-mono text-[10.5px] font-bold tracking-[0.63px] whitespace-nowrap',
            style.text,
          )}
        >
          {label}
        </p>
      </div>

      {rows && rows.length > 0 ? (
        <div className="grid grid-cols-[minmax(72px,96px)_minmax(0,1fr)] gap-x-[4px] font-mono text-[11.5px] leading-[1.7] text-slate-soft [&_span]:break-words">
          {rows.map((row) => (
            <div key={row.label} className="contents">
              <span>{row.label}</span>
              <span>{row.value}</span>
            </div>
          ))}
        </div>
      ) : null}

      {children}

      {action ? (
        action.to ? (
          <Link to={action.to} className={actionClass}>
            {action.label}
          </Link>
        ) : action.href ? (
          <a href={action.href} target="_blank" rel="noreferrer" className={actionClass}>
            {action.label}
          </a>
        ) : (
          <button type="button" onClick={action.onClick} className={cn(actionClass, 'cursor-pointer')}>
            {action.label}
          </button>
        )
      ) : null}
    </div>
  )
}

/** Figma: "Cited For" (node 23:60) — a small labelled block on the paper surface. */
export function EvidenceCallout({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex w-full shrink-0 flex-col gap-[4px] rounded-[8px] bg-paper px-[14px] py-[12px]',
        className,
      )}
    >
      <p className="text-[9.5px] font-semibold tracking-[1.14px] whitespace-nowrap text-slate-soft">
        {label}
      </p>
      <div className="text-[12.5px] leading-[1.55] text-ink">{children}</div>
    </div>
  )
}

/** Figma: "Excerpt" (node 23:70) — the quoted source passage with its yellow rule. */
export function EvidenceQuote({
  quote,
  attribution,
  className,
}: {
  quote: string
  attribution?: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex w-full shrink-0 flex-col gap-[8px] rounded-[8px] border-l-[3px] border-yellow-500 bg-paper py-[14px] pr-[14px] pl-[16px]',
        className,
      )}
    >
      <p className="font-mono text-[11.5px] leading-[1.5] italic text-ink">{quote}</p>
      {attribution ? <p className="text-[11px] text-slate">{attribution}</p> : null}
    </div>
  )
}

/** Figma: "Lawyer Assessment" (node 23:74) — states that only the lawyer decides. */
export function AssessmentNote({
  label,
  children,
  labelClassName = 'text-amber',
  className,
}: {
  label: string
  children: ReactNode
  /** Token class for the overline, e.g. `text-amber` pending, `text-green` recorded. */
  labelClassName?: string
  className?: string
}) {
  return (
    <div className={cn('flex w-full shrink-0 flex-col gap-[8px]', className)}>
      <p
        className={cn(
          'text-[10.5px] font-semibold tracking-[1.26px] whitespace-nowrap',
          labelClassName,
        )}
      >
        {label}
      </p>
      <div className="text-[12px] leading-[1.5] text-slate">{children}</div>
    </div>
  )
}

/** Visual weight of a decision button (nodes 23:79 – 23:87). */
export type DecisionTone = 'confirm' | 'correct' | 'reject' | 'unresolved' | 'primary'

const DECISION_TONES: Record<DecisionTone, string> = {
  confirm: 'bg-green text-white hover:bg-green/90',
  correct: 'border-[1.5px] border-amber bg-white text-amber hover:bg-amber-tint',
  reject: 'border-[1.5px] border-red bg-white text-red hover:bg-red-tint',
  unresolved: 'border-[1.5px] border-slate bg-white text-slate hover:bg-neutral-tint',
  primary: 'bg-carbon-900 text-yellow-500 hover:bg-carbon-700',
}

/** One button in the decision row — `to` navigates, otherwise `onClick` fires. */
export type DecisionAction = {
  label: string
  tone: DecisionTone
  to?: string
  onClick?: () => void
}

/** Figma: "Decisions" (node 23:77) — the two-by-two decision action row. */
export function DecisionRow({
  actions,
  className,
}: {
  actions: DecisionAction[]
  className?: string
}) {
  return (
    <div className={cn('grid w-full shrink-0 grid-cols-2 gap-[10px]', className)}>
      {actions.map((action) => {
        const classes = cn(
          'flex items-center justify-center rounded-[8px] px-[6px] py-[11px] text-center text-[12.5px] font-semibold transition-colors',
          DECISION_TONES[action.tone],
        )
        return action.to ? (
          <Link key={action.label} to={action.to} className={classes}>
            {action.label}
          </Link>
        ) : (
          <button
            key={action.label}
            type="button"
            onClick={action.onClick}
            className={cn(classes, 'cursor-pointer')}
          >
            {action.label}
          </button>
        )
      })}
    </div>
  )
}

/** Figma: "Evidence Panel" (node 17:68) — header, scrolling body slot, decision row. */
export function EvidencePane({
  overline,
  title,
  subtitle,
  closeTo,
  onClose,
  children,
  actions,
  className,
}: {
  overline: string
  title: string
  subtitle?: string
  /** Route for the ✕ affordance; falls back to `onClose`. */
  closeTo?: string
  onClose?: () => void
  children: ReactNode
  actions?: DecisionAction[]
  className?: string
}) {
  const closeClass =
    'text-[12px] font-semibold text-slate-soft transition-colors hover:text-ink'

  return (
    <section
      className={cn(
        'flex h-auto min-h-[420px] w-full shrink-0 flex-col gap-[11px] overflow-y-auto border-t border-mist bg-white px-[16px] py-[18px] sm:px-[26px] lg:h-full lg:min-h-0 lg:w-[408px] lg:border-t-0 lg:border-l',
        className,
      )}
    >
      {/* Panel Head — node 23:53 */}
      <div className="flex w-full shrink-0 items-center">
        <p className="text-[10.5px] font-semibold tracking-[1.26px] whitespace-nowrap text-slate">
          {overline}
        </p>
        <div className="min-w-px flex-1" />
        {closeTo ? (
          <Link to={closeTo} aria-label="Close panel" className={closeClass}>
            ✕
          </Link>
        ) : onClose ? (
          <button
            type="button"
            aria-label="Close panel"
            onClick={onClose}
            className={cn(closeClass, 'cursor-pointer')}
          >
            ✕
          </button>
        ) : null}
      </div>

      {/* Title — node 23:57 */}
      <div className="flex w-full shrink-0 flex-col gap-[4px]">
        <h2 className="font-display text-[19px] font-bold text-carbon-900">{title}</h2>
        {subtitle ? <p className="font-mono text-[12.5px] text-slate">{subtitle}</p> : null}
      </div>

      {children}

      {actions && actions.length > 0 ? <DecisionRow actions={actions} /> : null}
    </section>
  )
}

/* -------------------------------------------------------------------------- */
/* Footer + frame                                                              */
/* -------------------------------------------------------------------------- */

/** Figma: "Footer Bar" (node 17:69) — running review tally and session line. */
export function WorkspaceFooterBar({
  status,
  session,
  className,
}: {
  status: string
  session: string
  className?: string
}) {
  return (
    <footer
      className={cn(
        'flex w-full shrink-0 flex-wrap items-center gap-x-[16px] gap-y-[4px] bg-carbon-900 px-[16px] py-[13px] sm:px-[24px] lg:px-[40px]',
        className,
      )}
    >
      <p className="font-mono text-[12.5px] text-mist">{status}</p>
      <div className="min-w-px flex-1" />
      <p className="font-mono text-[12.5px] text-slate-soft">{session}</p>
    </footer>
  )
}

/** Figma: frame 05 · Workspace — Evidence (node 17:43) — nav, sub-header, three panes, footer. */
export function WorkspaceLayout({
  subHeader,
  rail,
  document: documentSlot,
  evidence,
  footer,
  className,
}: {
  /** Usually a `<WorkspaceSubHeader />`. */
  subHeader?: ReactNode
  /** Left pane — usually a `<ClaimRail />`. */
  rail: ReactNode
  /** Centre pane — usually a `<DocumentPane />`. */
  document: ReactNode
  /** Right pane — usually an `<EvidencePane />`. */
  evidence: ReactNode
  /** Usually a `<WorkspaceFooterBar />`. */
  footer?: ReactNode
  className?: string
}) {
  return (
    <AppShell
      showBoundaryStrip={false}
      className={cn('min-h-screen lg:h-screen lg:overflow-hidden', className)}
      contentClassName="min-h-0 overflow-y-auto lg:overflow-hidden"
    >
      {subHeader}
      {/* Main — node 17:65 */}
      <div className="flex min-h-0 w-full flex-1 flex-col items-stretch overflow-y-auto lg:flex-row lg:overflow-hidden">
        {rail}
        {documentSlot}
        {evidence}
      </div>
      {footer}
    </AppShell>
  )
}

export default WorkspaceLayout
