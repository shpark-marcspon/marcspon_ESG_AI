// @vitest-environment jsdom
// 서버를 부르는 화면의 동작. 가짜 통신 함수를 화면에 준다(서버도 프록시도 없다). 답의 값은 전부 지어낸 것이다.
// 이 테스트가 화면에 요구하는 것은 이름표뿐이다: 구획 = role region 과 그 이름, 실패 = role alert,
// 그리고 data-testid(exchanged, no-session, me-tenant, sites, calc-rows, factors-count, shortlist).
import { QueryClient } from '@tanstack/react-query';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { ApiPage, createDemoQueryClient } from './ApiPage.tsx';
import { CALC_EXAMPLE, SHORTLIST_EXAMPLE } from './examples.ts';

afterEach(cleanup);

/** 지어낸 토큰. 서명된 토큰이 아니다(꼴도 다르다). 화면 어디에도 남으면 안 되는 글자다. */
const TOKEN = '지어낸-토큰-어디에도-남으면-안-된다';

type Answer = () => Response;
const json =
  (status: number, body: unknown): Answer =>
  () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
const refusal = (status: number, code: string) =>
  json(status, { error: { code, message: `지어낸-${code}` } });
/** Vite 의 프록시가 서버에 닿지 못했을 때의 답: 502, 빈 본문, 길이 없이 chunked. */
const proxyDown: Answer = () =>
  new Response('', {
    status: 502,
    headers: { 'Content-Type': 'text/plain', 'Transfer-Encoding': 'chunked' },
  });

interface Call {
  key: string;
  url: string;
  body: string;
}

/** 서버의 흉내. 세션이 없으면 401 을 낸다. routes 에 적은 것이 기본 답을 덮는다. */
function fakeServer(routes: Record<string, Answer> = {}) {
  const calls: Call[] = [];
  const state = {
    session: false,
    sites: [] as { id: string; name: string; externalId: null }[],
  };
  const defaults: Record<string, Answer> = {
    'POST /auth/exchange': () => {
      state.session = true;
      return json(200, {
        tenant: { id: '지어낸-테넌트', name: '지어낸-회사' },
        user: { id: 'u', externalId: 'x', issuer: 'i', name: '지어낸-사람' },
        role: 'editor',
        expiresAt: '2099-01-01T00:00:00Z',
      })();
    },
    'GET /me': () =>
      json(200, {
        tenantId: '지어낸-테넌트',
        userId: 'u',
        role: 'editor',
        expiresAt: '2099-01-01T00:00:00Z',
      })(),
    'GET /sites': () => json(200, { sites: state.sites })(),
    'GET /reference/factors': () =>
      json(200, {
        results: [{ id: '지어낸-낱줄', nameOriginal: '지어낸-이름' }],
        count: 7,
        isNext: true,
        licenses: ['ok'],
      })(),
  };
  const open = ['POST /auth/exchange'];
  const fetch = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const key = `${request.method} ${url.pathname.replace(/^.*?\/api(?=\/)/, '')}`;
    calls.push({ key, url: request.url, body: await request.clone().text() });
    if (routes[key]) return routes[key]();
    if (!state.session && !open.includes(key))
      return refusal(401, 'NO_SESSION')();
    const answer = defaults[key];
    if (!answer) throw new Error(`가짜에 없는 경로: ${key}`);
    return answer();
  };
  return {
    fetch,
    calls,
    state,
    count: (key: string) => calls.filter((call) => call.key === key).length,
  };
}

function show(server: ReturnType<typeof fakeServer>) {
  const queryClient = createDemoQueryClient();
  render(<ApiPage fetch={server.fetch} queryClient={queryClient} />);
  return queryClient;
}

const region = (name: string) => within(screen.getByRole('region', { name }));
const tokenInput = () =>
  region('교환').getByLabelText('토큰') as HTMLInputElement;

async function exchange() {
  fireEvent.change(tokenInput(), { target: { value: TOKEN } });
  await act(
    async () =>
      void fireEvent.click(
        region('교환').getByRole('button', { name: '교환' }),
      ),
  );
}

/** 토큰의 글자가 남을 수 있는 자리 전부. */
function placesTokenCouldStay(
  queryClient: QueryClient,
): Record<string, string> {
  return {
    address: location.href,
    localStorage: JSON.stringify({ ...localStorage }),
    sessionStorage: JSON.stringify({ ...sessionStorage }),
    text: document.body.textContent ?? '',
    markup: document.body.innerHTML,
    inputs: [...document.querySelectorAll('input')]
      .map((input) => input.value)
      .join('\n'),
    mutationCache: JSON.stringify(
      queryClient
        .getMutationCache()
        .getAll()
        .map((mutation) => mutation.state),
    ),
    queryCache: JSON.stringify(
      queryClient
        .getQueryCache()
        .getAll()
        .map((query) => [query.queryKey, query.state]),
    ),
  };
}
function expectTokenNowhere(queryClient: QueryClient) {
  for (const [place, content] of Object.entries(
    placesTokenCouldStay(queryClient),
  )) {
    expect(content.includes(TOKEN), `토큰이 남았다: ${place}`).toBe(false);
  }
}

describe('교환', () => {
  it('「세션 없음」은 code NO_SESSION 으로만 가른다. 옛 소문자 legacyCode 는 읽지 않는다', async () => {
    const server = fakeServer({
      'GET /me': json(401, {
        error: {
          code: 'UNAUTHORIZED',
          message: '지어낸-말',
          fields: null,
          legacyCode: 'no_session',
        },
      }),
    });
    show(server);
    expect((await region('내 세션').findByRole('alert')).textContent).toContain(
      'UNAUTHORIZED',
    );
    expect(screen.queryByTestId('no-session')).toBeNull();
  });

  it('세션이 없으면 「먼저 교환」이고, 사업장과 기준정보는 묻지 않는다', async () => {
    const server = fakeServer();
    show(server);
    expect(await screen.findByTestId('no-session')).toHaveProperty(
      'textContent',
      expect.stringContaining('NO_SESSION'),
    );
    expect(screen.getByTestId('no-session').textContent).toContain('401');
    expect(server.count('GET /sites')).toBe(0);
    expect(server.count('GET /reference/factors')).toBe(0);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('교환하면 본문은 {token} 뿐이고, 내 세션과 사업장이 그려지고, 입력칸이 비고, 토큰의 글자가 어디에도 없다', async () => {
    const server = fakeServer();
    const queryClient = show(server);
    await screen.findByTestId('no-session');
    await exchange();

    const sent = server.calls.filter(
      (call) => call.key === 'POST /auth/exchange',
    );
    expect(sent).toHaveLength(1);
    expect(JSON.parse(sent[0]!.body)).toEqual({ token: TOKEN });
    expect(sent[0]!.url.includes(TOKEN)).toBe(false);

    expect((await screen.findByTestId('me-tenant')).textContent).toBe(
      '지어낸-테넌트',
    );
    expect((await screen.findByTestId('sites')).textContent).toContain(
      '사업장 없음',
    );
    expect(screen.getByTestId('exchanged').textContent).toContain(
      '지어낸-회사',
    );
    expect(tokenInput().value).toBe('');
    // 교환 뒤 조회가 다시 불렸다: 세션 없음(1번) → 교환 → 다시(2번).
    expect(server.count('GET /me')).toBe(2);
    expectTokenNowhere(queryClient);
    // 빈 검사가 아니다: 같은 자리들에 지어낸 테넌트는 보인다.
    expect(placesTokenCouldStay(queryClient).queryCache).toContain(
      '지어낸-테넌트',
    );
  });

  it('거절되면 code 와 message 가 alert 로 보이고, 그때도 입력칸이 비고 토큰의 글자가 어디에도 없다', async () => {
    const server = fakeServer({
      'POST /auth/exchange': refusal(403, 'unknown_tenant'),
    });
    const queryClient = show(server);
    await screen.findByTestId('no-session');
    await exchange();

    const alert = await region('교환').findByRole('alert');
    expect(alert.textContent).toContain('unknown_tenant');
    expect(alert.textContent).toContain('지어낸-unknown_tenant');
    expect(tokenInput().value).toBe('');
    // 실패한 변경 뒤에는 조회를 다시 부르지 않는다.
    expect(server.count('GET /me')).toBe(1);
    expectTokenNowhere(queryClient);
  });
});

describe('사업장', () => {
  it('만들면 목록은 다시 받은 것만 그린다: 새 이름은 둘째 GET /sites 에만 있다', async () => {
    const server = fakeServer({
      // 만들기의 답에는 다른 이름을 싣는다. 화면이 이 답을 목록에 덧붙이면 그 이름이 보인다.
      'POST /sites': () => {
        server.state.sites = [
          { id: 's1', name: '지어낸-다시-받은-이름', externalId: null },
        ];
        return json(201, {
          site: { id: 's1', name: '지어낸-응답의-이름', externalId: null },
        })();
      },
    });
    show(server);
    await screen.findByTestId('no-session');
    await exchange();
    await screen.findByTestId('sites');
    expect(server.count('GET /sites')).toBe(1);

    fireEvent.change(region('사업장').getByLabelText('사업장 이름'), {
      target: { value: '지어낸-입력한-이름' },
    });
    await act(
      async () =>
        void fireEvent.click(
          region('사업장').getByRole('button', { name: '만들기' }),
        ),
    );

    await waitFor(() =>
      expect(screen.getByTestId('sites').textContent).toContain(
        '지어낸-다시-받은-이름',
      ),
    );
    expect(screen.getByTestId('sites').textContent).not.toContain(
      '지어낸-응답의-이름',
    );
    expect(
      JSON.parse(server.calls.find((call) => call.key === 'POST /sites')!.body),
    ).toEqual({ name: '지어낸-입력한-이름' });
    expect(server.count('GET /sites')).toBe(2);
    expect(
      (region('사업장').getByLabelText('사업장 이름') as HTMLInputElement)
        .value,
    ).toBe('');
  });

  it('거절되면(403 FORBIDDEN) alert 로 보이고 목록을 다시 받지 않는다', async () => {
    const server = fakeServer({ 'POST /sites': refusal(403, 'FORBIDDEN') });
    show(server);
    await screen.findByTestId('no-session');
    await exchange();
    await screen.findByTestId('sites');
    fireEvent.change(region('사업장').getByLabelText('사업장 이름'), {
      target: { value: '지어낸-이름' },
    });
    await act(
      async () =>
        void fireEvent.click(
          region('사업장').getByRole('button', { name: '만들기' }),
        ),
    );
    expect((await region('사업장').findByRole('alert')).textContent).toContain(
      'FORBIDDEN',
    );
    expect(server.count('GET /sites')).toBe(1);
  });
});

describe('계산과 후보 추리기: 200 안의 갈래는 오류가 아니라 답이다', () => {
  async function ready(routes: Record<string, Answer>) {
    const server = fakeServer(routes);
    show(server);
    await screen.findByTestId('no-session');
    await exchange();
    await screen.findByTestId('me-tenant');
    return server;
  }

  it('계산의 failed 행은 alert 가 아니라 행으로 그려진다. ok 행의 값은 서버가 준 글자 그대로다', async () => {
    const server = await ready({
      'POST /inventory/calc': json(200, {
        gwpSetId: '지어낸-세트',
        aggregation: {},
        rows: [
          { status: 'ok', rowId: 'r1', co2e: '0.100', unit: 'tCO2eq' },
          {
            status: 'failed',
            rowId: 'r2',
            failure: { kind: 'factor_not_found' },
          },
        ],
      }),
    });
    await act(
      async () => void fireEvent.click(region('계산').getByRole('button')),
    );
    const rows = await screen.findByTestId('calc-rows');
    expect(
      [...rows.querySelectorAll('[data-row-status]')].map((row) =>
        row.getAttribute('data-row-status'),
      ),
    ).toEqual(['ok', 'failed']);
    // 끝의 0 을 지우거나 반올림하지 않는다.
    expect(within(rows).getByTestId('co2e').textContent).toBe('0.100');
    expect(rows.textContent).toContain('factor_not_found');
    expect(region('계산').queryByRole('alert')).toBeNull();
    // 보낸 본문은 예시 요청 그대로다. 계산은 서버의 상태를 바꾸지 않으므로 조회를 다시 부르지 않는다.
    expect(
      JSON.parse(
        server.calls.find((call) => call.key === 'POST /inventory/calc')!.body,
      ),
    ).toEqual(CALC_EXAMPLE);
    expect(server.count('GET /me')).toBe(2);
  });

  it('no_candidates 는 alert 가 아니라 답으로 그려진다', async () => {
    const server = await ready({
      'POST /inventory/scope3/shortlist': json(200, {
        status: 'no_candidates',
        physical: null,
        catalog: {},
      }),
    });
    await act(
      async () =>
        void fireEvent.click(region('Scope 3 후보 추리기').getByRole('button')),
    );
    expect(
      (await screen.findByTestId('shortlist')).getAttribute('data-status'),
    ).toBe('no_candidates');
    expect(region('Scope 3 후보 추리기').queryByRole('alert')).toBeNull();
    expect(
      JSON.parse(
        server.calls.find(
          (call) => call.key === 'POST /inventory/scope3/shortlist',
        )!.body,
      ),
    ).toEqual(SHORTLIST_EXAMPLE);
  });

  it('shortlisted 면 건수를 그린다', async () => {
    await ready({
      'POST /inventory/scope3/shortlist': json(200, {
        status: 'shortlisted',
        shown: 3,
        total: 9,
      }),
    });
    await act(
      async () =>
        void fireEvent.click(region('Scope 3 후보 추리기').getByRole('button')),
    );
    const answer = await screen.findByTestId('shortlist');
    expect(answer.getAttribute('data-status')).toBe('shortlisted');
    expect(answer.textContent).toContain('3');
    expect(answer.textContent).toContain('9');
  });

  it('기준정보는 count 와 results 의 낱줄을 그린다(옛 칸 total·items 는 읽지 않는다)', async () => {
    const server = await ready({});
    expect((await screen.findByTestId('factors-count')).textContent).toBe('7');
    expect(region('기준정보').getByText(/다음 페이지 있음/)).toBeTruthy();
    expect(region('기준정보').getByText('지어낸-이름')).toBeTruthy();
    expect(
      server.calls.find((call) => call.key === 'GET /reference/factors')!.url,
    ).toMatch(/\/api\/reference\/factors\?limit=5$/);
  });
});

describe('서버에 닿지 못함', () => {
  it('502 빈 본문(Vite 의 프록시가 닿지 못했을 때의 꼴)이면 「닿지 못했다」와 상태 코드가 보인다', async () => {
    const server = fakeServer({ 'GET /me': proxyDown });
    show(server);
    const alert = await region('내 세션').findByRole('alert');
    expect(alert.textContent).toContain('닿지 못했다');
    expect(alert.textContent).toContain('502');
    expect(screen.queryByTestId('no-session')).toBeNull();
    expect(screen.queryByTestId('me')).toBeNull();
  });

  it('교환이 502 빈 본문이면 교환된 것으로 보이지 않고, 조회를 다시 부르지 않는다', async () => {
    const server = fakeServer({ 'POST /auth/exchange': proxyDown });
    const queryClient = show(server);
    await screen.findByTestId('no-session');
    await exchange();
    expect((await region('교환').findByRole('alert')).textContent).toContain(
      '502',
    );
    expect(screen.queryByTestId('exchanged')).toBeNull();
    expect(server.count('GET /me')).toBe(1);
    expectTokenNowhere(queryClient);
  });
});
