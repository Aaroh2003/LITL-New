import { Link } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { LogoLockup } from '@/components/layout/LogoLockup'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Card, Overline } from '@/components/ui/Card'
import { StatusPill, type VerificationStatus } from '@/components/ui/StatusPill'
import { cn } from '@/lib/cn'
import { useAuth } from '@/lib/auth'

/** Landing — light mode only. First page of the product flow. */

const NAV_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'The report', href: '#the-boundary' },
  { label: 'For reviewers', href: '#for-reviewers' },
]

type Stage = {
  number: string
  title: string
  actor: 'SYSTEM' | 'LAWYER'
  body: string
}

const STAGES: Stage[] = [
  {
    number: '01',
    title: 'Detect',
    actor: 'SYSTEM',
    body: 'Pattern-based detection identifies some case citations, statutory references and quotations.',
  },
  {
    number: '02',
    title: 'Locate',
    actor: 'SYSTEM',
    body: 'The underlying authority is searched for in available repositories.',
  },
  {
    number: '03',
    title: 'Present',
    actor: 'SYSTEM',
    body: 'The evidence appears beside the claim it is supposed to support.',
  },
  {
    number: '04',
    title: 'Review',
    actor: 'LAWYER',
    body: 'The lawyer inspects the source against the assertion — not a score.',
  },
  {
    number: '05',
    title: 'Decide',
    actor: 'LAWYER',
    body: 'Confirm, correct, reject — or leave honestly unresolved.',
  },
  {
    number: '06',
    title: 'Record',
    actor: 'SYSTEM',
    body: 'The defined verification event is captured with its metadata.',
  },
]

const MACHINE_STATEMENT_LINES = [
  'The underlying authority was located in an available repository.',
  'Match: case name and reporter citation consistent.',
  '',
  'This says nothing about whether the proposition in the draft is correct.',
]

const DECISIONS: VerificationStatus[] = ['Confirmed', 'Corrected', 'Rejected', 'Unresolved']

const FEATURES = [
  {
    glyph: '◈',
    title: 'Model-agnostic',
    body: 'Works on the work product — output from ChatGPT, Claude, Gemini, a firm model, or any legal AI platform.',
  },
  {
    glyph: '⬒',
    title: 'A record, not a grade',
    body: 'Every metric describes the verification process. None claims to measure legal correctness. No fake 8.7/10.',
  },
  {
    glyph: '◎',
    title: 'Unresolved stays visible',
    body: 'Open questions are surfaced prominently rather than laundered into a green summary. Honesty over green.',
  },
]

const SECTION_X = 'px-[24px] md:px-[48px] xl:px-[80px]'
const CONTAINER = 'mx-auto flex w-full max-w-[1280px] flex-col'
const OCHRE_CTA =
  'rounded-[10px] bg-ochre text-white shadow-none hover:bg-ochre/90'

function scrollToLoop() {
  document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })
}

function ReferenceCard() {
  return (
    <div className="relative w-full shrink-0 lg:w-[480px] xl:w-[520px]">
      <div className="flex w-full flex-col gap-[18px] rounded-[14px] border border-mist/80 bg-white px-[26px] py-[24px] shadow-panel">
        <div className="flex flex-wrap items-center gap-[10px]">
          <span className="text-[11px] font-semibold tracking-[0.14em] text-slate-soft uppercase">
            Illustrative sample · not a live analysis
          </span>
          <span className="rounded-pill border border-mist px-[10px] py-[3px] text-[11.5px] font-medium text-slate">
            Case authority
          </span>
          <span className="inline-flex items-center gap-[5px] rounded-pill bg-green-tint px-[10px] py-[3px] text-[11.5px] font-semibold text-green">
            <span aria-hidden>✓</span>
            Confirmed
          </span>
        </div>

        <div>
          <p className="font-serif inline bg-cite-mark px-[6px] py-[2px] text-[18px] leading-[1.45] font-semibold text-ink">
            Arnesh Kumar v. State of Bihar, (2014) 8 SCC 273
          </p>
          <p className="mt-[10px] text-[10.5px] font-semibold tracking-[0.12em] text-slate-soft uppercase">
            Located passage · Supreme Court of India
          </p>
        </div>

        <p className="rounded-[8px] bg-passage-mark px-[14px] py-[12px] text-[13.5px] leading-[1.55] text-ink">
          11.3. The police officer shall forward the check list duly filled and furnish the
          reasons and materials which necessitated the arrest…
        </p>

        <div className="flex items-center gap-[10px]">
          <span
            className="flex size-[28px] shrink-0 items-center justify-center rounded-full bg-carbon-900 text-[10px] font-semibold text-yellow-500"
            aria-hidden
          >
            AS
          </span>
          <p className="flex-1 text-[12.5px] text-slate">
            Example decision only · no real reviewer or verification
          </p>
          <span
            className="flex size-[22px] items-center justify-center rounded-full bg-green text-[11px] font-bold text-white"
            aria-hidden
          >
            ✓
          </span>
        </div>
      </div>
    </div>
  )
}

export function LandingScreen() {
  const { config, session } = useAuth()
  return (
    <AppShell showNav={false} showBoundaryStrip={false} className="bg-cream">
      {/* ── Hero (light mode only) ───────────────────────────────────────── */}
      <section className="w-full bg-cream">
        <div className={cn(SECTION_X, 'py-[22px]')}>
          <div className={cn(CONTAINER, 'flex-row items-center gap-[28px]')}>
            <Link to="/" aria-label="LiTL home">
              <LogoLockup size={42} />
            </Link>
            <div className="flex-1" />
            <nav className="hidden items-center gap-[28px] md:flex">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="text-[14px] font-medium whitespace-nowrap text-slate transition-colors hover:text-ink"
                >
                  {link.label}
                </a>
              ))}
            </nav>
            {session ? (
              <ButtonLink
                to="/documents"
                variant="secondary"
                className="rounded-[10px] border-mist bg-white px-[18px] py-[10px] text-[14px] text-ink hover:bg-white"
              >
                Documents
              </ButtonLink>
            ) : config?.auth_mode === 'supabase' ? (
              <div className="flex items-center gap-[14px]">
                <Link to="/login" className="text-[14px] font-medium whitespace-nowrap text-slate transition-colors hover:text-ink">
                  Sign in
                </Link>
                <Link to="/signup" className="text-[14px] font-medium whitespace-nowrap text-slate transition-colors hover:text-ink">
                  Sign up
                </Link>
              </div>
            ) : null}
            <ButtonLink
              to="/upload"
              variant="primary"
              className={cn(OCHRE_CTA, 'px-[18px] py-[10px] text-[14px]')}
            >
              Verify a document
            </ButtonLink>
          </div>
        </div>

        <div className={cn(SECTION_X, 'pt-[56px] pb-[88px] md:pt-[72px] md:pb-[104px]')}>
          <div
            className={cn(CONTAINER, 'gap-[48px] lg:flex-row lg:items-center lg:gap-[64px]')}
          >
            <div className="flex min-w-px flex-1 flex-col items-start gap-[26px]">
              <div className="flex items-center gap-[12px]">
                <span className="h-[2px] w-[28px] shrink-0 bg-yellow-500" aria-hidden />
                <p className="text-[11.5px] font-semibold tracking-[1.6px] text-slate uppercase">
                  Verification for AI-assisted legal work
                </p>
              </div>

              <h1 className="font-display text-[36px] leading-[1.14] font-bold tracking-[-0.02em] text-ink md:text-[44px] xl:text-[52px]">
                AI generates.
                <br />
                LiTL locates evidence.
                <br />
                The lawyer decides.
              </h1>

              <p className="max-w-[540px] text-[16.5px] leading-[1.6] text-slate">
                LiTL detects legal references in English Indian documents, presents available
                source evidence, and records what you decide. Detection can miss references;
                no result certifies legal correctness.
              </p>

              <div className="flex flex-wrap items-center gap-[14px]">
                <ButtonLink
                  to="/upload"
                  variant="primary"
                  className={cn(OCHRE_CTA, 'px-[24px] py-[13px] text-[15px]')}
                >
                  Start verifying&nbsp;→
                </ButtonLink>
                <Button
                  variant="secondary"
                  onClick={scrollToLoop}
                  className="rounded-[10px] border-mist bg-white px-[22px] py-[13px] text-[15px] text-ink hover:bg-white"
                >
                  <span aria-hidden className="text-[15px] text-slate">
                    ▦
                  </span>
                  See how it works
                </Button>
              </div>

              <p className="flex max-w-[520px] items-start gap-[8px] text-[13px] leading-[1.5] text-slate-soft">
                <span
                  className="mt-[1px] flex size-[16px] shrink-0 items-center justify-center rounded-full border border-slate-soft/50 text-[10px] font-semibold"
                  aria-hidden
                >
                  i
                </span>
                LiTL never decides whether a statement is legally correct. It finds the evidence
                and records what the lawyer decides.
              </p>
            </div>

            <ReferenceCard />
          </div>
        </div>
      </section>

      {/* ── The Loop ─────────────────────────────────────────────────────── */}
      <section id="how-it-works" className={cn('w-full bg-cream pt-[88px] pb-[96px]', SECTION_X)}>
        <div className={cn(CONTAINER, 'items-center gap-[40px]')}>
          <div className="flex flex-col items-center gap-[14px] text-center">
            <Overline className="text-[11.5px] tracking-[1.84px]">THE VERIFICATION LOOP</Overline>
            <h2 className="font-display text-[32px] font-bold tracking-[-0.64px] text-ink">
              Six stages. One record.
            </h2>
            <p className="max-w-[620px] text-[16px] leading-[1.55] text-slate">
              LiTL automates evidence gathering around verification. It never automates the
              lawyer&apos;s judgment.
            </p>
          </div>

          <div className="grid w-full grid-cols-1 gap-[20px] md:grid-cols-2 lg:grid-cols-3">
            {STAGES.map((stage) => {
              const isLawyer = stage.actor === 'LAWYER'
              const inner = (
                <>
                  <div className="flex w-full items-center gap-[10px]">
                    <span className="font-display text-[18px] font-bold text-ochre">
                      {stage.number}
                    </span>
                    <span className="text-[17px] font-semibold text-ink">{stage.title}</span>
                    <span className="flex-1" />
                    <span
                      className={cn(
                        'rounded-[4px] px-[8px] py-[3px] text-[9.5px] font-semibold tracking-[0.95px]',
                        isLawyer ? 'bg-yellow-100 text-ochre' : 'bg-blue-tint text-blue',
                      )}
                    >
                      {stage.actor}
                    </span>
                  </div>
                  <p className="text-[13.5px] leading-[1.5] text-slate">{stage.body}</p>
                </>
              )

              return isLawyer ? (
                <div
                  key={stage.number}
                  className="flex flex-col items-start gap-[10px] rounded-[12px] border border-yellow-500/45 bg-yellow-100 p-[24px]"
                >
                  {inner}
                </div>
              ) : (
                <Card
                  key={stage.number}
                  tone="flat"
                  className="flex flex-col items-start gap-[10px] rounded-[12px] bg-white p-[24px]"
                >
                  {inner}
                </Card>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── The Boundary ─────────────────────────────────────────────────── */}
      <section id="the-boundary" className={cn('w-full bg-white pt-[88px] pb-[96px]', SECTION_X)}>
        <div className={cn(CONTAINER, 'items-center gap-[44px]')}>
          <div className="flex flex-col items-center gap-[14px] text-center">
            <Overline className="text-[11.5px] tracking-[1.84px]">
              THE RULE THE PRODUCT IS BUILT ON
            </Overline>
            <h2 className="font-display text-[32px] font-bold tracking-[-0.64px] text-ink">
              “Source found” is never “verified.”
            </h2>
            <p className="max-w-[680px] text-[16px] leading-[1.55] text-slate">
              A single green tick collapses five levels of verification depth into one
              reassuring symbol. LiTL keeps the seam between the machine&apos;s report and the
              lawyer&apos;s judgment visible — always.
            </p>
          </div>

          <div className="grid w-full grid-cols-1 items-stretch gap-[24px] lg:grid-cols-2">
            <div className="flex flex-col items-start gap-[16px] rounded-card border border-mist bg-cream p-[30px]">
              <p className="font-mono text-[12px] font-bold tracking-[0.96px] text-green">
                SOURCE FOUND
              </p>
              <p className="font-display text-[22px] font-bold text-ink">A machine statement.</p>
              <div className="font-mono text-[13px] leading-[1.65] text-slate">
                {MACHINE_STATEMENT_LINES.map((line, index) => (
                  <p key={index}>{line === '' ? '​' : line}</p>
                ))}
              </div>
            </div>

            <div className="flex flex-col items-start gap-[16px] rounded-card border border-mist bg-cream p-[30px]">
              <p className="text-[12px] font-semibold tracking-[0.96px] text-green">
                LAWYER ASSESSMENT
              </p>
              <p className="font-display text-[22px] font-bold text-ink">A human statement.</p>
              <p className="text-[14.5px] leading-[1.6] text-slate">
                Only this carries legal weight — and only the lawyer can make it. Nothing is
                marked verified without a recorded human action.
              </p>
              <div className="flex flex-wrap gap-[10px]">
                {DECISIONS.map((decision) => (
                  <StatusPill key={decision} status={decision} />
                ))}
              </div>
            </div>
          </div>

          <p className="text-center font-mono text-[17px] italic text-ochre">
            The system may say “source located.” Only the lawyer says “verified.” These two
            statements are never collapsed into one.
          </p>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────────────────── */}
      <section id="for-reviewers" className={cn('w-full bg-cream pt-[80px] pb-[88px]', SECTION_X)}>
        <div className={cn(CONTAINER, 'items-center gap-[36px]')}>
          <h2 className="text-center font-display text-[27px] font-bold tracking-[-0.54px] text-ink">
            Built for the lawyer who signs the work.
          </h2>
          <div className="grid w-full grid-cols-1 gap-[24px] md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <Card
                key={feature.title}
                tone="flat"
                className="flex flex-col items-start gap-[12px] rounded-[12px] bg-white px-[26px] py-[28px]"
              >
                <span className="flex items-center justify-center rounded-[8px] bg-yellow-100 p-[8px] text-[18px] font-semibold text-ochre">
                  {feature.glyph}
                </span>
                <p className="text-[17px] font-semibold text-ink">{feature.title}</p>
                <p className="text-[13.5px] leading-[1.55] text-slate">{feature.body}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA band ─────────────────────────────────────────────────────── */}
      <section className={cn('w-full border-y border-mist bg-white py-[72px]', SECTION_X)}>
        <div className={cn(CONTAINER, 'items-center gap-[22px] text-center')}>
          <h2 className="font-display text-[29px] font-bold tracking-[-0.58px] text-ink">
            Start an evidence-linked review.
          </h2>
          <p className="text-[16px] text-slate">
            Limited beta for one or two testers. Public, synthetic or anonymized drafts only.
          </p>
          <ButtonLink
            to="/upload"
            variant="primary"
            className={cn(OCHRE_CTA, 'px-[32px] py-[16px] text-[16px]')}
          >
            Start verifying&nbsp;→
          </ButtonLink>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer className={cn('w-full border-t border-mist bg-cream py-[40px]', SECTION_X)}>
        <div className={cn(CONTAINER, 'items-start gap-[18px]')}>
          <div className="flex w-full flex-wrap items-center gap-[28px]">
            <LogoLockup size={32} />
            <div className="flex-1" />
            <Link to="/help" className="text-[13px] font-medium text-slate underline">Help, privacy & limitations</Link>
            <Link to="/documents" className="text-[13px] font-medium text-slate underline">Your documents</Link>
          </div>
          <p className="max-w-[900px] text-[12px] leading-[1.55] text-slate-soft">
            LiTL does not certify that AI output is correct. It makes the boundary between
            machine-generated output, source evidence and human legal judgment visible and
            traceable.
          </p>
          <p className="text-[12px] text-slate-soft">
            Built for the ILTN × vibecode.law Vibeathon 2026
          </p>
        </div>
      </footer>
    </AppShell>
  )
}

export default LandingScreen
