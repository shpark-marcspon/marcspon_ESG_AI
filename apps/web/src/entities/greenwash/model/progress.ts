// 실행 진행 모델(밴드 FW1b ①, 시안 GW-03_r1). 처리 흐름 여섯 단계를 화면에서는 셋으로 묶는다(인계 3절).
//   1 텍스트 추출 → 2 문장 찾기·판정(이 단계만 쪽 진행 done/total) → 3 정리.
// 전체 진행률은 단계 무게로 셈한다: 추출 10 · 판정 80 · 정리 10(%). 판정 단계는 쪽 진행에 비례한다.
//   가정이다(무효 조건: 서버가 진행률을 직접 주거나 단계 시간이 크게 다르면 무게를 바꾼다). 진행 갱신 방식(폴링·SSE)은 정하지 않는다.

export const RUN_STAGES = ['extract', 'judge', 'summarize'] as const;
export type RunStage = (typeof RUN_STAGES)[number];

export const STAGE_WEIGHTS: Readonly<Record<RunStage, number>> = {
  extract: 10,
  judge: 80,
  summarize: 10,
};

export type RunState = 'running' | 'failed' | 'done';

export interface RunProgress {
  state: RunState;
  /** 지금(또는 멈춘) 단계. done 이면 의미 없다. */
  stage: RunStage;
  /** 판정 단계의 쪽 진행. total 은 점검할 쪽 수. */
  judge: { done: number; total: number };
}

export type StageState = 'done' | 'now' | 'todo' | 'failed';

/** 단계마다의 상태. */
export function stageStates(
  progress: RunProgress,
): Record<RunStage, StageState> {
  const at = RUN_STAGES.indexOf(progress.stage);
  const result = {} as Record<RunStage, StageState>;
  RUN_STAGES.forEach((stage, index) => {
    result[stage] =
      progress.state === 'done' || index < at ? 'done'
      : index > at ? 'todo'
      : progress.state === 'failed' ? 'failed'
      : 'now';
  });
  return result;
}

/** 전체 진행률(0~100 정수, 내림). done 이면 100. */
export function overallPercent(progress: RunProgress): number {
  if (progress.state === 'done') return 100;
  let sum = 0;
  for (const stage of RUN_STAGES) {
    if (stage === progress.stage) {
      if (stage === 'judge' && progress.judge.total > 0)
        sum +=
          (STAGE_WEIGHTS.judge *
            Math.min(progress.judge.done, progress.judge.total)) /
          progress.judge.total;
      break;
    }
    sum += STAGE_WEIGHTS[stage];
  }
  return Math.floor(sum);
}

/** 실패 지점. 실패가 아니면 null. 판정 단계면 쪽 진행을 함께 낸다. */
export function failurePoint(
  progress: RunProgress,
): { stage: RunStage; judge?: { done: number; total: number } } | null {
  if (progress.state !== 'failed') return null;
  return progress.stage === 'judge' ?
      { stage: 'judge', judge: { ...progress.judge } }
    : { stage: progress.stage };
}
