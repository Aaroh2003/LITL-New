import { cn } from '@/lib/cn'

/** Figma: "Status Pill" component set (node 3:23) on 03 · Foundations & Components. */
export type VerificationStatus =
  | 'Source found'
  | 'Requires review'
  | 'Could not be verified'
  | 'Confirmed'
  | 'Corrected'
  | 'Rejected'
  | 'Unresolved'

const STATUS_STYLES: Record<VerificationStatus, { surface: string; text: string; dot: string }> = {
  'Source found': { surface: 'bg-green-tint', text: 'text-green', dot: 'bg-green' },
  'Requires review': { surface: 'bg-amber-tint', text: 'text-amber', dot: 'bg-amber' },
  'Could not be verified': { surface: 'bg-red-tint', text: 'text-red', dot: 'bg-red' },
  Confirmed: { surface: 'bg-green', text: 'text-white', dot: 'bg-white' },
  Corrected: { surface: 'bg-amber', text: 'text-white', dot: 'bg-white' },
  Rejected: { surface: 'bg-red', text: 'text-white', dot: 'bg-white' },
  Unresolved: { surface: 'bg-neutral-tint', text: 'text-slate', dot: 'bg-slate' },
}

/**
 * Abbreviated labels used in the dense workspace rail, where the Figma rows
 * shorten the two longest statuses (nodes 17:111 – 17:167).
 */
export const RAIL_LABELS: Record<VerificationStatus, string> = {
  'Source found': 'Source found',
  'Requires review': 'Review',
  'Could not be verified': 'Not verified',
  Confirmed: 'Confirmed',
  Corrected: 'Corrected',
  Rejected: 'Rejected',
  Unresolved: 'Unresolved',
}

type StatusPillProps = {
  status: VerificationStatus
  /** Overrides the displayed text; the status still drives the colours. */
  label?: string
  /** The rail variant of the pill omits the leading dot. */
  showDot?: boolean
  className?: string
}

export function StatusPill({ status, label, showDot = true, className }: StatusPillProps) {
  const style = STATUS_STYLES[status]

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-[6px] rounded-pill px-[10px] py-[4px] text-[11.5px] font-semibold whitespace-nowrap',
        style.surface,
        style.text,
        className,
      )}
    >
      {showDot ? (
        <span className={cn('size-[6px] shrink-0 rounded-full', style.dot)} aria-hidden />
      ) : null}
      {label ?? status}
    </span>
  )
}

export default StatusPill
