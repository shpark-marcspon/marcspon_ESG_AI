// @vitest-environment jsdom
// 경로 표 시험(밴드 RT1 §1-6 단위). createAppRouter 에 메모리 기록·가짜 openPdf·목 저장소를 넣어 본다.
//   ① 표의 주소마다 그 화면 ② 모르는 주소 → /greenwash ③ 옛 주소는 넘기지 않는다(목록) ④ replace 셋은 기록을 늘리지 않고 push 는 늘린다
//   ⑤ [확정] 표식은 한 번만 ⑥ DEMOS 거짓이면 /dev/* → /greenwash. 그리고 router.tsx 의 mock= 글자 목록 = MOCK_SCENARIOS.
//   ⑦ 운영 관리자도 고객사 사용자와 같이 쓴다(밴드 GR3 — SV1 읽기 전용 걷음, sid:MARC-ENT-374·409): 쓰기 단추·저장소 쓰기·/greenwash/new 가 고객사와 같고,
//     운영 관리자만 다른 것은 인사말·[관리자 화면]·「내가 올린 것만」 숨김·목록 meta. greenwashAccess 단위.
//   ⑨ 기본 저장소(밴드 GW1R ② §3 D): createStore 없이 — 실어댑터가 세션 Api(Bearer)로 부른다, 목은 데모 빌드(context.admin.demos)의 탭 표지 뒤로만.
// 목을 가져오므로 app/greenwash 아래에 둔다(app/guards/layers.test.ts 의 rootTests).
import { StrictMode, createElement } from 'react';
import type { ReactNode } from 'react';

import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import { storeErrorKind } from '../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../entities/greenwash/api/index.ts';
import {
  MOCK_SCENARIOS,
  createMockStore,
} from '../../entities/greenwash/api/mock/index.ts';
import type { MockStoreControl } from '../../entities/greenwash/api/mock/index.ts';
import { listedGreenwashServer } from '../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../entities/greenwash/config/text.ts';
import type { OpenPdf } from '../../widgets/doc-viewer/index.ts';
import {
  MOCK_SEARCH_VALUES,
  createAppRouter,
  validateGreenwashSearch,
} from '../router.tsx';
import {
  MOCK_TAB_KEY,
  followSessionEnd,
  greenwashAccess,
  sendUpload,
} from './GreenwashRoutes.tsx';

afterEach(cleanup);

/**
 * 화면 다섯이 받은 store prop 을 붙잡는다(밴드 SV1 ② 검증 B1 — 처리기 연결을 글자가 아니라 행동으로 본다).
 * 밴드 DT1 ②: 쓰기 켬(canWrite) prop 도 붙잡는다 — 운영 관리자 갈래(GW-01b)가 화면까지 닿는지 본다.
 * 화면은 그대로 그린다(importActual 로 감쌈). 이 파일 안의 일이라 층을 넓히지 않는다.
 */
type Screen = (props: {
  store: GreenwashStore;
  canWrite?: boolean;
}) => ReactNode;
const { captured, capture } = vi.hoisted(() => {
  const captured = {
    stores: new Map<string, unknown>(),
    canWrite: new Map<string, boolean | undefined>(),
  };
  // vi.mock 의 공장보다 먼저 있어야 해서 hoisted 안에 둔다. createElement 는 그릴 때에야 부른다.
  const capture = (name: string, actual: Screen): Screen =>
    function Captured(props) {
      captured.stores.set(name, props.store);
      captured.canWrite.set(name, props.canWrite);
      return createElement(actual, props);
    };
  return { captured, capture };
});
vi.mock('../../pages/greenwash-list/index.ts', async (importActual) => {
  const actual = await importActual<{ ListScreen: Screen }>();
  return { ...actual, ListScreen: capture('list', actual.ListScreen) };
});
vi.mock('../../pages/greenwash-status/index.ts', async (importActual) => {
  const actual = await importActual<{ StatusScreen: Screen }>();
  return { ...actual, StatusScreen: capture('status', actual.StatusScreen) };
});
vi.mock('../../pages/greenwash-result/index.ts', async (importActual) => {
  const actual = await importActual<{ ResultScreen: Screen }>();
  return { ...actual, ResultScreen: capture('result', actual.ResultScreen) };
});
vi.mock('../../pages/greenwash-review/index.ts', async (importActual) => {
  const actual = await importActual<{ ReviewScreen: Screen }>();
  return { ...actual, ReviewScreen: capture('review', actual.ReviewScreen) };
});
vi.mock('../../pages/greenwash-new/index.ts', async (importActual) => {
  const actual = await importActual<{ NewCheckScreen: Screen }>();
  return { ...actual, NewCheckScreen: capture('new', actual.NewCheckScreen) };
});
afterEach(() => {
  captured.stores.clear();
  captured.canWrite.clear();
});
// 경로 컴포넌트는 게으르게 불린다(lazyRouteComponent). 전량 시험이 같이 돌 때 첫 import 가 1초를 넘을 수 있어 기다림을 넓힌다.
vi.setConfig({ testTimeout: 20_000 });
const WAIT = { timeout: 8_000 };

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

const neverOpen: OpenPdf = () => new Promise(() => {});

/**
 * 로그인 준비(밴드 LG1): 고객사 사용자로 복원되는 세션. 보관소에 refresh 하나, 가짜 서버는 refresh·/users/me 만 답한다.
 * 그린워싱 경로는 가드 뒤에 있다 — 이 준비로 지금까지의 단언을 그대로 둔다.
 * kind 로 운영 관리자(admin)로도 복원한다(밴드 SV1 — refresh·/users/me 둘 다 그 kind).
 */
const signedInAs = (kind: 'service' | 'admin') => ({
  baseUrl: 'http://test.local/api',
  storage: {
    getItem: () => 'refresh-test',
    setItem: () => {},
    removeItem: () => {},
  },
  send: async (request: Request) => {
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
});
const SIGNED_IN = signedInAs('service');

// 지연 로드 화면(lazyRouteComponent)을 미리 불러 둔다 — 부하 아래 첫 waitFor 가 모듈 로드를 기다리지 않게(예열, sid:MARC-ISSUE-318).
// 경로 파일을 직접 가져오지 않고(칸 규칙) 버리는 라우터 하나의 경로 조각을 모두 싣는다. 모듈은 한 번 실리면 다음 라우터도 바로 쓴다.
beforeAll(async () => {
  const router = createAppRouter({
    history: createMemoryHistory(),
    openPdf: neverOpen,
    createStore: () => createMockStore(),
    demos: true,
    session: SIGNED_IN,
  });
  await Promise.all(
    Object.values(router.routesById).map((route) =>
      router.loadRouteChunk(route),
    ),
  );
}, 60_000);

/** 저장소의 쓰기 넷. */
const WRITES = ['createDocument', 'createRun', 'rerun', 'putReview'] as const;

/** 라우터 하나. 그리지 않으면(draw: false) load 만 한다. kind 는 복원되는 세션의 사람(기본 고객사 사용자). */
async function setup(
  path: string,
  {
    demos = true,
    draw = true,
    kind = 'service',
  }: { demos?: boolean; draw?: boolean; kind?: 'service' | 'admin' } = {},
) {
  const history = createMemoryHistory({ initialEntries: [path] });
  const controls: MockStoreControl[] = [];
  const router = createAppRouter({
    history,
    openPdf: neverOpen,
    createStore: (search) => {
      const control = createMockStore({
        scenario: MOCK_SCENARIOS.find((value) => value === search.mock),
      });
      // 쓰기 넷을 지켜본다(안쪽 저장소에 닿은 쓰기 호출을 센다 — 밴드 SV1).
      for (const name of WRITES) vi.spyOn(control.store, name);
      controls.push(control);
      return control;
    },
    demos,
    session: kind === 'service' ? SIGNED_IN : signedInAs(kind),
  });
  // 이동을 센다(경로 컴포넌트의 useNavigate 는 router.navigate 를 부른다).
  const navigate = vi.spyOn(router, 'navigate');
  // main.tsx 와 같이 StrictMode 로 그린다(05b 표식은 두 번 렌더에도 남아야 한다).
  if (draw)
    render(
      <StrictMode>
        <RouterProvider router={router} />
      </StrictMode>,
    );
  else await act(() => router.load());
  return { router, history, controls, navigate };
}

const pathOf = (history: { location: { pathname: string } }) =>
  history.location.pathname;
const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );

describe('경로 표 ① 주소마다 그 화면', () => {
  it.each([
    ['/greenwash', 'list'],
    ['/greenwash/intro', 'intro'],
    ['/greenwash/new', 'new'],
    ['/greenwash/runs/run-1?mock=running', 'status'],
    ['/greenwash/runs/run-101/result', 'result'],
    ['/greenwash/runs/run-101/review', 'review'],
  ])('%s → %s', async (path, name) => {
    const { history } = await setup(path);
    await screenShown(name);
    expect(history.location.href).toBe(path);
    // data-run-id 는 실행을 보는 화면에서만
    const root = document.querySelector('.twp')!;
    expect(root.getAttribute('data-run-id')).toBe(
      /\/runs\/([^/?]+)/.exec(path)?.[1] ?? null,
    );
  });

  it.each(['/dev/viewer', '/dev/table', '/dev/api', '/dev/parts'])(
    '%s 는 데모 경로(demos 참)',
    async (path) => {
      const { router } = await setup(path, { draw: false });
      expect(router.state.location.pathname).toBe(path);
      expect(router.state.matches.at(-1)?.routeId).toBe(path);
    },
  );
});

describe('경로 표 ② 모르는 주소 → /greenwash(replace)', () => {
  it.each(['/', '/zzz', '/greenwash/xyz', '/greenwash/runs/x/zzz'])(
    '%s',
    async (path) => {
      const { history } = await setup(path);
      await screenShown('list');
      expect(pathOf(history)).toBe('/greenwash');
      expect(history.length).toBe(1);
    },
  );
});

describe('경로 표 ③ 옛 주소(?view=·?screen=·?run=)는 넘기지 않는다 — / 의 넘기기대로 목록, search 는 버린다', () => {
  it.each([
    '/?view=greenwash&screen=result&run=r1',
    '/?view=greenwash&screen=status&mock=failed',
    '/?screen=intro',
    '/?view=viewer&data=sample/compare.json',
  ])('%s → /greenwash', async (path) => {
    const { history } = await setup(path, { draw: false });
    await waitFor(() => expect(pathOf(history)).toBe('/greenwash'), WAIT);
    expect(history.location.search).toBe('');
    expect(history.length).toBe(1);
  });

  it('search 검사: 아는 키의 아는 값만, mock 글자 목록 = MOCK_SCENARIOS', () => {
    expect([...MOCK_SEARCH_VALUES]).toEqual([...MOCK_SCENARIOS]);
    expect(
      validateGreenwashSearch({
        mock: 'done',
        demo: '1',
        autofinish: '1',
        other: 'x',
      }),
    ).toEqual({ mock: 'done', demo: '1', autofinish: '1' });
    expect(
      validateGreenwashSearch({ mock: 'nope', demo: '2', autofinish: 1 }),
    ).toEqual({});
  });
});

const words = GW_TEXT.newCheck;

describe('경로 표 ④ push / replace', () => {
  it('목록 → [새 점검](push) → 시작(replace) → 끝남(replace) → 뒤로 = 목록', async () => {
    const { history, controls } = await setup('/greenwash');
    await screenShown('list');
    expect(history.length).toBe(1);
    fireEvent.click(
      screen.getByRole('button', { name: GW_TEXT.list.newCheck }),
    );
    await screenShown('new');
    expect(pathOf(history)).toBe('/greenwash/new');
    expect(history.length).toBe(2);

    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], '목-보고서-60쪽.pdf', {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    await screen.findByTestId('file-meta', {}, WAIT);
    const ceo = screen.getByLabelText(words.parts.names.ceo, {
      selector: 'input',
    });
    fireEvent.change(ceo, { target: { value: '2' } });
    fireEvent.blur(ceo);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    await screenShown('status');
    expect(pathOf(history)).toBe('/greenwash/runs/run-1');
    expect(history.length).toBe(2);

    await act(async () => controls[0]!.finish('run-1'));
    // 끝나도 저절로 넘기지 않는다: [결과 보기]를 누르면 replace 로 GW-04(디자인 대조 C8)
    const viewResult = await screen.findByRole(
      'button',
      { name: GW_TEXT.status.viewResult },
      WAIT,
    );
    expect(pathOf(history)).toBe('/greenwash/runs/run-1');
    fireEvent.click(viewResult);
    await screenShown('result');
    expect(pathOf(history)).toBe('/greenwash/runs/run-1/result');
    expect(history.length).toBe(2);

    await act(async () => history.back());
    await screenShown('list');
    expect(pathOf(history)).toBe('/greenwash');
  });

  it('결과(GW-04)에서 시작 → [검토 이어 하기](push) → 메뉴 「그린워싱 점검」(push)', async () => {
    const { history } = await setup('/greenwash/runs/run-101/result');
    await screenShown('result');
    expect(history.length).toBe(1);
    fireEvent.click(
      screen.getByRole('button', { name: GW_TEXT.result.continueReview }),
    );
    await screenShown('review');
    expect(pathOf(history)).toBe('/greenwash/runs/run-101/review');
    expect(history.length).toBe(2);
    fireEvent.click(
      screen.getByRole('button', { name: GW_TEXT.shell.menu.greenwash }),
    );
    await screenShown('list');
    expect(history.length).toBe(3);
  });
});

describe('경로 표 ④-2 끝난 GW-03 은 저절로 넘기지 않는다, [결과 보기]는 replace 한 번(디자인 대조 C8)', () => {
  it('끝난 실행의 GW-03 을 열면 navigate 0(다시 그려져도), [결과 보기]를 누르면 결과로 replace 한 번', async () => {
    const { history, navigate, router } = await setup(
      '/greenwash/runs/run-1?mock=done',
    );
    await screenShown('status');
    const viewResult = await screen.findByRole(
      'button',
      { name: GW_TEXT.status.viewResult },
      WAIT,
    );
    const toResult = () =>
      navigate.mock.calls.filter(
        ([options]) =>
          (options as { to?: string }).to === '/greenwash/runs/$runId/result',
      );
    // 경로 컴포넌트를 몇 번 더 그려도 결과로 가지 않는다(옛 자동 이동 effect 가 없다)
    for (let i = 0; i < 3; i++) {
      act(() => void router.invalidate());
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 30));
      });
    }
    expect(document.querySelector('[data-screen="status"]')).not.toBeNull();
    expect(toResult()).toHaveLength(0);
    expect(pathOf(history)).toBe('/greenwash/runs/run-1');
    fireEvent.click(viewResult);
    await screenShown('result');
    expect(toResult()).toHaveLength(1);
    expect((toResult()[0]![0] as { replace?: boolean }).replace).toBe(true);
    expect(pathOf(history)).toBe('/greenwash/runs/run-1/result');
    expect(history.length).toBe(1);
  });
});

describe('경로 표 ⑤ [확정] 표식은 한 번만', () => {
  it('GW-04 [확정] → 05b 뜸 → 목록 → 같은 실행 검토를 다시 열면 05b 없음', async () => {
    const { router, history } = await setup('/greenwash/runs/run-101/result');
    await screenShown('result');
    fireEvent.click(
      screen.getByRole('button', { name: GW_TEXT.result.confirm }),
    );
    await screenShown('review');
    expect(pathOf(history)).toBe('/greenwash/runs/run-101/review');
    // 주소·search·history.state 에 싣지 않는다
    expect(history.location.search).toBe('');
    expect(JSON.stringify(history.location.state)).not.toContain('confirm');
    await screen.findByRole('dialog', { name: GW_TEXT.confirm.title }, WAIT);

    // 표식은 GW-05 가 그려질 때 이미 지워졌다 — 표식을 지우지 않는 router.navigate 로 돌아와도 05b 는 없다.
    // (router.navigate 의 약속은 act 안에서 기다리지 않는다: 모달이 열린 채로는 끝나지 않는다.)
    act(() => void router.navigate({ to: '/greenwash' }));
    await screenShown('list');
    act(
      () =>
        void router.navigate({
          to: '/greenwash/runs/$runId/review',
          params: { runId: 'run-101' },
        }),
    );
    await screenShown('review');
    await waitFor(
      () => expect(screen.getByTestId('review-state')).toBeTruthy(),
      WAIT,
    );
    expect(
      screen.queryByRole('dialog', { name: GW_TEXT.confirm.title }),
    ).toBeNull();
  });
});

describe('경로 표 ⑤-2 다른 이동은 [확정] 표식을 지운다', () => {
  it('표식을 세운 뒤 목록에서 [새 점검]으로 가면 표식은 null', async () => {
    const { router } = await setup('/greenwash');
    await screenShown('list');
    const runtime = router.options.context.greenwash;
    runtime.confirmRunId = 'run-101';
    fireEvent.click(
      screen.getByRole('button', { name: GW_TEXT.list.newCheck }),
    );
    await screenShown('new');
    expect(runtime.confirmRunId).toBeNull();
  });
});

describe('경로 표 ⑥ DEMOS 거짓', () => {
  it.each(['/dev/viewer', '/dev/table', '/dev/api', '/dev/parts'])(
    '%s → /greenwash',
    async (path) => {
      const { history } = await setup(path, { demos: false, draw: false });
      await waitFor(() => expect(pathOf(history)).toBe('/greenwash'), WAIT);
    },
  );
});

describe('경로 표 ⑦ 운영 관리자도 고객사 사용자와 같이 쓴다(밴드 GR3, sid:MARC-ENT-374 3·4번·sid:MARC-ENT-409)', () => {
  type Snapshot = Parameters<typeof greenwashAccess>[0];
  const signedInState = (kind: 'service' | 'admin'): Snapshot => ({
    status: 'signedIn',
    user: {
      id: 1,
      username: 'u',
      name: '지어낸-사람',
      kind,
      companyId: kind === 'admin' ? null : 1,
      isInitial: false,
    },
  });

  /** 메서드마다 vi.fn 인 가짜 저장소(읽기는 정해진 값을 돌려준다). */
  function fakeStore() {
    const unsubscribe = vi.fn();
    const store = {
      createDocument: vi.fn(async () => ({
        documentId: 'd',
        pageCount: 1,
        hasText: true,
      })),
      createRun: vi.fn(async () => ({ runId: 'r' })),
      rerun: vi.fn(async () => ({ runId: 'r' })),
      putReview: vi.fn(async () => ({})),
      getRun: vi.fn(async () => ({ runId: 'run-x' })),
      subscribeRun: vi.fn(() => unsubscribe),
      listDocuments: vi.fn(async () => [{ documentId: 'd-1' }]),
      listDefaultTerms: vi.fn(async () => ['친환경']),
      getDocument: vi.fn(async () => ({ documentId: 'd-2' })),
      listCheckRows: vi.fn(async () => ({ rows: 'x' })),
      getResult: vi.fn(async () => ({ result: 1 })),
      getReview: vi.fn(async () => ({ review: 1 })),
      openDocumentPdf: vi.fn(async () => null),
    };
    return { store, unsubscribe };
  }
  const listRowsReady = () =>
    waitFor(
      () =>
        expect(
          document.querySelectorAll('[data-testid="row-status"]').length,
        ).toBeGreaterThan(0),
      WAIT,
    );

  it('greenwashAccess: 운영 관리자 → canWrite 참, 쓰기 넷은 안쪽 저장소로 그대로 간다(거절 0)', async () => {
    const { store } = fakeStore();
    const access = greenwashAccess(
      signedInState('admin'),
      store as unknown as GreenwashStore,
    );
    expect(access.canWrite).toBe(true);
    await expect(
      access.store.createDocument(new File(['x'], 'a.pdf')),
    ).resolves.toEqual({ documentId: 'd', pageCount: 1, hasText: true });
    await expect(
      access.store.createRun('d', {
        parts: {} as never,
        extraTerms: [],
        reportYear: null,
        previousDocumentId: null,
      }),
    ).resolves.toEqual({ runId: 'r' });
    await expect(access.store.rerun('run-1')).resolves.toEqual({
      runId: 'r',
    });
    await expect(access.store.putReview('run-1', {} as never)).resolves.toEqual(
      {},
    );
    for (const name of WRITES) expect(store[name], name).toHaveBeenCalledOnce();
  });

  it('greenwashAccess: 운영 관리자의 저장소는 안쪽 저장소 그 자체(읽기·구독 인자 그대로 — 넷째 onFailed 포함)', () => {
    const { store, unsubscribe } = fakeStore();
    const raw = store as unknown as GreenwashStore;
    const read = greenwashAccess(signedInState('admin'), raw).store;
    expect(read).toBe(raw);
    const listener = () => {};
    const onMissing = () => {};
    const onFailed = () => {};
    const off = read.subscribeRun('run-7', listener, onMissing, onFailed);
    expect(store.subscribeRun).toHaveBeenCalledWith(
      'run-7',
      listener,
      onMissing,
      onFailed,
    );
    off();
    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });

  it('greenwashAccess: 고객사 사용자 → canWrite 참, 같은 저장소. 로그인하지 않은 상태는 canWrite 거짓(저장소는 그대로 — 서버가 401)', () => {
    const { store } = fakeStore();
    const raw = store as unknown as GreenwashStore;
    expect(greenwashAccess(signedInState('service'), raw)).toEqual({
      canWrite: true,
      store: raw,
    });
    expect(greenwashAccess({ status: 'signedOut', notice: null }, raw)).toEqual(
      { canWrite: false, store: raw },
    );
  });

  it('운영 관리자 목록 실패 줄 [다시 실행] → 안쪽 저장소 rerun 한 번, 새 실행의 GW-03(push)', async () => {
    const { history, controls } = await setup('/greenwash', { kind: 'admin' });
    await screenShown('list');
    await listRowsReady();
    const rerun = document.querySelector<HTMLElement>('[data-next="rerun"]')!;
    expect(rerun).not.toBeNull();
    await act(async () => {
      fireEvent.click(rerun);
    });
    await waitFor(
      () => expect(pathOf(history)).toMatch(/^\/greenwash\/runs\/[^/]+$/),
      WAIT,
    );
    await screenShown('status');
    expect(controls[0]!.store.rerun).toHaveBeenCalledOnce();
    expect(history.length).toBe(2);
  });

  it('경로 컴포넌트는 화면에 control.store 를 넘기지 않는다 — 저장소는 useGreenwash 의 greenwashAccess 결과 하나(글자로 본다)', () => {
    const source = readFileSync(
      // jsdom 환경이라 import.meta.url 이 file: 이 아니다 — vitest 의 cwd(apps/web) 기준.
      resolve(process.cwd(), 'src/app/greenwash/GreenwashRoutes.tsx'),
      'utf8',
    );
    expect(source.match(/control\.store/g)).toHaveLength(1);
    expect(source).toMatch(/greenwashAccess\(state, control\.store\)/);
    expect(source.match(/\bstore=\{/g)).toHaveLength(5);
    expect(source.match(/\bstore=\{store\}/g)).toHaveLength(5);
    expect(source.match(/canWrite=\{canWrite\}/g)).toHaveLength(5);
    // 운영 관리자 갈래는 목록의 operator 하나(쓰기 갈래 아님 — sid:MARC-ENT-409 남김)
    expect(source.match(/operator=\{operator\}/g)).toHaveLength(1);
    expect(source).not.toMatch(/readOnlyStore|kind === 'service'/);
  });

  const writesOf = (controls: MockStoreControl[]) =>
    WRITES.map(
      (name) =>
        (controls[0]!.store[name] as ReturnType<typeof vi.fn>).mock.calls,
    ).flat().length;
  const button = (name: string) => screen.queryByRole('button', { name });

  it('GW_TEXT 글: 운영 관리자 인사말·[관리자 화면] — 그린워싱 머리에 그대로(고객사엔 없음)', async () => {
    expect(GW_TEXT.shell.adminGreeting).toBe('운영 관리자님 안녕하세요');
    expect(GW_TEXT.shell.toAdmin).toBe('관리자 화면');
    await setup('/greenwash', { kind: 'admin' });
    await screenShown('list');
    expect(screen.getByText(GW_TEXT.shell.adminGreeting)).toBeTruthy();
    expect(button(GW_TEXT.shell.toAdmin)).not.toBeNull();
    cleanup();
    await setup('/greenwash');
    await screenShown('list');
    expect(screen.getByText(GW_TEXT.shell.greeting)).toBeTruthy();
    expect(button(GW_TEXT.shell.toAdmin)).toBeNull();
  });

  it.each(['service', 'admin'] as const)(
    'GW-01 목록(%s): [새 점검]·줄의 [다시 실행]은 둘 다 있다. 그리기만으로는 저장소 쓰기 0',
    async (kind) => {
      const { controls } = await setup('/greenwash', { kind });
      await screenShown('list');
      await listRowsReady();
      expect(button(GW_TEXT.list.newCheck)).not.toBeNull();
      expect(
        document.querySelectorAll('[data-next="rerun"]').length,
      ).toBeGreaterThan(0);
      expect(
        document.querySelectorAll('[data-next]:not([data-next="rerun"])')
          .length,
      ).toBeGreaterThan(0);
      expect(writesOf(controls)).toBe(0);
    },
  );

  it.each(['service', 'admin'] as const)(
    'GW-00 소개(%s): [시작하기]는 둘 다 있고, 누르면 문서 목록 /greenwash(새 점검이 아니다 — 시안 댓글, sid:MARC-ENT-603)',
    async (kind) => {
      const { history } = await setup('/greenwash/intro', { kind });
      await screenShown('intro');
      const start = button(GW_TEXT.intro.start);
      expect(start).not.toBeNull();
      fireEvent.click(start!);
      await screenShown('list');
      expect(pathOf(history)).toBe('/greenwash');
    },
  );

  it.each(['service', 'admin'] as const)(
    'GW-03 실패한 실행(%s): [다시 실행]·[목록으로] 둘 다 있다',
    async (kind) => {
      const { controls } = await setup('/greenwash/runs/run-1?mock=failed', {
        kind,
      });
      await screen.findByTestId('failure', {}, WAIT);
      expect(button(GW_TEXT.status.rerun)).not.toBeNull();
      expect(
        screen.getAllByRole('button', { name: GW_TEXT.status.back }).length,
      ).toBeGreaterThan(0);
      expect(writesOf(controls)).toBe(0);
    },
  );

  it.each(['service', 'admin'] as const)(
    'GW-04 결과(%s): [확정]과 주 단추 [검토 이어 하기]가 둘 다 같다(sid:MARC-ENT-409 J1b — 「결과 보기」 갈래 걷음)',
    async (kind) => {
      const { controls } = await setup('/greenwash/runs/run-101/result', {
        kind,
      });
      await screen.findByRole(
        'button',
        { name: GW_TEXT.result.continueReview },
        WAIT,
      );
      expect(button(GW_TEXT.result.confirm)).not.toBeNull();
      expect(button(GW_TEXT.result.viewResult)).toBeNull();
      expect(writesOf(controls)).toBe(0);
    },
  );

  it.each(['service', 'admin'] as const)(
    'GW-05 검토(%s): 머리 [확정]·상세의 채택·제외·표시(ReviewMark)가 둘 다 있다',
    async (kind) => {
      const { controls } = await setup('/greenwash/runs/run-101/review', {
        kind,
      });
      await screen.findByTestId('review-row', {}, WAIT);
      expect(button(GW_TEXT.reviewScreen.confirm)).not.toBeNull();
      expect(button(GW_TEXT.review.adopted)).not.toBeNull();
      expect(button(GW_TEXT.review.excluded)).not.toBeNull();
      expect(screen.getByTestId('review-state')).toBeTruthy();
      expect(writesOf(controls)).toBe(0);
    },
  );

  it.each(['service', 'admin'] as const)(
    '[확정] 표식(run-101)을 세우고 GW-05 로(%s): 05b(확정 확인)가 둘 다 열린다',
    async (kind) => {
      const { router } = await setup('/greenwash/runs/run-101/result', {
        kind,
      });
      await screenShown('result');
      router.options.context.greenwash.confirmRunId = 'run-101';
      void router.navigate({
        to: '/greenwash/runs/$runId/review',
        params: { runId: 'run-101' },
      });
      await screen.findByTestId('review-row', {}, WAIT);
      expect(screen.queryByRole('dialog')).not.toBeNull();
    },
  );

  const REVIEW_NEXT = '[data-next="review"],[data-next="continue_review"]';
  /** 다음 할 일 칸(줄마다 마지막 칸). */
  const nextCellOf = (status: string) =>
    [
      ...document.querySelectorAll(
        `[data-testid="row-status"][data-status="${status}"]`,
      ),
    ].map((badge) => badge.closest('tr')!.lastElementChild as HTMLElement);

  it.each(['service', 'admin'] as const)(
    'GW-01 목록(%s) GW-01b 꼴(sid:MARC-ENT-409): 운영 관리자만 「내가 올린 것만」 없음·meta 「작업 회사 …」. 줄 다음 할 일·실패 줄 [다시 실행]·안내 글은 고객사와 같다',
    async (kind) => {
      const { controls } = await setup('/greenwash', { kind });
      await screenShown('list');
      await listRowsReady();
      const operator = kind === 'admin';
      // 「내가 올린 것만」 라벨·체크박스(J1a 남김)
      expect(screen.queryByText(GW_TEXT.list.mineOnly) !== null).toBe(
        !operator,
      );
      expect(
        screen.queryAllByRole('checkbox', { name: GW_TEXT.list.mineOnly }),
      ).toHaveLength(operator ? 0 : 1);
      // 검토하기·검토 이어 하기(J1b 걷음 — 둘 다 있다)
      expect(document.querySelectorAll(REVIEW_NEXT).length).toBeGreaterThan(1);
      const texts = [...document.querySelectorAll('[data-next]')].map(
        (node) => node.textContent,
      );
      expect(texts).toContain(GW_TEXT.list.next.review);
      expect(texts).toContain(GW_TEXT.list.next.continue_review);
      // 검토 대기·검토 중 줄의 단추는 글·data-next 가 함께 검토하기·검토 이어 하기
      const reviewCells = [
        ...nextCellOf('pending'),
        ...nextCellOf('in_review'),
      ];
      expect(nextCellOf('pending').length).toBeGreaterThan(0);
      expect(nextCellOf('in_review').length).toBeGreaterThan(0);
      for (const cell of reviewCells) {
        const node = cell.querySelector('[data-next]')!;
        expect(node.getAttribute('data-next')).not.toBe('view_result');
        expect(node.textContent).not.toBe(GW_TEXT.list.next.view_result);
      }
      // 실패 줄 다음 할 일 칸: 둘 다 [다시 실행](J1c 걷음)
      const failedCells = nextCellOf('failed');
      expect(failedCells.length).toBeGreaterThan(0);
      for (const cell of failedCells)
        expect(cell.querySelector('[data-next="rerun"]')).not.toBeNull();
      // 목록 아래 안내: 둘 다 고객사 글(J1d 걷음)
      const notice = screen.getByTestId('list-notice');
      expect(notice.textContent).toBe(GW_TEXT.list.notice);
      expect(notice.querySelector('svg')).not.toBeNull();
      expect('noticeReadOnly' in GW_TEXT.list).toBe(false);
      // 제목 줄 meta: 운영 관리자만 「작업 회사 …」(checks 의 companyName), 고객사 사용자는 설명 줄이 없다(시안 댓글 — sid:MARC-ENT-603)
      expect(GW_TEXT.list.metaOperator('목-회사')).toBe('작업 회사 목-회사');
      expect('meta' in GW_TEXT.list).toBe(false);
      expect(writesOf(controls)).toBe(0);
    },
  );

  it('GW_TEXT 글: 운영 관리자 meta 는 작업 회사 조각만(셈·안내 조각 지움), 고객사 meta 는 없다(시안 댓글 — sid:MARC-ENT-603)', () => {
    expect(GW_TEXT.list.metaOperator('가-회사')).toBe('작업 회사 가-회사');
    expect(GW_TEXT.list.metaOperator('가-회사')).not.toMatch(/문서|실행|계정/);
    expect('meta' in GW_TEXT.list).toBe(false);
  });

  it('운영 관리자가 줄의 「검토하기」(검토 대기 줄)를 누르면 /greenwash/runs/<id>/review, 저장소 쓰기 0', async () => {
    const { history, controls } = await setup('/greenwash', { kind: 'admin' });
    await screenShown('list');
    await listRowsReady();
    const target =
      nextCellOf('pending')[0]!.querySelector<HTMLElement>('[data-next]')!;
    expect(target.getAttribute('data-next')).toBe('review');
    expect(target.textContent).toBe(GW_TEXT.list.next.review);
    fireEvent.click(target);
    await waitFor(
      () =>
        expect(pathOf(history)).toMatch(/^\/greenwash\/runs\/[^/]+\/review$/),
      WAIT,
    );
    await screenShown('review');
    expect(writesOf(controls)).toBe(0);
  });

  it.each(['service', 'admin'] as const)(
    'GW-03 실패 안내(%s): 둘 다 고객사 글 「…[다시 실행]을 누르면…」(sid:MARC-ENT-409 C1 — 운영 관리자 글 갈래 걷음)',
    async (kind) => {
      await setup('/greenwash/runs/run-1?mock=failed', { kind });
      const info = await screen.findByTestId('failure-info', {}, WAIT);
      expect(info.textContent).toBe(GW_TEXT.status.failure);
      // v115 GW-03 r3 글 「…[다시 실행]을 누르면 같은 파일로…」(밴드 GW2R ②)
      expect(info.textContent).toContain('[다시 실행]을 누르면');
      expect('failureReadOnly' in GW_TEXT.status).toBe(false);
      // 덧글(failureNote)은 없다(디자인 답 D4 — 밴드 GW2R ②)
      expect(screen.queryByTestId('failure-note')).toBeNull();
    },
  );

  it('운영 관리자: 목록 → [새 점검](push) → 시작(replace) → GW-03, 안쪽 저장소 createDocument·createRun 한 번씩', async () => {
    const { history, controls } = await setup('/greenwash', { kind: 'admin' });
    await screenShown('list');
    fireEvent.click(
      screen.getByRole('button', { name: GW_TEXT.list.newCheck }),
    );
    await screenShown('new');
    expect(pathOf(history)).toBe('/greenwash/new');
    expect(history.length).toBe(2);
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], '목-보고서-60쪽.pdf', {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    await screen.findByTestId('file-meta', {}, WAIT);
    const ceo = screen.getByLabelText(words.parts.names.ceo, {
      selector: 'input',
    });
    fireEvent.change(ceo, { target: { value: '2' } });
    fireEvent.blur(ceo);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    await screenShown('status');
    expect(pathOf(history)).toBe('/greenwash/runs/run-1');
    expect(history.length).toBe(2);
    expect(controls[0]!.store.createDocument).toHaveBeenCalledOnce();
    expect(controls[0]!.store.createRun).toHaveBeenCalledOnce();
  });

  it.each(['service', 'admin'] as const)(
    '/greenwash/new 를 주소로 열면(%s) 그대로 새 점검 화면',
    async (kind) => {
      const { history } = await setup('/greenwash/new', { kind });
      await screenShown('new');
      expect(pathOf(history)).toBe('/greenwash/new');
    },
  );
});

describe('경로 표 ⑧ 화면이 받은 저장소(밴드 SV1 ② 검증 B1 — 처리기 연결을 행동으로, 밴드 GR3 에서 운영 관리자도 원 저장소)', () => {
  const SCREENS = [
    ['/greenwash', 'list', 'list'],
    ['/greenwash/runs/run-1?mock=failed', 'status', 'status'],
    ['/greenwash/runs/run-101/result', 'result', 'result'],
    ['/greenwash/runs/run-101/review', 'review', 'review'],
    ['/greenwash/new', 'new', 'new'],
  ] as const;

  it.each(SCREENS)(
    '운영 관리자 %s: 화면(%s)이 받은 저장소는 원 저장소 그대로(쓰기가 안쪽에 닿는다)',
    async (path, screenName, key) => {
      const { controls } = await setup(path, { kind: 'admin' });
      await screenShown(screenName);
      expect(captured.stores.get(key)).toBe(controls[0]!.store);
    },
  );

  it.each(SCREENS)(
    '고객사 사용자 %s: 화면(%s)이 받은 저장소는 원 저장소 그대로',
    async (path, screenName, key) => {
      const { controls } = await setup(path);
      await screenShown(screenName);
      expect(captured.stores.get(key)).toBe(controls[0]!.store);
    },
  );

  it.each(SCREENS.slice(0, 4))(
    '운영 관리자 %s: 화면(%s)이 받은 canWrite 는 참(sid:MARC-ENT-409 — 갈래가 화면까지 닿는다)',
    async (path, screenName, key) => {
      await setup(path, { kind: 'admin' });
      await screenShown(screenName);
      expect(captured.canWrite.has(key)).toBe(true);
      expect(captured.canWrite.get(key)).toBe(true);
    },
  );

  it.each(SCREENS.slice(0, 4))(
    '고객사 사용자 %s: 화면(%s)이 받은 canWrite 는 참',
    async (path, screenName, key) => {
      await setup(path);
      await screenShown(screenName);
      expect(captured.canWrite.get(key)).toBe(true);
    },
  );
});

/**
 * 기본 저장소로 라우터 하나(createStore 없음 — 밴드 GW1R ②). 세션의 통신 함수가 그린워싱 경로는 가짜 그린워싱 서버로, 나머지는 로그인 가짜로 보낸다.
 * demos 는 router context 의 admin.demos(데모 빌드인가). 같은 탭(sessionStorage)에서 다시 만들면 「새로고침」이다.
 */
function setupDefault(
  path: string,
  {
    demos = true,
    kind = 'service',
    greenwash = listedGreenwashServer(),
  }: {
    demos?: boolean;
    kind?: 'service' | 'admin';
    greenwash?: ReturnType<typeof listedGreenwashServer>;
  } = {},
) {
  const session = kind === 'service' ? SIGNED_IN : signedInAs(kind);
  const history = createMemoryHistory({ initialEntries: [path] });
  const router = createAppRouter({
    history,
    openPdf: neverOpen,
    demos,
    session: {
      ...session,
      send: (request: Request) =>
        greenwash.handles(request) ?
          greenwash.send(request)
        : session.send(request),
    },
  });
  // StrictMode 없이 그린다: 개발 모드의 effect 두 번 돌기가 읽기를 두 번 보내 「요청 한 번」을 흐린다(프로덕션 빌드는 한 번).
  render(<RouterProvider router={router} />);
  return { router, history, greenwash };
}

/** 목 씨앗 줄(목 저장소의 지어낸 이름은 「목-」으로 시작한다). */
const mockRowShown = () =>
  waitFor(
    () => expect(document.body.textContent).toContain('목-지속가능경영보고서'),
    WAIT,
  );
const serverRowShown = () =>
  waitFor(
    () => expect(document.body.textContent).toContain('지어낸 확정 보고서.pdf'),
    WAIT,
  );

describe('경로 표 ⑨ 기본 저장소 — 실어댑터, 목은 데모 빌드의 탭 표지 뒤로만(밴드 GW1R ② §3 D)', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => sessionStorage.clear());

  it('기본 /greenwash → GET /greenwash/checks 한 번, Authorization: Bearer(세션 Api), 목 씨앗 줄 없음', async () => {
    const { greenwash } = setupDefault('/greenwash');
    await serverRowShown();
    expect(greenwash.count('GET /greenwash/checks')).toBe(1);
    expect(greenwash.calls[0]!.headers.get('authorization')).toBe(
      'Bearer access-test',
    );
    expect(document.body.textContent).not.toContain('목-');
    expect(sessionStorage.getItem(MOCK_TAB_KEY)).toBeNull();
  });

  it('?store=mock → 그린워싱 요청 0(목), 표지가 남아 새로고침(같은 탭에서 라우터를 다시 만듦)·search 없는 주소도 목', async () => {
    const first = setupDefault('/greenwash?store=mock');
    await mockRowShown();
    expect(first.greenwash.calls).toEqual([]);
    expect(sessionStorage.getItem(MOCK_TAB_KEY)).toBe('mock');
    cleanup();
    const again = setupDefault('/greenwash');
    await mockRowShown();
    expect(again.greenwash.calls).toEqual([]);
  });

  it.each(['?mock=done', '?demo=1', '?autofinish=1'])(
    '옛 키 %s 도 데모 빌드에선 목 표지를 적는다',
    async (search) => {
      const { greenwash } = setupDefault(`/greenwash${search}`);
      await mockRowShown();
      expect(greenwash.calls).toEqual([]);
      expect(sessionStorage.getItem(MOCK_TAB_KEY)).toBe('mock');
    },
  );

  it.each([
    ['?store=mock', false],
    ['?mock=done', false],
    ['', true],
  ] as const)(
    'demos 거짓(프로덕션 빌드) + %s (표지 미리 있음: %s) → 실어댑터, 표지를 적지 않는다',
    async (search, flagged) => {
      if (flagged) sessionStorage.setItem(MOCK_TAB_KEY, 'mock');
      const { greenwash } = setupDefault(`/greenwash${search}`, {
        demos: false,
      });
      await serverRowShown();
      expect(greenwash.count('GET /greenwash/checks')).toBe(1);
      expect(sessionStorage.getItem(MOCK_TAB_KEY)).toBe(
        flagged ? 'mock' : null,
      );
    },
  );

  it('데모 띠(sid:MARC-ISSUE-227 ① — 밴드 GW2R ②): 목 탭(?store=mock)만 머리에 「데모 자료예요. …」, 실어댑터 탭·demos 거짓 빌드는 없다', async () => {
    setupDefault('/greenwash?store=mock');
    await mockRowShown();
    const notice = screen.getByTestId('gw-demo-notice');
    expect(notice.textContent).toBe(
      '데모 자료예요. 올리거나 확정해도 서버에 저장되지 않아요.',
    );
    expect(notice.className).toContain('bg-background-primary');
    cleanup();
    sessionStorage.clear();
    setupDefault('/greenwash');
    await serverRowShown();
    expect(screen.queryByTestId('gw-demo-notice')).toBeNull();
    cleanup();
    sessionStorage.setItem(MOCK_TAB_KEY, 'mock');
    setupDefault('/greenwash?store=mock', { demos: false });
    await serverRowShown();
    expect(screen.queryByTestId('gw-demo-notice')).toBeNull();
  });

  it.each([true, false])(
    '/greenwash/new (demos %s, 실어댑터): 보고연도 칸 있음·수정본 칸 없음(밴드 GW2R ③ Q8 — 모든 빌드)',
    async (demos) => {
      const { greenwash } = setupDefault('/greenwash/new', { demos });
      await screen.findByRole(
        'heading',
        { name: GW_TEXT.newCheck.title, level: 2 },
        WAIT,
      );
      expect(screen.getByLabelText(GW_TEXT.newCheck.year.label)).toBeTruthy();
      expect(screen.queryByText('수정본 연결')).toBeNull();
      expect(document.querySelector('input[type="radio"]')).toBeNull();
      // 이전 문서 목록(checks)을 읽지 않는다
      expect(greenwash.count('GET /greenwash/checks')).toBe(0);
    },
  );

  it('운영 관리자 GW-04 [내려받기] → 받기 모달 엑셀 줄(밴드 GDL1) → GET /greenwash/runs/5/report?confirmed=true(확정된 실행), Authorization: Bearer(세션 Api) — 읽기라 막지 않는다(밴드 GW2R ③)', async () => {
    const original = {
      create: URL.createObjectURL,
      revoke: URL.revokeObjectURL,
    };
    URL.createObjectURL = vi.fn(() => 'blob:지어낸');
    URL.revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {});
    const { greenwash } = setupDefault('/greenwash/runs/5/result', {
      kind: 'admin',
    });
    const opener = await screen.findByTestId('gw-downloads', {}, WAIT);
    await screen.findByRole(
      'button',
      { name: GW_TEXT.result.viewResult },
      WAIT,
    );
    fireEvent.click(opener);
    const excel = screen.getByTestId('gw-download-dialog-file-excel');
    expect(excel.textContent).toBe(GW_TEXT.downloads.excelConfirmed);
    await act(async () => {
      fireEvent.click(excel);
    });
    await waitFor(
      () => expect(greenwash.count('GET /greenwash/runs/5/report')).toBe(1),
      WAIT,
    );
    const call = greenwash.calls.find(
      (c) => c.path === '/greenwash/runs/5/report',
    )!;
    expect(call.query.toString()).toBe('confirmed=true');
    expect(call.headers.get('authorization')).toBe('Bearer access-test');
    await waitFor(() => expect(click).toHaveBeenCalledTimes(1), WAIT);
    click.mockRestore();
    // 바꾼 전역을 되돌린다(검증 권고 R7)
    URL.createObjectURL = original.create;
    URL.revokeObjectURL = original.revoke;
  });

  it('운영 관리자도 실어댑터(사용자 결정 Q9) — checks 401 이면 「문서 목록을 불러오지 못했어요」', async () => {
    const greenwash = listedGreenwashServer();
    greenwash.override['GET /greenwash/checks'] = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'COMPANY_REQUIRED',
            message: '지어낸',
            fields: null,
            legacyCode: 'company_required',
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      );
    setupDefault('/greenwash', { kind: 'admin', greenwash });
    const failure = await screen.findByTestId('load-failure', {}, WAIT);
    expect(failure.textContent).toContain(GW_TEXT.list.loadFailed);
    expect(greenwash.count('GET /greenwash/checks')).toBe(1);
  });

  it('[R4] 틀의 [로그아웃]은 저장소의 forget 을 부른다(이 탭에서 올린 File·쪽 수를 비움 — Q11)', async () => {
    const forget = vi.fn();
    const history = createMemoryHistory({ initialEntries: ['/greenwash'] });
    const router = createAppRouter({
      history,
      openPdf: neverOpen,
      session: SIGNED_IN,
      createStore: () => ({ ...createMockStore(), forget }),
    });
    render(<RouterProvider router={router} />);
    await screenShown('list');
    expect(forget).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    // ⑤ M3: 로그아웃도 세션 끝 구독이 비운다(revoke 뒤 signedOut 전이에서 — 로그아웃 단추가 직접 부르지 않는다)
    await waitFor(() => expect(forget).toHaveBeenCalledTimes(1), WAIT);
  });

  it('[⑤ M4] 데모 빌드의 목 탭 표지는 로그아웃(세션 끝)에 지운다', async () => {
    const history = createMemoryHistory({
      initialEntries: ['/greenwash?store=mock'],
    });
    const router = createAppRouter({
      history,
      openPdf: neverOpen,
      session: SIGNED_IN,
    });
    render(<RouterProvider router={router} />);
    await mockRowShown();
    expect(sessionStorage.getItem(MOCK_TAB_KEY)).toBe('mock');
    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    await waitFor(
      () => expect(sessionStorage.getItem(MOCK_TAB_KEY)).toBeNull(),
      WAIT,
    );
  });

  it('[⑤ M3] followSessionEnd: signedIn → signedOut(만료) 전이마다 한 번, 다른 바뀜에는 부르지 않는다', () => {
    let state: { status: string } = { status: 'signedIn' };
    const listeners = new Set<() => void>();
    const session = {
      getSnapshot: () => state,
      subscribe: (listener: () => void) => {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
    };
    const set = (next: { status: string }) => {
      state = next;
      listeners.forEach((listener) => listener());
    };
    const end = vi.fn();
    const off = followSessionEnd(session, end);
    set({ status: 'signedIn' });
    expect(end).not.toHaveBeenCalled();
    set({ status: 'signedOut' }); // 만료(refresh 실패)·사용 중지·로그아웃 모두 이 전이
    expect(end).toHaveBeenCalledTimes(1);
    set({ status: 'signedOut' });
    expect(end).toHaveBeenCalledTimes(1);
    set({ status: 'signedIn' });
    set({ status: 'restoring' });
    expect(end).toHaveBeenCalledTimes(2);
    off();
    set({ status: 'signedIn' });
    set({ status: 'signedOut' });
    expect(end).toHaveBeenCalledTimes(2);
  });

  it('[⑤ S1] sendUpload: 서명 주소에 쿠키·리퍼러·캐시 없이, Authorization 없이 PUT 한다. 2xx 가 아니면 거절', async () => {
    const fetch = vi
      .fn<(url: string, init: RequestInit) => Promise<Response>>()
      .mockResolvedValueOnce(new Response('', { status: 200 }))
      .mockResolvedValueOnce(new Response('', { status: 403 }));
    // fetch 만 갈아 끼운다(beforeAll 의 ResizeObserver 흉내는 그대로 — unstubAllGlobals 를 쓰지 않는다)
    const original = globalThis.fetch;
    globalThis.fetch = fetch as unknown as typeof globalThis.fetch;
    try {
      const file = new File([new Uint8Array(5)], '지어낸.pdf');
      await sendUpload('https://store.test/up/1?sig=x', 'PUT', file);
      expect(fetch).toHaveBeenCalledWith('https://store.test/up/1?sig=x', {
        method: 'PUT',
        body: file,
        credentials: 'omit',
        referrerPolicy: 'no-referrer',
        cache: 'no-store',
      });
      await expect(
        sendUpload('https://store.test/up/1?sig=x', 'PUT', file),
      ).rejects.toThrow();
    } finally {
      globalThis.fetch = original;
    }
  });

  it('sendUpload: 앞단 프록시의 413 은 StoreError too_large(크기 안내 갈래 — 밴드 GP1), 그 밖 실패는 too_large 가 아니다', async () => {
    const fetch = vi
      .fn<(url: string, init: RequestInit) => Promise<Response>>()
      .mockResolvedValueOnce(new Response('', { status: 413 }))
      .mockResolvedValueOnce(new Response('', { status: 500 }));
    const original = globalThis.fetch;
    globalThis.fetch = fetch as unknown as typeof globalThis.fetch;
    try {
      const file = new File([new Uint8Array(5)], '지어낸.pdf');
      const kindOf = (promise: Promise<void>) =>
        promise.then(
          () => 'ok',
          (error: unknown) => storeErrorKind(error),
        );
      expect(
        await kindOf(sendUpload('https://store.test/up/1?sig=x', 'PUT', file)),
      ).toBe('too_large');
      expect(
        await kindOf(sendUpload('https://store.test/up/1?sig=x', 'PUT', file)),
      ).toBe('rejected');
    } finally {
      globalThis.fetch = original;
    }
  });
});
