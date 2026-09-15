import type { DocumentParagraph } from '@/components/workspace/WorkspaceLayout'

/** Page 3 of the draft (nodes 21:57 – 21:60); shared by the other workspace variants. */
export const DRAFT_PARAGRAPHS: DocumentParagraph[] = [
  {
    id: '3',
    segments: [
      {
        text: '3.  It is respectfully submitted that the alleged offence carries a maximum punishment of seven years. The guidelines in ',
      },
      { text: 'D.K. Basu v. State of West Bengal, (1997) 1 SCC 416', tone: 'found' },
      { text: ' and the safeguards of ' },
      { text: 'Section 41 CrPC', tone: 'found' },
      { text: " squarely apply to the applicant's arrest." },
    ],
  },
  {
    id: '4',
    segments: [
      { text: "4.  The Hon'ble Supreme Court has held that " },
      { text: '“arrest is not mandatory merely because it is permissible”', tone: 'review' },
      {
        text: ', and that the police officer must record reasons demonstrating necessity before effecting arrest.',
      },
    ],
  },
  {
    id: '5',
    segments: [
      { text: '5.  In ' },
      { text: 'Arnesh Kumar v. State of Bihar, (2014) 8 SCC 469', tone: 'active' },
      {
        text: ', this position was affirmed: for offences punishable up to seven years, notice under Section 41A CrPC ought ordinarily to precede arrest, and bail is the rule.',
      },
    ],
  },
  {
    id: '6',
    segments: [
      { text: '6.  Reliance is further placed on ' },
      { text: 'Satender Kumar Antil v. CBI, (2022) 10 SCC 51', tone: 'unverified' },
      {
        text: ', which consolidates the governing bail principles and deprecates mechanical remand.',
      },
    ],
  },
]
