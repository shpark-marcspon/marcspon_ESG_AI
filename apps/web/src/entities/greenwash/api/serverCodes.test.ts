import { describe, expect, it } from 'vitest';

import { STORE_ERROR_BY_CODE, storeErrorKindOf } from './serverCodes.ts';

describe('서버 code → 저장소의 거절 갈래', () => {
  it.each([
    [409, 'REVIEW_LOCKED', 'review_locked'],
    [409, 'RUN_NOT_DONE', 'run_not_done'],
    [409, 'NO_REVIEW', 'no_review'],
    [404, 'NOT_FOUND', 'not_found'],
    [422, 'VALIDATION_ERROR', 'rejected'],
    [400, 'BAD_REQUEST', 'rejected'],
    [400, 'INVALID_REVIEW', 'rejected'],
    [400, 'INVALID_OPTIONS', 'rejected'],
    [409, 'DOCUMENT_NOT_UPLOADED', 'rejected'],
    [409, 'IDEMPOTENCY_KEY_REUSED', 'rejected'],
    [413, 'UPLOAD_TOO_LARGE', 'too_large'],
    [409, 'REJUDGE_RUNNING', 'rejudge_running'],
    [409, 'NOTHING_TO_REJUDGE', 'nothing_to_rejudge'],
  ] as const)('%i %s → %s', (status, code, kind) => {
    expect(storeErrorKindOf(status, code)).toBe(kind);
  });

  it('표의 줄은 이 열여섯뿐이다(GW1R ① 이 셋을, GW2R ③ 이 report 의 NOT_CONFIRMED·NO_REPORT 와 PATCH 의 NOT_UPLOADED 를, GR2 가 IDEMPOTENCY_KEY_REUSED 를, GP1 이 UPLOAD_TOO_LARGE 를, GRJ1 이 재판단 409 둘을 더함)', () => {
    expect(STORE_ERROR_BY_CODE).toEqual({
      REVIEW_LOCKED: 'review_locked',
      RUN_NOT_DONE: 'run_not_done',
      NO_REVIEW: 'no_review',
      REJUDGE_RUNNING: 'rejudge_running',
      NOTHING_TO_REJUDGE: 'nothing_to_rejudge',
      NOT_FOUND: 'not_found',
      VALIDATION_ERROR: 'rejected',
      BAD_REQUEST: 'rejected',
      INVALID_REVIEW: 'rejected',
      INVALID_OPTIONS: 'rejected',
      DOCUMENT_NOT_UPLOADED: 'rejected',
      NOT_CONFIRMED: 'rejected',
      NO_REPORT: 'rejected',
      NOT_UPLOADED: 'rejected',
      IDEMPOTENCY_KEY_REUSED: 'rejected',
      UPLOAD_TOO_LARGE: 'too_large',
    });
  });

  it('표에 없는 이름은 상태 코드로: 404 류는 not_found, 그 밖은 rejected', () => {
    expect(storeErrorKindOf(404, 'RUN_NOT_FOUND')).toBe('not_found');
    expect(storeErrorKindOf(404, 'DOCUMENT_NOT_FOUND')).toBe('not_found');
    expect(storeErrorKindOf(422, 'HTTP_422')).toBe('rejected');
    expect(storeErrorKindOf(409, 'NOT_CONFIRMED')).toBe('rejected');
    expect(storeErrorKindOf(403, 'FORBIDDEN')).toBe('rejected');
    expect(storeErrorKindOf(500, 'INTERNAL_SERVER_ERROR')).toBe('rejected');
    // 이름 없는 413(앞단 프록시의 본문 한도)도 크기 갈래(밴드 GP1)
    expect(storeErrorKindOf(413, '')).toBe('too_large');
  });

  it('옛 소문자와 객체의 물려받은 이름은 표에 걸리지 않는다', () => {
    expect(storeErrorKindOf(409, 'review_locked')).toBe('rejected');
    expect(storeErrorKindOf(409, 'run_not_done')).toBe('rejected');
    expect(storeErrorKindOf(409, 'toString')).toBe('rejected');
    expect(storeErrorKindOf(409, '__proto__')).toBe('rejected');
  });
});
