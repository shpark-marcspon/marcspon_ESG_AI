// @vitest-environment jsdom
// 원고작성 경로 표 시험(밴드 RPW1 ① — 발주서 §2-1, app/ghg/router.test.tsx 꼴). createAppRouter 에 메모리 기록과 세션 send 뒤에 가짜 원고작성
//   서버(entities/drafting/api/testing.ts)를 둔다 — 새 router context 칸은 없다(실어댑터는 session.api + 틀의 sendUpload).
//   ① 두 종류 사용자가 /drafting·/drafting/new·…/document·…/outline·…/runs/$runId 에 머문다 · 운영 관리자는 인사말·[관리자 화면] · 안 로그인 → /login
//   ② STEP 띠는 RP-02·03·04 에서만(지금 단계) · 레이아웃 자식 beforeLoad 0
//   ③ RP-01 [새 프로젝트] → /drafting/new push · RP-02 [다음] → 만들기·올림 셋·PUT …/document → …/outline replace
//     (서명 PUT 은 globalThis.fetch 로 — Authorization·쿠키 0) · [취소] → 목록 · 줄 「다음 할 일」 → 다시 올리기·RP-03
//   ④ 다시 올리기 주소 id 가 정수가 아니면 요청 없이 찾지 못함
//   ⑤(경계 ②) RP-03 [초안 만들기] → POST /runs → …/runs/$runId push · RP-03 고친 채 [목록으로] → 나가기 창(useBlocker) → [나가기] 면 목록
//   ⑥(밴드 RPW6) RP-00 /drafting/intro — 두 종류 사용자가 머물고 [시작하기]가 보인다(권한 갈래: RP-01 [새 프로젝트]와 같이 둘 다) · LNB 「보고서 작성」 켬 ·
//     STEP 띠 0 · 그리는 동안 원고작성 요청 0 · RP-01 「작성 안내」 → push · [시작하기] → /drafting/new push · 안 로그인 → /login · 뒤로 → 목록
import { StrictMode } from 'react';

import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeDraftingServer,
  fakeOutline,
} from '../../entities/drafting/api/testing.ts';
import { DR_TEXT } from '../../entities/drafting/config/text.ts';
import { createAppRouter } from '../router.tsx';
import { sendUpload } from './DraftingRoutes.tsx';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
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
type Server = ReturnType<typeof fakeDraftingServer>;

/** 그 종류로 복원되는 세션(null 은 안 로그인). 세션 밖 경로는 가짜 원고작성 서버로. */
function sessionOf(kind: Kind, drafting: Server) {
  return {
    baseUrl: BASE,
    storage: {
      getItem: () => (kind ? 'refresh-test' : null),
      setItem: () => {},
      removeItem: () => {},
    },
    send: async (request: Request) => {
      if (drafting.handles(request)) return drafting.send(request);
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
  };
}

// 지연 로드 화면을 미리 불러 둔다(예열, sid:MARC-ISSUE-318).
beforeAll(async () => {
  const router = createAppRouter({
    history: createMemoryHistory(),
    session: sessionOf('service', fakeDraftingServer({ baseUrl: BASE })),
  });
  await Promise.all(
    Object.values(router.routesById).map((route) =>
      router.loadRouteChunk(route),
    ),
  );
}, 60_000);

function setup(
  path: string,
  kind: Kind = 'service',
  drafting = fakeDraftingServer({
    baseUrl: BASE,
    projects: [{ id: 7, name: '지어낸 보고서 가', year: 2026 }],
  }),
) {
  const history = createMemoryHistory({ initialEntries: [path] });
  const router = createAppRouter({
    history,
    session: sessionOf(kind, drafting),
  });
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  return { router, history, drafting };
}

const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );
const pathIs = (history: { location: { pathname: string } }, path: string) =>
  waitFor(() => expect(history.location.pathname).toBe(path), WAIT);
const shell = DR_TEXT.shell;
const stepNow = () =>
  document.querySelector('[aria-current="step"]')?.textContent ?? null;
/** STEP 띠가 그 화면 안 제목 뒤인가(RPW2 B2 — 실제 화면). */
const stepAfterTitle = () => {
  const title = document.querySelector('[data-screen] h2')!;
  const step = document.querySelector(
    `[data-screen] ol[aria-label="${DR_TEXT.steps.label}"]`,
  )!;
  return Boolean(
    title.compareDocumentPosition(step) & Node.DOCUMENT_POSITION_FOLLOWING,
  );
};

describe('서명 PUT(⑨)', () => {
  it('signal 을 fetch 에 넘긴다 · 없으면 칸도 없다 · Authorization·쿠키 0', async () => {
    const fetch = vi.fn(async () => new Response('', { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    const file = new File(['지어낸'], '지어낸.pdf');
    const { signal } = new AbortController();
    await sendUpload('http://storage.test/up', 'PUT', file, signal);
    await sendUpload('http://storage.test/up', 'PUT', file);
    const inits = fetch.mock.calls.map(
      (call) => (call as unknown as [string, RequestInit])[1],
    );
    expect(inits[0]!.signal).toBe(signal);
    expect('signal' in inits[1]!).toBe(false);
    expect(inits[0]!.credentials).toBe('omit');
    expect(inits[0]!.headers).toBeUndefined();
  });
});

describe('원고작성 경로', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /drafting 에 머문다(RP-01) · STEP 띠 0',
    async (kind) => {
      const { history } = setup('/drafting', kind);
      await screenShown('drafting-list');
      expect(history.location.pathname).toBe('/drafting');
      expect(screen.getByRole('heading', { name: shell.title })).not.toBeNull();
      expect(document.querySelector('[aria-current="step"]')).toBeNull();
      expect(document.querySelector('[aria-current="page"]')?.textContent).toBe(
        shell.menu.drafting,
      );
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

  it.each([
    ['/drafting/new', 'drafting-new', 1],
    ['/drafting/projects/7/document', 'drafting-new', 1],
  ] as const)(
    'service·admin: %s 에 머문다 · STEP %i',
    async (path, name, step) => {
      for (const kind of ['service', 'admin'] as const) {
        const { history } = setup(path, kind);
        await screenShown(name);
        expect(history.location.pathname).toBe(path);
        expect(stepNow()).toContain(DR_TEXT.steps.items[step - 1]);
        expect(stepAfterTitle()).toBe(true);
        cleanup();
      }
    },
  );

  it.each([
    ['/drafting/projects/7/outline', 'drafting-outline', 2],
    ['/drafting/projects/7/runs/301', 'drafting-draft', 3],
  ] as const)(
    'service·admin: %s 에 머문다(경계 ②) · STEP %i',
    async (path, name, step) => {
      for (const kind of ['service', 'admin'] as const) {
        const { history } = setup(path, kind);
        await screenShown(name);
        expect(stepNow()).toContain(DR_TEXT.steps.items[step - 1]);
        expect(stepAfterTitle()).toBe(true);
        expect(history.location.pathname).toBe(path);
        cleanup();
      }
    },
  );

  it.each([
    '/drafting',
    '/drafting/new',
    '/drafting/projects/7/document',
    '/drafting/projects/7/outline',
    '/drafting/projects/7/runs/301',
  ])('안 로그인: %s → /login', async (path) => {
    const { history } = setup(path, null);
    await pathIs(history, '/login');
  });

  it('레이아웃 자식 경로에는 beforeLoad 가 없다(가드는 /drafting 하나)', () => {
    const { router } = setup('/drafting');
    const children = Object.values(router.routesById).filter(
      (route) => route.id.startsWith('/drafting/') && route.id !== '/drafting/',
    );
    expect(children.length).toBeGreaterThanOrEqual(4);
    for (const route of children)
      expect(route.options.beforeLoad, route.id).toBeUndefined();
    expect(router.routesById['/drafting'].options.beforeLoad).toBeDefined();
  });
});

describe('원고작성 이동', () => {
  it('RP-01 [새 프로젝트] → /drafting/new push · [취소] → 목록', async () => {
    const { history } = setup('/drafting');
    await screenShown('drafting-list');
    await waitFor(
      () =>
        expect(document.querySelector('[data-project-id="7"]')).not.toBeNull(),
      WAIT,
    );
    fireEvent.click(
      screen.getAllByRole('button', { name: DR_TEXT.list.newProject })[0]!,
    );
    await pathIs(history, '/drafting/new');
    expect(history.length).toBe(2);
    await screenShown('drafting-new');
    fireEvent.click(
      screen.getByRole('button', { name: DR_TEXT.create.cancel }),
    );
    await pathIs(history, '/drafting');
  });

  it('줄 「다음 할 일」: 문서 없음 → 다시 올리기 · 목차 없음 → RP-03', async () => {
    const drafting = fakeDraftingServer({
      baseUrl: BASE,
      projects: [
        { id: 7, name: '지어낸 보고서 가', year: 2026 },
        { id: 8, name: '지어낸 보고서 나', year: 2025 },
      ],
    });
    drafting.seedProject(8, { documentId: drafting.seedDocument() });
    const { history } = setup('/drafting', 'service', drafting);
    await waitFor(
      () => expect(document.querySelector('[data-next]')).not.toBeNull(),
      WAIT,
    );
    const row7 = document
      .querySelector('[data-project-id="7"]')!
      .closest('tr')!;
    fireEvent.click(row7.querySelector('[data-next="upload"]')!);
    await pathIs(history, '/drafting/projects/7/document');
    history.back();
    await pathIs(history, '/drafting');
    await waitFor(
      () =>
        expect(document.querySelector('[data-next="outline"]')).not.toBeNull(),
      WAIT,
    );
    fireEvent.click(document.querySelector('[data-next="outline"]')!);
    await pathIs(history, '/drafting/projects/8/outline');
  });

  it('RP-02 [다음]: 만들기 → 서명 PUT(globalThis.fetch, Authorization 0) → confirm → PUT …/document → …/outline replace', async () => {
    const drafting = fakeDraftingServer({ baseUrl: BASE });
    const puts: Request[] = [];
    vi.stubGlobal('fetch', async (url: string, init: RequestInit) => {
      const request = new Request(url, init);
      puts.push(request);
      await drafting.sendUpload(url, init.method ?? 'GET', init.body as File);
      return new Response(null, { status: 200 });
    });
    const { history } = setup('/drafting/new', 'service', drafting);
    await screenShown('drafting-new');
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    fireEvent.change(input, {
      target: {
        files: [
          new File(['%PDF-1.4 지어낸'], '지어낸 전년도.pdf', {
            type: 'application/pdf',
          }),
        ],
      },
    });
    const next = screen.getByRole('button', { name: DR_TEXT.create.next });
    await waitFor(
      () => expect(next.hasAttribute('disabled')).toBe(false),
      WAIT,
    );
    fireEvent.click(next);
    await pathIs(history, '/drafting/projects/1/outline');
    expect(history.length).toBe(1);
    expect(puts).toHaveLength(1);
    expect(puts[0]!.method).toBe('PUT');
    expect(puts[0]!.headers.get('Authorization')).toBeNull();
    expect(puts[0]!.credentials).toBe('omit');
    expect(drafting.count('POST /drafting/projects')).toBe(1);
    expect(drafting.count('POST /documents')).toBe(1);
    expect(drafting.count('POST /documents/101/confirm')).toBe(1);
    expect(drafting.bodies('PUT /drafting/projects/1/document')).toEqual([
      { documentId: 101 },
    ]);
  });

  it('다시 올리기 주소 id 가 정수가 아니면 요청 없이 찾지 못함', async () => {
    const { drafting } = setup('/drafting/projects/x7/document');
    await screenShown('drafting-new');
    await waitFor(
      () =>
        expect(screen.getByText(DR_TEXT.create.projectMissing)).not.toBeNull(),
      WAIT,
    );
    expect(
      drafting.calls.filter((call) => call.path.startsWith('/drafting')),
    ).toEqual([]);
  });

  it('RP-03 [초안 만들기] → POST /runs → …/runs/$runId push(진행 화면)', async () => {
    const drafting = fakeDraftingServer({
      baseUrl: BASE,
      projects: [{ id: 7, name: '지어낸 보고서 가', year: 2026 }],
    });
    drafting.seedProject(7, {
      documentId: drafting.seedDocument(),
      nodes: fakeOutline(),
    });
    const { history } = setup(
      '/drafting/projects/7/outline',
      'service',
      drafting,
    );
    await screenShown('drafting-outline');
    const start = await screen.findByRole(
      'button',
      { name: DR_TEXT.outline.start },
      WAIT,
    );
    fireEvent.click(start);
    const runId = 301;
    await pathIs(history, `/drafting/projects/7/runs/${runId}`);
    expect(drafting.count('POST /runs')).toBe(1);
    expect(history.length).toBe(2);
    await screenShown('drafting-draft');
  });

  it('RP-03 고친 채 [목록으로] → 나가기 창 · [계속 고치기]면 머묾 · [저장하지 않고 나가기]면 목록', async () => {
    const drafting = fakeDraftingServer({
      baseUrl: BASE,
      projects: [{ id: 7, name: '지어낸 보고서 가', year: 2026 }],
    });
    drafting.seedProject(7, { documentId: drafting.seedDocument() });
    const { history } = setup(
      '/drafting/projects/7/outline',
      'service',
      drafting,
    );
    await screenShown('drafting-outline');
    fireEvent.click(
      await screen.findByRole('button', { name: DR_TEXT.outline.addTop }, WAIT),
    );
    fireEvent.click(
      screen.getByRole('button', { name: DR_TEXT.outline.toList }),
    );
    const stay = await screen.findByRole(
      'button',
      { name: DR_TEXT.outline.leaveStay },
      WAIT,
    );
    fireEvent.click(stay);
    await waitFor(
      () => expect(screen.queryByTestId('leave-dialog')).toBeNull(),
      WAIT,
    );
    expect(history.location.pathname).toBe('/drafting/projects/7/outline');
    fireEvent.click(
      screen.getByRole('button', { name: DR_TEXT.outline.toList }),
    );
    fireEvent.click(
      await screen.findByRole(
        'button',
        { name: DR_TEXT.outline.leaveGo },
        WAIT,
      ),
    );
    await pathIs(history, '/drafting');
  });
});

describe('원고작성 경로 ⑥ RP-00 작성 안내(밴드 RPW6, sid:MARC-ENT-530)', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /drafting/intro 는 RP-00 을 그리고 머문다 · 「보고서 작성」 켬 · STEP 띠 0 · [시작하기] 보임 · 요청 0',
    async (kind) => {
      const { history, drafting } = setup('/drafting/intro', kind);
      await screenShown('drafting-intro');
      expect(history.location.pathname).toBe('/drafting/intro');
      expect(document.querySelector('[aria-current="page"]')?.textContent).toBe(
        shell.menu.drafting,
      );
      expect(document.querySelector('[aria-current="step"]')).toBeNull();
      // 권한 갈래: 운영 관리자도 [시작하기]가 보인다(RP-01 [새 프로젝트]가 두 종류 모두에게 보이는 것과 같다).
      expect(
        screen.getByRole('button', { name: DR_TEXT.intro.start }),
      ).toBeTruthy();
      expect(
        kind === 'admin' ?
          screen.getByText(shell.adminGreeting)
        : screen.getByText(shell.greeting),
      ).toBeTruthy();
      await act(async () => {});
      expect(drafting.calls).toHaveLength(0);
    },
  );

  it('RP-01 「작성 안내」 → /drafting/intro(push — 기록이 하나 는다) · 뒤로 → 목록', async () => {
    const { history } = setup('/drafting');
    const link = await waitFor(
      () => screen.getByRole('link', { name: DR_TEXT.list.introLink }),
      WAIT,
    );
    const before = history.length;
    fireEvent.click(link);
    await screenShown('drafting-intro');
    expect(history.location.pathname).toBe('/drafting/intro');
    expect(history.length).toBe(before + 1);
    act(() => history.back());
    await screenShown('drafting-list');
    expect(history.location.pathname).toBe('/drafting');
  });

  it('[시작하기] → /drafting/new(push), RP-02 가 그려짐', async () => {
    const { history } = setup('/drafting/intro');
    await screenShown('drafting-intro');
    const before = history.length;
    fireEvent.click(screen.getByRole('button', { name: DR_TEXT.intro.start }));
    await screenShown('drafting-new');
    expect(history.location.pathname).toBe('/drafting/new');
    expect(history.length).toBe(before + 1);
  });

  it('안 로그인: /drafting/intro → /login', async () => {
    const { history } = setup('/drafting/intro', null);
    await pathIs(history, '/login');
  });

  it('경로 트리: /drafting/intro 가 있고 beforeLoad 가 없다(가드는 레이아웃 /drafting 하나)', () => {
    const { router } = setup('/login');
    const routes = Object.values(router.routesById) as {
      id: string;
      options: { beforeLoad?: unknown };
    }[];
    const intro = routes.find((route) => route.id === '/drafting/intro');
    expect(intro).toBeDefined();
    expect(intro!.options.beforeLoad).toBeUndefined();
  });
});
