/**
 * The 10-screen desktop flow from Figma page "01 · Desktop Flow".
 * Order and node ids mirror the Figma canvas so screens stay traceable.
 */
export type FlowStep = {
  path: string
  /** Figma node id for this frame. */
  nodeId: string
  /** Number shown on the Figma frame label, e.g. "01". */
  step: string
  label: string
  title: string
}

export const FLOW: FlowStep[] = [
  { path: '/', nodeId: '4:2', step: '01', label: 'Landing', title: '01 · Landing' },
  { path: '/upload', nodeId: '12:10', step: '02', label: 'Upload', title: '02 · Upload' },
  { path: '/analyzing', nodeId: '14:23', step: '03', label: 'Analysing', title: '03 · Analyzing' },
  {
    path: '/summary',
    nodeId: '14:66',
    step: '04',
    label: 'Detection Summary',
    title: '04 · Detection Summary',
  },
  {
    path: '/workspace/evidence',
    nodeId: '17:43',
    step: '05',
    label: 'Review · Evidence',
    title: '05 · Workspace — Evidence',
  },
  {
    path: '/workspace/quote-mismatch',
    nodeId: '25:53',
    step: '06',
    label: 'Review · Quote Mismatch',
    title: '06 · Workspace — Quote Mismatch',
  },
  {
    path: '/workspace/unverified',
    nodeId: '27:63',
    step: '07',
    label: 'Review · Not Verifiable',
    title: '07 · Workspace — Could Not Be Verified',
  },
  {
    path: '/workspace/complete',
    nodeId: '29:73',
    step: '08',
    label: 'Review Complete',
    title: '08 · Workspace — Review Complete',
  },
  {
    path: '/report',
    nodeId: '31:83',
    step: '09',
    label: 'Verification Report',
    title: '09 · Verification Report',
  },
  {
    path: '/senior-review',
    nodeId: '31:207',
    step: '10',
    label: 'Senior Review',
    title: '10 · Senior Review',
  },
]

export function getFlowIndex(pathname: string): number {
  return FLOW.findIndex((s) => s.path === pathname)
}

export function getNextStep(pathname: string): FlowStep | undefined {
  const i = getFlowIndex(pathname)
  return i >= 0 ? FLOW[i + 1] : undefined
}

export function getPrevStep(pathname: string): FlowStep | undefined {
  const i = getFlowIndex(pathname)
  return i > 0 ? FLOW[i - 1] : undefined
}
