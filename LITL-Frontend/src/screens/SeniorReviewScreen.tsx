import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { StatusPill, type VerificationStatus } from '@/components/ui/StatusPill'
import { CLAIMS, DOCUMENT } from '@/data/claims'
import { cn } from '@/lib/cn'

/** Figma: 10 · Senior Review (node 31:207) */

type QueueEntry = {
  fileName: string
  submitted: string
  author: string
  coverage: string
  unresolved: string
  /** The unresolved chip goes red once anything is outstanding. */
  hasUnresolved: boolean
}

const QUEUE: QueueEntry[] = [
  {
    fileName: DOCUMENT.fileName,
    submitted: '12 min ago',
    author: `${DOCUMENT.reviewer} · Junior Associate`,
    coverage: '94% coverage',
    unresolved: '1 unresolved',
    hasUnresolved: true,
  },
  {
    fileName: 'Rejoinder_Sharma_v_NHAI.docx',
    submitted: '1 hr ago',
    author: 'K. Menon · Associate',
    coverage: '100% coverage',
    unresolved: '0 unresolved',
    hasUnresolved: false,
  },
  {
    fileName: 'Legal_Notice_Vendor_Term.docx',
    submitted: '3 hrs ago',
    author: 'R. Iyer · Associate',
    coverage: '87% coverage',
    unresolved: '3 unresolved',
    hasUnresolved: true,
  },
]

const STATS: Array<{ value: string; label: string; emphasis?: boolean }> = [
  { value: '94%', label: 'verification coverage' },
  { value: String(DOCUMENT.referenceCount), label: 'references detected' },
  { value: '17', label: 'recorded outcomes' },
  { value: '1', label: 'unresolved', emphasis: true },
]

const SIGNAL_LINES = [
  'Session duration:  15m 12s        Sources opened:  13 of 16 located',
  'Review actions:    18 of 18        Corrections:     3 recorded',
]

/** Ref 09 is the item the junior left unresolved — pulled from the shared dataset. */
const UNRESOLVED_CLAIM = CLAIMS.find((claim) => claim.id === '09')

type PreviewItem = {
  ref: string
  title: string
  detail: string
  status: VerificationStatus
}

const PREVIEW_ITEMS: PreviewItem[] = [
  {
    ref: '07',
    title: 'Arnesh Kumar v. Bihar (2014)',
    detail: 'Confirmed · source opened · 2m 41s',
    status: 'Confirmed',
  },
  {
    ref: '06',
    title: 'Quotation · “arrest is not mandatory…”',
    detail: 'Corrected · aligned to para 8',
    status: 'Corrected',
  },
  {
    ref: '09',
    title: UNRESOLVED_CLAIM?.label ?? 'Satender Kumar Antil v. CBI',
    detail: 'Left unresolved · flagged for you',
    status: 'Unresolved',
  },
]

type Decision = 'approved' | 'returned'

export function SeniorReviewScreen() {
  const [decision, setDecision] = useState<Decision | null>(null)

  return (
    <AppShell showBoundaryStrip={false} navInitials="SM">
      <div className="flex flex-1 flex-col items-stretch gap-[20px] px-[16px] py-[20px] sm:gap-[28px] sm:px-[24px] sm:py-[28px] lg:flex-row lg:px-[40px] lg:py-[32px]">
        {/* ---------------------------------------------------------- Queue */}
        <div className="flex w-full shrink-0 flex-col gap-[14px] lg:w-[392px]">
          <p className="text-[11px] font-semibold tracking-[1.54px] text-slate">APPROVAL QUEUE</p>
          <h1 className="font-display text-[24px] font-bold text-carbon-900">
            Awaiting your decision
          </h1>

          {QUEUE.map((entry, index) => (
            <Card
              key={entry.fileName}
              tone="flat"
              className={cn(
                'flex flex-col gap-[8px] px-[18px] py-[16px] [&]:rounded-[10px]',
                index === 0 && '[&]:border-[1.5px] [&]:border-yellow-500',
              )}
            >
              <div className="flex w-full items-center gap-[8px]">
                <p className="text-[13px] font-semibold text-ink">{entry.fileName}</p>
                <div className="h-[4px] min-w-px flex-1" />
                <p className="text-[10.5px] whitespace-nowrap text-slate-soft">{entry.submitted}</p>
              </div>
              <p className="text-[11.5px] text-slate">{entry.author}</p>
              <div className="flex items-start gap-[8px]">
                <span className="rounded-pill bg-green-tint px-[8px] py-[2px] text-[9.5px] font-semibold text-green">
                  {entry.coverage}
                </span>
                <span
                  className={cn(
                    'rounded-pill px-[8px] py-[2px] text-[9.5px] font-semibold',
                    entry.hasUnresolved ? 'bg-red-tint text-red' : 'bg-neutral-tint text-slate',
                  )}
                >
                  {entry.unresolved}
                </span>
              </div>
            </Card>
          ))}
        </div>

        {/* --------------------------------------------------------- Detail */}
        <Card
          tone="flat"
          className="flex min-w-px flex-1 flex-col gap-[20px] px-[32px] py-[28px] [&]:rounded-[12px]"
        >
          {/* Detail head */}
            <div className="flex w-full flex-wrap items-center gap-[16px]">
            <div className="flex min-w-px flex-1 flex-col gap-[5px]">
              <h2 className="font-display text-[24px] font-bold text-carbon-900">
                {DOCUMENT.fileName}
              </h2>
              <p className="text-[13px] text-slate">
                Prepared by {DOCUMENT.reviewer} · AI-assisted draft · Submitted 12 min ago
              </p>
            </div>
            <ButtonLink
              to="/report"
              variant="secondary"
              size="sm"
              className="px-[16px] py-[9px] text-[12.5px]"
            >
              Open full report ↗
            </ButtonLink>
          </div>

          {/* Stat strip */}
            <div className="grid w-full grid-cols-2 items-start rounded-[10px] bg-paper sm:flex">
            {STATS.map((stat) => (
              <div
                key={stat.label}
                className="flex min-w-px flex-1 flex-col items-center gap-[2px] px-[10px] py-[14px] sm:px-[24px] sm:py-[16px]"
              >
                <p
                  className={cn(
                    'font-display text-[28px] font-bold',
                    stat.emphasis ? 'text-red' : 'text-carbon-900',
                  )}
                >
                  {stat.value}
                </p>
                <p className="text-center text-[11px] text-slate">{stat.label}</p>
              </div>
            ))}
          </div>

          {/* Review signals */}
          <div className="flex w-full flex-col gap-[8px] rounded-[10px] bg-carbon-900 px-[18px] py-[16px]">
            <p className="font-mono text-[10.5px] font-medium tracking-[0.63px] text-yellow-500">
              REVIEW SIGNALS — RECORDED, NOT INFERRED
            </p>
            <div className="font-mono text-[12px] text-blue-tint/70">
              {SIGNAL_LINES.map((line) => (
                <p key={line} className="leading-[1.75] whitespace-pre-wrap">
                  {line}
                </p>
              ))}
            </div>
            <p className="max-w-[700px] text-[11px] leading-[1.5] text-slate-soft/85">
              Signals describe what happened in the review session. They do not claim the reviewer
              understood every item — LiTL never asserts that.
            </p>
          </div>

          {/* Unresolved alert */}
          <div className="flex w-full flex-col gap-[6px] rounded-[10px] border-l-[3px] border-amber bg-amber-tint px-[18px] py-[14px]">
            <p className="text-[11px] font-semibold tracking-[0.66px] whitespace-pre text-amber">
              {'▸  1 UNRESOLVED ITEM REQUIRES YOUR ATTENTION'}
            </p>
            <p className="max-w-[690px] text-[12.5px] leading-[1.55] text-ink">
              Ref {UNRESOLVED_CLAIM?.id ?? '09'} · {UNRESOLVED_CLAIM?.label ?? 'Satender Kumar Antil v. CBI'} —
              reporter citation could not be matched. The junior flagged it rather than forcing a
              resolution. Inspect the evidence before approving.
            </p>
          </div>

          {/* Items at a glance */}
          <div className="flex w-full flex-col">
            <p className="text-[10px] font-semibold tracking-[1.2px] text-slate-soft">
              ITEMS AT A GLANCE
            </p>
            {PREVIEW_ITEMS.map((item) => (
              <div key={item.ref} className="flex w-full flex-col">
                <div className="flex w-full items-center gap-[12px] py-[11px]">
                  <p className="font-mono text-[11.5px] font-medium text-slate-soft">{item.ref}</p>
                  <div className="flex min-w-px flex-1 flex-col gap-[2px]">
                    <p className="text-[12.5px] font-semibold text-ink">{item.title}</p>
                    <p className="text-[11px] text-slate">{item.detail}</p>
                  </div>
                  <StatusPill status={item.status} className="px-[9px] py-[3px] text-[10px]" />
                </div>
                <div className="h-px w-full bg-mist/60" aria-hidden />
              </div>
            ))}
          </div>

          {/* Decision bar */}
          {decision === null ? (
            <div className="flex w-full flex-wrap items-center gap-[12px]">
              <p className="text-[11.5px] text-slate-soft">
                Your decision is recorded as the final workflow stage.
              </p>
              <div className="h-[8px] min-w-px flex-1" />
              <Button
                variant="secondary"
                onClick={() => setDecision('returned')}
                className="bg-white px-[20px] text-[13.5px] [&]:border-[1.5px] [&]:border-amber [&]:text-amber [&]:hover:bg-amber-tint"
              >
                Return for review
              </Button>
              <Button
                onClick={() => setDecision('approved')}
                className="text-[13.5px] whitespace-pre [&]:bg-green [&]:text-white [&]:hover:bg-green/90"
              >
                {'✓  Approve'}
              </Button>
            </div>
          ) : (
            <div
              className={cn(
                'flex w-full items-center gap-[12px] rounded-[10px] px-[18px] py-[14px]',
                decision === 'approved' ? 'bg-green-tint' : 'bg-amber-tint',
              )}
            >
              <span
                className={cn(
                  'text-[13.5px] font-semibold whitespace-pre',
                  decision === 'approved' ? 'text-green' : 'text-amber',
                )}
              >
                {decision === 'approved' ? '✓  Approved' : '▸  Returned for review'}
              </span>
              <span className="text-[11.5px] text-slate">
                Recorded as the final workflow stage.
              </span>
              <div className="h-[8px] min-w-px flex-1" />
              <span className="font-mono text-[11.5px] text-slate-soft">
                {DOCUMENT.recordNumber}
              </span>
              <Button variant="ghost" size="sm" onClick={() => setDecision(null)}>
                Undo
              </Button>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  )
}

export default SeniorReviewScreen
