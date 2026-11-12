import { afterEach, describe, expect, it, vi } from 'vitest';

import { appHref, appPath, withParams } from './address.ts';

describe('withParams', () => {
  it('적힌 인자만 바꾸고 나머지는 순서까지 그대로 둔다', () => {
    expect(
      withParams('?data=sample/compare.json&screen=compact', {
        data: 'sample/sentences.json',
      }),
    ).toBe('?data=sample%2Fsentences.json&screen=compact');
    expect(
      withParams('?view=table&data=sample&screen=cards&calcFail=1', {
        data: 'fake',
        rows: '5000',
      }),
    ).toBe('?view=table&data=fake&screen=cards&calcFail=1&rows=5000');
  });

  it('null 이면 그 인자를 뺀다. 없는 인자를 빼도 그대로다', () => {
    expect(withParams('?data=a&mode=fill&screen=compact', { mode: null })).toBe(
      '?data=a&screen=compact',
    );
    expect(withParams('?data=a', { mode: null, rows: null })).toBe('?data=a');
  });

  it('인자가 하나도 없던 주소에도 붙는다', () => {
    expect(withParams('', { data: 'sample/compare.json', mode: null })).toBe(
      '?data=sample%2Fcompare.json',
    );
  });
});

// base 가 '/' 라 그냥은 BASE_URL 을 빼먹어도 같은 글자다 — 하위 경로(/sub/)로 바꿔 본다.
describe('appPath·appHref (앱 뿌리 주소)', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('appPath 는 BASE_URL 을 붙인 경로 글자다(앞의 / 는 하나로)', () => {
    vi.stubEnv('BASE_URL', '/sub/');
    expect(appPath('dev/table')).toBe('/sub/dev/table');
    expect(appPath('/local/index.json')).toBe('/sub/local/index.json');
    expect(appPath('sample/compare.json')).toBe('/sub/sample/compare.json');
    vi.stubEnv('BASE_URL', '/');
    expect(appPath('dev/viewer')).toBe('/dev/viewer');
  });

  it('appHref 는 쪽 주소가 아니라 앱 뿌리 기준 절대 URL 이다. 이미 절대 URL 이면 그대로', () => {
    vi.stubEnv('BASE_URL', '/sub/');
    vi.stubGlobal('document', { baseURI: 'http://host.test/sub/dev/viewer' });
    expect(appHref('api-py')).toBe('http://host.test/sub/api-py');
    expect(appHref('sample/sample-a.pdf')).toBe(
      'http://host.test/sub/sample/sample-a.pdf',
    );
    // 앞 / 가 붙으면 origin 기준(appPath 와 달리 앱 뿌리를 붙이지 않는다)
    expect(appHref('/api-py')).toBe('http://host.test/api-py');
    expect(appHref('https://other.test/a.pdf')).toBe(
      'https://other.test/a.pdf',
    );
    vi.stubEnv('BASE_URL', '/');
    expect(appHref('api-py')).toBe('http://host.test/api-py');
  });
});
