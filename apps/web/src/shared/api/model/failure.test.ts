import { describe, expect, it } from 'vitest';

import {
  asFailure,
  companyRefusalOf,
  failureOf,
  isApiFailure,
  needsReauth,
} from './failure.ts';
import type { ApiFailure } from './failure.ts';

describe('실패의 가름', () => {
  it('서버가 정한 꼴이면 api. code 는 대문자 그대로, fields 가 null 이면 빈 객체, legacyCode 는 싣지 않는다', () => {
    const failure = failureOf(403, {
      error: {
        code: 'FORBIDDEN',
        message: '지어낸-말',
        fields: null,
        legacyCode: 'forbidden',
      },
    });
    expect(failure).toEqual({
      kind: 'api',
      status: 403,
      code: 'FORBIDDEN',
      message: '지어낸-말',
      fields: {},
    });
    expect(failure).not.toHaveProperty('legacyCode');
  });

  it('422 VALIDATION_ERROR 의 fields 를 싣는다(칸 경로 → 문장 목록)', () => {
    expect(
      failureOf(422, {
        error: {
          code: 'VALIDATION_ERROR',
          message: '지어낸-말',
          fields: {
            'rows.0.factorYear': ['지어낸-문장-하나', '지어낸-문장-둘'],
            name: ['지어낸-문장'],
          },
          legacyCode: 'invalid_input',
        },
      }),
    ).toEqual({
      kind: 'api',
      status: 422,
      code: 'VALIDATION_ERROR',
      message: '지어낸-말',
      fields: {
        'rows.0.factorYear': ['지어낸-문장-하나', '지어낸-문장-둘'],
        name: ['지어낸-문장'],
      },
    });
  });

  it('fields 가 없거나 꼴이 다르면 빈 객체. 글자 목록이 아닌 칸은 버린다', () => {
    const fieldsOf = (fields: unknown) => {
      const failure = failureOf(422, {
        error: { code: 'VALIDATION_ERROR', message: 'm', fields },
      });
      return failure.kind === 'api' ? failure.fields : null;
    };
    expect(
      failureOf(400, { error: { code: 'BAD_REQUEST', message: 'm' } }),
    ).toMatchObject({ kind: 'api', fields: {} });
    expect(fieldsOf(['x'])).toEqual({});
    expect(fieldsOf('x')).toEqual({});
    expect(fieldsOf({ a: ['ok'], b: 'not-a-list', c: [1] })).toEqual({
      a: ['ok'],
    });
  });

  it('그 꼴이 아니면 unexpected. 본문이 있으면 싣고, 비었으면(undefined, 빈 글자) 싣지 않는다', () => {
    expect(failureOf(500, 'Internal Server Error')).toEqual({
      kind: 'unexpected',
      status: 500,
      body: 'Internal Server Error',
    });
    expect(failureOf(502, undefined)).toEqual({
      kind: 'unexpected',
      status: 502,
    });
    expect(failureOf(502, '')).toEqual({ kind: 'unexpected', status: 502 });
    // 비슷하지만 칸이 모자란 것은 api 가 아니다.
    expect(failureOf(400, { error: { code: 'x' } }).kind).toBe('unexpected');
    expect(failureOf(400, { error: 'x' }).kind).toBe('unexpected');
    expect(failureOf(400, null).kind).toBe('unexpected');
  });

  it('던져진 것을 갈래로 읽는다. 갈래가 아닌 것은 network 로 본다', () => {
    const failure = failureOf(401, {
      error: { code: 'NO_SESSION', message: '지어낸-말', fields: null },
    });
    expect(asFailure(failure)).toBe(failure);
    expect(asFailure(new TypeError('x'))).toEqual({ kind: 'network' });
    expect(asFailure(undefined)).toEqual({ kind: 'network' });
    expect(isApiFailure({ kind: '다른 것' })).toBe(false);
  });
});

describe('세션을 다시 받아야 하는 실패', () => {
  const api = (status: number, code: string): ApiFailure => ({
    kind: 'api',
    status,
    code,
    message: 'm',
    fields: {},
  });

  it('444 TOKEN_NOT_VALID 와 401 NO_SESSION 이면 참', () => {
    expect(needsReauth(api(444, 'TOKEN_NOT_VALID'))).toBe(true);
    expect(needsReauth(api(401, 'NO_SESSION'))).toBe(true);
    // 상태 코드나 code 하나만 맞아도 참이다.
    expect(needsReauth(api(444, 'HTTP_444'))).toBe(true);
    expect(needsReauth(api(401, 'TOKEN_NOT_VALID'))).toBe(true);
  });

  it('그 밖의 거절, 옛 소문자, 서버에 닿지 못함은 거짓', () => {
    expect(needsReauth(api(401, 'UNAUTHORIZED'))).toBe(false);
    expect(needsReauth(api(403, 'FORBIDDEN'))).toBe(false);
    expect(needsReauth(api(401, 'no_session'))).toBe(false);
    expect(needsReauth({ kind: 'unexpected', status: 444 })).toBe(false);
    expect(needsReauth({ kind: 'network' })).toBe(false);
  });
});

describe('회사 거절의 갈래(sid:MARC-ENT-374)', () => {
  const api = (status: number, code: string): ApiFailure => ({
    kind: 'api',
    status,
    code,
    message: 'm',
    fields: {},
  });

  it('셋의 code 를 갈래로 읽는다. COMPANY_NOT_FOUND 는 400 도 404 도 not_found', () => {
    expect(companyRefusalOf(api(400, 'COMPANY_AMBIGUOUS'))).toBe('ambiguous');
    expect(companyRefusalOf(api(403, 'COMPANY_INACTIVE'))).toBe('inactive');
    expect(companyRefusalOf(api(400, 'COMPANY_NOT_FOUND'))).toBe('not_found');
    expect(companyRefusalOf(api(404, 'COMPANY_NOT_FOUND'))).toBe('not_found');
  });

  it('상태 코드로 가르지 않는다: 다른 code·옛 소문자·unexpected·network 는 null', () => {
    expect(companyRefusalOf(api(403, 'FORBIDDEN'))).toBeNull();
    expect(companyRefusalOf(api(403, 'PASSWORD_CHANGE_REQUIRED'))).toBeNull();
    expect(companyRefusalOf(api(400, 'company_ambiguous'))).toBeNull();
    expect(companyRefusalOf({ kind: 'unexpected', status: 403 })).toBeNull();
    expect(companyRefusalOf({ kind: 'network' })).toBeNull();
  });

  it('회사 거절은 세션을 다시 받아야 하는 실패가 아니다', () => {
    for (const [status, code] of [
      [400, 'COMPANY_AMBIGUOUS'],
      [403, 'COMPANY_INACTIVE'],
      [400, 'COMPANY_NOT_FOUND'],
    ] as const)
      expect(needsReauth(api(status, code)), code).toBe(false);
  });
});
