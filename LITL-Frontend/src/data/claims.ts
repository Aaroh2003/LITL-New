import type { VerificationStatus } from '@/components/ui/StatusPill'

/**
 * Shared mock dataset for the LiTL prototype.
 *
 * Derived from Figma "04 · Detection Summary" (node 14:66) — which states
 * 18 legal references detected, 14 source found, 3 require review,
 * 1 could not be verified — and from the reference rail / document body
 * reproduced across the workspace frames (17:43, 25:53, 27:63, 31:83).
 */

/** The detection categories the design names in the reference rail. */
export type ClaimKind = 'Case citation' | 'Statutory reference' | 'Quotation'

export type Claim = {
  id: string
  kind: ClaimKind
  label: string
  excerpt: string
  status: VerificationStatus
  source?: string
  note?: string
}

/** Document metadata as the design displays it. */
export const DOCUMENT = {
  fileName: 'Bail_Application_Draft.docx',
  title: 'Application for Bail under Section 439, CrPC',
  court: 'IN THE COURT OF THE SESSIONS JUDGE AT PATNA',
  /** "18 legal references detected" */
  referenceCount: 18,
  /** "analysed in 42 seconds" */
  analysedIn: '42 seconds',
  /** "Page 3 of 24 · highlighted spans are detected references" */
  currentPage: 3,
  pageCount: 24,
  /** "Generated 27 Aug 2026 · 14:35 IST" on the report frame. */
  uploadedAt: '27 Aug 2026 · 14:35 IST',
  reviewer: 'A. P. Singh',
  recordNumber: 'LTL-2026-0847',
  state: 'Review in progress',
} as const

/**
 * One entry per verification point, in the detection state the summary screen
 * reports (before any lawyer decision has been recorded).
 */
export const CLAIMS: Claim[] = [
  {
    id: '01',
    kind: 'Statutory reference',
    label: 'Section 439 CrPC',
    excerpt: 'Application for Bail under Section 439, CrPC',
    status: 'Source found',
    source: 'Code of Criminal Procedure, 1973 — s.439',
    note: 'Repository: India Code · provision text retrieved in full.',
  },
  {
    id: '02',
    kind: 'Statutory reference',
    label: 'Section 437 CrPC',
    excerpt:
      'The applicant is not accused of an offence punishable with death or imprisonment for life within the meaning of Section 437 CrPC.',
    status: 'Source found',
    source: 'Code of Criminal Procedure, 1973 — s.437',
    note: 'Repository: India Code · provision text retrieved in full.',
  },
  {
    id: '03',
    kind: 'Case citation',
    label: 'Gurbaksh Singh Sibbia v. Punjab',
    excerpt:
      'The principles restated in Gurbaksh Singh Sibbia v. State of Punjab, (1980) 2 SCC 565 govern the exercise of this discretion.',
    status: 'Source found',
    source: '(1980) 2 SCC 565',
    note: 'Repository: Indian Kanoon · Bench: Supreme Court · 09 Apr 1980',
  },
  {
    id: '04',
    kind: 'Statutory reference',
    label: 'Section 41 CrPC',
    excerpt:
      "The guidelines in D.K. Basu v. State of West Bengal, (1997) 1 SCC 416 and the safeguards of Section 41 CrPC squarely apply to the applicant's arrest.",
    status: 'Source found',
    source: 'Code of Criminal Procedure, 1973 — s.41',
    note: 'Repository: India Code · provision text retrieved in full.',
  },
  {
    id: '05',
    kind: 'Case citation',
    label: 'D.K. Basu v. State of W.B.',
    excerpt:
      "The guidelines in D.K. Basu v. State of West Bengal, (1997) 1 SCC 416 and the safeguards of Section 41 CrPC squarely apply to the applicant's arrest.",
    status: 'Source found',
    source: '(1997) 1 SCC 416',
    note: 'Repository: Indian Kanoon · Bench: Supreme Court · 18 Dec 1996',
  },
  {
    id: '06',
    kind: 'Quotation',
    label: '“arrest is not mandatory…”',
    excerpt: '“arrest is not mandatory merely because it is permissible”',
    status: 'Requires review',
    source: 'Attributed to Arnesh Kumar v. State of Bihar, para 8',
    note: 'The quoted text does not appear verbatim in the located source passage.',
  },
  {
    id: '07',
    kind: 'Case citation',
    label: 'Arnesh Kumar v. Bihar',
    excerpt:
      'In Arnesh Kumar v. State of Bihar, (2014) 8 SCC 469, this position was affirmed: for offences punishable up to seven years, notice under Section 41A CrPC ought ordinarily to precede arrest, and bail is the rule.',
    status: 'Source found',
    source: '(2014) 8 SCC 469',
    note: 'Repository: Indian Kanoon · Bench: Supreme Court · 02 Jul 2014 · Match: case name and reporter citation consistent',
  },
  {
    id: '08',
    kind: 'Statutory reference',
    label: 'Section 41A CrPC notice',
    excerpt:
      'Notice under Section 41A CrPC ought ordinarily to precede arrest for offences punishable up to seven years.',
    status: 'Source found',
    source: 'Code of Criminal Procedure, 1973 — s.41A',
    note: 'Repository: India Code · provision text retrieved in full.',
  },
  {
    id: '09',
    kind: 'Case citation',
    label: 'Satender Kumar Antil v. CBI',
    excerpt:
      'Reliance is further placed on Satender Kumar Antil v. CBI, (2022) 10 SCC 51, which consolidates the governing bail principles and deprecates mechanical remand.',
    status: 'Could not be verified',
    source: '(2022) 10 SCC 51 — as cited in the draft',
    note: 'Searched: Indian Kanoon · connected repositories. Case name: match found (2021 SCC OnLine SC 3302). Reporter: (2022) 10 SCC 51 — no consistent match.',
  },
  {
    id: '10',
    kind: 'Case citation',
    label: 'Siddharth v. State of U.P.',
    excerpt:
      'Siddharth v. State of Uttar Pradesh, (2022) 1 SCC 676 deprecates routine arrest where the accused has cooperated throughout the investigation.',
    status: 'Source found',
    source: '(2022) 1 SCC 676',
    note: 'Repository: Indian Kanoon · Bench: Supreme Court · 16 Aug 2021',
  },
  {
    id: '11',
    kind: 'Statutory reference',
    label: 'Section 170 CrPC',
    excerpt:
      'The investigating officer was under no obligation to arrest the applicant before filing the report under Section 170 CrPC.',
    status: 'Source found',
    source: 'Code of Criminal Procedure, 1973 — s.170',
    note: 'Repository: India Code · provision text retrieved in full.',
  },
  {
    id: '12',
    kind: 'Case citation',
    label: 'Sanjay Chandra v. CBI',
    excerpt:
      'Sanjay Chandra v. CBI, (2012) 1 SCC 40 holds that the object of bail is neither punitive nor preventative.',
    status: 'Source found',
    source: '(2012) 1 SCC 40',
    note: 'Repository: Indian Kanoon · Bench: Supreme Court · 23 Nov 2011',
  },
  {
    id: '13',
    kind: 'Quotation',
    label: '“bail is the rule, jail…”',
    excerpt: '“bail is the rule and committal to jail an exception”',
    status: 'Requires review',
    source: 'Attributed to State of Rajasthan v. Balchand, para 2',
    note: 'The located passage carries the same sense but different wording.',
  },
  {
    id: '14',
    kind: 'Statutory reference',
    label: 'Section 167(2) CrPC',
    excerpt:
      'The statutory period contemplated by Section 167(2) CrPC has elapsed without the filing of a charge-sheet.',
    status: 'Source found',
    source: 'Code of Criminal Procedure, 1973 — s.167(2)',
    note: 'Repository: India Code · provision text retrieved in full.',
  },
  {
    id: '15',
    kind: 'Case citation',
    label: 'Moti Ram v. State of M.P.',
    excerpt:
      'Onerous sureties, as cautioned against in Moti Ram v. State of M.P., (1978) 4 SCC 47, would defeat the order itself.',
    status: 'Source found',
    source: '(1978) 4 SCC 47',
    note: 'Repository: Indian Kanoon · Bench: Supreme Court · 24 Aug 1978',
  },
  {
    id: '16',
    kind: 'Quotation',
    label: '“must record reasons…”',
    excerpt:
      '“the police officer must record reasons demonstrating necessity before effecting arrest”',
    status: 'Requires review',
    source: 'Attributed to the Hon’ble Supreme Court, para 4 of the draft',
    note: 'No attribution is given in the draft; the located passage is a paraphrase.',
  },
  {
    id: '17',
    kind: 'Statutory reference',
    label: 'Article 21, Constitution',
    excerpt:
      'Continued detention would offend the liberty guaranteed by Article 21 of the Constitution of India.',
    status: 'Source found',
    source: 'Constitution of India — Article 21',
    note: 'Repository: India Code · provision text retrieved in full.',
  },
  {
    id: '18',
    kind: 'Case citation',
    label: 'P. Chidambaram v. ED',
    excerpt:
      'P. Chidambaram v. Directorate of Enforcement, (2019) 9 SCC 24 sets out the triple test applied to bail in economic offences.',
    status: 'Source found',
    source: '(2019) 9 SCC 24',
    note: 'Repository: Indian Kanoon · Bench: Supreme Court · 05 Sep 2019',
  },
]

const EMPTY_COUNTS: Record<VerificationStatus, number> = {
  'Source found': 0,
  'Requires review': 0,
  'Could not be verified': 0,
  Confirmed: 0,
  Corrected: 0,
  Rejected: 0,
  Unresolved: 0,
}

/** Totals per verification status, derived from CLAIMS. */
export const CLAIM_COUNTS: Record<VerificationStatus, number> = CLAIMS.reduce<
  Record<VerificationStatus, number>
>(
  (counts, claim) => {
    counts[claim.status] += 1
    return counts
  },
  { ...EMPTY_COUNTS },
)
