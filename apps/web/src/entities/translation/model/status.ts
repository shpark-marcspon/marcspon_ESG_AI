// 영문번역 파트 상태의 셈(밴드 TRW0b, 결정 sid:MARC-ENT-392·393·404). 순수 함수와 타입만 — 글은 config/text.ts, 글로 바꾸는 것은 ui/labels.ts
//   (칸 규칙: config 는 ui 만 가져온다 — app/guards/layers.test.ts). 서버 상태 낱말과 잇는 것은 어댑터 몫(TRW1).

/** 파트(실행) 하나의 상태. 탭·목록·표가 같이 쓴다. failed_partial = 끝까지 갔지만 못 옮긴 쪽이 있거나 검수가 멈춤(디자인 e9). */
export const TAB_STATES = [
  'done',
  'running',
  'queued',
  'failed',
  'failed_partial',
] as const;
export type TabState = (typeof TAB_STATES)[number];

/** 묶음 셈의 상태 — 실패 둘(failed·failed_partial)은 「실패」 하나로 센다(감독 답 ★A, 10-23). */
export type SummaryState = 'done' | 'running' | 'queued' | 'failed';
/** 묶음 셈의 글 차례(시안 TR-01 「완료 2 진행 중 1」·「완료 1 실패 1」·「진행 중 1 대기 1」 — ★A). */
export const SUMMARY_ORDER: readonly SummaryState[] = [
  'done',
  'running',
  'queued',
  'failed',
];

/** 준비 단계에서 막은 까닭(시안 TR-03 4번 표의 다섯). 글은 config/text.ts(디자인 e9 확정 판 예고). */
export const REJECTION_KEYS = [
  'no_pages',
  'ceo_over_limit',
  'bad_file',
  'too_large',
  'over_budget',
] as const;
export type RejectionKey = (typeof REJECTION_KEYS)[number];

/** 번역 검수 이슈 유형 열(시안 TR-04 「유형은 열 가지예요」 차례). 서버 글자와 잇는 것·「그 밖」 줄은 어댑터 몫. */
export const ISSUE_TYPE_KEYS = [
  'glossary_violation',
  'term_inconsistency',
  'structure_changed',
  'omission',
  'untranslated',
  'number_unit',
  'grammar',
  'unnatural',
  'table_content',
  'figure_caption',
] as const;
export type IssueTypeKey = (typeof ISSUE_TYPE_KEYS)[number];

/** 심각도(shared RiskBadge 의 등급과 같은 셋). */
export const SEVERITIES = ['high', 'mid', 'low'] as const;
export type Severity = (typeof SEVERITIES)[number];

/** 파트 상태를 가진 것(파트 줄·탭). */
interface HasState {
  state: TabState;
}

/** 실패 둘을 「실패」로. */
export function summaryStateOf(state: TabState): SummaryState {
  return state === 'failed_partial' ? 'failed' : state;
}

/** 묶음 셈(「완료 2 · 진행 중 1」): 있는 상태만, SUMMARY_ORDER 차례. */
export function batchSummary(
  parts: readonly HasState[],
): { state: SummaryState; n: number }[] {
  return SUMMARY_ORDER.flatMap((state) => {
    const n = parts.filter(
      (part) => summaryStateOf(part.state) === state,
    ).length;
    return n > 0 ? [{ state, n }] : [];
  });
}

/** 끝난(완료) 파트 수. */
export function doneCount(parts: readonly HasState[]): number {
  return parts.filter((part) => part.state === 'done').length;
}

/** 돌거나 기다리는 파트가 있는가. */
export function isActive(state: TabState): boolean {
  return state === 'running' || state === 'queued';
}

/**
 * 화면 제목 갈래(시안 TR-03 「화면 제목은 …」): 하나라도 돌거나 기다리면 running,
 * 도는 것 없이 실패가 있으면 needs_retry, 그 밖(모두 완료)은 done.
 */
export type ScreenTitleKey = 'running' | 'done' | 'needs_retry';
export function screenTitleKey(parts: readonly HasState[]): ScreenTitleKey {
  if (parts.some((part) => isActive(part.state))) return 'running';
  if (parts.some((part) => summaryStateOf(part.state) === 'failed'))
    return 'needs_retry';
  return 'done';
}

/** 목록 줄의 다음 할 일(묶음): 돌거나 기다리는 파트가 있으면 진행 보기, 아니면 결과 보기. */
export function batchNext(parts: readonly HasState[]): 'progress' | 'result' {
  return parts.some((part) => isActive(part.state)) ? 'progress' : 'result';
}

/** 파트 줄의 갈래(결정 393): 거절(까닭 있음)·서버 오류·일부 쪽. */
export type FailureKind = 'server_error' | 'partial' | 'rejected';
export function failureKindOf(part: {
  state: TabState;
  reason?: RejectionKey;
}): FailureKind | null {
  if (part.state === 'failed_partial') return 'partial';
  if (part.state !== 'failed') return null;
  return part.reason === undefined ? 'server_error' : 'rejected';
}
