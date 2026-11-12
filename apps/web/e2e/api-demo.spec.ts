// 서버를 부르는 화면(/dev/api)을 빌드 결과에서 연다. 서버도 컨테이너도 없다: /api/ 아래의 요청을 여기서 채운다.
// 답의 값은 전부 지어낸 것이다. 떠 있는 api-py 에 닿는 확인은 e2e/live/ 에 따로 있다(평소에는 돌지 않는다).
import { expect, test } from '@playwright/test';
import type { Page, Route } from '@playwright/test';

import { useMockStore } from './greenwash-server.ts';
import { signIn } from './session.ts';

// 그린워싱 화면을 목 저장소로 연다(밴드 GW1R Q1 — 기본은 실어댑터, 목은 데모 빌드의 탭 표지 뒤로만). 단언은 그대로다.
test.beforeEach(({ page }) => useMockStore(page));

/** 서버의 흉내. 부른 것을 「메서드 주소」로 적는다. */
async function fakeApi(page: Page) {
  const calls: string[] = [];
  const state = {
    session: false,
    sites: [] as { id: string; name: string; externalId: null }[],
  };
  const answer = (route: Route, status: number, body: unknown) =>
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^.*?\/api(?=\/)/, '');
    calls.push(`${request.method()} ${request.url()}`);
    const key = `${request.method()} ${path}`;
    if (key === 'POST /auth/exchange') {
      state.session = true;
      return answer(route, 200, {
        tenant: { id: '지어낸-테넌트', name: '지어낸-회사' },
        user: { id: 'u', externalId: 'x', issuer: 'i', name: '지어낸-사람' },
        role: 'editor',
        expiresAt: '2099-01-01T00:00:00Z',
      });
    }
    if (!state.session)
      return answer(route, 401, {
        error: {
          code: 'NO_SESSION',
          message: '지어낸-세션 없음',
          fields: null,
          legacyCode: 'no_session',
        },
      });
    if (key === 'GET /me')
      return answer(route, 200, {
        tenantId: '지어낸-테넌트',
        userId: 'u',
        role: 'editor',
        expiresAt: '2099-01-01T00:00:00Z',
      });
    if (key === 'GET /sites') return answer(route, 200, { sites: state.sites });
    if (key === 'POST /sites') {
      const { name } = request.postDataJSON() as { name: string };
      state.sites = [
        ...state.sites,
        { id: `s${state.sites.length + 1}`, name, externalId: null },
      ];
      return answer(route, 201, { site: state.sites.at(-1) });
    }
    if (key === 'GET /reference/factors')
      return answer(route, 200, {
        results: [],
        count: 0,
        isNext: false,
        licenses: [],
      });
    return answer(route, 404, {
      error: {
        code: 'NOT_FOUND',
        message: '지어낸-없는 경로',
        fields: null,
        legacyCode: 'not_found',
      },
    });
  });
  return { calls, state };
}

test('/dev/api 가 빌드에서 뜨고, 교환 → 사업장 만들기 → 다시 받은 목록', async ({
  page,
}) => {
  const api = await fakeApi(page);
  await page.goto('/dev/api');
  await expect(page.getByTestId('no-session')).toContainText('NO_SESSION');

  await page.getByLabel('토큰').fill('지어낸-토큰');
  await page.getByRole('button', { name: '교환' }).click();
  await expect(page.getByTestId('me-tenant')).toHaveText('지어낸-테넌트');
  await expect(page.getByLabel('토큰')).toHaveValue('');
  await expect(page.getByTestId('sites')).toContainText('사업장 없음');

  await page.getByLabel('사업장 이름').fill('지어낸-사업장');
  await page.getByRole('button', { name: '만들기' }).click();
  await expect(page.getByTestId('sites')).toContainText('지어낸-사업장');
  expect(
    api.calls.filter(
      (call) => call.startsWith('GET ') && call.endsWith('/sites'),
    ),
  ).toHaveLength(2);
});

test('요청의 주소는 앱 뿌리(BASE_URL) 아래의 api/… 다(쪽 주소 /dev/api 아래가 아니다)', async ({
  page,
  baseURL,
}) => {
  const api = await fakeApi(page);
  await page.goto('/dev/api');
  await expect(page.getByTestId('no-session')).toBeVisible();
  expect(api.calls).toEqual([`GET ${baseURL}api/me`]);

  await page.getByLabel('토큰').fill('지어낸-토큰');
  await page.getByRole('button', { name: '교환' }).click();
  await expect(page.getByTestId('me-tenant')).toBeVisible();
  await expect(page.getByTestId('sites')).toBeVisible();
  expect(api.calls).toContain(`POST ${baseURL}api/auth/exchange`);
  expect(api.calls).toContain(`GET ${baseURL}api/sites`);
  expect(api.calls).toContain(`GET ${baseURL}api/reference/factors?limit=5`);
  // 주소에는 아무 인자도 없다(토큰이 실리지 않는다).
  expect(new URL(page.url()).search).toBe('');
});

test('다른 화면은 서버를 부르지 않는다: 루트(/)는 그린워싱, 모르는 주소·옛 view 도 그린워싱, /dev/viewer 는 문서 뷰어, /dev/table 은 검토 표', async ({
  page,
}) => {
  const api = await fakeApi(page);
  // 로그인 준비(밴드 LG1): 로그인 경로만 signIn 이 답한다(나중에 단 route 가 이긴다) — api.calls 에는 들지 않는다.
  await signIn(page);
  // 루트는 그린워싱 목록(/greenwash). 모르는 주소도 목록으로 떨어진다(밴드 RT1 — 경로 표의 splat).
  await page.goto('/');
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  await page.goto('/dev/nope');
  await expect(page.locator('[data-screen="list"]')).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/greenwash');
  // 옛 ?view= 는 그린워싱만 넘긴다. 데모 이름·Object.prototype 의 이름은 목록으로 떨어진다
  for (const name of ['api', 'constructor', '__proto__', 'hasOwnProperty']) {
    await page.goto(`/?view=${name}`);
    await expect(page.locator('[data-screen="list"]')).toBeVisible();
  }
  await page.goto('/dev/viewer');
  await expect(page.locator('[data-document-id]').first()).toBeVisible();
  await expect(page.getByRole('region', { name: '교환' })).toHaveCount(0);

  await page.goto('/dev/table?data=sample');
  await expect(page.locator('[data-row-id]').first()).toBeVisible();
  await expect(page.getByRole('region', { name: '교환' })).toHaveCount(0);
  expect(api.calls).toEqual([]);
});
