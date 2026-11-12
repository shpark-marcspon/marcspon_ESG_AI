// 실행 만들기 열쇠(밴드 GR2): 소문자 UUID(서버 KEY_PATTERN), 부를 때마다 다르다. randomUUID 가 없는 출처(http)에서도 같은 꼴.
import { afterEach, describe, expect, it, vi } from 'vitest';

import { IDEMPOTENCY_KEY_PATTERN, newIdempotencyKey } from './idempotency.ts';

const V4 =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('newIdempotencyKey', () => {
  it('소문자 UUID v4, 서버 무늬에 맞고 부를 때마다 다르다', () => {
    const made = Array.from({ length: 50 }, () => newIdempotencyKey());
    for (const key of made) {
      expect(key).toMatch(V4);
      expect(IDEMPOTENCY_KEY_PATTERN.test(key)).toBe(true);
    }
    expect(new Set(made).size).toBe(made.length);
  });

  it('randomUUID 가 없으면(보안 출처 밖) getRandomValues 로 같은 꼴을 짓는다', () => {
    const real = crypto;
    vi.stubGlobal('crypto', {
      getRandomValues: <T extends ArrayBufferView>(array: T) =>
        real.getRandomValues(array),
    });
    const made = Array.from({ length: 50 }, () => newIdempotencyKey());
    for (const key of made) expect(key).toMatch(V4);
    expect(new Set(made).size).toBe(made.length);
  });

  it('무늬는 서버 KEY_PATTERN 과 같다: 대문자·중괄호·짧은 글은 받지 않는다', () => {
    for (const bad of [
      '0F8A3C2E-5B1D-4E7A-9C6F-2D4B8E1A7C3F',
      '{0f8a3c2e-5b1d-4e7a-9c6f-2d4b8e1a7c3f}',
      '0f8a3c2e5b1d4e7a9c6f2d4b8e1a7c3f',
      '',
    ])
      expect(IDEMPOTENCY_KEY_PATTERN.test(bad)).toBe(false);
  });
});
