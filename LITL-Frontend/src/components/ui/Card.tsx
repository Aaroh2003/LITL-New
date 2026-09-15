import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

type CardProps = {
  children: ReactNode
  /** `panel` uses the larger radius + softer elevation used by workspace panels. */
  tone?: 'card' | 'panel' | 'flat'
  className?: string
} & HTMLAttributes<HTMLDivElement>

export function Card({ children, tone = 'card', className, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'border border-mist bg-white',
        tone === 'card' && 'rounded-[16px] shadow-card',
        tone === 'panel' && 'rounded-panel shadow-panel',
        tone === 'flat' && 'rounded-card',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

export function Overline({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('type-overline text-gold-ink', className)}>{children}</p>
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn('h-px w-full bg-mist', className)} aria-hidden />
}

export default Card
