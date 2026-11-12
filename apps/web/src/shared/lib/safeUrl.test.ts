// 안전 링크 판별(밴드 MD1). 줄마다 새 규칙과 옛 규칙의 값을 나란히 못 박는다.
import { describe, expect, it } from 'vitest';

import { isSafeLinkUrl } from './safeUrl.ts';

// materiality 고치기 검사(entities/materiality/model/edits.ts)의 SAFE_URL 사본 — 서버 _SAFE_URL 의 거울이라 남는다. 보이기(isSafeLinkUrl)와 어디서 갈리는지 이 표가 적는다(IRW12 뒤에도 지우지 않음).
const OLD_SAFE_URL = /^https?:\/\//;

const TABLE: [value: string, next: boolean, old: boolean][] = [
  ['http://example.com', true, true],
  ['https://example.com/a?b=1#c', true, true],
  ['  https://example.com  ', true, true],
  ['HTTPS://Example.com/a', true, false], // 다른 줄 ①
  ['javascript:alert(1)', false, false],
  ['JAVASCRIPT:alert(1)', false, false],
  ['  javascript:alert(1)', false, false],
  ['data:text/html,hi', false, false],
  ['vbscript:x', false, false],
  ['/rel', false, false],
  ['rel', false, false],
  ['//example.com', false, false],
  ['ftp://example.com/a', false, false],
  ['mailto:a@example.com', false, false],
  ['', false, false],
  ['   ', false, false],
  ['http:/example.com', false, false],
  ['https:example.com', false, false],
  ['https://', false, true], // 다른 줄 ②
  ['http://', false, true], // 다른 줄 ③
];

describe('isSafeLinkUrl', () => {
  it.each(TABLE)('%j → 새 %s · 옛 %s', (value, next, old) => {
    expect(isSafeLinkUrl(value)).toBe(next);
    expect(OLD_SAFE_URL.test(value.trim())).toBe(old);
  });

  it('옛 규칙과 다른 줄은 정확히 셋이다', () => {
    const differ = TABLE.filter(
      ([value]) => isSafeLinkUrl(value) !== OLD_SAFE_URL.test(value.trim()),
    ).map(([value]) => value);
    expect(differ).toEqual(['HTTPS://Example.com/a', 'https://', 'http://']);
    expect(differ.length === 3).toBe(true);
  });
});
