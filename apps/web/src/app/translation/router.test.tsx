// @vitest-environment jsdom
// 영문번역 경로 표 시험(밴드 TRW1a ② — 발주서 §3-2 9). createAppRouter 에 메모리 기록·가짜 영문번역 서버를 앞에 둔 실어댑터를 넣는다.
//   ① /translation(고객사·운영 관리자) 은 머문다(틀이 그려짐) · /translation/new → TR-02 ② 메뉴 「영문번역」 → /translation, 「그린워싱 점검」 → /greenwash
//   ③ ?part= 는 아는 값만(zzz 는 버림) ④ [번역 시작] → 묶음 화면 replace(기록이 늘지 않음), 일부만 시작하면 못 한 파트를 메모리에.
import { StrictMode } from 'react';

import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeDocument,
  fakeLayout,
  fakeOptions,
  fakeRun,
  fakeTranslationServer,
  refusal,
  serverStoreOf,
} from '../../entities/translation/api/testing.ts';
import { TR_TEXT } from '../../entities/translation/config/text.ts';
import { createAppRouter, validateTranslationSearch } from '../router.tsx';
import { copyText } from './TranslationRoutes.tsx';

afterEach(cleanup);
// 경로 컴포넌트는 게으르게 불린다. 전량 시험이 같이 돌 때 첫 import 가 늦을 수 있어 기다림을 넓힌다(그린워싱 경로 시험과 같다).
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

/** 고객사 사용자(service)·운영 관리자(admin)로 복원되는 세션(그린워싱 경로 시험의 signedInAs 꼴). */
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

// 지연 로드 화면(lazyRouteComponent)을 미리 불러 둔다 — 부하 아래 첫 waitFor 가 모듈 로드를 기다리지 않게(예열, sid:MARC-ISSUE-318).
// 경로 파일을 직접 가져오지 않고(칸 규칙) 버리는 라우터 하나의 경로 조각을 모두 싣는다. 모듈은 한 번 실리면 다음 라우터도 바로 쓴다.
beforeAll(async () => {
  const server = fakeTranslationServer();
  const router = createAppRouter({
    history: createMemoryHistory(),
    createTranslationStore: () => serverStoreOf(server),
    session: signedInAs('service'),
  });
  await Promise.all(
    Object.values(router.routesById).map((route) =>
      router.loadRouteChunk(route),
    ),
  );
}, 60_000);

function setup(path: string, kind: 'service' | 'admin' = 'service') {
  const history = createMemoryHistory({ initialEntries: [path] });
  const server = fakeTranslationServer();
  const router = createAppRouter({
    history,
    createTranslationStore: (deps) =>
      serverStoreOf(server, {
        sendUpload:
          deps.sendUpload === undefined ? undefined : server.sendUpload,
      }),
    session: signedInAs(kind),
  });
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  );
  return { router, history, server };
}

const shellShown = () =>
  waitFor(
    () =>
      expect(
        screen.getByRole('button', { name: TR_TEXT.shell.menu.translation }),
      ).toBeTruthy(),
    WAIT,
  );
const screenShown = (name: string) =>
  waitFor(
    () =>
      expect(document.querySelector(`[data-screen="${name}"]`)).not.toBeNull(),
    WAIT,
  );

describe('영문번역 경로 ① 주소마다', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /translation 은 머문다(틀), /translation/new 는 TR-02',
    async (kind) => {
      const list = setup('/translation', kind);
      await shellShown();
      expect(list.history.location.pathname).toBe('/translation');
      cleanup();
      const fresh = setup('/translation/new', kind);
      await screenShown('translation-new');
      expect(fresh.history.location.pathname).toBe('/translation/new');
      expect(
        screen.getByText(
          kind === 'admin' ?
            TR_TEXT.shell.adminGreeting
          : TR_TEXT.shell.greeting,
        ),
      ).toBeTruthy();
    },
  );
});

describe('영문번역 경로 ② 메뉴', () => {
  it('「영문번역」 → /translation, 「그린워싱 점검」 → /greenwash', async () => {
    const { history } = setup('/translation/new');
    await screenShown('translation-new');
    fireEvent.click(
      screen.getByRole('button', { name: TR_TEXT.shell.menu.translation }),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/translation'),
      WAIT,
    );
    fireEvent.click(
      screen.getByRole('button', { name: TR_TEXT.shell.menu.greenwash }),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/greenwash'),
      WAIT,
    );
  });
});

describe('영문번역 경로 ② 메뉴 · 그린워싱 틀에서(H5)', () => {
  it('그린워싱 틀의 「영문번역」이 켜져 있고 누르면 /translation', async () => {
    const { history } = setup('/greenwash/intro');
    const item = await waitFor(
      () =>
        screen.getByRole('button', { name: TR_TEXT.shell.menu.translation }),
      WAIT,
    );
    expect(item.hasAttribute('disabled')).toBe(false);
    expect(item.getAttribute('aria-disabled')).not.toBe('true');
    fireEvent.click(item);
    await waitFor(
      () => expect(history.location.pathname).toBe('/translation'),
      WAIT,
    );
  });
});

describe('영문번역 경로 ③ search', () => {
  it('part 는 아는 값만', () => {
    expect(validateTranslationSearch({ part: 'zzz' })).toEqual({});
    expect(validateTranslationSearch({ part: 'ceo' })).toEqual({ part: 'ceo' });
    expect(validateTranslationSearch({ part: 'all', x: '1' })).toEqual({
      part: 'all',
    });
  });

  it('?part=zzz 로 열면 버린 채 머문다', async () => {
    const { history, router } = setup(
      '/translation/documents/12/batches/run-3?part=zzz',
    );
    await shellShown();
    expect(history.location.pathname).toBe(
      '/translation/documents/12/batches/run-3',
    );
    // 기록의 글자는 그대로, 라우터가 고른 search 에는 part 가 없다.
    expect(router.state.matches.at(-1)!.search).toEqual({});
  });
});

describe('영문번역 경로 ④ [번역 시작] → 묶음 화면 replace', () => {
  const TXT = new TextEncoder().encode('[PAGE 1]\na\n[PAGE 2]\nb');
  async function fillAndStart() {
    const fileCard = document.querySelector('[data-card="file"]')!;
    fireEvent.change(fileCard.querySelector('input[type="file"]')!, {
      target: { files: [new File([TXT], 'sample_extract.txt')] },
    });
    await act(async () => {});
    fireEvent.change(document.querySelector('[data-part-field="ceo"]')!, {
      target: { value: '1' },
    });
    fireEvent.change(document.querySelector('[data-part-field="story"]')!, {
      target: { value: '2' },
    });
    const client = screen.getByTestId('glossary-client');
    fireEvent.change(client.querySelector('input[type="file"]')!, {
      target: { files: [new File([new Uint8Array([80, 75])], 'g.xlsx')] },
    });
    await act(async () => {});
    const words = TR_TEXT.newTranslation.company;
    for (const [label, value] of [
      [words.name, 'Sample Corp'],
      [words.subject, 'virtual services'],
      [words.standards, 'GRI'],
    ] as const)
      fireEvent.change(screen.getByLabelText(label, { exact: false }), {
        target: { value },
      });
    fireEvent.click(screen.getByTestId('start'));
  }

  it('모두 시작 → 묶음 화면 주소로 replace(기록 길이 그대로)', async () => {
    const { history, router, server } = setup('/translation/new');
    await screenShown('translation-new');
    const before = history.length;
    await fillAndStart();
    await waitFor(
      () =>
        expect(history.location.pathname).toMatch(
          /^\/translation\/documents\/12\/batches\/[0-9a-f-]{36}$/,
        ),
      WAIT,
    );
    expect(history.length).toBe(before);
    expect(server.count('POST /runs')).toBe(2);
    expect(router.options.context.translation.notStarted.size).toBe(0);
  });

  it('일부만 시작 → 못 한 파트를 메모리에(묶음 열쇠로)', async () => {
    const { history, router, server } = setup('/translation/new');
    server.override['POST /runs'] = [
      () =>
        new Response(JSON.stringify({ id: 50, status: 'queued' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      () => refusal(400, 'INVALID_OPTIONS'),
    ];
    await screenShown('translation-new');
    await fillAndStart();
    await waitFor(
      () => expect(history.location.pathname).toMatch(/batches\//),
      WAIT,
    );
    const key = history.location.pathname
      .replace('/translation/documents/', '')
      .replace('/batches/', '/');
    expect(router.options.context.translation.notStarted.get(key)).toEqual({
      started: ['ceo'],
      failed: ['story'],
    });
  });
});

describe('영문번역 경로 ⑤ TR-00 번역 안내(밴드 TRP3, sid:MARC-ENT-435)', () => {
  it.each(['service', 'admin'] as const)(
    '%s: /translation/intro 는 TR-00 을 그리고 머문다 · 지금 메뉴는 「영문번역」',
    async (kind) => {
      const { history } = setup('/translation/intro', kind);
      await screenShown('translation-intro');
      expect(history.location.pathname).toBe('/translation/intro');
      expect(
        screen
          .getByRole('button', { name: TR_TEXT.shell.menu.translation })
          .getAttribute('aria-current'),
      ).toBe('page');
      // 운영 관리자도 [시작하기]가 보인다(sid:MARC-ENT-380).
      expect(
        screen.getByRole('button', { name: TR_TEXT.intro.start }),
      ).toBeTruthy();
    },
  );

  it('/translation 의 「번역 안내」 → /translation/intro(push — 기록이 하나 는다)', async () => {
    const { history } = setup('/translation');
    const link = await waitFor(
      () => screen.getByRole('link', { name: TR_TEXT.list.introLink }),
      WAIT,
    );
    const before = history.length;
    fireEvent.click(link);
    await screenShown('translation-intro');
    expect(history.location.pathname).toBe('/translation/intro');
    expect(history.length).toBe(before + 1);
  });

  // [WS1] [시작하기]는 목록으로(새 번역이 아니다 — sid:MARC-ENT-625, 그린워싱 GW-00 과 같다).
  it('[시작하기] → /translation(push), TR-01 목록이 그려짐', async () => {
    const { history } = setup('/translation/intro');
    await screenShown('translation-intro');
    const before = history.length;
    fireEvent.click(screen.getByRole('button', { name: TR_TEXT.intro.start }));
    await screenShown('translation-list');
    expect(history.location.pathname).toBe('/translation');
    expect(history.length).toBe(before + 1);
    expect(
      document.querySelector('[data-screen="translation-new"]'),
    ).toBeNull();
  });

  // [WS1] 맴돎 없음: 빈 목록에도 [새 번역]이 있고 누르면 TR-02.
  it('[시작하기] → 빈 목록 [새 번역] → /translation/new(push), TR-02 가 그려짐', async () => {
    const { history } = setup('/translation/intro');
    await screenShown('translation-intro');
    fireEvent.click(screen.getByRole('button', { name: TR_TEXT.intro.start }));
    const empty = await waitFor(() => screen.getByTestId('list-empty'), WAIT);
    expect(empty.textContent).toContain(TR_TEXT.list.empty);
    const before = history.length;
    fireEvent.click(
      within(empty).getByRole('button', { name: TR_TEXT.list.newTranslation }),
    );
    await screenShown('translation-new');
    expect(history.location.pathname).toBe('/translation/new');
    expect(history.length).toBe(before + 1);
  });

  it('경로 트리: /translation/intro 에는 beforeLoad 가 없다(가드는 레이아웃 /translation 하나)', () => {
    const { router } = setup('/login');
    const routes = Object.values(router.routesById) as {
      id: string;
      options: { beforeLoad?: unknown };
    }[];
    const intro = routes.find((route) => route.id === '/translation/intro');
    expect(intro).toBeDefined();
    expect(intro!.options.beforeLoad).toBeUndefined();
    expect(
      routes.find((route) => route.id === '/translation')?.options.beforeLoad,
    ).toBeTypeOf('function');
  });
});

// 밴드 TRP3 ② — 검증 권고 1(감독 81): TR-00 에서 브라우저 뒤로 → 목록이 다시 그려진다.
describe('영문번역 경로 ⑥ TR-00 → 뒤로(history.back) → 목록', () => {
  it('/translation 「번역 안내」 → TR-00 → history.back() → /translation 목록 화면', async () => {
    const { history } = setup('/translation');
    const link = await waitFor(
      () => screen.getByRole('link', { name: TR_TEXT.list.introLink }),
      WAIT,
    );
    fireEvent.click(link);
    await screenShown('translation-intro');
    act(() => history.back());
    await screenShown('translation-list');
    expect(history.location.pathname).toBe('/translation');
    expect(
      document.querySelector('[data-screen="translation-intro"]'),
    ).toBeNull();
  });
});

// 밴드 TRW6 ② S2: /translation/pdf/new(TR-P02) — 주소로 열면 PDF 꼴 새 번역, 목록 [PDF로 새 번역] 은 push, [취소] → 목록.
describe('영문번역 경로 ⑦ PDF 새 번역 (TRW6 ②)', () => {
  it('/translation/pdf/new 는 PDF 꼴 새 번역(받는 꼴 .pdf · 제목)', async () => {
    const { history } = setup('/translation/pdf/new');
    await screenShown('translation-new');
    expect(history.location.pathname).toBe('/translation/pdf/new');
    expect(
      screen.getByRole('heading', { name: TR_TEXT.pdfNew.title }),
    ).toBeTruthy();
    const input = document.querySelector<HTMLInputElement>(
      '[data-card="file"] input[type="file"]',
    )!;
    expect(input.getAttribute('accept')).toContain('.pdf');
  });

  it('목록 [PDF로 새 번역] → /translation/pdf/new(push) · [취소] → /translation', async () => {
    const { history } = setup('/translation');
    const button = await waitFor(() => screen.getByTestId('new-pdf'), WAIT);
    const before = history.length;
    fireEvent.click(button);
    await screenShown('translation-new');
    expect(history.location.pathname).toBe('/translation/pdf/new');
    expect(history.length).toBe(before + 1);
    fireEvent.click(
      screen.getByRole('button', { name: TR_TEXT.newTranslation.cancel }),
    );
    await waitFor(
      () => expect(history.location.pathname).toBe('/translation'),
      WAIT,
    );
  });

  it('/translation/new 는 그대로 워드 꼴(PDF 안내 0)', async () => {
    setup('/translation/new');
    await screenShown('translation-new');
    expect(
      screen.getByRole('heading', { name: TR_TEXT.newTranslation.title }),
    ).toBeTruthy();
    expect(screen.queryByTestId('pdf-range-guide')).toBeNull();
  });
});

// PDF 보기(밴드 TRW6 ③ S3): 표 「자리」 → …/pdf/$runId(push) 그 쪽·그 상자 + 띠 · [← 결과 요약] → 묶음 화면 그 파트 탭 ·
// 둘째 진입([PDF로 보기])은 표식이 소진돼 고름·띠 0. 화면은 틀이 넘긴 openPdf(시험의 가짜)로 연다.
describe('영문번역 경로 ⑧ PDF 보기 (TRW6 ③)', () => {
  const BATCH = '0b9f1a2c-3d4e-4f50-8a6b-7c8d9e0f1a2b';
  const original = {
    create: URL.createObjectURL,
    revoke: URL.revokeObjectURL,
  };
  afterEach(() => {
    URL.createObjectURL = original.create;
    URL.revokeObjectURL = original.revoke;
  });

  /** 다른 묶음(견주기 워드 — 밴드 TRW7 ② B1 갈래). */
  const OTHER = '1c2d3e4f-5a6b-4c7d-8e9f-0a1b2c3d4e5f';
  function setupPdf() {
    URL.createObjectURL = vi.fn(() => 'blob:fake-pdf');
    URL.revokeObjectURL = vi.fn();
    const layout = fakeLayout(4) as Record<string, unknown> & {
      variants: { label: string; units: Record<string, unknown>[] }[];
    };
    layout.variants[0]!.label = 'single';
    layout.variants[0]!.units[0] = {
      tag: 'BLOCK 1',
      page: 4,
      level: 'block',
      translations: ['Climate Strategy', 'Made-up text about cuts'],
    };
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12, {
          fileName: 'made_up.pdf',
          pdf: new Uint8Array([37, 80, 68, 70]),
        }),
      ],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 4, BATCH), {
          flowId: 'translation.pdf@158',
        }),
        fakeRun(31, 12, fakeOptions('general', 6, 7, BATCH)),
        fakeRun(
          32,
          12,
          fakeOptions('story', 4, 4, OTHER, {
            style: { compareAb: true, single: 'B' },
          }),
        ),
      ],
    });
    server.advance(30, { status: 'done', layout });
    server.advance(31, { status: 'done' });
    server.advance(32, { status: 'done' });
    const opened: string[] = [];
    const history = createMemoryHistory({
      initialEntries: [`/translation/documents/12/batches/${BATCH}?part=story`],
    });
    const router = createAppRouter({
      history,
      createTranslationStore: () => serverStoreOf(server),
      session: signedInAs('service'),
      openPdf: async (url) => {
        opened.push(url);
        return {
          renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
          close() {},
        };
      },
    });
    render(
      <StrictMode>
        <RouterProvider router={router} />
      </StrictMode>,
    );
    return { history, opened, router };
  }

  const box = (id: string) =>
    document.querySelector(`[data-box="${id}"]`) as HTMLElement | null;

  it('「자리」 → 그 상자 고름·띠 · [← 결과 요약] → 그 파트 탭 · [PDF로 보기] 다시 → 첫 쪽·고름 0', async () => {
    const { history, opened } = setupPdf();
    const place = await waitFor(
      () => screen.getByTestId('qa-issue-place'),
      WAIT,
    );
    const before = history.length;
    fireEvent.click(place);
    await screenShown('translation-pdf');
    expect(history.location.pathname).toBe(
      `/translation/documents/12/batches/${BATCH}/pdf/30`,
    );
    expect(history.length).toBe(before + 1);
    await waitFor(
      () => expect(box('p4-b2')?.getAttribute('data-selected')).toBe('true'),
      WAIT,
    );
    expect(opened).toContain('blob:fake-pdf');
    expect(screen.getByTestId('pdf-from-table').textContent).toBe(
      TR_TEXT.pdfView.fromTable(
        TR_TEXT.pdfView.placeUnit(4, 2),
        TR_TEXT.issues.types.unnatural,
      ),
    );

    fireEvent.click(screen.getByTestId('pdf-back'));
    await screenShown('translation-run');
    expect(history.location.pathname).toBe(
      `/translation/documents/12/batches/${BATCH}`,
    );
    expect(history.location.search).toContain('part=story');

    fireEvent.click(await waitFor(() => screen.getByTestId('open-pdf'), WAIT));
    await screenShown('translation-pdf');
    await waitFor(() => expect(box('p4-b2')).not.toBeNull(), WAIT);
    expect(box('p4-b2')!.getAttribute('data-selected')).toBeNull();
    expect(screen.queryByTestId('pdf-from-table')).toBeNull();
  });

  it('표식은 한 번만: 「자리」로 들어간 뒤 뒤로·앞으로 다시 들어오면 고름·띠 0', async () => {
    const { history } = setupPdf();
    fireEvent.click(
      await waitFor(() => screen.getByTestId('qa-issue-place'), WAIT),
    );
    await waitFor(
      () => expect(box('p4-b2')?.getAttribute('data-selected')).toBe('true'),
      WAIT,
    );
    act(() => history.back());
    await screenShown('translation-run');
    act(() => history.forward());
    await screenShown('translation-pdf');
    await waitFor(() => expect(box('p4-b2')).not.toBeNull(), WAIT);
    expect(box('p4-b2')!.getAttribute('data-selected')).toBeNull();
    expect(screen.queryByTestId('pdf-from-table')).toBeNull();
  });

  // 밴드 TRW7 ② W5 ⓕ: 돌아온 표 줄 — summaryFocus 는 한 번 쓰고 지운다.
  it('「자리」 → [← 결과 요약] → 눌렀던 줄 data-returned·화면 안(scrollIntoView center) · 다음 진입엔 0', async () => {
    const into = vi.fn();
    const saved = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = into;
    try {
      const { history } = setupPdf();
      fireEvent.click(
        await waitFor(() => screen.getByTestId('qa-issue-place'), WAIT),
      );
      await screenShown('translation-pdf');
      into.mockClear();
      fireEvent.click(screen.getByTestId('pdf-back'));
      await screenShown('translation-run');
      const returned = await waitFor(
        () =>
          screen
            .getByTestId('qa-issues')
            .querySelector('tr[data-returned]') as HTMLElement,
        WAIT,
      );
      expect(returned).not.toBeNull();
      expect(returned.textContent).toContain(TR_TEXT.pdfView.placeUnit(4, 2));
      expect(
        screen.getByTestId('qa-issues').querySelectorAll('tr[data-returned]'),
      ).toHaveLength(1);
      expect(into).toHaveBeenCalledWith({ block: 'center' });
      expect(into.mock.contexts).toContain(returned);
      // 용어 표에는 돌아온 줄 0(이슈 줄을 눌렀다).
      expect(
        screen.getByTestId('glossary-miss').querySelector('tr[data-returned]'),
      ).toBeNull();

      // 두 번째 진입(기록 뒤로 → PDF 보기 → 뒤로 → 처음 묶음 화면): 표식은 이미 지워져 강조 0.
      //   ([PDF로 보기]로 다시 들어가면 표식을 null 로 덮어 지우지 않아도 0 이 되므로 기록으로 잰다 — 심은 파손 P12.)
      act(() => history.back());
      await screenShown('translation-pdf');
      act(() => history.back());
      await screenShown('translation-run');
      await waitFor(() => screen.getByTestId('qa-issue-place'), WAIT);
      expect(document.querySelector('tr[data-returned]')).toBeNull();
    } finally {
      Element.prototype.scrollIntoView = saved;
    }
  });

  // 검증 B1: 남은 표식이 다른 묶음(견주기)의 첫 탭·표를 바꾸지 않는다 — 쓰지 않고 지운다.
  it('다른 묶음 첫 진입 → 남은 표식(B 문체)을 쓰지 않음 — 탭 A · 강조 0 · 표식 지움', async () => {
    const { history, router } = setupPdf();
    await waitFor(() => screen.getByTestId('qa-issue-place'), WAIT);
    const runtime = router.options.context.translation;
    runtime.control!.summaryFocus = {
      documentId: '12',
      batchKey: BATCH,
      runId: '32',
      label: 'B',
      table: 'issues',
      index: 0,
    };
    // 목록을 거쳐(RunRoute 가 새로 붙음) 다른 묶음으로.
    act(() => history.push('/translation'));
    await screenShown('translation-list');
    act(() => history.push(`/translation/documents/12/batches/${OTHER}`));
    const tabA = await waitFor(
      () => screen.getByRole('tab', { name: TR_TEXT.run.styleTab('A') }),
      WAIT,
    );
    await waitFor(() => screen.getByTestId('qa-issues'), WAIT);
    expect(tabA.getAttribute('aria-selected')).toBe('true');
    expect(document.querySelector('tr[data-returned]')).toBeNull();
    await waitFor(() => expect(runtime.control!.summaryFocus).toBeNull());
  });

  it('용어 「자리」 → [← 결과 요약] → 용어 표의 그 줄만 data-returned', async () => {
    setupPdf();
    fireEvent.click(
      await waitFor(() => screen.getByTestId('glossary-miss-place'), WAIT),
    );
    await screenShown('translation-pdf');
    fireEvent.click(screen.getByTestId('pdf-back'));
    await screenShown('translation-run');
    await waitFor(
      () =>
        expect(
          screen
            .getByTestId('glossary-miss')
            .querySelectorAll('tr[data-returned]'),
        ).toHaveLength(1),
      WAIT,
    );
    expect(
      screen.getByTestId('qa-issues').querySelector('tr[data-returned]'),
    ).toBeNull();
  });

  it('주소로 바로 열면(새로 고침 — 표식 없음) 띠 0 · 빈 서버면 layout 404 한 줄', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:fake-pdf');
    URL.revokeObjectURL = vi.fn();
    const { router } = setup(
      `/translation/documents/12/batches/${BATCH}/pdf/30`,
    );
    expect(router).toBeTruthy();
    await screenShown('translation-pdf');
    // 빈 가짜 서버 — layout 404 → 한 줄.
    await waitFor(() => screen.getByTestId('pdf-not-found'), WAIT);
    expect(screen.queryByTestId('pdf-from-table')).toBeNull();
  });

  // 밴드 TRW7 ③b W8(감독 답 Q1 — 파트 탭만): 보기 머리 파트 탭 → 같은 경로의 그 파트 runId(replace) · [← 결과 요약] → 그 파트 탭.
  it('파트 탭: 다른 PDF 파트 누름 → …/pdf/<그 runId> replace · 그 파트 보기 · [← 결과 요약] → ?part=그 파트', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:fake-pdf');
    URL.revokeObjectURL = vi.fn();
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12, {
          fileName: 'made_up.pdf',
          pdf: new Uint8Array([37, 80, 68, 70]),
        }),
      ],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 4, BATCH), {
          flowId: 'translation.pdf@158',
        }),
        fakeRun(33, 12, fakeOptions('general', 6, 6, BATCH), {
          flowId: 'translation.pdf@158',
        }),
      ],
    });
    server.advance(30, { status: 'done', layout: fakeLayout(4) });
    server.advance(33, { status: 'done', layout: fakeLayout(6) });
    const history = createMemoryHistory({
      initialEntries: [`/translation/documents/12/batches/${BATCH}/pdf/30`],
    });
    const router = createAppRouter({
      history,
      createTranslationStore: () => serverStoreOf(server),
      session: signedInAs('service'),
      openPdf: async () => ({
        renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
        close() {},
      }),
    });
    render(
      <StrictMode>
        <RouterProvider router={router} />
      </StrictMode>,
    );
    await screenShown('translation-pdf');
    const general = await waitFor(
      () =>
        screen.getByRole('tab', {
          name: new RegExp(TR_TEXT.parts.names.general),
        }),
      WAIT,
    );
    const before = history.length;
    fireEvent.mouseDown(general, { button: 0 });
    fireEvent.click(general);
    await waitFor(
      () =>
        expect(history.location.pathname).toBe(
          `/translation/documents/12/batches/${BATCH}/pdf/33`,
        ),
      WAIT,
    );
    expect(history.length).toBe(before);
    await waitFor(
      () =>
        expect(screen.getByTestId('pdf-page-title').textContent).toContain(
          TR_TEXT.pdfView.pageTitle(6),
        ),
      WAIT,
    );
    await waitFor(
      () =>
        expect(
          screen
            .getByRole('tab', { name: new RegExp(TR_TEXT.parts.names.general) })
            .getAttribute('aria-selected'),
        ).toBe('true'),
      WAIT,
    );
    fireEvent.click(screen.getByTestId('pdf-back'));
    await waitFor(
      () => expect(history.location.search).toContain('part=general'),
      WAIT,
    );
  });

  // 밴드 TRW8 ①: 파트 탭을 누르는 동안 탭 줄(PartSwitch)은 붙은 채 — 경로의 key 를 빼고 몸(Ready)만 runId 로 새로.
  //   표식(pdfFocus)은 처음 runId 에만 쓴다(옮긴 파트는 첫 쪽·고름 0·띠 0).
  it('파트 탭 누름 → 탭 줄은 같은 요소로 한 번도 빠지지 않음 · 새 파트 몸 · 「자리」 표식은 처음 파트에만', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:fake-pdf');
    URL.revokeObjectURL = vi.fn();
    const story = fakeLayout(4) as Record<string, unknown> & {
      variants: { label: string; units: Record<string, unknown>[] }[];
    };
    story.variants[0]!.label = 'single';
    story.variants[0]!.units[0] = {
      tag: 'BLOCK 1',
      page: 4,
      level: 'block',
      translations: ['Climate Strategy', 'Made-up text about cuts'],
    };
    const general = fakeLayout(6) as Record<string, unknown> & {
      variants: { label: string }[];
    };
    general.variants[0]!.label = 'single';
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12, {
          fileName: 'made_up.pdf',
          pdf: new Uint8Array([37, 80, 68, 70]),
        }),
      ],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 4, 4, BATCH), {
          flowId: 'translation.pdf@158',
        }),
        fakeRun(33, 12, fakeOptions('general', 6, 6, BATCH), {
          flowId: 'translation.pdf@158',
        }),
      ],
    });
    server.advance(30, { status: 'done', layout: story });
    server.advance(33, { status: 'done', layout: general });
    const history = createMemoryHistory({
      initialEntries: [`/translation/documents/12/batches/${BATCH}?part=story`],
    });
    const router = createAppRouter({
      history,
      createTranslationStore: () => serverStoreOf(server),
      session: signedInAs('service'),
      openPdf: async () => ({
        renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
        close() {},
      }),
    });
    render(
      <StrictMode>
        <RouterProvider router={router} />
      </StrictMode>,
    );
    fireEvent.click(
      await waitFor(() => screen.getByTestId('qa-issue-place'), WAIT),
    );
    await screenShown('translation-pdf');
    await waitFor(() => screen.getByTestId('pdf-from-table'), WAIT);
    expect(document.querySelector('[data-box][data-selected]')).not.toBeNull();
    const bar = await waitFor(() => screen.getByTestId('pdf-part-tabs'), WAIT);
    let gone = 0;
    const observer = new MutationObserver(() => {
      if (document.querySelector('[data-testid="pdf-part-tabs"]') === null)
        gone += 1;
    });
    observer.observe(document.body, { childList: true, subtree: true });
    const tab = within(bar).getByRole('tab', {
      name: new RegExp(TR_TEXT.parts.names.general),
    });
    fireEvent.mouseDown(tab, { button: 0 });
    fireEvent.click(tab);
    // 누른 직후(같은 차례) — 탭 줄 그대로.
    expect(bar.isConnected).toBe(true);
    await waitFor(
      () =>
        expect(history.location.pathname).toBe(
          `/translation/documents/12/batches/${BATCH}/pdf/33`,
        ),
      WAIT,
    );
    expect(screen.getByTestId('pdf-part-tabs')).toBe(bar);
    await waitFor(
      () =>
        expect(screen.getByTestId('pdf-page-title').textContent).toContain(
          TR_TEXT.pdfView.pageTitle(6),
        ),
      WAIT,
    );
    observer.disconnect();
    expect(gone).toBe(0);
    expect(screen.getByTestId('pdf-part-tabs')).toBe(bar);
    expect(
      within(bar)
        .getByRole('tab', { name: new RegExp(TR_TEXT.parts.names.general) })
        .getAttribute('aria-selected'),
    ).toBe('true');
    // 옮긴 파트에는 표식 0 — 띠·고름 없음.
    expect(screen.queryByTestId('pdf-from-table')).toBeNull();
    expect(document.querySelector('[data-box][data-selected]')).toBeNull();
    // 처음 파트로 되돌아와도 표식은 다시 쓰지 않는다(한 번만 — 검증 B1).
    const back = within(bar).getByRole('tab', {
      name: new RegExp(TR_TEXT.parts.names.story),
    });
    fireEvent.mouseDown(back, { button: 0 });
    fireEvent.click(back);
    await waitFor(
      () =>
        expect(screen.getByTestId('pdf-page-title').textContent).toContain(
          TR_TEXT.pdfView.pageTitle(4),
        ),
      WAIT,
    );
    await waitFor(
      () =>
        expect(document.querySelectorAll('[data-box]').length).toBeGreaterThan(
          0,
        ),
      WAIT,
    );
    expect(screen.queryByTestId('pdf-from-table')).toBeNull();
    expect(document.querySelector('[data-box][data-selected]')).toBeNull();
  });
});

function withExec(result: boolean) {
  const seen: string[] = [];
  const exec = vi.fn((command: string) => {
    const area = document.querySelector('textarea');
    seen.push(`${command}:${area?.value ?? ''}`);
    return result;
  });
  Object.defineProperty(document, 'execCommand', {
    value: exec,
    configurable: true,
  });
  return { exec, seen };
}

// 밴드 TRW14 ③: 「번역 복사」 클립보드 쓰기 — clipboard 가 있으면 그것, 없거나 거절이면 숨긴 textarea + execCommand, 둘 다 안 되면 reject.
describe('copyText (TRW14 ③)', () => {
  afterEach(() => {
    Reflect.deleteProperty(document, 'execCommand');
  });
  it('clipboard.writeText 가 있으면 그것만 부른다', async () => {
    const writeText = vi.fn(async () => {});
    const { exec } = withExec(true);
    await copyText('Made-up text', {
      navigator: { clipboard: { writeText } } as unknown as Navigator,
      document,
    });
    expect(writeText).toHaveBeenCalledWith('Made-up text');
    expect(exec).not.toHaveBeenCalled();
  });

  it('clipboard 없음 → 숨긴 textarea + execCommand("copy"), 끝나면 textarea 를 걷는다', async () => {
    const { seen } = withExec(true);
    await copyText('Line one\nline two', {
      navigator: {} as Navigator,
      document,
    });
    expect(seen).toEqual(['copy:Line one\nline two']);
    expect(document.querySelector('textarea')).toBeNull();
  });

  it('clipboard 거절 → execCommand 로 · 그것도 false 면 reject', async () => {
    const writeText = vi.fn(async () => {
      throw new Error('denied');
    });
    const { exec } = withExec(true);
    const navigator = { clipboard: { writeText } } as unknown as Navigator;
    await copyText('Fake', { navigator, document });
    expect(exec).toHaveBeenCalledTimes(1);
    withExec(false);
    await expect(copyText('Fake', { navigator, document })).rejects.toThrow();
    expect(document.querySelector('textarea')).toBeNull();
  });
});
