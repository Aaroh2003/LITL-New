import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/lib/cn'

export type ButtonVariant = 'primary' | 'accent' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-carbon-900 text-yellow-500 hover:bg-carbon-700',
  /** The yellow "go" CTA used on Detection Summary, Review Complete and the report. */
  accent:
    'bg-yellow-500 text-carbon-900 shadow-[0_4px_22px_0] shadow-yellow-500/40 hover:bg-yellow-500/85',
  secondary:
    'border-[1.5px] border-carbon-900/25 text-carbon-900 bg-transparent hover:bg-carbon-900/5',
  ghost: 'text-slate hover:text-ink hover:bg-carbon-900/5',
  danger: 'border-[1.5px] border-red/30 text-red bg-transparent hover:bg-red-tint',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'px-[14px] py-[7px] text-[13px] rounded-[7px]',
  md: 'px-[24px] py-[12px] text-[14px] rounded-[8px]',
  lg: 'px-[30px] py-[15px] text-[15.5px] rounded-[10px]',
}

type BaseProps = {
  variant?: ButtonVariant
  size?: ButtonSize
  className?: string
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...rest
}: BaseProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex cursor-pointer items-center justify-center gap-[8px] font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-45',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

export function ButtonLink({
  to,
  variant = 'primary',
  size = 'md',
  className,
  children,
}: BaseProps & { to: string }) {
  return (
    <Link
      to={to}
      className={cn(
        'inline-flex items-center justify-center gap-[8px] font-semibold whitespace-nowrap transition-colors',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
    >
      {children}
    </Link>
  )
}

export default Button
