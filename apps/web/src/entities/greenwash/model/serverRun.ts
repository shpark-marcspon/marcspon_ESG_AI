// 서버 실행 상태 → 화면 진행 모델(밴드 FW2 ①, sid:MARC-ISSUE-99 3). 순수 함수만.
// 계약: generated/api.d.ts 의 RunOut.status(queued·processing·done·failed)와 RunOut.steps[](RunStepOut: step·status·done·total).
// 흐름 greenwash.colab@E0 의 단계 여섯(선언 차례): extract · index · judge · wordcount · locate · report.
//   화면 단계 셋: 텍스트 추출 = extract, 문장 찾기·판정 = index + judge, 정리 = wordcount + locate + report.
//   판정 쪽 진행은 judge 단계의 done/total 이다(없으면 0 / 점검할 쪽 수).
// 무효 조건: 서버가 단계 이름을 바꾸거나 더하면(모르는 단계는 건너뛴다) 표를 고친다. judge 의 done/total 이 쪽이 아니라 문장 수면
//   GW-03 의 「n / m쪽」 글이 틀린다(지금 계약은 단위를 말하지 않는다 — 보고 「계약에 물을 것」).
import { RUN_STAGES } from './progress.ts';
import type { RunProgress, RunStage } from './progress.ts';

export type ServerRunStatus = 'queued' | 'processing' | 'done' | 'failed';
export type ServerStepStatus = 'pending' | 'running' | 'done' | 'failed';

export interface ServerStep {
  step: string;
  status: ServerStepStatus;
  done: number | null;
  total: number | null;
}

/** 서버 단계 → 화면 단계. */
export const SERVER_STAGE: Readonly<Record<string, RunStage>> = {
  extract: 'extract',
  index: 'judge',
  judge: 'judge',
  wordcount: 'summarize',
  locate: 'summarize',
  report: 'summarize',
};

/**
 * 화면 진행 모델로 맞춘다.
 * - state: done → done, failed → failed, queued·processing → running.
 * - stage: 실패면 실패한 단계(없으면 끝나지 않은 첫 단계), 돌고 있으면 끝나지 않은 첫 단계, 다 끝났으면 정리.
 * - judge: judge 단계의 done/total. total 이 없으면 checkedPages, 판정을 지났으면 done = total.
 */
export function progressFromServer(
  status: ServerRunStatus,
  steps: readonly ServerStep[],
  checkedPages: number,
): RunProgress {
  const known = steps.filter((step) => SERVER_STAGE[step.step] !== undefined);
  const failedStep = known.find((step) => step.status === 'failed');
  const openStep = known.find((step) => step.status !== 'done');
  const at: RunStage =
    status === 'done' ? 'summarize'
    : status === 'failed' && failedStep ? SERVER_STAGE[failedStep.step]!
    : openStep ? SERVER_STAGE[openStep.step]!
    : 'summarize';
  const judgeStep = known.find((step) => step.step === 'judge');
  const total = judgeStep?.total ?? checkedPages;
  const pastJudge =
    status === 'done' || RUN_STAGES.indexOf(at) > RUN_STAGES.indexOf('judge');
  const done = pastJudge ? total : Math.min(judgeStep?.done ?? 0, total);
  return {
    state:
      status === 'done' ? 'done'
      : status === 'failed' ? 'failed'
      : 'running',
    stage: at,
    judge: { done, total },
  };
}
