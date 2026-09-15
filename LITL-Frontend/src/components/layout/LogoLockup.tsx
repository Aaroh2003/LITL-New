import { cn } from '@/lib/cn'

/** Figma: "Logo Lockup" component (node 3:24). */
export function LogoLockup({
  className,
  size = 100,
}: {
  className?: string
  size?: number
}) {
  return (
    <div className={cn('flex items-center', className)}>
      <img
        src="/favicon.svg"
        alt="LiTL"
        className="block w-auto shrink-0 object-contain"
        style={{ height: size }}
      />
    </div>
  )
}

export default LogoLockup
