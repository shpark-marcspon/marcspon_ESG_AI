// 실행 실패의 갈래(밴드 GW2R ② — GW-03 r3 멈춤 카드, GW-01 다음 할 일). 순수 함수만.
// 가름은 실패 code(서버 RunOut.errorCode) 하나다. 멈춘 단계(extract·index)나 글로 가르지 않는다:
//   서버는 setup_error 를 index 단계에서(tests_integration/test_run_flow.py), no_text_layer 를 extract 단계에서 내고,
//   step_error 는 어느 단계에서든 난다 — 단계로 가르면 index 의 step_error 를 설정 문제로, extract 의 step_error 를 스캔본으로 잘못 본다.
//   - no_text_layer: 글자 층 없는 PDF(디자인 원문 v101·v115 GW-03 r3 「멈춤 · 스캔본 PDF」) — [새 점검]. 같은 파일로 다시 돌려도 같은 끝.
//   - setup_error: 키·공급사 설정 없음(sid:MARC-ISSUE-228 노트, 디자인 답 D1) — [목록으로]만. 다시 실행해도 같은 끝.
//   - 그 밖(step_error·attempts_exhausted·모름·null): 일반 멈춤 — [다시 실행].

/** 글자 층이 없는 PDF 의 실패 code(서버 runs/calc/errors.py). */
export const NO_TEXT_LAYER = 'no_text_layer';
/** 서비스 설정(키·공급사)이 없어 시작하지 못한 실패 code. */
export const SETUP_ERROR = 'setup_error';

export type FailureKind = 'no_text' | 'setup' | 'general';

/** 실패 code → 갈래. */
export function failureKind(errorCode: string | null | undefined): FailureKind {
  if (errorCode === NO_TEXT_LAYER) return 'no_text';
  if (errorCode === SETUP_ERROR) return 'setup';
  return 'general';
}

/** [다시 실행]을 둘 실패인가(일반 멈춤만 — 같은 입력으로 다시 돌려 나을 수 있다). */
export function canRerun(errorCode: string | null | undefined): boolean {
  return failureKind(errorCode) === 'general';
}
