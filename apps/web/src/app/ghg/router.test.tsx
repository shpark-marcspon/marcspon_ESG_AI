// @vitest-environment jsdom
// 온실가스 경로 표 시험(밴드 W12-0a ② — 발주서 §3 6, app/materiality/router.test.tsx 꼴). createAppRouter 에 메모리 기록과
//   세션 send 뒤에 가짜 온실가스 서버(entities/ghg/api/testing.ts)를 둔다 — 새 router context 칸은 없다(실어댑터는 session.api).
//   ① /ghg·/ghg/ → /ghg/organization(replace) · 두 종류 사용자 머묾 · 지금 메뉴 「온실가스」 · 운영 관리자는 인사말·[관리자 화면]
//   ② 안 로그인 → /login · 다른 틀에서 메뉴 「온실가스」 → /ghg/organization
//   ③ 행 → 상세 push · 「사업장 추가」 → new push · 새로 저장(201) → 상세 replace · [취소](바꾼 것 없음) → 목록 · 없는 id → 찾지 못함 · 레이아웃 자식 beforeLoad 0
//   ④ (밴드 W12-0b2 ③) /ghg/inventory·…/index-settings 두 역할 · year 검색 거름(글자·범위 밖·없음 → 전년도로 replace — W12-4 ②, sid:MARC-ENT-578) · 탭 줄 current(상세에서도
//     「조직구조」)·누르면 push · 초기 모달 확인 → S17 push · S17 저장 → S2 자리 push +「저장됐어요」 · [취소] → S2 자리 · S17 연도 바꿈 replace
//   ⑤ (밴드 W12-1a ①, sid:MARC-ISSUE-468) R6 S2 연도 바꿈 replace(기록 수 그대로) · R7 「저장됐어요」는 처음 그린 뒤 기록 state 에서 걷힘 — 새로 고침 뒤 0
import { StrictMode } from 'react';

import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { fakeGhgServer } from '../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../entities/ghg/config/text.ts';
import { yearsOf } from '../../entities/ghg/model/index.ts';
import { createAppRouter, validateGhgYearSearch } from '../router.tsx';

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

/** 그 종류로 복원되는 세션(null 은 안 로그인). 세션 밖 경로는 가짜 온실가스 서버로. */
function sessionOf(kind: Kind, ghg = fakeGhgServer({ baseUrl: BASE })) {
  return {
    ghg,
    options: {
      baseUrl: BASE,
      storage: {
        getItem: () => (kind ? 'refresh-test' : null),
        setItem: () => {},
        removeItem: () => {},
      },
      send: async (request: Request) => {
        if (ghg.handles(request)) return ghg.send(request);
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

function setup(path: string, kind: Kind = 'service') {
  const history = createMemoryHistory({ initialEntries: [path] });
  const { ghg, options } = sessionOf(kind);
  const router = createAppRouter({ history, session: options });
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  return { router, history, ghg };
}

/** S12-02a: S2 빈 해 = 빈 상태만(초기 세팅 창 0). */
async function emptyShown() {
  await screen.findByTestId('inventory-empty', undefined, WAIT);
  expect(screen.queryByRole('dialog')).toBeNull();
}
const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );
const pathIs = (history: { location: { pathname: string } }, path: string) =>
  waitFor(() => expect(history.location.pathname).toBe(path), WAIT);
const shell = GHG_TEXT.shell;
const words = GHG_TEXT.organization;

describe('온실가스 경로', () => {
  it.each(['/ghg', '/ghg/'])(
    '%s → /ghg/dashboard(replace — 기록이 하나, 밴드 DB1 — 전에는 /ghg/organization)',
    async (path) => {
      const { history } = setup(path);
      await screenShown('ghg-dashboard');
      await pathIs(history, '/ghg/dashboard');
      await searchIs(history, `?year=${THIS_YEAR - 1}`);
      expect(history.length).toBe(1);
    },
  );

  it.each(['service', 'admin'] as const)(
    '%s: /ghg/organization 에 머문다 · 지금 메뉴 「온실가스」',
    async (kind) => {
      const { history } = setup('/ghg/organization', kind);
      await screenShown('ghg-organization');
      expect(history.location.pathname).toBe('/ghg/organization');
      const current = document.querySelector('[aria-current="page"]');
      expect(current?.textContent).toBe(shell.menu.ghg);
      const ghg = screen.getByRole('button', { name: shell.menu.ghg });
      expect(ghg.getAttribute('aria-disabled')).toBeNull();
      if (kind === 'admin') {
        expect(screen.getByText(shell.adminGreeting)).not.toBeNull();
        fireEvent.click(screen.getByRole('button', { name: shell.toAdmin }));
        await pathIs(history, '/admin/accounts');
      } else {
        expect(screen.getByText(shell.greeting)).not.toBeNull();
        expect(
          screen.queryByRole('button', { name: shell.toAdmin }),
        ).toBeNull();
      }
    },
  );

  it('안 로그인 → /login', async () => {
    const { history } = setup('/ghg/organization', null);
    await pathIs(history, '/login');
  });

  it('다른 틀의 메뉴 「온실가스」 → 첫 화면 /ghg/dashboard(밴드 DB1)', async () => {
    const { history } = setup('/materiality/intro');
    await screenShown('materiality-intro');
    fireEvent.click(screen.getByRole('button', { name: shell.menu.ghg }));
    await screenShown('ghg-dashboard');
    await pathIs(history, '/ghg/dashboard');
  });

  it('행 → 상세 push · [취소](바꾼 것 없음) → 목록 · 「사업장 추가」 → new · 새로 저장 → 상세 replace', async () => {
    const { history, ghg } = setup('/ghg/organization');
    await screenShown('ghg-organization');
    await waitFor(
      () =>
        expect(document.querySelector('tr[data-branch-id="1"]')).not.toBeNull(),
      WAIT,
    );
    fireEvent.click(
      screen.getByRole('button', { name: words.openRow('본사') }),
    );
    await pathIs(history, '/ghg/organization/branches/1');
    await screenShown('ghg-branch');
    await screen.findByDisplayValue('본사', undefined, WAIT);
    fireEvent.click(
      screen.getByRole('button', { name: GHG_TEXT.branch.cancel }),
    );
    await pathIs(history, '/ghg/organization');
    fireEvent.click(await screen.findByRole('button', { name: words.add }));
    await pathIs(history, '/ghg/organization/branches/new');
    const lengthBefore = history.length;
    fireEvent.change(
      await screen.findByRole('textbox', { name: GHG_TEXT.branch.name }),
      { target: { value: '제5공장' } },
    );
    fireEvent.click(screen.getByRole('button', { name: GHG_TEXT.branch.save }));
    await pathIs(history, '/ghg/organization/branches/2');
    expect(history.length).toBe(lengthBefore);
    expect(ghg.count('POST /branches')).toBe(1);
    await screen.findByDisplayValue('제5공장', undefined, WAIT);
  });

  it('없는 id → 「사업장을 찾지 못했어요」 + [목록으로]', async () => {
    const { history } = setup('/ghg/organization/branches/99');
    await screen.findByText(GHG_TEXT.branch.notFound, undefined, WAIT);
    fireEvent.click(
      screen.getByRole('button', { name: GHG_TEXT.branch.toList }),
    );
    await pathIs(history, '/ghg/organization');
  });

  it('경로 트리: /ghg 의 자식 일곱(밴드 DB1 대시보드), 자식에 beforeLoad 없음', () => {
    const { router } = setup('/login', null);
    const routes = Object.values(router.routesById) as {
      id: string;
      parentRoute?: { id: string };
      options: { beforeLoad?: unknown };
    }[];
    const children = routes.filter((row) => row.parentRoute?.id === '/ghg');
    expect(children.map((row) => row.id).sort()).toEqual(
      [
        '/ghg/dashboard',
        '/ghg/inventory',
        '/ghg/inventory/index-settings',
        '/ghg/organization',
        '/ghg/organization/branches/$branchId',
        '/ghg/organization/branches/new',
        '/ghg/scope3',
      ].sort(),
    );
    for (const row of children) expect(row.options.beforeLoad).toBeUndefined();
  });
});

const inventory = GHG_TEXT.inventory;
const THIS_YEAR = yearsOf(new Date())[0]!;
const searchIs = (history: { location: { search: string } }, search: string) =>
  waitFor(() => expect(history.location.search).toBe(search), WAIT);
// 모달이 열리면 뒤는 aria-hidden 이라 hidden 까지 찾는다.
const tab = (name: string) => screen.getByRole('tab', { name, hidden: true });
/** Radix 탭은 누름(mousedown)으로 고른다. */
const pressTab = (name: string) =>
  fireEvent.mouseDown(tab(name), { button: 0, ctrlKey: false });

describe('온실가스 데이터 경로(W12-0b2)', () => {
  it('year 검색 거름: 네 자리 숫자 글자·정수만 정수로 · 그 밖은 열쇠만(undefined)', () => {
    expect(validateGhgYearSearch({ year: '2025' })).toEqual({ year: 2025 });
    expect(validateGhgYearSearch({ year: 2025 })).toEqual({ year: 2025 });
    for (const year of ['abcd', ' 2025', '2025.0', '02025', '', '1e3', 2025.5])
      expect(validateGhgYearSearch({ year })).toStrictEqual({
        year: undefined,
      });
    expect(validateGhgYearSearch({})).toStrictEqual({ year: undefined });
  });

  it.each(['service', 'admin'] as const)(
    '%s: /ghg/inventory?year=올해 에 머문다 · 탭 「온실가스 데이터」 current · 메뉴 「온실가스」',
    async (kind) => {
      const { history } = setup(`/ghg/inventory?year=${THIS_YEAR}`, kind);
      await screenShown('ghg-inventory');
      expect(history.location.search).toBe(`?year=${THIS_YEAR}`);
      await emptyShown();
      expect(tab(inventory.tabs.inventory).getAttribute('aria-selected')).toBe(
        'true',
      );
      expect(
        tab(inventory.tabs.organization).getAttribute('aria-selected'),
      ).toBe('false');
      const current = document.querySelector('[aria-current="page"]');
      expect(current?.textContent).toBe(shell.menu.ghg);
    },
  );

  it.each([
    ['/ghg/inventory', '없음'],
    ['/ghg/inventory?year=abcd', '글자'],
    ['/ghg/inventory?year=2026.5', '소수'],
    ['/ghg/inventory?year=1999', '범위 밖(앞)'],
    [`/ghg/inventory?year=${THIS_YEAR + 1}`, '범위 밖(뒤)'],
    [`/ghg/inventory/index-settings?year=${THIS_YEAR - 5}`, 'S17 범위 밖'],
  ])('%s(%s) → 전년도로 replace(기록 하나)', async (path) => {
    const { history } = setup(path);
    await searchIs(history, `?year=${THIS_YEAR - 1}`);
    expect(history.length).toBe(1);
    await screenShown(
      path.includes('index-settings') ? 'ghg-index-settings' : 'ghg-inventory',
    );
  });

  it('탭 줄: 사업장 상세에서도 「조직구조」 current · 「온실가스 데이터」 → /ghg/inventory push · 「조직구조」 → /ghg/organization', async () => {
    const { history } = setup('/ghg/organization/branches/1');
    await screenShown('ghg-branch');
    expect(tab(inventory.tabs.organization).getAttribute('aria-selected')).toBe(
      'true',
    );
    const before = history.length;
    pressTab(inventory.tabs.inventory);
    await screenShown('ghg-inventory');
    await searchIs(history, `?year=${THIS_YEAR - 1}`);
    expect(history.location.pathname).toBe('/ghg/inventory');
    expect(history.length).toBe(before + 1);
    await waitFor(
      () =>
        expect(
          tab(inventory.tabs.inventory).getAttribute('aria-selected'),
        ).toBe('true'),
      WAIT,
    );
    await emptyShown();
    pressTab(inventory.tabs.organization);
    await pathIs(history, '/ghg/organization');
    await screenShown('ghg-organization');
  });

  it('S12-02a [인덱스 설정](창 없음) → S17 push(같은 연도) · 연도 바꿈 replace · [저장] → S2 자리 push +「저장됐어요」 · [인덱스 설정] → [취소] → S2 자리', async () => {
    const year = THIS_YEAR - 1;
    const { history, ghg } = setup(`/ghg/inventory?year=${year}`);
    await emptyShown(); // S12-02a: 창 없이 빈 상태 — [인덱스 설정]이 바로 S17
    const before = history.length;
    fireEvent.click(
      screen.getByRole('button', { name: inventory.indexSettings }),
    );
    await pathIs(history, '/ghg/inventory/index-settings');
    expect(history.location.search).toBe(`?year=${year}`);
    expect(history.length).toBe(before + 1);
    await screenShown('ghg-index-settings');
    expect(tab(inventory.tabs.inventory).getAttribute('aria-selected')).toBe(
      'true',
    );
    const settings = GHG_TEXT.indexSettings;
    await screen.findByRole('button', { name: settings.save }, WAIT);
    fireEvent.change(
      screen.getByRole('combobox', { name: settings.yearLabel }),
      { target: { value: `${year - 1}` } },
    );
    await searchIs(history, `?year=${year - 1}`);
    expect(history.length).toBe(before + 1);
    await waitFor(
      () =>
        expect(
          ghg.count('GET /inventory/scope12/index-tree'),
        ).toBeGreaterThanOrEqual(3),
      WAIT,
    );
    fireEvent.click(
      await screen.findByRole('button', { name: settings.save }, WAIT),
    );
    fireEvent.submit(
      (
        await screen.findByTestId('save-confirm', undefined, WAIT)
      ).querySelector('form')!,
    ); // S12C1 da787b28: [저장] → 확인 창 → [확인].
    await pathIs(history, '/ghg/inventory');
    expect(history.location.search).toBe(`?year=${year - 1}`);
    expect(history.length).toBe(before + 2);
    expect(
      ghg.bodies(`PUT /inventory/scope12/index-selections/${year - 1}`),
    ).toEqual([{ facilityNodeIds: [] }]);
    expect(
      (await screen.findByTestId('toast', undefined, WAIT)).textContent,
    ).toBe(inventory.saved);
    await emptyShown();
    fireEvent.click(
      screen.getByRole('button', { name: inventory.indexSettings }),
    );
    await pathIs(history, '/ghg/inventory/index-settings');
    fireEvent.click(
      await screen.findByRole('button', { name: settings.cancel }, WAIT),
    );
    await pathIs(history, '/ghg/inventory');
    expect(history.location.search).toBe(`?year=${year - 1}`);
    await screenShown('ghg-inventory');
    expect(screen.queryByTestId('toast')).toBeNull();
  });
});

describe('S2 연도·「저장됐어요」(sid:MARC-ISSUE-468 R6·R7)', () => {
  it('R6: S2 연도 바꿈은 replace — 기록 수 그대로 · 주소 연도 바뀜 · 그 해를 다시 읽음', async () => {
    const year = THIS_YEAR - 1;
    const { history, ghg } = setup(`/ghg/inventory?year=${year}`);
    await emptyShown();
    const before = history.length;
    fireEvent.change(
      screen.getByRole('combobox', { name: inventory.yearLabel }),
      { target: { value: `${year - 1}` } },
    );
    await searchIs(history, `?year=${year - 1}`);
    expect(history.length).toBe(before);
    await waitFor(
      () =>
        expect(
          ghg.calls.some(
            (call) =>
              call.path === '/inventory/scope12/rows' &&
              call.query.get('year') === `${year - 1}`,
          ),
        ).toBe(true),
      WAIT,
    );
  });

  it('R7: S17 저장 → S2 「저장됐어요」 — 기록 state 의 ghgSaved 는 곧 걷힘(replace, 기록 수 그대로) · 같은 기록으로 새로 그리면(새로 고침) 0', async () => {
    const year = THIS_YEAR;
    const { history, ghg } = setup(
      `/ghg/inventory/index-settings?year=${year}`,
    );
    const before = history.length;
    fireEvent.click(
      await screen.findByRole(
        'button',
        { name: GHG_TEXT.indexSettings.save },
        WAIT,
      ),
    );
    fireEvent.submit(
      (
        await screen.findByTestId('save-confirm', undefined, WAIT)
      ).querySelector('form')!,
    ); // S12C1 da787b28: [저장] → 확인 창 → [확인].
    await pathIs(history, '/ghg/inventory');
    expect(
      (await screen.findByTestId('toast', undefined, WAIT)).textContent,
    ).toBe(inventory.saved);
    await waitFor(
      () =>
        expect(
          (history.location.state as { ghgSaved?: unknown }).ghgSaved,
        ).not.toBe(true),
      WAIT,
    );
    expect(history.length).toBe(before + 1);
    expect(history.location.search).toBe(`?year=${year}`);
    expect(screen.getByTestId('toast').textContent).toBe(inventory.saved);
    cleanup();
    const router = createAppRouter({
      history,
      session: sessionOf('service', ghg).options,
    });
    render(
      <StrictMode>
        <RouterProvider router={router} />
      </StrictMode>,
    );
    await screenShown('ghg-inventory');
    await emptyShown();
    expect(screen.queryByTestId('toast')).toBeNull();
  });
  it('R7: S2 에서 연도를 바꾸면 「저장됐어요」 를 걷음', async () => {
    const year = THIS_YEAR;
    const { history } = setup(`/ghg/inventory/index-settings?year=${year}`);
    fireEvent.click(
      await screen.findByRole(
        'button',
        { name: GHG_TEXT.indexSettings.save },
        WAIT,
      ),
    );
    fireEvent.submit(
      (
        await screen.findByTestId('save-confirm', undefined, WAIT)
      ).querySelector('form')!,
    ); // S12C1 da787b28: [저장] → 확인 창 → [확인].
    await pathIs(history, '/ghg/inventory');
    await screen.findByTestId('toast', undefined, WAIT);
    // 빈 선택 저장이라 빈 상태(S12-02a — 창 없음) — 연도를 바꾼다.
    await emptyShown();
    expect(screen.getByTestId('toast')).toBeTruthy();
    fireEvent.change(
      screen.getByRole('combobox', { name: inventory.yearLabel }),
      { target: { value: `${year - 1}` } },
    );
    await searchIs(history, `?year=${year - 1}`);
    await waitFor(() => expect(screen.queryByTestId('toast')).toBeNull());
  });
});
