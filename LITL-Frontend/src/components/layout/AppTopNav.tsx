import { NavLink } from 'react-router-dom'
import { LogoLockup } from './LogoLockup'
import { cn } from '@/lib/cn'
import { useAuth } from '@/lib/auth'
import { useState } from 'react'
import { errorMessage } from '@/lib/api'
import { Button } from '@/components/ui/Button'

const LINKS = [
  { label: 'Documents', to: '/documents' },
  { label: 'Upload', to: '/upload' },
  { label: 'Help & privacy', to: '/help' },
]

/** Figma: "App Top Nav" component (node 3:28). */
export function AppTopNav({
  className,
  /** Signed-in initials shown in the avatar — "SM" on the senior-review frame. */
  initials,
}: {
  className?: string
  initials?: string
}) {
  const { config, session, signOut } = useAuth()
  const [error, setError] = useState('')
  return (
    <header
      className={cn(
        'no-print flex min-h-[64px] w-full shrink-0 flex-wrap items-center gap-[16px] border-b border-mist bg-white px-[16px] py-3 sm:gap-[24px] sm:px-[24px] lg:px-[40px]',
        className,
      )}
    >
      <NavLink to="/" aria-label="LiTL home">
        <LogoLockup />
      </NavLink>

      <div className="flex-1" />

      <nav className="flex flex-wrap items-center gap-4">
        {LINKS.map((link) => (
          <NavLink
            key={link.label}
            to={link.to}
            className={({ isActive }) =>
              cn(
                'text-[14px] font-medium transition-colors hover:text-ink',
                isActive ? 'text-ink' : 'text-slate',
              )
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>

      {session ? <><span className="max-w-40 truncate text-small">{session.user.email}</span><Button size="sm" variant="ghost" onClick={() => { if (!window.confirm('Sign out? Any unsaved review input will be discarded.')) return; setError(''); void signOut().catch((cause) => setError(errorMessage(cause))) }}>Sign out</Button></> : config?.auth_mode === 'supabase' ? <><NavLink to="/login">Sign in</NavLink><NavLink to="/signup">Sign up</NavLink></> : <span className="text-small text-slate">{initials || 'Limited beta'}</span>}
      {error && <p role="alert" className="text-red">{error}</p>}
    </header>
  )
}

export default AppTopNav
