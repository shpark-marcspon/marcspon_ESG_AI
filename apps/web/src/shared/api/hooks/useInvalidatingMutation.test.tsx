// @vitest-environment jsdom
// 변경 뒤의 무효화, 그리고 「2xx 가 아니면 성공이 아니다」의 변경 쪽.
// 조회 둘(GET /sites, GET /reference/factors?limit=5)을 보는 관찰자를 세워 두고 POST /sites 를 부른다. 가짜 통신 함수가 호출 수를 센다.
import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { createApi } from '../client.ts';
import {
  emptyChunked,
  emptyWithLength,
  fakeFetch,
  json,
  refusal,
  textFailure,
  unreachable,
} from '../testing.ts';
import { createInvalidatingMutation } from './useInvalidatingMutation.ts';

afterEach(cleanup);

const BASE = 'http://web.test/api';
const SITES = 'GET /sites';
const FACTORS = 'GET /reference/factors';

function setup(create: Parameters<typeof fakeFetch>[1][string]) {
  const fake = fakeFetch(BASE, {
    [SITES]: json(200, { sites: [] }),
    [FACTORS]: json(200, {
      results: [],
      count: 0,
      isNext: false,
      licenses: [],
    }),
    'POST /sites': create,
  });
  const api = createApi({ baseUrl: BASE, fetch: fake.fetch });
  const useChange = createInvalidatingMutation(api);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const hook = renderHook(
    () => ({
      sites: api.$api.useQuery('get', '/sites'),
      factors: api.$api.useQuery('get', '/reference/factors', {
        params: { query: { limit: 5 } },
      }),
      create: useChange('post', '/sites'),
    }),
    { wrapper },
  );
  return { fake, hook, queryClient };
}

async function loaded(context: ReturnType<typeof setup>) {
  await waitFor(() => {
    expect(context.hook.result.current.sites.isSuccess).toBe(true);
    expect(context.hook.result.current.factors.isSuccess).toBe(true);
  });
  expect(context.fake.count(SITES)).toBe(1);
  expect(context.fake.count(FACTORS)).toBe(1);
}

/** POST /sites 를 부르고 끝날 때까지 기다린다. 성공이면 "success", 실패면 던져진 것을 돌려준다. */
async function change(context: ReturnType<typeof setup>): Promise<unknown> {
  let outcome: unknown;
  await act(async () => {
    outcome = await context.hook.result.current.create
      .mutateAsync({ body: { name: '지어낸-사업장' } })
      .then(
        () => 'success',
        (error: unknown) => error,
      );
  });
  // 혹시 늦게 도는 다시 받기가 있으면 세어지도록 한 박자 둔다.
  await act(
    async () => void (await new Promise((resolve) => setTimeout(resolve, 20))),
  );
  return outcome;
}

describe('변경 뒤의 무효화', () => {
  it('성공하면 ["get"] 으로 시작하는 조회가 전부 다시 불린다: 두 조회가 각각 1번씩 는다', async () => {
    const context = setup(
      json(201, {
        site: { id: '지어낸-id', name: '지어낸-사업장', externalId: null },
      }),
    );
    await loaded(context);
    expect(await change(context)).toBe('success');
    expect(context.fake.count('POST /sites')).toBe(1);
    expect(context.fake.count(SITES)).toBe(2);
    expect(context.fake.count(FACTORS)).toBe(2);
    expect(context.hook.result.current.create.isSuccess).toBe(true);
  });

  it('변경의 키는 ["post", 경로] 라 ["get"] 에 걸리지 않는다', async () => {
    const context = setup(
      json(201, {
        site: { id: '지어낸-id', name: '지어낸-사업장', externalId: null },
      }),
    );
    await loaded(context);
    await change(context);
    expect(
      context.queryClient
        .getMutationCache()
        .getAll()
        .map((mutation) => mutation.options.mutationKey),
    ).toEqual([['post', '/sites']]);
  });

  it('쓰는 쪽의 onSuccess 도 불린다(무효화 뒤에)', async () => {
    const fake = fakeFetch(BASE, {
      [SITES]: json(200, { sites: [] }),
      'POST /sites': json(201, {
        site: { id: '지어낸-id', name: '지어낸-사업장', externalId: null },
      }),
    });
    const api = createApi({ baseUrl: BASE, fetch: fake.fetch });
    const useChange = createInvalidatingMutation(api);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const seen: number[] = [];
    const hook = renderHook(
      () => ({
        sites: api.$api.useQuery('get', '/sites'),
        create: useChange('post', '/sites', {
          onSuccess: () => void seen.push(fake.count(SITES)),
        }),
      }),
      {
        wrapper: ({ children }: { children: ReactNode }) => (
          <QueryClientProvider client={queryClient}>
            {children}
          </QueryClientProvider>
        ),
      },
    );
    await waitFor(() => expect(hook.result.current.sites.isSuccess).toBe(true));
    await act(
      async () =>
        void (await hook.result.current.create.mutateAsync({
          body: { name: '지어낸-사업장' },
        })),
    );
    expect(seen).toEqual([2]);
  });
});

describe('2xx 가 아니면 성공이 아니다: 변경. 실패한 변경 뒤에는 조회가 다시 불리지 않는다', () => {
  const cases: [string, Parameters<typeof fakeFetch>[1][string], unknown][] = [
    [
      '403 + 서버가 정한 오류 본문 → api',
      refusal(403, 'FORBIDDEN'),
      {
        kind: 'api',
        status: 403,
        code: 'FORBIDDEN',
        message: '지어낸-FORBIDDEN',
        fields: {},
      },
    ],
    [
      '401 + 서버가 정한 오류 본문 → api',
      refusal(401, 'NO_SESSION'),
      {
        kind: 'api',
        status: 401,
        code: 'NO_SESSION',
        message: '지어낸-NO_SESSION',
        fields: {},
      },
    ],
    [
      '500 + 글자 본문 → unexpected',
      textFailure,
      { kind: 'unexpected', status: 500, body: 'Internal Server Error' },
    ],
    [
      '502 빈 본문(Content-Length: 0) → unexpected',
      emptyWithLength,
      { kind: 'unexpected', status: 502 },
    ],
    [
      '502 빈 본문(chunked) → unexpected',
      emptyChunked,
      { kind: 'unexpected', status: 502 },
    ],
    ['통신 함수가 던짐 → network', unreachable, { kind: 'network' }],
  ];
  for (const [name, answer, failure] of cases) {
    it(`${name}, 무효화 0`, async () => {
      const context = setup(answer);
      await loaded(context);
      expect(await change(context)).toEqual(failure);
      expect(context.hook.result.current.create.isError).toBe(true);
      expect(context.hook.result.current.create.error).toEqual(failure);
      expect(context.fake.count(SITES)).toBe(1);
      expect(context.fake.count(FACTORS)).toBe(1);
    });
  }
});
