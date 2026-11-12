// 클라이언트: 키의 꼴, 요청의 꼴, 그리고 「2xx 가 아니면 성공이 아니다」(조회 쪽. 변경 쪽은 hooks/ 의 테스트).
// 가짜 통신 함수를 createApi 에 준다. 서버도 브라우저도 없다.
import { QueryClient } from '@tanstack/react-query';

import { describe, expect, it } from 'vitest';

import { createApi } from './client.ts';
import { INVALIDATE_AFTER_MUTATION } from './model/index.ts';
import {
  emptyChunked,
  emptyWithLength,
  fakeFetch,
  json,
  refusal,
  textFailure,
  unreachable,
} from './testing.ts';

const BASE = 'http://web.test/app/api';
// 다시 시도는 화면이 정한다. 테스트는 한 번만 묻게 한다.
const queries = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe('키의 꼴 (openapi-react-query 의 판이 오르면 여기가 먼저 빨개진다)', () => {
  const { $api } = createApi({ baseUrl: BASE, fetch: unreachable });

  it('init 이 없으면 두 칸이다(셋째 칸에 undefined 가 없다)', () => {
    expect($api.queryOptions('get', '/sites').queryKey).toEqual([
      'get',
      '/sites',
    ]);
    expect($api.queryOptions('get', '/sites').queryKey).toHaveLength(2);
  });

  it('init 이 있으면 세 칸이다', () => {
    const init = { params: { query: { limit: 5 } } };
    expect(
      $api.queryOptions('get', '/reference/factors', init).queryKey,
    ).toEqual(['get', '/reference/factors', init]);
  });

  it('둘 다 ["get"] 으로 시작한다. 변경 뒤에 무효로 표시하는 키가 그것이다', () => {
    expect(INVALIDATE_AFTER_MUTATION).toEqual(['get']);
    for (const key of [
      $api.queryOptions('get', '/sites').queryKey,
      $api.queryOptions('get', '/reference/factors', {
        params: { query: { limit: 5 } },
      }).queryKey,
    ]) {
      expect(key.slice(0, INVALIDATE_AFTER_MUTATION.length)).toEqual([
        ...INVALIDATE_AFTER_MUTATION,
      ]);
    }
  });
});

describe('요청의 꼴', () => {
  it('주소는 바탕 주소 아래이고, 쿠키는 같은 출처에만 싣는다', async () => {
    const fake = fakeFetch(BASE, {
      'GET /reference/factors': json(200, {
        results: [],
        count: 0,
        isNext: false,
        licenses: [],
      }),
    });
    const { client } = createApi({ baseUrl: BASE, fetch: fake.fetch });
    await client.GET('/reference/factors', { params: { query: { limit: 5 } } });
    expect(fake.calls).toHaveLength(1);
    expect(fake.calls[0]!.url).toBe(`${BASE}/reference/factors?limit=5`);
    expect(fake.calls[0]!.credentials).toBe('same-origin');
  });

  it('POST 의 본문은 JSON 이다', async () => {
    const fake = fakeFetch(BASE, {
      'POST /sites': json(201, {
        site: { id: '지어낸-id', name: '지어낸-사업장', externalId: null },
      }),
    });
    const { client } = createApi({ baseUrl: BASE, fetch: fake.fetch });
    const { data } = await client.POST('/sites', {
      body: { name: '지어낸-사업장' },
    });
    expect(data?.site.name).toBe('지어낸-사업장');
    expect(fake.calls[0]!.method).toBe('POST');
    expect(fake.calls[0]!.contentType).toBe('application/json');
    expect(JSON.parse(fake.calls[0]!.body)).toEqual({ name: '지어낸-사업장' });
  });

  it('통신 함수는 만들 때 준 것을 쓴다(전역을 보지 않는다)', async () => {
    const fake = fakeFetch(BASE, {
      'GET /me': json(200, { tenantId: '지어낸-테넌트' }),
    });
    const { client } = createApi({ baseUrl: BASE, fetch: fake.fetch });
    const kept = globalThis.fetch;
    globalThis.fetch = unreachable;
    try {
      expect((await client.GET('/me')).response.status).toBe(200);
    } finally {
      globalThis.fetch = kept;
    }
  });
});

describe('2xx 가 아니면 성공이 아니다: 조회', () => {
  const ask = (answer: Parameters<typeof fakeFetch>[1][string]) => {
    const fake = fakeFetch(BASE, { 'GET /me': answer });
    const { $api } = createApi({ baseUrl: BASE, fetch: fake.fetch });
    return queries().fetchQuery($api.queryOptions('get', '/me'));
  };

  it('401 + 서버가 정한 오류 본문 → api, 상태 코드와 code 가 같이 온다', async () => {
    await expect(ask(refusal(401, 'NO_SESSION'))).rejects.toEqual({
      kind: 'api',
      status: 401,
      code: 'NO_SESSION',
      message: '지어낸-NO_SESSION',
      fields: {},
    });
  });

  it('500 + 글자 본문 → unexpected', async () => {
    await expect(ask(textFailure)).rejects.toEqual({
      kind: 'unexpected',
      status: 500,
      body: 'Internal Server Error',
    });
  });

  it('502 빈 본문(Content-Length: 0) → unexpected. null 로 성공하지 않는다', async () => {
    await expect(ask(emptyWithLength)).rejects.toEqual({
      kind: 'unexpected',
      status: 502,
    });
  });

  it('502 빈 본문(chunked) → unexpected. TanStack 의 「data cannot be undefined」로 우연히 거절되는 것이 아니다', async () => {
    await expect(ask(emptyChunked)).rejects.toEqual({
      kind: 'unexpected',
      status: 502,
    });
  });

  it('통신 함수가 던짐 → network', async () => {
    await expect(ask(unreachable)).rejects.toEqual({ kind: 'network' });
  });

  it('client.GET 을 직접 불러도 같다(조회 훅을 거치지 않는 길)', async () => {
    const fake = fakeFetch(BASE, { 'GET /me': emptyWithLength });
    const { client } = createApi({ baseUrl: BASE, fetch: fake.fetch });
    await expect(client.GET('/me')).rejects.toEqual({
      kind: 'unexpected',
      status: 502,
    });
  });

  it('2xx 는 그대로 지난다', async () => {
    await expect(
      ask(json(200, { tenantId: '지어낸-테넌트' })),
    ).resolves.toEqual({ tenantId: '지어낸-테넌트' });
  });
});
