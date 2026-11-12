// @vitest-environment jsdom
// 온실가스 Scope 3 경로 시험(밴드 S3W1 ③ — 발주서 §3 8, app/ghg/router.test.tsx 꼴). createAppRouter 에 메모리 기록과 세션 send 뒤에
//   가짜 온실가스 서버 둘(entities/ghg — S2 자리, entities/ghg-scope3 — /documents·/runs·/inventory/scope3)을 둔다. 새 router context 칸은 없다.
//   ① /ghg/scope3?year=전년도 두 역할 머묾 · 모듈 탭 「온실가스 데이터」·Scope 탭 「Scope 3」 current · 메뉴 「온실가스」 · 실어댑터가 그 해 실행을 읽음
//   ② year 거름(없음·글자·소수·올해·범위 밖 → 전년도로 replace, 기록 하나) · 연도 바꿈 replace
//   ③ Scope 탭 이동은 연도를 실어 push — 받는 화면 범위 밖이면 그 화면 기본 해로 replace(둘 다 전년도 — W12-4 ②, sid:MARC-ENT-578. 범위는 S2 올해부터 · Scope 3 전년도부터)
//   ④ 모듈 탭 줄 셋(밴드 DB1 — 맨 앞 「대시보드」, 그 뒤 차례·글 그대로) · /ghg 넘김은 router.test.tsx
import { StrictMode } from 'react';

import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { fakeScope3Server } from '../../entities/ghg-scope3/api/testing.ts';
import type { FakeRunSeed } from '../../entities/ghg-scope3/api/testing.ts';
import { S3_TEXT } from '../../entities/ghg-scope3/config/text.ts';
import { yearsOf } from '../../entities/ghg-scope3/model/index.ts';
import { fakeGhgServer } from '../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../entities/ghg/config/text.ts';
import { yearsOf as s2YearsOf } from '../../entities/ghg/model/index.ts';
import { createAppRouter } from '../router.tsx';

afterEach(cleanup);
vi.setConfig({ testTimeout: 20_000 });
const WAIT = { timeout: 8_000 };
const BASE = 'http://test.local/api';

beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

type Kind = 'service' | 'admin' | null;

/** Scope 3 가짜가 받는 경로(문서·실행·양식). */
const scope3Path = (request: Request) =>
  /^\/api\/(documents|runs|inventory\/scope3)(\/|$)/.test(
    new URL(request.url).pathname,
  );

/** 그 종류로 복원되는 세션(null 은 안 로그인). 세션 밖 경로는 가짜 온실가스 서버 둘로. */
function sessionOf(kind: Kind, runs: FakeRunSeed[] = []) {
  const ghg = fakeGhgServer({ baseUrl: BASE });
  const scope3 = fakeScope3Server({
    baseUrl: BASE,
    operator: kind === 'admin',
    runs,
  });
  return {
    ghg,
    scope3,
    options: {
      baseUrl: BASE,
      storage: {
        getItem: () => (kind ? 'refresh-test' : null),
        setItem: () => {},
        removeItem: () => {},
      },
      send: async (request: Request) => {
        if (ghg.handles(request)) return ghg.send(request);
        if (scope3Path(request)) return scope3.send(request);
        const refresh = new URL(request.url).pathname.endsWith('/auth/refresh');
        const body =
          refresh ?
            {
              access: 'access-test',
              refresh: 'refresh-test',
              accessExpiresAt: '2099-01-01T00:30:00Z',
              refreshExpiresAt: '2099-01-08T00:00:00Z',
              isInitial: false,
              kind,
            }
          : {
              id: 1,
              username: kind === 'admin' ? 'ops.admin' : 'user01',
              name: '지어낸-사람',
              kind,
              companyId: kind === 'admin' ? null : 1,
              isInitial: false,
            };
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      },
    },
  };
}

// 지연 로드 화면을 미리 불러 둔다(예열, sid:MARC-ISSUE-318).
beforeAll(async () => {
  const router = createAppRouter({
    history: createMemoryHistory(),
    session: sessionOf('service').options,
  });
  await Promise.all(
    Object.values(router.routesById).map((route) =>
      router.loadRouteChunk(route),
    ),
  );
}, 60_000);

function setup(path: string, kind: Kind = 'service', runs?: FakeRunSeed[]) {
  const history = createMemoryHistory({ initialEntries: [path] });
  const { ghg, scope3, options } = sessionOf(kind, runs);
  const router = createAppRouter({ history, session: options });
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  return { router, history, ghg, scope3 };
}

const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );
const pathIs = (history: { location: { pathname: string } }, path: string) =>
  waitFor(() => expect(history.location.pathname).toBe(path), WAIT);
const searchIs = (history: { location: { search: string } }, search: string) =>
  waitFor(() => expect(history.location.search).toBe(search), WAIT);
// 모달이 열리면 뒤는 aria-hidden 이라 hidden 까지 찾는다.
const tab = (name: string) => screen.getByRole('tab', { name, hidden: true });
const selected = (name: string) => tab(name).getAttribute('aria-selected');
/** Radix 탭은 누름(mousedown)으로 고른다. */
const pressTab = (name: string) =>
  fireEvent.mouseDown(tab(name), { button: 0, ctrlKey: false });
/** S2 자리가 빈 상태로 뜰 때까지(가짜 S2 서버는 고른 잎 0 — S12-02a 뒤 초기 세팅 창 없음). */
async function closeSetup() {
  await screen.findByTestId('inventory-empty', undefined, WAIT);
  expect(screen.queryByRole('dialog')).toBeNull();
}

const shell = GHG_TEXT.shell;
const moduleTabs = GHG_TEXT.inventory.tabs;
const scopeTabs = S3_TEXT.scopeTabs;
const LAST = yearsOf(new Date())[0]!;
const THIS_YEAR = s2YearsOf(new Date())[0]!;

describe('온실가스 Scope 3 경로(S3W1)', () => {
  it('기본 해: Scope 3 는 전년도 · S2 고를 수 있는 해의 첫 값은 올해(기본 해는 둘 다 전년도 — sid:MARC-ENT-578)', () => {
    expect(LAST).toBe(THIS_YEAR - 1);
  });

  it.each(['service', 'admin'] as const)(
    '%s: /ghg/scope3?year=전년도 에 머문다 · 모듈 탭 「온실가스 데이터」·Scope 탭 「Scope 3」 current · 메뉴 「온실가스」 · 그 해 실행을 읽음',
    async (kind) => {
      const { history, scope3 } = setup(`/ghg/scope3?year=${LAST}`, kind, [
        { id: 7, status: 'done', reportYear: LAST },
      ]);
      await screenShown('ghg-scope3');
      await screen.findByTestId('s3-done', undefined, WAIT);
      expect(history.location.pathname).toBe('/ghg/scope3');
      expect(history.location.search).toBe(`?year=${LAST}`);
      expect(history.length).toBe(1);
      expect(selected(moduleTabs.inventory)).toBe('true');
      expect(selected(moduleTabs.organization)).toBe('false');
      expect(selected(scopeTabs.scope3)).toBe('true');
      expect(selected(scopeTabs.scope12)).toBe('false');
      // 고른 탭 글·밑줄 brand(GX3 고침 1 — ScopeTabs 만 덮음).
      expect(tab(scopeTabs.scope3).className).toContain(
        'data-[state=active]:text-text-brand',
      );
      // 「Scope 3」 탭에만 AI 반짝이(GX4 ④): 읽지 않는 svg 하나 · 접근 이름은 「Scope 3」 그대로 · Scope 1&2 탭에는 0.
      const sparkles = tab(scopeTabs.scope3).querySelectorAll('svg');
      expect(sparkles).toHaveLength(1);
      expect(sparkles[0]!.getAttribute('aria-hidden')).toBe('true');
      expect(sparkles[0]!.getAttribute('fill')).toBe('none');
      expect(sparkles[0]!.querySelector('path')!.getAttribute('fill')).toBe(
        'currentColor',
      );
      expect(tab(scopeTabs.scope12).querySelectorAll('svg')).toHaveLength(0);
      const current = document.querySelector('[aria-current="page"]');
      expect(current?.textContent).toBe(shell.menu.ghg);
      // 그 해 마지막 실행은 그 해 상태의 latest → GET /runs/{id}(GX5 — 목록 GET /runs 는 읽지 않는다).
      expect(
        scope3.count(`GET /inventory/scope3/years/${LAST}`),
      ).toBeGreaterThan(0);
      expect(scope3.count('GET /runs')).toBe(0);
      expect(scope3.count('GET /runs/7')).toBeGreaterThan(0);
      expect(
        screen.getByText(
          kind === 'admin' ? shell.adminGreeting : shell.greeting,
        ),
      ).not.toBeNull();
    },
  );

  it('안 로그인 → /login', async () => {
    const { history } = setup(`/ghg/scope3?year=${LAST}`, null);
    await pathIs(history, '/login');
  });

  it.each([
    ['/ghg/scope3', '없음'],
    ['/ghg/scope3?year=abcd', '글자'],
    ['/ghg/scope3?year=2025.5', '소수'],
    [`/ghg/scope3?year=${THIS_YEAR}`, '올해(범위 밖 — 뒤)'],
    [`/ghg/scope3?year=${LAST - 5}`, '범위 밖(앞)'],
  ])('%s(%s) → 전년도로 replace(기록 하나)', async (path) => {
    const { history } = setup(path);
    await searchIs(history, `?year=${LAST}`);
    expect(history.location.pathname).toBe('/ghg/scope3');
    expect(history.length).toBe(1);
    await screenShown('ghg-scope3');
  });

  it('연도 바꿈 → replace(기록 수 그대로) · 그 해 실행을 다시 읽음', async () => {
    const { history, scope3 } = setup(`/ghg/scope3?year=${LAST}`);
    await screenShown('ghg-scope3');
    const select = await screen.findByRole(
      'combobox',
      { name: S3_TEXT.screen.yearLabel },
      WAIT,
    );
    const yearRead = (year: number) =>
      scope3.count(`GET /inventory/scope3/years/${year}`);
    await waitFor(() => expect(yearRead(LAST)).toBeGreaterThan(0), WAIT);
    const before = yearRead(LAST - 2);
    fireEvent.change(select, { target: { value: `${LAST - 2}` } });
    await searchIs(history, `?year=${LAST - 2}`);
    expect(history.length).toBe(1);
    await waitFor(
      () => expect(yearRead(LAST - 2)).toBeGreaterThan(before),
      WAIT,
    );
  });

  it('Scope 탭: 「Scope 1&2」 → /ghg/inventory?year=같은 해 push · S2 자리에서 「Scope 1&2」 current · 「Scope 3」 → 돌아옴', async () => {
    const { history } = setup(`/ghg/scope3?year=${LAST}`);
    await screenShown('ghg-scope3');
    pressTab(scopeTabs.scope12);
    await pathIs(history, '/ghg/inventory');
    await searchIs(history, `?year=${LAST}`);
    expect(history.length).toBe(2);
    await screenShown('ghg-inventory');
    await closeSetup();
    await waitFor(() => expect(selected(scopeTabs.scope12)).toBe('true'), WAIT);
    expect(selected(scopeTabs.scope3)).toBe('false');
    expect(selected(moduleTabs.inventory)).toBe('true');
    pressTab(scopeTabs.scope3);
    await pathIs(history, '/ghg/scope3');
    await searchIs(history, `?year=${LAST}`);
    expect(history.length).toBe(3);
    await screenShown('ghg-scope3');
  });

  it('Scope 탭 이동의 연도가 받는 화면 범위 밖이면 그 화면 기본 해: S2 올해 → Scope 3 전년도 · Scope 3 의 다섯째 해 → S2 전년도', async () => {
    const { history } = setup(`/ghg/inventory?year=${THIS_YEAR}`);
    await screenShown('ghg-inventory');
    await closeSetup();
    pressTab(scopeTabs.scope3);
    await pathIs(history, '/ghg/scope3');
    await searchIs(history, `?year=${LAST}`);
    // push 하나 뒤 replace(기록 둘).
    expect(history.length).toBe(2);
    await screenShown('ghg-scope3');
    const select = await screen.findByRole(
      'combobox',
      { name: S3_TEXT.screen.yearLabel },
      WAIT,
    );
    fireEvent.change(select, { target: { value: `${LAST - 4}` } });
    await searchIs(history, `?year=${LAST - 4}`);
    pressTab(scopeTabs.scope12);
    await pathIs(history, '/ghg/inventory');
    await searchIs(history, `?year=${THIS_YEAR - 1}`);
    await screenShown('ghg-inventory');
  });

  it('모듈 탭 줄 셋(「대시보드 · 온실가스 데이터 · 조직구조」 차례 — 밴드 DB1) · Scope 3 에서 「조직구조」 → /ghg/organization', async () => {
    const { history } = setup(`/ghg/scope3?year=${LAST}`);
    await screenShown('ghg-scope3');
    const list = screen.getByRole('tablist', {
      name: GHG_TEXT.inventory.tabsLabel,
    });
    expect(
      within(list)
        .getAllByRole('tab')
        .map((one) => one.textContent),
    ).toEqual([
      moduleTabs.dashboard,
      moduleTabs.inventory,
      moduleTabs.organization,
    ]);
    const scope = screen.getByRole('tablist', { name: S3_TEXT.scopeTabsLabel });
    expect(
      within(scope)
        .getAllByRole('tab')
        .map((one) => one.textContent),
    ).toEqual([scopeTabs.scope12, scopeTabs.scope3]);
    pressTab(moduleTabs.organization);
    await pathIs(history, '/ghg/organization');
    await screenShown('ghg-organization');
    expect(
      screen.queryByRole('tablist', { name: S3_TEXT.scopeTabsLabel }),
    ).toBeNull();
  });

  it.each(['/ghg', '/ghg/'])(
    '%s → /ghg/dashboard(replace — 밴드 DB1 이 갈음, 전에는 /ghg/organization)',
    async (path) => {
      const { history } = setup(path);
      await screenShown('ghg-dashboard');
      await pathIs(history, '/ghg/dashboard');
      expect(history.length).toBe(1);
    },
  );
});
