// 출처 링크 판별(http(s) 만 — 밴드 DV9 §3). utm 꼬리 떼기는 공통 칩으로 옮겨 갔다(밴드 DV12).
import { describe, expect, it } from 'vitest';

import { isWebLink } from './webUrl.ts';

const NOT_WEB = [
  'javascript:alert(1)',
  'data:text/html,x',
  'mailto:a@example.com',
  '/relative',
  'ftp://x',
  '',
  'example.com/a',
  'https://',
  'http:example.com',
  'http:/example.com',
];

describe('isWebLink', () => {
  it('http·https(대소문자 섞임 포함)는 링크', () => {
    for (const url of [
      'https://example.com/a',
      'http://example.com/a',
      'HTTPS://Example.com/a',
    ])
      expect(isWebLink(url), url).toBe(true);
  });

  it('앞뒤 공백은 떼고 판별한다(칩의 isSafeLinkUrl 과 같음 — 밴드 DV11)', () => {
    for (const url of [
      '  https://example.com/a',
      '\u00a0https://example.com/a',
      'https://example.com/a  ',
    ])
      expect(isWebLink(url), url).toBe(true);
  });

  it('javascript:·data:·mailto:·상대 주소·ftp·빈 글자·파싱 실패는 링크가 아니다', () => {
    for (const url of NOT_WEB) expect(isWebLink(url), url).toBe(false);
  });

  it('쿼리 꼬리는 판별을 바꾸지 않는다', () => {
    for (const url of [
      'https://example.com/a?utm_source=openai',
      'https://example.com/a?utm_source=news',
      'https://example.com/a?b=1',
    ])
      expect(isWebLink(url), url).toBe(true);
  });
});
