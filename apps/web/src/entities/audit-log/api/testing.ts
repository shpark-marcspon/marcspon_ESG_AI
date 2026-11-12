// 시험용 가짜 감사 기록 서버(밴드 AD5R ①). 시험만 쓴다(공개 표면이 아니다).
// 답의 꼴은 api-py 의 GET /audit-logs(AuditPageOut)·GET /audit-logs/actors(AuditActorListOut)를 따른다. 값은 전부 지어낸 것이다.
// Bearer 는 보지 않는다(세션 가짜 서버의 몫).
//   - GET /audit-logs 는 받은 limit·offset 으로 줄을 잘라 낼 뿐 거르지 않는다 — 시험은 거르기를 요청 URL 로 단언한다.
//   - 받은 요청을 calls 에 적는다(쿼리는 URLSearchParams 로).
// override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다. 연결 끊김은 던지는 함수로).
import type { AuditActorRow, AuditEventRow } from '../model/index.ts';

export interface FakeAuditCall {
  method: string;
  path: string;
  query: URLSearchParams;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (status: number, code: string) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

/** 지어낸 감사 줄 하나(기본: 고객사 사용자의 로그인 성공). */
export function fakeAuditRow(
  id: number,
  overrides: Partial<AuditEventRow> = {},
): AuditEventRow {
  return {
    id,
    at: '2026-10-15T14:20:00+09:00',
    companyId: 1,
    actorKind: 'service',
    actorUserId: 11,
    actorName: '담당자 가',
    actorUsername: 'user11',
    action: 'login',
    event: 'login_succeeded',
    result: 'success',
    reason: null,
    targetKind: null,
    targetId: null,
    targetLabel: null,
    changedFields: null,
    module: null,
    requestId: null,
    ...overrides,
  };
}

/** 지어낸 행위자 하나. */
export function fakeActor(
  actorUserId: number,
  overrides: Partial<AuditActorRow> = {},
): AuditActorRow {
  return {
    actorKind: 'service',
    actorUserId,
    actorName: `담당자 ${actorUserId}`,
    actorUsername: `user${actorUserId}`,
    ...overrides,
  };
}

export function fakeAuditServer(
  rows: AuditEventRow[] = [],
  actors: AuditActorRow[] = [],
  { baseUrl = 'http://test.local/api' } = {},
) {
  const calls: FakeAuditCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};

  const answer = (key: string, url: URL): Response => {
    if (key === 'GET /audit-logs') {
      const limit = Number(url.searchParams.get('limit') ?? 20);
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const page = rows.slice(offset, offset + limit);
      return json(200, {
        count: rows.length,
        isNext: offset + page.length < rows.length,
        results: page,
      });
    }
    if (key === 'GET /audit-logs/actors') return json(200, { results: actors });
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) =>
    /^\/audit-logs(\/actors)?$/.test(pathOf(request));

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(request);
    const key = `${request.method} ${path}`;
    calls.push({ method: request.method, path, query: url.searchParams });
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(key, url);
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  /** GET /audit-logs 요청들의 쿼리(글자 — 키 차례 그대로). */
  const listQueries = () =>
    calls
      .filter((call) => call.path === '/audit-logs')
      .map((call) => Object.fromEntries(call.query));

  return { send, handles, calls, count, listQueries, override, rows, actors };
}
