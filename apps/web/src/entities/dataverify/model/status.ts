// 실행·단계·결과 단계의 상태 갈래(밴드 DV2a ① — 판 DV-03·04·04a, 디자인 2e DV2a-design-text.md ③④). 글은 문구 표가 갈래 열쇠로 고른다.
// 단계 상태 잇기(발주서 §1-3): pending → 대기 · running → 진행 중 · done → 완료 · failed → 못 함. 「돌리지 않음」은 단계 값에 없고
//   실행이 끝난 뒤 결과의 plan·review·insight.status = not_run 에서만 온다. 결과 단계의 partial 은 「다 마치기 전에 멈춤」(밴드 DV6 — 횟수 상한은 말하지 않는다).
// 실패 까닭은 둘로만(2e ③): unparsable → unreadable(「AI 답을 읽지 못했어요」), 그 밖 일곱 → call(「AI 호출이 실패했어요」).
import { formatKst } from '../../../shared/lib/time.ts';
import { STEP_NAMES } from './result.ts';
import type {
  DataverifyResult,
  FailureKind,
  RunStep,
  StepName,
  StepStatus,
} from './result.ts';

export interface StepView {
  name: StepName;
  status: StepStatus;
}

/** 단계 다섯(흐름 차례). 서버가 주지 않은 단계는 대기. */
export function stepViews(steps: readonly RunStep[]): StepView[] {
  return STEP_NAMES.map((name) => ({
    name,
    status: steps.find((step) => step.step === name)?.status ?? 'pending',
  }));
}

/** 「다섯 단계 가운데 n번째」의 n: 진행 중(또는 못 함) 단계, 없으면 끝난 단계 다음(1..5). */
export function currentStep(views: readonly StepView[]): number {
  const at = views.findIndex(
    (view) => view.status === 'running' || view.status === 'failed',
  );
  if (at >= 0) return at + 1;
  const done = views.filter((view) => view.status === 'done').length;
  return Math.min(done + 1, views.length);
}

export type Stage = 'plan' | 'review' | 'insight';
export const STAGES: readonly Stage[] = ['plan', 'review', 'insight'];
/** 결과 단계 줄의 상태: 완료 · 다 마치기 전에 멈춤 · 실패 · 돌리지 않음. */
export type StageState = 'done' | 'partial' | 'failed' | 'not_run';

export function stageState(result: DataverifyResult, stage: Stage): StageState {
  const value = result[stage];
  if (value.status === 'done') return value.partial ? 'partial' : 'done';
  return value.status;
}

/** 「일부 단계 못 함」: 세 단계 가운데 실패가 하나 이상. */
export const someStageFailed = (result: DataverifyResult) =>
  STAGES.some((stage) => result[stage].status === 'failed');

export type FailureReason = 'unreadable' | 'call';
export const failureReason = (kind: FailureKind): FailureReason =>
  kind === 'unparsable' ? 'unreadable' : 'call';

/** 띠 갈래(2e ③ 표의 줄, 계산 계획 → 계산 검토 → 인사이트 차례). */
export type Notice =
  | 'plan_partial'
  | 'plan_unreadable'
  | 'plan_failed'
  | 'review_partial'
  | 'review_failed'
  | 'insight_partial'
  | 'insight_failed';

export function notices(result: DataverifyResult): Notice[] {
  const out: Notice[] = [];
  const { plan, review, insight } = result;
  if (plan.status === 'done' && plan.partial) out.push('plan_partial');
  if (plan.status === 'failed')
    out.push(
      failureReason(plan.failure.kind) === 'unreadable' ? 'plan_unreadable' : (
        'plan_failed'
      ),
    );
  if (review.status === 'done' && review.partial) out.push('review_partial');
  if (review.status === 'failed') out.push('review_failed');
  if (insight.status === 'done' && insight.partial) out.push('insight_partial');
  if (insight.status === 'failed') out.push('insight_failed');
  return out;
}

/** 경고 「입력에 테마 「환경」이 없다」(colab_156.py:400). 「환경」이 빈 목록이면 이 경고가 없다. */
export const NO_TARGET_THEME = 'no_target_theme';
export const hasNoTarget = (result: DataverifyResult) =>
  result.warnings.includes(NO_TARGET_THEME);

/** 실행 시각 글(한국 시각 「2026-10-19 10:40」 — 화면은 shared/lib 을 직접 부르지 않는다). 읽을 수 없으면 받은 글자 그대로. */
export const atText = (iso: string) => formatKst(iso);
