// @vitest-environment jsdom
// RP-01 보고서 프로젝트 목록(밴드 RPW1 ① 시험 S2 — 발주서 §2-1·§2-0 ②③). 진짜 실어댑터 + 가짜 원고작성 서버(목록은 override 로 줄을 심는다).
//   요청 하나(limit 100·offset 0, companyId 0) · 회사 칸 0 · 상태 여덟(글·배지·다음 할 일 글·가는 곳) · 만드는 중 n/m · 「목차 · 초안」 셈(없으면 「—」) ·
//   전년도 보고서 이름(없으면 「전년도 보고서 없음」) · 다음 할 일·줄 누름 → onNext · 상태 탭·보고연도·검색 거르기(화면 안 — 요청 더 0) ·
//   거른 빔 → [거르기 풀기] · 빈 목록(단추 하나) · 불러오지 못함(CM-03) → [다시 시도] · 회사 거절(두 역할 글) · 100 넘음 · 서버 message 0.
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
  fakeDraftingServer,
  json,
  refusal,
  storeOf,
  unreachable,
} from '../../../entities/drafting/api/testing.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import type {
  ProjectRow,
  RunItem,
} from '../../../entities/drafting/model/index.ts';
import { ListScreen } from './ListScreen.tsx';

afterEach(cleanup);
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

const words = DR_TEXT.list;
const LIST = 'GET /drafting/projects';
const flush = () => act(async () => {});

const run = (id: number, patch: Partial<RunItem> = {}): RunItem => ({
  id,
  status: 'done',
  createdAt: '2026-10-20T01:00:00Z',
  finishedAt: '2026-10-20T01:05:00Z',
  outlineId: 201,
  baseRunId: null,
  rebuild: [],
  progress: null,
  rejected: false,
  leaves: { total: 4, drafted: 4, noMaterial: 0, failed: 0, notRun: 0 },
  ...patch,
});
const row = (id: number, patch: Partial<ProjectRow> = {}): ProjectRow => ({
  id,
  name: `지어낸 보고서 ${id}`,
  year: 2026,
  createdAt: '2026-10-19T16:30:00Z',
  hasDocument: true,
  documentName: `지어낸-${id}-전년도.pdf`,
  outlineId: 201,
  outlineRevision: 1,
  latestRun: run(300 + id),
  ...patch,
});

/** 상태 여덟(id 1~8 — 차례대로 no_document … failed). */
const ROWS: ProjectRow[] = [
  row(1, {
    hasDocument: false,
    documentName: null,
    outlineId: null,
    outlineRevision: null,
    latestRun: null,
    year: 2025,
  }),
  row(2, { outlineId: null, outlineRevision: null, latestRun: null }),
  row(3, { latestRun: null }),
  row(4, {
    latestRun: run(304, {
      status: 'processing',
      finishedAt: null,
      progress: { step: 'draft', done: 5, total: 11 },
      rejected: null,
      leaves: null,
    }),
  }),
  row(5),
  row(6, {
    latestRun: run(306, {
      leaves: { total: 8, drafted: 5, noMaterial: 1, failed: 1, notRun: 1 },
    }),
  }),
  row(7, { outlineId: 202, outlineRevision: 2 }),
  row(8, {
    latestRun: run(308, { status: 'failed', rejected: null, leaves: null }),
  }),
];

function setup(
  rows: ProjectRow[] = ROWS,
  { operator = false, count = rows.length } = {},
) {
  const server = fakeDraftingServer();
  server.override[LIST] = () =>
    json(200, { count, isNext: count > rows.length, results: rows });
  const onNew = vi.fn();
  const onNext = vi.fn();
  render(
    <ListScreen
      store={storeOf(server)}
      operator={operator}
      onNew={onNew}
      onNext={onNext}
    />,
  );
  return { server, onNew, onNext };
}

const shown = () =>
  [...document.querySelectorAll('tbody [data-project-id]')].map((node) =>
    Number((node as HTMLElement).dataset.projectId),
  );
const rowOf = (id: number) =>
  document.querySelector(`[data-project-id="${id}"]`)!.closest('tr')!;
const loaded = () => waitFor(() => expect(shown().length).toBeGreaterThan(0));
const tab = (name: string) =>
  fireEvent.mouseDown(screen.getByRole('tab', { name }));
function choose(name: string, option: string) {
  fireEvent.keyDown(screen.getByRole('button', { name }), { key: 'Enter' });
  fireEvent.click(screen.getByRole('menuitemradio', { name: option }));
}

describe('RP-01 목록 — 요청과 칸', () => {
  it('요청 하나 — limit 100 · offset 0, companyId 0', async () => {
    const { server } = setup();
    await loaded();
    const calls = server.calls.filter((c) => `${c.method} ${c.path}` === LIST);
    expect(calls).toHaveLength(1);
    expect(Object.fromEntries(calls[0]!.query)).toEqual({
      limit: '100',
      offset: '0',
    });
    expect(screen.getByText(words.summary(8))).not.toBeNull();
  });

  it('칸 여섯 — 회사 칸 0(§2-0 ②)', async () => {
    setup();
    await loaded();
    const heads = [...document.querySelectorAll('thead th')].map(
      (th) => th.textContent,
    );
    expect(heads).toEqual(Object.values(words.columns));
    expect(heads.some((head) => head?.includes('회사'))).toBe(false);
  });

  it('상태 여덟 — 글·다음 할 일·가는 곳(§2-0 ③)', async () => {
    const { onNext } = setup();
    await loaded();
    const expected = [
      ['no_document', words.states.no_document, { to: 'upload' }],
      ['no_outline', words.states.no_outline, { to: 'outline' }],
      ['no_draft', words.states.no_draft, { to: 'outline' }],
      ['drafting', words.drafting(5, 11), { to: 'run', runId: 304 }],
      ['done', words.states.done, { to: 'run', runId: 305 }],
      ['partial', words.states.partial, { to: 'run', runId: 306 }],
      [
        'outline_changed',
        words.states.outline_changed,
        { to: 'run', runId: 307 },
      ],
      ['failed', words.states.failed, { to: 'run', runId: 308 }],
    ] as const;
    expected.forEach(([state, text, next], index) => {
      const id = index + 1;
      const tr = rowOf(id);
      const cell = within(tr).getByTestId('row-state');
      expect(cell.dataset.state, String(id)).toBe(state);
      expect(cell.textContent).toBe(text);
      const button = tr.querySelector<HTMLElement>('[data-next]')!;
      expect(button.textContent).toBe(words.next[state]);
      fireEvent.click(button);
      expect(onNext).toHaveBeenLastCalledWith(id, next);
    });
    expect(onNext).toHaveBeenCalledTimes(8);
  });

  it('「목차 · 초안」 — 잎 셈이 있으면 「m개 중 n개」, 없으면 「—」 · 전년도 보고서 이름', async () => {
    setup();
    await loaded();
    const leaves = (id: number) =>
      within(rowOf(id)).getByTestId('row-leaves').textContent;
    expect(leaves(5)).toBe(words.leaves(4, 4));
    expect(leaves(6)).toBe(words.leaves(5, 8));
    expect(leaves(1)).toBe(words.noLeaves);
    // 만드는 중 초안 단계 = 그 단계의 처리 수(RPW2 ⑧ — 「11개 중 5개」).
    expect(leaves(4)).toBe('11개 중 5개');
    expect(within(rowOf(1)).getByTestId('document-name').textContent).toBe(
      words.noDocumentName,
    );
    expect(within(rowOf(5)).getByTestId('document-name').textContent).toBe(
      '지어낸-5-전년도.pdf',
    );
  });

  it('만든 날은 한국 날짜(UTC 16:30 → 다음 날)', async () => {
    setup([row(1)]);
    await loaded();
    expect(rowOf(1).textContent).toContain('2026-10-20');
  });

  it('줄 누름도 「다음 할 일」 자리로', async () => {
    const { onNext } = setup();
    await loaded();
    fireEvent.click(rowOf(2));
    expect(onNext).toHaveBeenLastCalledWith(2, { to: 'outline' });
  });
});

describe('RP-01 목록 — 거르기(화면 안)', () => {
  it('상태 탭 — 준비 중·만드는 중·초안 완료·실패, 요청은 더 없다', async () => {
    const { server } = setup();
    await loaded();
    tab(words.filters.preparing);
    await waitFor(() => expect(shown()).toEqual([1, 2, 3]));
    tab(words.filters.drafting);
    await waitFor(() => expect(shown()).toEqual([4]));
    tab(words.filters.done);
    await waitFor(() => expect(shown()).toEqual([5, 6, 7]));
    tab(words.filters.failed);
    await waitFor(() => expect(shown()).toEqual([8]));
    expect(server.count(LIST)).toBe(1);
  });

  it('보고연도 — 줄에 있는 해만(큰 해 먼저)', async () => {
    setup();
    await loaded();
    choose(words.yearLabel, words.yearOption(2025));
    await waitFor(() => expect(shown()).toEqual([1]));
  });

  it('검색 — 이름·전년도 보고서 파일 이름', async () => {
    setup();
    await loaded();
    fireEvent.change(screen.getByLabelText(words.search), {
      target: { value: '지어낸-6-' },
    });
    await waitFor(() => expect(shown()).toEqual([6]));
  });

  it('거른 빔 → 「조건에 맞는 프로젝트가 없어요」 + [거르기 풀기]', async () => {
    setup([row(5)]);
    await loaded();
    tab(words.filters.failed);
    const empty = await screen.findByTestId('list-empty-filtered');
    expect(empty.textContent).toContain(words.filteredEmpty);
    fireEvent.click(
      within(empty).getByRole('button', { name: words.clearFilter }),
    );
    await waitFor(() => expect(shown()).toEqual([5]));
  });
});

describe('RP-01 목록 — 빈·실패·거절', () => {
  it('빈 목록 — 빈 글 + [새 프로젝트] 하나', async () => {
    const { onNew } = setup([]);
    const empty = await screen.findByTestId('list-empty');
    expect(empty.textContent).toContain(words.empty);
    const buttons = screen.getAllByRole('button', { name: words.newProject });
    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]!);
    expect(onNew).toHaveBeenCalledOnce();
  });

  it('목록을 불러오지 못함(CM-03) → [다시 시도] 로 다시 읽음', async () => {
    const server = fakeDraftingServer();
    server.override[LIST] = [unreachable];
    render(
      <ListScreen
        store={storeOf(server)}
        operator={false}
        onNew={() => {}}
        onNext={() => {}}
      />,
    );
    await screen.findByText(words.failed);
    fireEvent.click(screen.getByRole('button', { name: DR_TEXT.common.retry }));
    await waitFor(() => expect(server.count(LIST)).toBe(2));
    await screen.findByTestId('list-empty');
  });

  it.each([
    [false, DR_TEXT.company.inactive],
    [true, DR_TEXT.companyOperator.inactive],
  ])(
    '회사 거절(운영 관리자 %s) → 회사 글 한 줄 · 서버 message 0',
    async (operator, text) => {
      const server = fakeDraftingServer({ company: 'COMPANY_INACTIVE' });
      render(
        <ListScreen
          store={storeOf(server)}
          operator={operator}
          onNew={() => {}}
          onNext={() => {}}
        />,
      );
      const alert = await screen.findByTestId('company-refusal');
      expect(alert.textContent).toBe(text);
      expect(document.body.textContent).not.toContain('지어낸-서버글');
    },
  );

  it('500 거절의 서버 message 는 싣지 않는다', async () => {
    const server = fakeDraftingServer();
    server.override[LIST] = () => refusal(500, 'INTERNAL_ERROR');
    render(
      <ListScreen
        store={storeOf(server)}
        operator={false}
        onNew={() => {}}
        onNext={() => {}}
      />,
    );
    await screen.findByText(words.failed);
    await flush();
    expect(document.body.textContent).not.toContain('지어낸-서버글');
  });

  it('count 가 받은 줄보다 많으면 「최근 100건만 보여요」', async () => {
    setup([row(1)], { count: 140 });
    await loaded();
    expect(screen.getByTestId('list-more').textContent).toBe(words.more);
  });
});

describe('RPW5 #1·#2·#3 목록 — 검색 칸 폭 · 카드 안 안내 상자 · 숨긴 상태 글', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('검색 칸 w-[300px](다른 모듈 목록과 같은 폭)', async () => {
    setup();
    await loaded();
    const search = screen.getByRole('textbox', { name: words.search });
    expect(search.closest('.w-\\[300px\\]')).not.toBeNull();
    expect(document.querySelector('.w-52')).toBeNull();
  });

  it('표 카드 안 맨 아래 안내 상자 = 판 RP-01 글', async () => {
    setup();
    await loaded();
    const notice = screen.getByTestId('list-notice');
    expect(notice.textContent).toBe(words.notice);
    const card = notice.parentElement!;
    expect(card.contains(screen.getByRole('table'))).toBe(true);
    expect(card.lastElementChild).toBe(notice);
  });

  it('숨긴 role="status" 는 처음부터 있고 299ms 빈 글 / 300ms 「불러오는 중」 → 받으면 빈 글(같은 마디)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const server = fakeDraftingServer();
    let open!: () => void;
    const gate = new Promise<void>((resolve) => (open = resolve));
    server.override[LIST] = () =>
      gate.then(() =>
        json(200, { count: 1, isNext: false, results: [ROWS[0]] }),
      );
    render(
      <ListScreen
        store={storeOf(server)}
        operator={false}
        onNew={vi.fn()}
        onNext={vi.fn()}
      />,
    );
    await flush();
    const live = screen.getByRole('status');
    expect(live.className).toContain('sr-only');
    expect(live.textContent).toBe('');
    act(() => vi.advanceTimersByTime(299));
    expect(live.textContent).toBe('');
    act(() => vi.advanceTimersByTime(1));
    expect(live.textContent).toBe(DR_TEXT.common.loading);
    await act(async () => open());
    await flush();
    expect(live.isConnected).toBe(true);
    expect(live.textContent).toBe('');
    expect(shown()).toEqual([ROWS[0]!.id]);
  });
});

// 밴드 RPW6(sid:MARC-ENT-530): 머리 오른쪽 「작성 안내」 링크 — 판 RP-01 g-title 의 g-small 링크. onIntro 를 받을 때만,
//   목록 상태와 상관없이(채움·빔·회사 거절) 늘 보인다. 눌러도 목록 요청은 더 없다. 빈 목록은 안내로 넘기지 않는다.
describe('RPW6 목록 — 「작성 안내」 링크', () => {
  function drawWith(server: ReturnType<typeof fakeDraftingServer>) {
    const onIntro = vi.fn();
    const onNew = vi.fn();
    const onNext = vi.fn();
    render(
      <ListScreen
        store={storeOf(server)}
        operator={false}
        onNew={onNew}
        onNext={onNext}
        onIntro={onIntro}
      />,
    );
    return { onIntro, onNew, onNext };
  }

  it('채운 목록: 제목 줄 링크 「작성 안내」(href /drafting/intro) → onIntro 한 번 · 목록 요청 더 0', async () => {
    const server = fakeDraftingServer();
    server.override[LIST] = () =>
      json(200, { count: ROWS.length, isNext: false, results: ROWS });
    const { onIntro, onNew, onNext } = drawWith(server);
    await loaded();
    const link = screen.getByRole('link', { name: '작성 안내' });
    expect(link.getAttribute('href')).toBe('/drafting/intro');
    // 제목(h2) 과 같은 머리 줄(화면의 첫 자식) 안이다.
    const head = document.querySelector(
      '[data-screen="drafting-list"]',
    )!.firstElementChild!;
    expect(head.querySelector('h2')!.textContent).toBe(words.title);
    expect(head.contains(link)).toBe(true);
    const before = server.count(LIST);
    fireEvent.click(link);
    expect(onIntro).toHaveBeenCalledOnce();
    expect(onNew).not.toHaveBeenCalled();
    expect(onNext).not.toHaveBeenCalled();
    await flush();
    expect(server.count(LIST)).toBe(before);
  });

  it('빈 목록: 링크는 그대로 · 스스로 안내로 넘기지 않는다(onIntro 0)', async () => {
    const server = fakeDraftingServer();
    server.override[LIST] = () =>
      json(200, { count: 0, isNext: false, results: [] });
    const { onIntro } = drawWith(server);
    await screen.findByTestId('list-empty');
    await flush();
    expect(screen.getByRole('link', { name: '작성 안내' })).toBeTruthy();
    expect(onIntro).not.toHaveBeenCalled();
  });

  it('회사 거절: 링크는 그대로', async () => {
    drawWith(fakeDraftingServer({ company: 'COMPANY_INACTIVE' }));
    await screen.findByTestId('company-refusal');
    expect(screen.getByRole('link', { name: '작성 안내' })).toBeTruthy();
  });

  it('onIntro 가 없으면 링크 0', async () => {
    setup();
    await loaded();
    expect(screen.queryByRole('link', { name: '작성 안내' })).toBeNull();
  });
});
