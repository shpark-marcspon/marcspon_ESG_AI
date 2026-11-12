// e2e 의 로그인 도우미(밴드 LG1). 서버도 컨테이너도 없다: /api/ 아래의 로그인 경로를 여기서 채운다. 답의 값은 전부 지어낸 것이다.
//   - signIn: 로그인한 채로 시작한다 — 쪽을 열 때마다 sessionStorage 에 refresh 를 심고(addInitScript), refresh·/users/me 를 route 로 답한다.
//     그린워싱 경로는 가드 뒤에 있어 기존 그린워싱 e2e 는 이것을 먼저 부른다(단언은 바꾸지 않는다).
//     route 는 나중에 단 것이 이긴다: 다른 흉내(/api/** 전부)를 먼저 달고 이것을 뒤에 부르면 로그인 경로만 여기서 답한다.
//   - fakeAuthApi: 로그인 화면 e2e 의 흉내 서버(login·refresh·revoke·/users/me·/users/me/password). 부른 것을 「메서드 경로」로 적는다.
// 보관소 키는 세션 model 의 것을 쓴다(e2e → entities/session/model·config 는 층 시험이 허락한 문 — N10).
import type { Page, Route } from '@playwright/test';

import { REFRESH_STORAGE_KEY } from '../src/entities/session/model/index.ts';

type Kind = 'admin' | 'service';

const answer = (route: Route, status: number, body?: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: body === undefined ? '' : JSON.stringify(body),
  });
const refusal = (route: Route, status: number, code: string) =>
  answer(route, status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

const pairOf = (n: number, kind: Kind, isInitial: boolean) => ({
  access: `access-e2e-${n}`,
  refresh: `refresh-e2e-${n}`,
  accessExpiresAt: '2099-01-01T00:30:00Z',
  refreshExpiresAt: '2099-01-08T00:00:00Z',
  isInitial,
  kind,
});
const meOf = (username: string, kind: Kind, isInitial: boolean) => ({
  id: 1,
  username,
  name: `지어낸-${username}`,
  kind,
  companyId: kind === 'admin' ? null : 1,
  isInitial,
});

/** 로그인한 채로 시작한다(새로고침 뒤의 꼴: 보관소의 refresh 로 복원). */
export async function signIn(
  page: Page,
  {
    kind = 'service',
    username = 'user01',
  }: { kind?: Kind; username?: string } = {},
) {
  await page.addInitScript(
    ([key, value]) => sessionStorage.setItem(key!, value!),
    [REFRESH_STORAGE_KEY, 'refresh-e2e-0'],
  );
  await page.route('**/api/auth/refresh', (route) =>
    answer(route, 200, pairOf(0, kind, false)),
  );
  await page.route('**/api/users/me', (route) =>
    answer(route, 200, meOf(username, kind, false)),
  );
}

export interface FakeAccount {
  password: string;
  kind: Kind;
  isInitial?: boolean;
  locked?: boolean;
}

/** 로그인 화면 e2e 의 흉내 서버. accounts = 아이디 → 계정(바뀌면 그대로 고쳐 쓴다). */
export async function fakeAuthApi(
  page: Page,
  accounts: Record<string, FakeAccount>,
) {
  const calls: string[] = [];
  const bodies: Record<string, unknown>[] = [];
  let serial = 0;
  /** access → 아이디. */
  const accesses = new Map<string, string>();
  const refreshes = new Map<string, string>();
  /** 남은 refresh 503 횟수(failRefresh — 서버에 닿지 못하는 꼴, refresh 는 쓰지 않은 채 남는다). */
  let refreshFailures = 0;
  const issue = (username: string) => {
    const account = accounts[username]!;
    const pair = pairOf(++serial, account.kind, Boolean(account.isInitial));
    accesses.set(pair.access, username);
    refreshes.set(pair.refresh, username);
    return pair;
  };
  const who = (route: Route) =>
    accesses.get(
      (route.request().headers()['authorization'] ?? '').replace(
        /^Bearer /,
        '',
      ),
    );
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^.*?\/api(?=\/)/, '');
    const key = `${request.method()} ${path}`;
    calls.push(key);
    const body = (request.postDataJSON() ?? {}) as Record<string, string>;
    bodies.push(body);
    switch (key) {
      case 'POST /auth/login': {
        const account = accounts[body.username ?? ''];
        if (account?.locked) return refusal(route, 401, 'ACCOUNT_LOCKED');
        if (!account || account.password !== body.password)
          return refusal(route, 401, 'INVALID_CREDENTIALS');
        return answer(route, 200, issue(body.username!));
      }
      case 'POST /auth/refresh': {
        if (refreshFailures > 0) {
          refreshFailures--;
          return refusal(route, 503, 'SERVICE_UNAVAILABLE');
        }
        const username = refreshes.get(body.refresh ?? '');
        if (!username) return refusal(route, 444, 'TOKEN_NOT_VALID');
        refreshes.delete(body.refresh!);
        return answer(route, 200, issue(username));
      }
      case 'POST /auth/revoke':
        refreshes.delete(body.refresh ?? '');
        return answer(route, 204);
      case 'GET /users/me': {
        const username = who(route);
        if (!username) return refusal(route, 444, 'TOKEN_NOT_VALID');
        const account = accounts[username]!;
        return answer(
          route,
          200,
          meOf(username, account.kind, Boolean(account.isInitial)),
        );
      }
      case 'POST /users/me/password': {
        const username = who(route);
        if (!username) return refusal(route, 444, 'TOKEN_NOT_VALID');
        const account = accounts[username]!;
        if (body.currentPassword !== account.password)
          return refusal(route, 400, 'CURRENT_PASSWORD_MISMATCH');
        account.password = body.newPassword!;
        account.isInitial = false;
        return answer(route, 200, issue(username));
      }
    }
    return refusal(route, 404, 'NOT_FOUND');
  });
  return {
    calls,
    bodies,
    /** 다음 refresh n 번을 503 으로 답한다(Infinity = 켬, 0 = 끔). */
    failRefresh: (times: number) => {
      refreshFailures = times;
    },
  };
}
