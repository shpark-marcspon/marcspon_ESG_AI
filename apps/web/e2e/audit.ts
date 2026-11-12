// e2e 의 감사 기록 흉내 서버(밴드 AD5R). /api/audit-logs·/api/audit-logs/actors 를 page.route 로 채운다. 답의 값은 전부 지어낸 것이다.
//   - GET /audit-logs → AuditPageOut. 받은 쿼리의 action 이 있으면 그 행동의 줄만(서버 거르기 흉내 — 화면이 쿼리를 보냈는지 줄 수로도 보인다),
//     limit·offset 으로 자른다. 그 밖의 거르기(q·날짜·사람)는 하지 않는다 — 시험은 요청 URL 로 단언한다.
//   - GET /audit-logs/actors → AuditActorListOut.
//   - 받은 요청의 URL 을 모은다(urls).
// 로그인은 e2e/session.ts 의 signIn({ kind: 'admin' }) 을 먼저 부른다.
import type { Page, Route } from '@playwright/test';

export interface FakeAuditRow {
  id: number;
  at: string;
  companyId: number | null;
  actorKind: 'admin' | 'service' | 'command' | 'anonymous';
  actorUserId: number | null;
  actorName: string | null;
  actorUsername: string | null;
  action: string;
  event: string;
  result: 'success' | 'failure';
  reason: string | null;
  targetKind: string | null;
  targetId: number | null;
  targetLabel: string | null;
  changedFields: string[] | null;
  /** 그 줄의 모듈 id(밴드 AD4X ③ — 모듈과 무관하거나 옛 줄이면 null). */
  module: string | null;
  requestId: string | null;
}

export interface FakeAuditActor {
  actorKind: 'admin' | 'service';
  actorUserId: number;
  actorName: string | null;
  actorUsername: string | null;
}

const answer = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

export const auditRow = (
  id: number,
  overrides: Partial<FakeAuditRow> = {},
): FakeAuditRow => ({
  id,
  at: '2026-10-15T14:20:00+09:00',
  companyId: 1,
  actorKind: 'service',
  actorUserId: 11,
  actorName: '지어낸 담당자',
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
});

export async function fakeAuditApi(
  page: Page,
  rows: FakeAuditRow[],
  actors: FakeAuditActor[],
) {
  const urls: URL[] = [];
  await page.route(/\/api\/audit-logs\/actors(\?.*)?$/, async (route) => {
    urls.push(new URL(route.request().url()));
    return answer(route, 200, { results: actors });
  });
  await page.route(/\/api\/audit-logs(\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    urls.push(url);
    const action = url.searchParams.get('action');
    const matched = rows.filter((row) => !action || row.action === action);
    const limit = Number(url.searchParams.get('limit') ?? 20);
    const offset = Number(url.searchParams.get('offset') ?? 0);
    const results = matched.slice(offset, offset + limit);
    return answer(route, 200, {
      count: matched.length,
      isNext: offset + results.length < matched.length,
      results,
    });
  });
  /** GET /audit-logs 요청들(줄 경로만). */
  const listUrls = () =>
    urls.filter((url) => url.pathname === '/api/audit-logs');
  return { urls, listUrls };
}
