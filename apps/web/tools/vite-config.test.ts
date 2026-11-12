import { describe, expect, it } from 'vitest';

import config, { API_PROXY_KEY } from '../vite.config.ts';

// Vite 는 프록시 키가 ^ 로 시작하면 정규식으로, 아니면 앞부분 일치(startsWith)로 본다
// (vite 8.3.2 dist/node/chunks/node.js 의 createProxyContextMatcher). 여기서는 그 규칙대로 키를 대 본다.
const matches = (key: string, url: string) =>
  key.startsWith('^') ? new RegExp(key).test(url) : url.startsWith(key);

describe('api-py 로 넘기는 프록시 (밴드 SW1W)', () => {
  it('/api 와 그 아래만 넘기고, /apix·/api-py 는 넘기지 않는다', () => {
    expect(Object.keys(config.server?.proxy ?? {})).toEqual([API_PROXY_KEY]);
    for (const url of ['/api', '/api/me', '/api/reference/factors?limit=5'])
      expect(matches(API_PROXY_KEY, url), url).toBe(true);
    for (const url of ['/apix', '/api-py/me', '/dev/api', '/assets/api.js'])
      expect(matches(API_PROXY_KEY, url), url).toBe(false);
  });

  it('접두를 떼지 않는다(api-py 도 /api 아래에 있다)', () => {
    const entry = config.server?.proxy?.[API_PROXY_KEY];
    expect(typeof entry === 'object' && entry.rewrite).toBeFalsy();
  });
});
