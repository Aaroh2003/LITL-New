import type { ReactNode } from 'react'
import { AppTopNav } from './AppTopNav'
import { cn } from '@/lib/cn'
import { useAuth } from '@/lib/auth'

export const BOUNDARY_STATEMENT =
  'LiTL does not certify that AI is correct. It records the verification process — detect, locate, present, review, decide, record.'

/**
 * The chrome shared by every in-app screen: the top nav, a content area, and the
 * "boundary strip" that states what LiTL does and does not claim.
 * Figma: nodes 12:11 (nav), 12:25 (content), 12:55 (boundary strip).
 */
export function AppShell({
  children,
  className,
  contentClassName,
  showBoundaryStrip = true,
  showNav = true,
  navInitials,
}: {
  children: ReactNode
  className?: string
  contentClassName?: string
  showBoundaryStrip?: boolean
  showNav?: boolean
  navInitials?: string
}) {
  const { config } = useAuth()
  return (
    <div className={cn('flex min-h-screen w-full flex-col bg-paper', className)}>
      {showNav ? <AppTopNav initials={navInitials} /> : null}
      {config?.auth_mode === 'local' && <div className="notice no-print rounded-none text-center"><strong>LOCAL-ONLY MODE — no login or user isolation.</strong> Use only public/synthetic/anonymized documents on your own machine. Never expose this API publicly.</div>}
      <main className={cn('flex min-h-px flex-1 flex-col', contentClassName)}>{children}</main>
      {showBoundaryStrip ? <BoundaryStrip /> : null}
    </div>
  )
}

export function BoundaryStrip({ className }: { className?: string }) {
  return (
    <footer
      className={cn(
        'flex w-full shrink-0 items-start justify-center border-t border-mist bg-white px-[16px] py-[14px] sm:px-[24px] sm:py-[18px] lg:px-[40px]',
        className,
      )}
    >
      <p className="text-center text-[12px] text-slate-soft">{BOUNDARY_STATEMENT}</p>
    </footer>
  )
}

export default AppShell
