// 서버의 거절 code → 저장소의 거절 갈래(StoreErrorKind). 서버 code 를 앱 안의 말로 옮기는 자리는 이 표 하나다.
//
// 서버(apps/api-py, 밴드 E2 뒤)의 오류 본문은 `{error:{code,message,fields,legacyCode}}` 이고 code 는 대문자 세부 이름이다.
// StoreErrorKind 는 앱 안의 말이라 소문자 그대로 둔다. 옛 소문자 legacyCode 는 읽지 않는다(C1 에서 걷힌다).
// 실어댑터(api/server.ts, 밴드 GW1R)가 이 표를 쓴다. 목 저장소는 StoreError 를 바로 던지므로 이 표를 거치지 않는다.
import type { StoreErrorKind } from './store.ts';

/** 세부 이름으로 가르는 것. 409 의 셋은 검토 저장(putReview)의 거절이다. */
export const STORE_ERROR_BY_CODE: Readonly<Record<string, StoreErrorKind>> = {
  REVIEW_LOCKED: 'review_locked',
  RUN_NOT_DONE: 'run_not_done',
  NO_REVIEW: 'no_review',
  // 재판단 만들기(밴드 GRJ1)의 409 둘.
  REJUDGE_RUNNING: 'rejudge_running',
  NOTHING_TO_REJUDGE: 'nothing_to_rejudge',
  NOT_FOUND: 'not_found',
  VALIDATION_ERROR: 'rejected',
  BAD_REQUEST: 'rejected',
  // 실어댑터(밴드 GW1R ① Q12)가 만나는 400·409 셋. 상태 코드로도 rejected 지만 이름으로 못 박는다(뒤에 갈래가 생기면 여기서 바꾼다).
  INVALID_REVIEW: 'rejected',
  INVALID_OPTIONS: 'rejected',
  DOCUMENT_NOT_UPLOADED: 'rejected',
  // 엑셀 report(밴드 GW2R ③)의 409 둘: 확정 전에 확정본을 청함·dry-run(엑셀 없음). 화면은 갈래 없이 「내려받지 못했어요」.
  NOT_CONFIRMED: 'rejected',
  NO_REPORT: 'rejected',
  // 보고연도 PATCH(밴드 GW2R ③)의 409 — 올림 확인 전 문서.
  NOT_UPLOADED: 'rejected',
  // 실행 만들기(밴드 GR2)의 409 — 같은 Idempotency-Key 에 다른 본문. 표로는 rejected, createRun 만 key_reused 로 덮는다(server.ts, sid:MARC-ISSUE-312).
  IDEMPOTENCY_KEY_REUSED: 'rejected',
  // 문서 만들기의 413 — 크기 한도(GP1 §1-8). 앞단 프록시의 이름 없는 413 은 아래 상태 코드로.
  UPLOAD_TOO_LARGE: 'too_large',
};

/**
 * 거절 하나를 갈래로. code 가 표에 있으면 그것, 없으면 상태 코드로: 404 류 → not_found, 413 → too_large, 422·400 → rejected.
 * 그 밖(401·403·409 의 모르는 이름·5xx …)은 rejected 다(storeErrorKind 가 StoreError 아닌 것을 rejected 로 보는 것과 같다).
 */
export function storeErrorKindOf(status: number, code: string): StoreErrorKind {
  if (Object.hasOwn(STORE_ERROR_BY_CODE, code))
    return STORE_ERROR_BY_CODE[code]!;
  if (status === 404) return 'not_found';
  if (status === 413) return 'too_large';
  return 'rejected';
}
