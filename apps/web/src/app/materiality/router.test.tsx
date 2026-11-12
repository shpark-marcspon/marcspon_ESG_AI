// @vitest-environment jsdom
// 중대성평가 경로 표 시험(밴드 IRW1 ② — 발주서 §3-2 10, 데이터 검증 app/dataverify/router.test.tsx 꼴). createAppRouter 에 메모리 기록·
//   가짜 중대성평가 서버를 앞에 둔 실어댑터를 넣는다.
//   ① 두 종류 사용자: /materiality/runs/7 → IR-03 · …/result → IR-04 — 머문다 · 지금 메뉴는 「중대성평가」 · 운영 관리자는 인사말·[관리자 화면]
//   ② [결과 보기] → IR-04 push · [다시 실행] → 새 IR-03 push · 아직 끝나지 않은 실행의 결과 주소 → IR-03 replace · [목록으로] → /materiality
//   ③ 세션 끝(로그아웃)에 저장소가 쥔 열쇠를 버린다(forget) · followSessionEnd.
//   ④ (경계 ③) /materiality → IR-01(두 종류 사용자) · 메뉴 「중대성평가」가 켜져 다른 틀에서 /materiality 로 · 목록 [결과 보기]·[진행 보기] push.
//   ⑤ (밴드 IRW2 ②) /materiality/intro → IR-00 · /materiality/new → IR-02(두 종류 사용자) ·
//     IR-00 [시작하기] → IR-02 push · IR-02 [취소] → /materiality · [평가 시작] 201 → IR-03 replace.
//   ⑥ (밴드 IRW2 ③) 목록 [평가 안내] → IR-00 · [새 평가] → IR-02(push) · 빈 목록(거름 없는 첫 쪽 0건)은 /materiality 그대로 IR-00 몸(Q9).
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

import {
  doneRun,
  fakeMaterialityServer,
  fakeRun,
  fakeSteps,
  serverStoreOf,
} from '../../entities/materiality/api/testing.ts';
import type { FakeRun } from '../../entities/materiality/api/testing.ts';
import { IR_TEXT } from '../../entities/materiality/config/text.ts';
import { createAppRouter } from '../router.tsx';
import { followSessionEnd } from './MaterialityRoutes.tsx';

afterEach(cleanup);
// 경로 컴포넌트는 게으르게 불린다. 전량 시험이 같이 돌 때 첫 import 가 늦을 수 있어 기다림을 넓힌다(데이터 검증 경로 시험과 같다).
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

/** 고객사 사용자(service)·운영 관리자(admin)로 복원되는 세션(데이터 검증 경로 시험의 signedInAs 꼴). */
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

// 지연 로드 화면을 미리 불러 둔다(예열, sid:MARC-ISSUE-318 — 데이터 검증 경로 시험 꼴).
beforeAll(async () => {
  const router = createAppRouter({
    history: createMemoryHistory(),
    createMaterialityStore: () => serverStoreOf(fakeMaterialityServer()),
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
  runs: FakeRun[] = [],
  forget?: () => void,
) {
  const history = createMemoryHistory({ initialEntries: [path] });
  const server = fakeMaterialityServer({ runs });
  const router = createAppRouter({
    history,
    createMaterialityStore: () => {
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
const menu = IR_TEXT.shell.menu;
const FAILED = fakeRun(8, {
  status: 'failed',
  steps: fakeSteps(1, 'failed'),
  startedAt: '2026-10-19T14:02:00+09:00',
  finishedAt: '2026-10-19T14:10:00+09:00',
  errorCode: 'flow_failed',
});

describe('중대성평가 경로 ① 주소마다', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /materiality/runs/7 → IR-03 · …/result → IR-04 — 머문다',
    async (kind) => {
      for (const [path, name] of [
        ['/materiality/runs/7', 'materiality-status'],
        ['/materiality/runs/7/result', 'materiality-result'],
      ] as const) {
        const { history } = setup(path, kind, [doneRun(7)]);
        await screenShown(name);
        expect(history.location.pathname).toBe(path);
        expect(
          screen.getByText(
            kind === 'admin' ?
              IR_TEXT.shell.adminGreeting
            : IR_TEXT.shell.greeting,
          ),
        ).toBeTruthy();
        expect(
          screen.queryByRole('button', { name: IR_TEXT.shell.toAdmin }) !==
            null,
        ).toBe(kind === 'admin');
        const current = await waitFor(
          () => document.querySelector('[aria-current="page"]')!,
          WAIT,
        );
        expect(current.textContent).toContain(menu.materiality);
        cleanup();
      }
    },
  );

  it('고객사 사용자: /materiality/zzz 는 첫 화면으로', async () => {
    const { history } = setup('/materiality/zzz');
    await waitFor(
      () => expect(history.location.pathname).toBe('/greenwash'),
      WAIT,
    );
  });
});

describe('중대성평가 경로 ② 이동', () => {
  it('IR-03 [결과 보기] → IR-04(push)', async () => {
    const { history } = setup('/materiality/runs/7', 'service', [doneRun(7)]);
    await screenShown('materiality-status');
    fireEvent.click(
      await screen.findByRole('button', { name: IR_TEXT.common.viewResult }),
    );
    await screenShown('materiality-result');
    expect(history.location.pathname).toBe('/materiality/runs/7/result');
    expect(history.length).toBe(2);
  });

  it('IR-03 실패 [다시 실행] → 새 실행의 IR-03(push) · 같은 options', async () => {
    const { history, server } = setup('/materiality/runs/8', 'admin', [FAILED]);
    await screenShown('materiality-status');
    fireEvent.click(
      await screen.findByRole('button', { name: IR_TEXT.common.rerun }),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality/runs/30'),
      WAIT,
    );
    expect(history.length).toBe(2);
    expect(server.runs.get(30)!.options).toEqual(FAILED.options);
  });

  it('IR-04 [다시 실행] → 새 IR-03(push)', async () => {
    const { history } = setup('/materiality/runs/7/result', 'service', [
      doneRun(7),
    ]);
    await screenShown('materiality-result');
    fireEvent.click(
      await screen.findByRole('button', { name: IR_TEXT.common.rerun }),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality/runs/30'),
      WAIT,
    );
  });

  it('아직 끝나지 않은 실행의 결과 주소 → IR-03(replace)', async () => {
    const { history } = setup('/materiality/runs/9/result', 'service', [
      fakeRun(9, { status: 'processing', steps: fakeSteps(3, 'running') }),
    ]);
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality/runs/9'),
      WAIT,
    );
    await screenShown('materiality-status');
    expect(history.length).toBe(1);
  });

  it('[목록으로] → /materiality', async () => {
    const { history } = setup('/materiality/runs/8', 'service', [FAILED]);
    await screenShown('materiality-status');
    fireEvent.click(
      (
        await screen.findAllByRole('button', { name: IR_TEXT.common.toList })
      )[0]!,
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality'),
      WAIT,
    );
  });
});

describe('중대성평가 경로 ③ 세션', () => {
  it('틀의 [로그아웃]은 저장소의 forget 을 부른다(세션 끝 구독 — 쥔 열쇠를 버림)', async () => {
    const forget = vi.fn();
    setup('/materiality/runs/7', 'service', [doneRun(7)], forget);
    await screenShown('materiality-status');
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

describe('중대성평가 경로 ④ 목록·메뉴(경계 ③)', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /materiality → IR-01 — 머문다',
    async (kind) => {
      const { history } = setup('/materiality', kind, [doneRun(7)]);
      await screenShown('materiality-list');
      expect(history.location.pathname).toBe('/materiality');
    },
  );

  it.each(['/dataverify/intro', '/translation/new', '/greenwash/intro'])(
    '%s 틀의 「중대성평가」가 켜져 있고 누르면 /materiality',
    async (path) => {
      const { history } = setup(path);
      const item = await waitFor(
        () => screen.getByRole('button', { name: menu.materiality }),
        WAIT,
      );
      expect(item.getAttribute('aria-disabled')).toBeNull();
      fireEvent.click(item);
      await waitFor(
        () => expect(history.location.pathname).toBe('/materiality'),
        WAIT,
      );
    },
  );

  it('목록 [결과 보기] → IR-04 · [진행 보기] → IR-03(push)', async () => {
    const { history } = setup('/materiality', 'service', [
      doneRun(7),
      fakeRun(9, { status: 'processing', steps: fakeSteps(3, 'running') }),
    ]);
    await screenShown('materiality-list');
    fireEvent.click(
      await screen.findByRole(
        'button',
        { name: IR_TEXT.list.next.result },
        WAIT,
      ),
    );
    await screenShown('materiality-result');
    expect(history.location.pathname).toBe('/materiality/runs/7/result');
    expect(history.length).toBe(2);
    history.back();
    fireEvent.click(
      await screen.findByRole(
        'button',
        { name: IR_TEXT.list.next.progress },
        WAIT,
      ),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality/runs/9'),
      WAIT,
    );
  });
});

describe('중대성평가 경로 ⑤ 평가 안내·새 평가(밴드 IRW2 ②)', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /materiality/intro → IR-00 · /materiality/new → IR-02 — 머문다',
    async (kind) => {
      for (const [path, name] of [
        ['/materiality/intro', 'materiality-intro'],
        ['/materiality/new', 'materiality-new'],
      ] as const) {
        const { history } = setup(path, kind);
        await screenShown(name);
        expect(history.location.pathname).toBe(path);
        const current = await waitFor(
          () => document.querySelector('[aria-current="page"]')!,
          WAIT,
        );
        expect(current.textContent).toContain(menu.materiality);
        cleanup();
      }
    },
  );

  it('IR-00 [시작하기] → IR-02(push) · IR-02 [취소] → /materiality', async () => {
    const { history } = setup('/materiality/intro', 'service', [doneRun(7)]);
    await screenShown('materiality-intro');
    fireEvent.click(screen.getByRole('button', { name: IR_TEXT.intro.start }));
    await screenShown('materiality-new');
    expect(history.location.pathname).toBe('/materiality/new');
    expect(history.length).toBe(2);
    fireEvent.click(
      screen.getByRole('button', { name: IR_TEXT.newRun.cancel }),
    );
    await screenShown('materiality-list');
    expect(history.location.pathname).toBe('/materiality');
  });

  it('운영 관리자 IR-02 [평가 시작] 201 → 새 실행의 IR-03(replace)', async () => {
    const { history, server } = setup('/materiality/new', 'admin');
    await screenShown('materiality-new');
    const type = (name: string, value: string) =>
      fireEvent.change(screen.getByRole('textbox', { name }), {
        target: { value },
      });
    type('기업명', '가상물산');
    type('SASB 산업명', '가상 산업');
    type('1번째 토픽 이름', '가상토픽 A');
    type('가상토픽 A 서브토픽 이름', '가상 서브');
    const before = history.length;
    fireEvent.click(screen.getByTestId('start'));
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality/runs/30'),
      WAIT,
    );
    expect(history.length).toBe(before);
    expect(server.posts()).toHaveLength(1);
    await screenShown('materiality-status');
  });
});

describe('중대성평가 경로 ⑥ 목록 → 평가 안내·새 평가(밴드 IRW2 ③)', () => {
  it('목록 [평가 안내] → IR-00 · [새 평가] → IR-02(push)', async () => {
    const { history } = setup('/materiality', 'service', [doneRun(7)]);
    await screenShown('materiality-list');
    fireEvent.click(
      await screen.findByRole('link', { name: IR_TEXT.list.introLink }, WAIT),
    );
    await screenShown('materiality-intro');
    expect(history.location.pathname).toBe('/materiality/intro');
    expect(history.length).toBe(2);
    history.back();
    fireEvent.click(
      await screen.findByRole('button', { name: IR_TEXT.list.newRun }, WAIT),
    );
    await screenShown('materiality-new');
    expect(history.location.pathname).toBe('/materiality/new');
  });

  it.each(['service', 'admin'] as const)(
    '%s: 빈 목록 → /materiality 그대로 IR-00 몸 · [시작하기] → IR-02',
    async (kind) => {
      const { history } = setup('/materiality', kind);
      await screenShown('materiality-intro');
      expect(history.location.pathname).toBe('/materiality');
      expect(document.querySelector('[data-screen="materiality-list"]')).toBe(
        null,
      );
      fireEvent.click(
        screen.getByRole('button', { name: IR_TEXT.intro.start }),
      );
      await screenShown('materiality-new');
      expect(history.location.pathname).toBe('/materiality/new');
    },
  );
});

describe('중대성평가 경로 ⑦ 결과 고치기 나가기(밴드 IRW11 Q9)', () => {
  const edit = IR_TEXT.result.edit;
  async function openEdit() {
    const setupResult = setup('/materiality/runs/7/result', 'service', [
      doneRun(7),
    ]);
    await screenShown('materiality-result');
    const [open] = await screen.findAllByRole(
      'button',
      { name: edit.open },
      WAIT,
    );
    fireEvent.click(open!);
    const box = await screen.findByRole('textbox', { name: edit.definition });
    return { ...setupResult, box };
  }

  it('바꾼 채 왼쪽 메뉴 → 창 · [계속 고치기] 머묾 · [나가기] → 그 경로', async () => {
    const { history, box } = await openEdit();
    fireEvent.change(box, { target: { value: '가상 정의 글 고침' } });
    fireEvent.click(screen.getByRole('button', { name: menu.materiality }));
    const dialog = await screen.findByTestId('leave-dialog', undefined, WAIT);
    expect(within(dialog).getByText(edit.leaveTitle)).toBeTruthy();
    fireEvent.click(
      within(dialog).getByRole('button', { name: edit.leaveStay }),
    );
    await waitFor(
      () => expect(screen.queryByTestId('leave-dialog')).toBeNull(),
      WAIT,
    );
    expect(history.location.pathname).toBe('/materiality/runs/7/result');
    expect(
      (
        screen.getByRole('textbox', {
          name: edit.definition,
        }) as HTMLTextAreaElement
      ).value,
    ).toBe('가상 정의 글 고침');
    fireEvent.click(screen.getByRole('button', { name: menu.materiality }));
    fireEvent.click(
      within(
        await screen.findByTestId('leave-dialog', undefined, WAIT),
      ).getByRole('button', { name: edit.leaveGo }),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality'),
      WAIT,
    );
  });

  it('안 바꾸면 묻지 않고 간다', async () => {
    const { history } = await openEdit();
    fireEvent.click(screen.getByRole('button', { name: menu.materiality }));
    await waitFor(
      () => expect(history.location.pathname).toBe('/materiality'),
      WAIT,
    );
    expect(screen.queryByTestId('leave-dialog')).toBeNull();
  });
});
