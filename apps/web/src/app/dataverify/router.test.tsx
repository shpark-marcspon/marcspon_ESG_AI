// @vitest-environment jsdom
// 데이터 검증 경로 표 시험(밴드 DV2a ② — 발주서 §3-2 8, 영문번역 app/translation/router.test.tsx 꼴). createAppRouter 에 메모리 기록·
//   가짜 데이터 검증 서버를 앞에 둔 실어댑터를 넣는다.
//   ① 두 종류 사용자: /dataverify·/dataverify/intro → DV-00 · /dataverify/new → DV-02 · /dataverify/zzz → 첫 화면
//   ② 메뉴: 「데이터 검증」 → /dataverify, 「그린워싱 점검」·「영문번역」 → 그 경로, 그린워싱·영문번역 틀에서도 「데이터 검증」이 켜져 있다
//   ③ [시작하기] → DV-02 · 세션 끝(로그아웃)에 저장소가 쥔 열쇠를 버린다(forget).
//   ④ (경계 ③) /dataverify/runs/$runId → DV-03 · …/result → DV-04 · [검증 시작] → DV-03(replace) · [결과 보기]·[다시 실행] push ·
//      아직 끝나지 않은 실행의 결과 주소 → DV-03(replace).
//   ⑤ (DV2b) /dataverify: 실행이 없으면 DV-00(주소 그대로 — QB5 (가)), 있으면 목록(운영 관리자도) · 「검증 안내」 → /dataverify/intro ·
//      [결과 보기] → DV-04 · [진행 보기] → DV-03 · [새 검증] → DV-02.
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

import {
  fakeDataverifyServer,
  fakeRun,
  fakeSteps,
  serverStoreOf,
} from '../../entities/dataverify/api/testing.ts';
import type {
  AdvanceInput,
  FakeRun,
} from '../../entities/dataverify/api/testing.ts';
import { DV_TEXT } from '../../entities/dataverify/config/text.ts';
import { createAppRouter } from '../router.tsx';
import { followSessionEnd } from './DataverifyRoutes.tsx';

afterEach(cleanup);
// 경로 컴포넌트는 게으르게 불린다. 전량 시험이 같이 돌 때 첫 import 가 늦을 수 있어 기다림을 넓힌다(영문번역 경로 시험과 같다).
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

/** 고객사 사용자(service)·운영 관리자(admin)로 복원되는 세션(영문번역 경로 시험의 signedInAs 꼴). */
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

// 지연 로드 화면(lazyRouteComponent)을 미리 불러 둔다 — 부하 아래 첫 waitFor 가 모듈 로드를 기다리지 않게(예열, sid:MARC-ISSUE-318 —
// app/auth/router.test.tsx 꼴). ② 가 그린워싱·영문번역 틀로도 가므로 데이터 검증 것만이 아니라 버리는 라우터 하나의 경로 조각을 모두 싣는다.
beforeAll(async () => {
  const router = createAppRouter({
    history: createMemoryHistory(),
    createDataverifyStore: () => serverStoreOf(fakeDataverifyServer()),
    session: signedInAs('service'),
  });
  await Promise.all(
    Object.values(router.routesById).map((route) =>
      router.loadRouteChunk(route),
    ),
  );
}, 60_000);

function setup(
  path: string,
  kind: 'service' | 'admin' = 'service',
  forget?: () => void,
  runs: (FakeRun & { advance?: AdvanceInput })[] = [],
) {
  const history = createMemoryHistory({ initialEntries: [path] });
  const server = fakeDataverifyServer({ runs });
  // 끝난 실행은 가짜 서버가 결과(기본 지어낸 결과)·엑셀을 단다.
  for (const run of runs) if (run.advance) server.advance(run.id, run.advance);
  const router = createAppRouter({
    history,
    createDataverifyStore: () => {
      const store = serverStoreOf(server, { pollMs: 5 });
      return forget ? { ...store, forget } : store;
    },
    session: signedInAs(kind),
  });
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  return { router, history, server };
}

const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );
const menu = DV_TEXT.shell.menu;

describe('데이터 검증 경로 ① 주소마다', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /dataverify·/dataverify/intro 는 DV-00, /dataverify/new 는 DV-02 — 머문다',
    async (kind) => {
      for (const [path, name] of [
        ['/dataverify', 'dataverify-intro'],
        ['/dataverify/intro', 'dataverify-intro'],
        ['/dataverify/new', 'dataverify-new'],
      ] as const) {
        const { history } = setup(path, kind);
        await screenShown(name);
        expect(history.location.pathname).toBe(path);
        expect(
          screen.getByText(
            kind === 'admin' ?
              DV_TEXT.shell.adminGreeting
            : DV_TEXT.shell.greeting,
          ),
        ).toBeTruthy();
        // 지금 메뉴는 「데이터 검증」.
        const current = await waitFor(
          () => document.querySelector('[aria-current="page"]')!,
          WAIT,
        );
        expect(current.textContent).toContain(menu.validation);
        cleanup();
      }
    },
  );

  it.each([
    ['service', '/greenwash'],
    ['admin', '/admin/accounts'],
  ] as const)('%s: /dataverify/zzz 는 첫 화면(%s)으로', async (kind, home) => {
    const { history } = setup('/dataverify/zzz', kind);
    await waitFor(() => expect(history.location.pathname).toBe(home), WAIT);
  });
});

describe('데이터 검증 경로 ② 메뉴', () => {
  it('「데이터 검증」 → /dataverify, 「그린워싱 점검」 → /greenwash', async () => {
    const { history } = setup('/dataverify/new');
    await screenShown('dataverify-new');
    fireEvent.click(screen.getByRole('button', { name: menu.validation }));
    await waitFor(
      () => expect(history.location.pathname).toBe('/dataverify'),
      WAIT,
    );
    fireEvent.click(screen.getByRole('button', { name: menu.greenwash }));
    await waitFor(
      () => expect(history.location.pathname).toBe('/greenwash'),
      WAIT,
    );
  });

  it('「영문번역」 → /translation · 꺼진 하나는 가지 않는다', async () => {
    const { history } = setup('/dataverify/intro');
    await screenShown('dataverify-intro');
    const on = screen.getByRole('button', { name: menu.materiality });
    expect(on.getAttribute('aria-disabled')).toBeNull();
    expect(
      screen
        .getByRole('button', { name: menu.ghg })
        .getAttribute('aria-disabled'),
    ).toBeNull();
    for (const off of [menu.dashboard]) {
      const item = screen.getByRole('button', { name: off });
      expect(item.getAttribute('aria-disabled'), off).toBe('true');
      fireEvent.click(item);
    }
    expect(history.location.pathname).toBe('/dataverify/intro');
    fireEvent.click(screen.getByRole('button', { name: menu.translation }));
    await waitFor(
      () => expect(history.location.pathname).toBe('/translation'),
      WAIT,
    );
  });

  it.each(['/greenwash/intro', '/translation/new'])(
    '%s 틀의 「데이터 검증」이 켜져 있고 누르면 /dataverify',
    async (path) => {
      const { history } = setup(path);
      const item = await waitFor(
        () => screen.getByRole('button', { name: menu.validation }),
        WAIT,
      );
      expect(item.hasAttribute('disabled')).toBe(false);
      expect(item.getAttribute('aria-disabled')).not.toBe('true');
      fireEvent.click(item);
      await waitFor(
        () => expect(history.location.pathname).toBe('/dataverify'),
        WAIT,
      );
    },
  );
});

describe('데이터 검증 경로 ③ 이동·세션 끝', () => {
  it('DV-00 [시작하기] → /dataverify/new(push)', async () => {
    const { history } = setup('/dataverify');
    await screenShown('dataverify-intro');
    const before = history.length;
    fireEvent.click(screen.getByRole('button', { name: DV_TEXT.intro.start }));
    await screenShown('dataverify-new');
    expect(history.location.pathname).toBe('/dataverify/new');
    expect(history.length).toBe(before + 1);
  });

  it('DV-02 [취소] → /dataverify', async () => {
    const { history } = setup('/dataverify/new');
    await screenShown('dataverify-new');
    fireEvent.click(
      screen.getByRole('button', { name: DV_TEXT.newCheck.cancel }),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/dataverify'),
      WAIT,
    );
  });

  it('틀의 [로그아웃]은 저장소의 forget 을 부른다(세션 끝 구독 — 쥔 열쇠를 버림)', async () => {
    const forget = vi.fn();
    setup('/dataverify', 'service', forget);
    await screenShown('dataverify-intro');
    expect(forget).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '로그아웃' }));
    await waitFor(() => expect(forget).toHaveBeenCalledTimes(1), WAIT);
  });

  it('followSessionEnd: signedIn 을 벗어나는 전이마다 한 번', () => {
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
    set({ status: 'signedOut' });
    set({ status: 'signedOut' });
    expect(end).toHaveBeenCalledTimes(1);
    off();
    set({ status: 'signedIn' });
    set({ status: 'signedOut' });
    expect(end).toHaveBeenCalledTimes(1);
  });
});

const DONE_RUN = { ...fakeRun(7), advance: { status: 'done' } as const };
const FAILED_RUN = fakeRun(8, {
  status: 'failed',
  steps: fakeSteps(1, 'failed'),
  errorCode: 'flow_failed',
});

/** 지어낸 EDK 한 벌(환경 항목 하나 — 열쇠 열하나). 경로 시험은 model/testing.ts 를 가져오지 않는다(app/guards/layers.test.ts). */
const EDK = {
  환경: [
    {
      ID: 'E-001',
      테마: '환경',
      항목: '기후변화',
      대분류: '온실가스 배출량',
      중분류: '직접 배출량',
      소분류: 'Scope 1',
      '입력 방식': '직접 입력',
      단위: 'tCO2eq',
      values: { '2023': 1200, '2024': 1300 },
      핵심데이터: 'Y',
      메모: '',
    },
  ],
};

describe('데이터 검증 경로 ④ 처리 상태·결과', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /dataverify/runs/7 → DV-03 · …/result → DV-04 — 머문다',
    async (kind) => {
      for (const [path, name] of [
        ['/dataverify/runs/7', 'dataverify-status'],
        ['/dataverify/runs/7/result', 'dataverify-result'],
      ] as const) {
        const { history } = setup(path, kind, undefined, [DONE_RUN]);
        await screenShown(name);
        expect(history.location.pathname).toBe(path);
        cleanup();
      }
    },
  );

  it('DV-02 [검증 시작] → /dataverify/runs/30 (replace — 뒤로 가기가 DV-02 로 돌지 않음)', async () => {
    const { history, server } = setup('/dataverify/new');
    await screenShown('dataverify-new');
    const before = history.length;
    fireEvent.mouseDown(
      screen.getByRole('tab', { name: DV_TEXT.newCheck.tabPaste }),
    );
    const area = await screen.findByRole('textbox', {
      name: DV_TEXT.newCheck.pasteLabel,
    });
    fireEvent.change(area, { target: { value: JSON.stringify(EDK) } });
    fireEvent.change(screen.getByLabelText(DV_TEXT.newCheck.name), {
      target: { value: '가상건설' },
    });
    fireEvent.change(screen.getByLabelText(DV_TEXT.newCheck.sasb), {
      target: { value: 'Engineering & Construction Services' },
    });
    const topic = screen.getByRole('textbox', {
      name: DV_TEXT.newCheck.topicAdd,
    });
    fireEvent.change(topic, { target: { value: '기후변화 대응' } });
    fireEvent.keyDown(topic, { key: 'Enter' });
    fireEvent.click(screen.getByTestId('start'));
    await screenShown('dataverify-status');
    expect(history.location.pathname).toBe('/dataverify/runs/30');
    expect(history.length).toBe(before);
    expect(server.posts()).toHaveLength(1);
  });

  it('DV-03 [결과 보기] → …/result(push) · DV-04 [다시 실행] → 새 DV-03(push)', async () => {
    const { history } = setup('/dataverify/runs/7', 'service', undefined, [
      DONE_RUN,
    ]);
    await screenShown('dataverify-status');
    const before = history.length;
    const view = await waitFor(
      () => screen.getByRole('button', { name: DV_TEXT.common.viewResult }),
      WAIT,
    );
    fireEvent.click(view);
    await screenShown('dataverify-result');
    expect(history.location.pathname).toBe('/dataverify/runs/7/result');
    expect(history.length).toBe(before + 1);
    const rerun = await waitFor(
      () => screen.getByRole('button', { name: DV_TEXT.common.rerun }),
      WAIT,
    );
    fireEvent.click(rerun);
    await waitFor(
      () => expect(history.location.pathname).toBe('/dataverify/runs/30'),
      WAIT,
    );
    expect(history.length).toBe(before + 2);
    await screenShown('dataverify-status');
  });

  it('멈춘 실행 DV-03 [다시 실행] → 새 DV-03 · [목록으로] → /dataverify', async () => {
    const { history } = setup('/dataverify/runs/8', 'service', undefined, [
      FAILED_RUN,
    ]);
    const rerun = await waitFor(
      () => screen.getByRole('button', { name: DV_TEXT.common.rerun }),
      WAIT,
    );
    fireEvent.click(rerun);
    await waitFor(
      () => expect(history.location.pathname).toBe('/dataverify/runs/30'),
      WAIT,
    );
    const back = await waitFor(
      () => screen.getByRole('button', { name: DV_TEXT.common.toList }),
      WAIT,
    );
    fireEvent.click(back);
    await waitFor(
      () => expect(history.location.pathname).toBe('/dataverify'),
      WAIT,
    );
  });

  it('아직 끝나지 않은 실행의 결과 주소 → DV-03(replace)', async () => {
    const { history } = setup(
      '/dataverify/runs/9/result',
      'service',
      undefined,
      [fakeRun(9, { status: 'processing', steps: fakeSteps(2, 'running') })],
    );
    const before = history.length;
    await waitFor(
      () => expect(history.location.pathname).toBe('/dataverify/runs/9'),
      WAIT,
    );
    await screenShown('dataverify-status');
    expect(history.length).toBe(before);
  });
});

describe('데이터 검증 경로 ⑤ 목록(DV2b)', () => {
  const list = DV_TEXT.list;
  it.each(['service', 'admin'] as const)(
    '%s: 실행이 있으면 /dataverify 는 목록 · 없으면 DV-00(주소 그대로)',
    async (kind) => {
      const { history } = setup('/dataverify', kind, undefined, [
        { ...fakeRun(3), advance: { status: 'done' } },
      ]);
      await screenShown('dataverify-list');
      expect(history.location.pathname).toBe('/dataverify');
      expect(
        screen.queryByRole('checkbox', { name: list.mineOnly }) === null,
      ).toBe(kind === 'admin');
      cleanup();
      const empty = setup('/dataverify', kind);
      await screenShown('dataverify-intro');
      expect(empty.history.location.pathname).toBe('/dataverify');
      expect(
        document.querySelector('[data-screen="dataverify-list"]'),
      ).toBeNull();
    },
  );

  it('「검증 안내」 → /dataverify/intro · [결과 보기] → DV-04 · [진행 보기] → DV-03 · [새 검증] → DV-02', async () => {
    const { history } = setup('/dataverify', 'service', undefined, [
      { ...fakeRun(3), advance: { status: 'done' } },
      fakeRun(4),
    ]);
    await screenShown('dataverify-list');
    fireEvent.click(screen.getByText(list.introLink));
    await screenShown('dataverify-intro');
    expect(history.location.pathname).toBe('/dataverify/intro');
    history.back();
    await screenShown('dataverify-list');
    fireEvent.click(await screen.findByText(list.next.result, undefined, WAIT));
    await screenShown('dataverify-result');
    expect(history.location.pathname).toBe('/dataverify/runs/3/result');
    history.back();
    await screenShown('dataverify-list');
    fireEvent.click(
      await screen.findByText(list.next.progress, undefined, WAIT),
    );
    await screenShown('dataverify-status');
    expect(history.location.pathname).toBe('/dataverify/runs/4');
    history.back();
    await screenShown('dataverify-list');
    fireEvent.click(
      screen.getAllByRole('button', { name: list.newCheck }).at(0)!,
    );
    await screenShown('dataverify-new');
    expect(history.location.pathname).toBe('/dataverify/new');
  });
});
