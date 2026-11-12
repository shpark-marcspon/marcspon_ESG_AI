// 서버 단계 → 판 IR-03 줄 여섯(밴드 IRW1 ① — 발주서 §2-1, 감독 정함). 서버 단계는 materiality.iro@155 의 열(★B —
//   apps/api-py/esgapi/materiality/flows/iro_155.py:163-170): load · regulation · keywords · controversy · report · part2_seed ·
//   impact · financial · pathway · report_iro. 줄 이름·설명 글은 판(config/text.ts 의 IR_TEXT.status.steps).
// 줄 상태: 하나라도 failed → 실패 · 전부 done → 완료 · running 이 있거나 done·pending 이 섞임 → 진행 중 · 그 밖 대기.
// 모르는 단계 이름 → 던진다(의도 — 서버가 단계를 바꾸면 이 표를 고친다. 화면은 shared load-failure 로 보인다).
// 진행 수: 진행 중 줄의 토픽(2부는 서브토픽 자리) 단계 done/total(IRW6, sid:MARC-ISSUE-378). 끝난 줄 「· n건」은 서버가 내지 않아 0(Q3).
import type { RunStep } from './result.ts';

export type StepLine =
  'regulation' | 'controversy' | 'impact' | 'financial' | 'pathway' | 'report';

/** 줄 여섯(판 차례)과 그 줄에 드는 서버 단계. */
export const STEP_LINES: readonly {
  line: StepLine;
  steps: readonly string[];
}[] = [
  { line: 'regulation', steps: ['load', 'regulation'] },
  {
    line: 'controversy',
    steps: ['keywords', 'controversy', 'report', 'part2_seed'],
  },
  { line: 'impact', steps: ['impact'] },
  { line: 'financial', steps: ['financial'] },
  { line: 'pathway', steps: ['pathway'] },
  { line: 'report', steps: ['report_iro'] },
];

export type LineStatus = 'pending' | 'running' | 'done' | 'failed';

export interface StepCount {
  done: number;
  total: number;
  unit: 'topic' | 'subtopic';
}

export interface StepLineView {
  line: StepLine;
  status: LineStatus;
  /** 진행 중 줄의 수(그 줄 running · 수 단계 running · total > 0 일 때만), 그 밖 null. */
  count: StepCount | null;
}

/** 줄 → 수를 내는 서버 단계와 단위(2부 셋은 서버 셈 그대로 서브토픽 자리 — IRW6 Q2). report 줄은 수 없음. */
const COUNTED: Partial<
  Record<StepLine, { step: string; unit: StepCount['unit'] }>
> = {
  regulation: { step: 'regulation', unit: 'topic' },
  controversy: { step: 'controversy', unit: 'topic' },
  impact: { step: 'impact', unit: 'subtopic' },
  financial: { step: 'financial', unit: 'subtopic' },
  pathway: { step: 'pathway', unit: 'subtopic' },
};

function countOf(
  line: StepLine,
  status: LineStatus,
  steps: readonly RunStep[],
): StepCount | null {
  const counted = COUNTED[line];
  if (counted === undefined || status !== 'running') return null;
  const step = steps.find((s) => s.step === counted.step);
  if (
    step === undefined ||
    step.status !== 'running' ||
    step.done === null ||
    step.total === null ||
    step.total <= 0
  )
    return null;
  return { done: step.done, total: step.total, unit: counted.unit };
}

export class UnknownStepError extends Error {
  constructor(step: string) {
    super(`unknown materiality step: ${step}`);
    this.name = 'UnknownStepError';
  }
}

const KNOWN = new Set(STEP_LINES.flatMap(({ steps }) => steps));

/** 줄 여섯의 상태. 서버가 주지 않은 단계는 pending. 모르는 단계 이름이 있으면 던진다. */
export function stepLines(steps: readonly RunStep[]): StepLineView[] {
  for (const step of steps)
    if (!KNOWN.has(step.step)) throw new UnknownStepError(step.step);
  return STEP_LINES.map(({ line, steps: names }) => {
    const statuses = names.map(
      (name) => steps.find((step) => step.step === name)?.status ?? 'pending',
    );
    const status: LineStatus =
      statuses.includes('failed') ? 'failed'
      : statuses.every((s) => s === 'done') ? 'done'
      : statuses.includes('running') || statuses.includes('done') ? 'running'
      : 'pending';
    return { line, status, count: countOf(line, status, steps) };
  });
}

/** 머리 「진행 <지금 줄 이름>」의 줄: 진행 중(또는 실패) 줄, 없으면 끝난 줄 다음(다 끝났으면 마지막). */
export function currentLine(views: readonly StepLineView[]): StepLine {
  const at = views.find(
    (view) => view.status === 'running' || view.status === 'failed',
  );
  if (at !== undefined) return at.line;
  const next = views.find((view) => view.status !== 'done');
  return (next ?? views[views.length - 1]!).line;
}

/** 서버 단계 이름 하나 → 판 줄(목록 「처리 중 · <줄 이름>」 — currentStep). 모르는 이름이면 null(화면은 「처리 중」만). */
export function lineOfStep(step: string): StepLine | null {
  return STEP_LINES.find(({ steps }) => steps.includes(step))?.line ?? null;
}
