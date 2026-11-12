// 시험용 가짜 계정 서버(밴드 AD1 ②). 시험만 쓴다(공개 표면이 아니다).
// 답의 꼴은 api-py 의 /users 경로 셋(발주서 §1)을 따른다. 값은 전부 지어낸 것이다. Bearer 는 보지 않는다(세션 가짜 서버의 몫).
//   - GET /users?limit&offset → UserPageOut(id 오름). POST /users → 201(아이디가 있으면 409 USERNAME_TAKEN).
//   - POST /users/{id}/password-reset → 200(없는 id 면 404 USER_NOT_FOUND). isInitial 참·잠금 풀림.
//   - PATCH /users/{id} → 200(본문의 name·isActive 만 바꿈. 없는 id 면 404 USER_NOT_FOUND, 둘 다 없거나 null 이면 422 VALIDATION_ERROR).
//   - GET /users 는 q·status 로 거르지 않는다(쿼리는 calls 에만 적힌다) — 화면이 웹에서 다시 거르는 우회를 시험이 잡게(UA1W 발주서 §3).
//     count 는 기본이 전부의 수이고, setCount 로 따로 줄 수 있다(설명 줄의 개수 시험 — total ≠ 거른 count ≠ 실린 줄 수).
//   - 받은 요청을 calls 에 적는다(본문 글자 그대로 — 시험이 password 를 견준다).
// override 에 「메서드 경로」(PATCH 는 `PATCH /users/2` 처럼 id 별) → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다. 연결 끊김은 던지는 함수로).
//   답 함수는 요청 주소(URL)를 받고, undefined 를 내면 기본 답으로 간다(UA1W — 쿼리로 가르는 시험).
import type { Account } from '../model/index.ts';

export interface FakeAccountsCall {
  method: string;
  path: string;
  query: string;
  body: string;
}

/** 바꾼 답. 요청 주소를 받는다(쿼리로 가르는 시험 — 서버 거르기 흉내). undefined 를 내면 기본 답. */
type Answer = (
  url: URL,
) => Response | Promise<Response> | undefined | Promise<Response | undefined>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  });

/** 지어낸 계정 하나. */
export function fakeAccount(
  id: number,
  overrides: Partial<Account> = {},
): Account {
  return {
    id,
    companyId: 1,
    username: `user${String(id).padStart(2, '0')}`,
    name: `담당자 ${id}`,
    isActive: true,
    isInitial: false,
    isLocked: false,
    branchId: null,
    lastLoginAt: '2026-10-15T14:20:00+09:00',
    createdAt: '2026-10-01T09:00:00+09:00',
    companyName: '고객사 A',
    ...overrides,
  };
}

export function fakeAccountsServer(
  initial: Account[] = [],
  { baseUrl = 'http://test.local/api' } = {},
) {
  const accounts = initial.map((account) => ({ ...account }));
  const calls: FakeAccountsCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  let serial = Math.max(0, ...accounts.map((account) => account.id));
  /** GET /users 가 낼 count(없으면 전부의 수). limit=1 이면 total, 그 밖은 list 로 따로 줄 수 있다. */
  const counts: { total: number | null; list: number | null } = {
    total: null,
    list: null,
  };

  const answer = (
    key: string,
    url: URL,
    body: string,
  ): Response | Promise<Response> => {
    const input = (body ? JSON.parse(body) : {}) as Record<string, unknown>;
    if (key === 'GET /users') {
      const limit = Number(url.searchParams.get('limit') ?? 20);
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const rows = accounts.slice(offset, offset + limit);
      return json(200, {
        count: (limit === 1 ? counts.total : counts.list) ?? accounts.length,
        isNext: offset + rows.length < accounts.length,
        results: rows,
      });
    }
    if (key === 'POST /users') {
      if (accounts.some((account) => account.username === input.username))
        return refusal(409, 'USERNAME_TAKEN');
      const account = fakeAccount(++serial, {
        username: input.username as string,
        name: input.name as string,
        isInitial: true,
        lastLoginAt: null,
        createdAt: '2026-10-01T09:00:00+09:00',
        companyName: '고객사 A',
      });
      accounts.push(account);
      return json(201, account);
    }
    const reset = /^POST \/users\/(\d+)\/password-reset$/.exec(key);
    if (reset) {
      const account = accounts.find((row) => row.id === Number(reset[1]));
      if (!account) return refusal(404, 'USER_NOT_FOUND');
      account.isInitial = true;
      account.isLocked = false;
      return json(200, account);
    }
    const edit = /^PATCH \/users\/(\d+)$/.exec(key);
    if (edit) {
      const account = accounts.find((row) => row.id === Number(edit[1]));
      if (!account) return refusal(404, 'USER_NOT_FOUND');
      const { name, isActive } = input;
      if ((name ?? null) === null && (isActive ?? null) === null)
        return refusal(422, 'VALIDATION_ERROR', { body: ['둘 중 하나'] });
      if (typeof name === 'string') account.name = name;
      if (typeof isActive === 'boolean') account.isActive = isActive;
      return json(200, account);
    }
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) => {
    const path = new URL(request.url).pathname.slice(
      new URL(baseUrl).pathname.length,
    );
    return path === '/users' || /^\/users\/\d+(\/password-reset)?$/.test(path);
  };

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = url.pathname.slice(new URL(baseUrl).pathname.length);
    const body = await request.clone().text();
    const key = `${request.method} ${path}`;
    calls.push({ method: request.method, path, query: url.search, body });
    const replaced = override[key];
    const next = Array.isArray(replaced) ? replaced.shift() : replaced;
    const given = next ? await next(url) : undefined;
    return given ?? answer(key, url, body);
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  /** 쓰기 요청(POST·PATCH) 본문들. */
  const writes = () =>
    calls
      .filter((call) => call.method !== 'GET')
      .map((call) => JSON.parse(call.body) as Record<string, unknown>);

  /** PATCH 요청들(차례 그대로 — 경로의 id 와 본문 글자). */
  const patches = () =>
    calls
      .filter((call) => call.method === 'PATCH')
      .map((call) => ({
        id: Number(call.path.split('/')[2]),
        body: call.body,
      }));
  /** GET /users 의 쿼리들(쪽마다 — URLSearchParams 로). */
  const listQueries = () =>
    calls
      .filter((call) => call.method === 'GET' && call.path === '/users')
      .map((call) => new URLSearchParams(call.query));
  /** 목록 호출(GET /users 중 limit=100 — 전체 수 limit=1 은 뺀다)의 셈(critic 반영 2). */
  const listCount = () =>
    listQueries().filter((query) => query.get('limit') === '100').length;
  /** 전체 수 호출(GET /users?limit=1)의 셈. */
  const totalCount = () =>
    listQueries().filter((query) => query.get('limit') === '1').length;
  /** 마지막 쓰기 요청(GET 이 아닌 것). */
  const lastWrite = () => calls.filter((call) => call.method !== 'GET').at(-1);
  /** count 를 따로 준다(total = limit=1 의 답, list = 그 밖). */
  const setCount = (next: Partial<typeof counts>) =>
    Object.assign(counts, next);

  return {
    send,
    handles,
    calls,
    count,
    writes,
    patches,
    listQueries,
    listCount,
    totalCount,
    lastWrite,
    setCount,
    override,
    accounts,
  };
}
