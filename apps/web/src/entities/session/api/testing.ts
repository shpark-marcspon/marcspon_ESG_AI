// 시험용 가짜 로그인 서버와 메모리 보관소(밴드 LG1). 시험만 쓴다(공개 표면이 아니다).
// 답의 꼴은 api-py 의 로그인 경로(발주서 §1)를 따른다. 값은 전부 지어낸 것이다.
//   - access 가 틀리거나 만료면 444 TOKEN_NOT_VALID, 머리 없음은 401.
//   - refresh 는 rotate: 옛 것을 다시 내면 그 계보 전부를 끊는다(444).
//   - isInitial 이면 /users/me·/users/me/password 만 열리고 그 밖(GET /users)은 403 PASSWORD_CHANGE_REQUIRED.
import type { SessionStorageLike } from './store.ts';

export interface FakeUser {
  password: string;
  kind: 'admin' | 'service';
  isInitial?: boolean;
  /** 참이면 로그인은 401 ACCOUNT_LOCKED(5번 틀려 10분). */
  locked?: boolean;
  /** 참이면 /users/me 가 401 USER_UNAVAILABLE. */
  unavailable?: boolean;
}

export interface FakeAuthCall {
  method: string;
  path: string;
  authorization: string | null;
  body: string;
}

type Override = () => Response | Promise<Response>;

const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
const refusal = (status: number, code: string) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

/** 메모리 보관소(sessionStorage 의 꼴 셋). */
export function memoryStorage(initial: Record<string, string> = {}) {
  const items = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
    removeItem: (key: string) => void items.delete(key),
    items,
  } satisfies SessionStorageLike & { items: Map<string, string> };
}

/**
 * 가짜 서버. users = 아이디 → 계정. 경로는 바탕 주소(/api) 뒤의 것.
 * override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(연결 끊김은 던지는 함수로).
 */
export function fakeAuthServer(
  users: Record<string, FakeUser>,
  { baseUrl = 'http://test.local/api' } = {},
) {
  const calls: FakeAuthCall[] = [];
  const override: Record<string, Override> = {};
  let serial = 0;
  /** 살아 있는 access → 아이디. */
  const accesses = new Map<string, string>();
  /** refresh → { 아이디, 계보, 살아 있음 }. */
  const refreshes = new Map<
    string,
    { username: string; family: number; alive: boolean }
  >();
  const deadFamilies = new Set<number>();
  let holds: Promise<void> | null = null;
  let last: { access: string; refresh: string } | null = null;

  const issue = (username: string, family = ++serial) => {
    const n = ++serial;
    const access = `access-${n}`;
    const refresh = `refresh-${n}`;
    accesses.set(access, username);
    refreshes.set(refresh, { username, family, alive: true });
    const user = users[username]!;
    last = { access, refresh };
    return {
      access,
      refresh,
      accessExpiresAt: '2099-01-01T00:30:00Z',
      refreshExpiresAt: '2099-01-08T00:00:00Z',
      isInitial: Boolean(user.isInitial),
      kind: user.kind,
    };
  };
  const killFamily = (family: number) => {
    deadFamilies.add(family);
    for (const row of refreshes.values())
      if (row.family === family) row.alive = false;
  };
  const bearerUser = (request: Request) => {
    const header = request.headers.get('Authorization');
    if (!header?.startsWith('Bearer ')) return { status: 401 as const };
    const username = accesses.get(header.slice('Bearer '.length));
    return username === undefined ?
        { status: 444 as const }
      : { status: 200 as const, username };
  };

  const answer = async (
    key: string,
    request: Request,
    body: string,
  ): Promise<Response> => {
    const input = (body ? JSON.parse(body) : {}) as Record<string, string>;
    switch (key) {
      case 'POST /auth/login': {
        if (!/^[\w.@+-]+$/.test(input.username ?? ''))
          return refusal(422, 'VALIDATION_ERROR');
        const user = users[input.username!];
        if (user?.locked) return refusal(401, 'ACCOUNT_LOCKED');
        if (!user || user.password !== input.password)
          return refusal(401, 'INVALID_CREDENTIALS');
        return json(200, issue(input.username!));
      }
      case 'POST /auth/refresh': {
        if (holds) await holds;
        const row = refreshes.get(input.refresh ?? '');
        if (!row || deadFamilies.has(row.family))
          return refusal(444, 'TOKEN_NOT_VALID');
        if (!row.alive) {
          // 죽은 refresh 를 다시 냈다: 그 계보 전부를 끊는다.
          killFamily(row.family);
          return refusal(444, 'TOKEN_NOT_VALID');
        }
        row.alive = false;
        return json(200, issue(row.username, row.family));
      }
      case 'POST /auth/revoke': {
        const row = refreshes.get(input.refresh ?? '');
        if (!row) return refusal(444, 'TOKEN_NOT_VALID');
        killFamily(row.family);
        return json(204, undefined);
      }
      case 'GET /users/me': {
        const who = bearerUser(request);
        if (who.status === 401) return refusal(401, 'NO_TOKEN');
        if (who.status === 444) return refusal(444, 'TOKEN_NOT_VALID');
        const user = users[who.username]!;
        if (user.unavailable) return refusal(401, 'USER_UNAVAILABLE');
        return json(200, {
          id: Object.keys(users).indexOf(who.username) + 1,
          username: who.username,
          name: `지어낸-${who.username}`,
          kind: user.kind,
          companyId: user.kind === 'admin' ? null : 1,
          isInitial: Boolean(user.isInitial),
        });
      }
      case 'GET /users': {
        const who = bearerUser(request);
        if (who.status === 401) return refusal(401, 'NO_TOKEN');
        if (who.status === 444) return refusal(444, 'TOKEN_NOT_VALID');
        if (users[who.username]!.isInitial)
          return refusal(403, 'PASSWORD_CHANGE_REQUIRED');
        return json(200, { count: 0, isNext: false, results: [] });
      }
      case 'POST /users/me/password': {
        const who = bearerUser(request);
        if (who.status === 401) return refusal(401, 'NO_TOKEN');
        if (who.status === 444) return refusal(444, 'TOKEN_NOT_VALID');
        const user = users[who.username]!;
        if (user.locked) return refusal(401, 'ACCOUNT_LOCKED');
        if (input.currentPassword !== user.password)
          return refusal(400, 'CURRENT_PASSWORD_MISMATCH');
        if ((input.newPassword ?? '').length < 8)
          return refusal(400, 'PASSWORD_REJECTED');
        user.password = input.newPassword!;
        user.isInitial = false;
        // 다른 기기의 refresh 를 모두 끊고 새 계보를 낸다.
        for (const row of refreshes.values())
          if (row.username === who.username) killFamily(row.family);
        return json(200, issue(who.username));
      }
    }
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  const send = async (request: Request): Promise<Response> => {
    const path = new URL(request.url).pathname.slice(
      new URL(baseUrl).pathname.length,
    );
    const body = await request.clone().text();
    const key = `${request.method} ${path}`;
    calls.push({
      method: request.method,
      path,
      authorization: request.headers.get('Authorization'),
      body,
    });
    const replaced = override[key];
    if (replaced) return replaced();
    return answer(key, request, body);
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;

  return {
    send,
    calls,
    count,
    override,
    users,
    /** 이미 낸 access 를 모두 죽인다(30분이 지난 꼴). */
    expireAccess: () => accesses.clear(),
    /** 지금 살아 있는 refresh(계보마다 하나). 시험이 보관소에 심는다. */
    liveRefreshOf: (username: string) =>
      [...refreshes.entries()].find(
        ([, row]) =>
          row.username === username &&
          row.alive &&
          !deadFamilies.has(row.family),
      )?.[0] ?? null,
    /** 마지막으로 낸 짝(로그인·refresh·바꾸기). */
    lastIssued: () => last,
    /** 로그인 없이 계정 하나의 짝을 낸다(복원 시험의 바탕). */
    issue,
    /** refresh 답을 풀어 줄 때까지 붙든다. 푸는 함수를 돌려준다. */
    holdRefresh: () => {
      let release!: () => void;
      holds = new Promise<void>((resolve) => {
        release = () => {
          holds = null;
          resolve();
        };
      });
      return release;
    },
  };
}
