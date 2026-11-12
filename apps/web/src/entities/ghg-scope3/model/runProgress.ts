// Scope 3 실행의 진행 셈(밴드 S3W3d ③ — 발주서 1-5·1-6 G, 값 파일 V1·덧). 순수 함수 — 글·표기 0(글은 pages 쪽이 고른다).
// GET /runs/{id} 의 steps 를 읽는다. 쓸 수 있는 것은 단계 이름과 status 뿐이다: total 은 늘 done 과 같고(서버가 estimate 를 안 넘김) done 은 LLM 호출 수라 진행률이 아니다.
// 끝난 단계 수는 시간 비율이 아니다(시트 없는 단계는 곧바로 끝난다) — 퍼센트·남은 시간을 만들지 않는다.

/** 서버 선언 차례의 단계(esgapi/inventory/flows/scope3_colab_157.py). C10 은 계산 단계가 없다. */
export const RUN_STEP_NAMES = [
  'c1',
  'c2',
  'c3',
  'c4',
  'c5',
  'c6',
  'c7',
  'c8',
  'c9',
  'c11',
  'c12',
  'c13',
  'c14',
  'c15',
  'assemble',
] as const;
export type RunStepName = (typeof RUN_STEP_NAMES)[number];

export const RUN_STEP_STATUSES = [
  'pending',
  'running',
  'done',
  'failed',
] as const;
export type RunStepStatus = (typeof RUN_STEP_STATUSES)[number];

export interface RunStep {
  step: RunStepName;
  status: RunStepStatus;
}

/** 화면에 그릴 진행. 마무리는 세지 않는다(값 파일 덧). 단계를 못 읽으면 null(셈 줄을 숨긴다). */
export type RunProgress =
  { kind: 'counting'; done: number; total: number } | { kind: 'assembling' };

export function progressOf(steps: readonly RunStep[]): RunProgress | null {
  const categories = steps.filter((one) => one.step !== 'assemble');
  if (categories.length === 0) return null;
  const assembling = steps.some(
    (one) => one.step === 'assemble' && one.status === 'running',
  );
  if (assembling) return { kind: 'assembling' };
  return {
    kind: 'counting',
    done: categories.filter((one) => one.status === 'done').length,
    total: categories.length,
  };
}
