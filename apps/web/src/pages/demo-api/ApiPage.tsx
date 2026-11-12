// 서버(apps/api-py)를 부르는 화면 하나. 부품이 아니라 「쓰는 쪽의 예」다: 교환 → 내 세션 → 사업장 → 계산 → 기준정보 → Scope 3 후보 추리기.
// 메뉴도 디자인도 없다. 구획마다 단추 하나와 답의 요약뿐이다.
//
// ★ 연습용 선택이고 패칭 컨벤션이 아니다. QueryClient 와 그 기본값은 이 화면이 만든다(src/api 는 품지 않는다).
//
// 서버에 닿는 길: 쪽과 같은 출처의 `api/…` 로 부르고, Vite 의 프록시가 api-py 로 넘긴다(vite.config.ts). 그래서 세션 쿠키가 실린다.
// 세션 쿠키는 HttpOnly 라 이 화면이 읽지 못한다. 「세션이 있는가」는 GET /me 의 답으로만 안다.
import { useState } from 'react';
import type { FormEvent } from 'react';

import {
  QueryClient,
  QueryClientProvider,
  useQueryClient,
} from '@tanstack/react-query';

import {
  asFailure,
  createApi,
  createInvalidatingMutation,
} from '../../shared/api/index.ts';
import type {
  Api,
  ApiFailure,
  CreateApiOptions,
  Schemas,
} from '../../shared/api/index.ts';
import { appHref } from '../../shared/lib/address.ts';
import './api-demo.css';
import { CALC_EXAMPLE, SHORTLIST_EXAMPLE } from './examples.ts';

export interface ApiPageProps {
  /** 통신 함수. 테스트가 가짜를 준다. */
  fetch?: CreateApiOptions['fetch'];
  /** 테스트가 캐시를 들여다보려고 준다. 안 주면 여기서 만든다. */
  queryClient?: QueryClient;
}

/** 이 화면의 패칭 기본값. 라이브러리의 것 그대로 두되 다시 시도만 끈다: 401(세션 없음)을 세 번 되묻지 않게. */
export const createDemoQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false } } });

export function ApiPage({ fetch, queryClient }: ApiPageProps) {
  const [client] = useState(() => queryClient ?? createDemoQueryClient());
  // 바탕 주소는 앱 뿌리(appHref) 기준으로 만든다(쪽 주소 /dev/api 기준이면 바탕이 쪽 주소 /dev/api 와 겹친다 — 밴드 RT1).
  const [api] = useState(() =>
    createApi({
      baseUrl: appHref('api'),
      fetch,
    }),
  );
  const [useChange] = useState(() => createInvalidatingMutation(api));
  return (
    <QueryClientProvider client={client}>
      <Flow api={api} useChange={useChange} />
    </QueryClientProvider>
  );
}

function Failure({ failure }: { failure: ApiFailure }) {
  if (failure.kind === 'api') {
    return (
      <p role="alert" data-failure="api">
        <code>{failure.code}</code> {failure.message} ({failure.status})
      </p>
    );
  }
  return (
    <p role="alert" data-failure={failure.kind}>
      서버에 닿지 못했다(api-py 가 떠 있는가)
      {failure.kind === 'unexpected' ? `. 상태 코드 ${failure.status}` : ''}
    </p>
  );
}

type ExchangeNote =
  { ok: Schemas['ExchangeOut'] } | { failure: ApiFailure } | null;

function Flow({
  api,
  useChange,
}: {
  api: Api;
  useChange: Api['$api']['useMutation'];
}) {
  const { $api } = api;
  const queryClient = useQueryClient();

  // ── 내 세션. 세션이 있는가는 이 답으로만 안다.
  const me = $api.useQuery('get', '/me');
  const hasSession = me.isSuccess;
  const meFailure = me.isError ? asFailure(me.error) : null;
  const noSession =
    meFailure?.kind === 'api' && meFailure.code === 'NO_SESSION';

  // ── 교환. 토큰은 요청의 본문에만 싣는다. 주소·저장소·캐시에 남기지 않는다.
  const [token, setToken] = useState('');
  const [exchangeNote, setExchangeNote] = useState<ExchangeNote>(null);
  const exchange = useChange('post', '/auth/exchange');
  /** 변경의 기록에는 변수(= 토큰이 든 본문)가 남는다. 훅에서 떼고(reset) 캐시에서도 뺀다(떼기만 하면 5분 더 남는다). */
  function forgetExchange() {
    exchange.reset();
    const cache = queryClient.getMutationCache();
    for (const mutation of cache.findAll({
      mutationKey: ['post', '/auth/exchange'],
    }))
      cache.remove(mutation);
  }
  async function onExchange(event: FormEvent) {
    event.preventDefault();
    try {
      // 성공하면 useChange 가 조회 전부를 무효로 표시한다(세션이 바뀌었다).
      const out = await exchange.mutateAsync({ body: { token } });
      setExchangeNote(out ? { ok: out } : null);
    } catch (error) {
      // 거절의 code 와 message 는 기록을 지우기 전에 화면의 상태로 옮긴다.
      setExchangeNote({ failure: asFailure(error) });
    } finally {
      setToken('');
      forgetExchange();
    }
  }

  // ── 사업장. 목록은 응답으로 덧붙이지 않는다. 무효화로 다시 받은 것만 그린다.
  const sites = $api.useQuery('get', '/sites', undefined, {
    enabled: hasSession,
  });
  const [siteName, setSiteName] = useState('');
  const createSite = useChange('post', '/sites', {
    onSuccess: () => setSiteName(''),
  });
  function onCreateSite(event: FormEvent) {
    event.preventDefault();
    createSite.mutate({ body: { name: siteName } });
  }

  // ── 계산, 후보 추리기. POST 이지만 서버의 상태를 바꾸지 않는다(저장하지 않는다). 그래서 무효화하지 않는 변경으로 부른다.
  const calc = $api.useMutation('post', '/inventory/calc');
  const shortlist = $api.useMutation('post', '/inventory/scope3/shortlist');

  // ── 기준정보.
  const factors = $api.useQuery(
    'get',
    '/reference/factors',
    { params: { query: { limit: 5 } } },
    { enabled: hasSession },
  );

  return (
    <main className="ad">
      <h1>서버 호출 (api-py)</h1>

      <section aria-label="교환">
        <h2>POST /auth/exchange</h2>
        <form onSubmit={onExchange}>
          <label>
            토큰{' '}
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </label>
          <button type="submit" disabled={token === '' || exchange.isPending}>
            교환
          </button>
        </form>
        {exchangeNote && 'ok' in exchangeNote && (
          <p data-testid="exchanged">
            교환됨: {exchangeNote.ok.tenant.name} · {exchangeNote.ok.user.name}{' '}
            · {exchangeNote.ok.role}
          </p>
        )}
        {exchangeNote && 'failure' in exchangeNote && (
          <Failure failure={exchangeNote.failure} />
        )}
      </section>

      <section aria-label="내 세션">
        <h2>GET /me</h2>
        {me.isPending && <p className="ad-note">묻는 중</p>}
        {noSession && (
          <p data-testid="no-session">
            먼저 교환한다. 세션이 없다: <code>{meFailure.code}</code> (
            {meFailure.status})
          </p>
        )}
        {meFailure && !noSession && <Failure failure={meFailure} />}
        {me.data && (
          <p data-testid="me">
            테넌트 <code data-testid="me-tenant">{me.data.tenantId}</code> ·
            사용자 <code>{me.data.userId}</code> · {me.data.role}
          </p>
        )}
      </section>

      <section aria-label="사업장">
        <h2>GET /sites · POST /sites</h2>
        {!hasSession && <p className="ad-note">먼저 교환</p>}
        {hasSession && sites.isError && (
          <Failure failure={asFailure(sites.error)} />
        )}
        {hasSession && sites.data && (
          <ul data-testid="sites">
            {sites.data.sites.map((site) => (
              <li key={site.id}>{site.name}</li>
            ))}
            {sites.data.sites.length === 0 && (
              <li className="ad-note">사업장 없음</li>
            )}
          </ul>
        )}
        {hasSession && (
          <form onSubmit={onCreateSite}>
            <label>
              사업장 이름{' '}
              <input
                value={siteName}
                onChange={(event) => setSiteName(event.target.value)}
              />
            </label>
            <button
              type="submit"
              disabled={siteName === '' || createSite.isPending}
            >
              만들기
            </button>
          </form>
        )}
        {createSite.isError && (
          <Failure failure={asFailure(createSite.error)} />
        )}
      </section>

      <section aria-label="계산">
        <h2>POST /inventory/calc</h2>
        <button
          type="button"
          disabled={!hasSession || calc.isPending}
          onClick={() => calc.mutate({ body: CALC_EXAMPLE })}
        >
          예시 한 행 계산
        </button>
        {calc.isError && <Failure failure={asFailure(calc.error)} />}
        {calc.data && (
          <ul data-testid="calc-rows">
            {calc.data.rows.map((row) =>
              // failed 는 오류가 아니라 답이다(200 안의 갈래). 값은 서버가 준 글자 그대로 그린다.
              row.status === 'ok' ?
                <li key={row.rowId} data-row-status="ok">
                  {row.rowId}: <span data-testid="co2e">{row.co2e}</span>{' '}
                  {row.unit}
                </li>
              : <li key={row.rowId} data-row-status="failed">
                  {row.rowId}: 계산하지 못한 행 (<code>{row.failure.kind}</code>
                  )
                </li>,
            )}
          </ul>
        )}
      </section>

      <section aria-label="기준정보">
        <h2>GET /reference/factors?limit=5</h2>
        {!hasSession && <p className="ad-note">먼저 교환</p>}
        {hasSession && factors.isError && (
          <Failure failure={asFailure(factors.error)} />
        )}
        {hasSession && factors.data && (
          <>
            <p>
              조건에 맞는 낱줄{' '}
              <span data-testid="factors-count">{factors.data.count}</span>건
              {factors.data.isNext ? ' (다음 페이지 있음)' : ''}
            </p>
            <ul>
              {factors.data.results.map((item) => (
                <li key={item.id}>{item.nameOriginal}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section aria-label="Scope 3 후보 추리기">
        <h2>POST /inventory/scope3/shortlist</h2>
        <button
          type="button"
          disabled={!hasSession || shortlist.isPending}
          onClick={() => shortlist.mutate({ body: SHORTLIST_EXAMPLE })}
        >
          예시 품목의 후보 추리기
        </button>
        {shortlist.isError && <Failure failure={asFailure(shortlist.error)} />}
        {shortlist.data &&
          // no_candidates 는 오류가 아니라 답이다.
          (shortlist.data.status === 'no_candidates' ?
            <p data-testid="shortlist" data-status="no_candidates">
              후보 없음 (<code>no_candidates</code>)
            </p>
          : <p data-testid="shortlist" data-status={shortlist.data.status}>
              후보 {shortlist.data.shown}건 (추리기 전 {shortlist.data.total}건)
            </p>)}
      </section>
    </main>
  );
}
