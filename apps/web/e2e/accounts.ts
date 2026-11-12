// e2e 의 계정 관리 흉내 서버(밴드 AD1). /api/users 경로 셋을 page.route 로 채운다. 답의 값은 전부 지어낸 것이다.
//   - GET /users → UserPageOut(limit·offset), POST /users → 201(아이디가 있으면 409 USERNAME_TAKEN),
//     POST /users/{id}/password-reset → 200. 받은 쓰기 본문과 「메서드 경로」를 모은다(시험이 임시 비밀번호를 견준다).
//   - PATCH /users/{id} → 200(본문의 name·isActive 를 입힌다 — UA1W). GET /users 의 쿼리는 queries 에 모은다(q·status 는 거르지 않는다).
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다(이 도우미는 /users/me 를 건드리지 않는다).
import type { Page, Route } from '@playwright/test';

export interface FakeAccountRow {
  id: number;
  companyId: number;
  username: string;
  name: string;
  isActive: boolean;
  isInitial: boolean;
  isLocked: boolean;
  branchId: null;
  lastLoginAt: string | null;
  createdAt: string;
  companyName: string;
}

const answer = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

export const accountRow = (
  id: number,
  overrides: Partial<FakeAccountRow> = {},
): FakeAccountRow => ({
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
});

export async function fakeAccountsApi(page: Page, rows: FakeAccountRow[]) {
  const accounts = rows.map((row) => ({ ...row }));
  const calls: string[] = [];
  const writes: Record<string, unknown>[] = [];
  /** GET /users 의 쿼리들(차례 그대로). */
  const queries: URLSearchParams[] = [];
  /** PATCH /users/{id} 의 주소 id 와 본문 글자(차례 그대로). */
  const patches: { id: number; body: string }[] = [];
  await page.route(/\/api\/users(\?.*)?$/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push(`${request.method()} /users`);
    if (request.method() === 'GET') {
      queries.push(url.searchParams);
      const limit = Number(url.searchParams.get('limit') ?? 20);
      const offset = Number(url.searchParams.get('offset') ?? 0);
      const results = accounts.slice(offset, offset + limit);
      return answer(route, 200, {
        count: accounts.length,
        isNext: offset + results.length < accounts.length,
        results,
      });
    }
    const body = request.postDataJSON() as Record<string, string>;
    writes.push(body);
    if (accounts.some((row) => row.username === body.username))
      return answer(route, 409, {
        error: {
          code: 'USERNAME_TAKEN',
          message: '지어낸-USERNAME_TAKEN',
          fields: null,
          legacyCode: 'username_taken',
        },
      });
    const row = accountRow(accounts.length + 1, {
      username: body.username,
      name: body.name,
      isInitial: true,
      lastLoginAt: null,
    });
    accounts.push(row);
    return answer(route, 201, row);
  });
  await page.route(/\/api\/users\/\d+\/password-reset$/, async (route) => {
    const request = route.request();
    const id = Number(/users\/(\d+)\//.exec(request.url())![1]);
    calls.push(`POST /users/${id}/password-reset`);
    writes.push(request.postDataJSON() as Record<string, unknown>);
    const row = accounts.find((account) => account.id === id)!;
    row.isInitial = true;
    row.isLocked = false;
    return answer(route, 200, row);
  });
  await page.route(/\/api\/users\/\d+$/, async (route) => {
    const request = route.request();
    if (request.method() !== 'PATCH') return route.fallback();
    const id = Number(/users\/(\d+)$/.exec(request.url())![1]);
    const body = request.postData() ?? '';
    calls.push(`PATCH /users/${id}`);
    patches.push({ id, body });
    const row = accounts.find((account) => account.id === id)!;
    Object.assign(row, JSON.parse(body) as Partial<FakeAccountRow>);
    return answer(route, 200, row);
  });
  return { calls, writes, queries, patches, accounts };
}
