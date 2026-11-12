// @vitest-environment jsdom
// 밴드 LE1 ②: GW-01 문서 목록의 불러오기·오류 꼴(sid:MARC-ENT-260 ①②). 밴드 GL1(sid:MARC-ENT-443 ②③)이 첫 그림 꼴을 고침:
//   - 미룬 목록: 첫 그림부터 aria-busy 표(머리줄 + 자리 잡은 줄 5)·설명 막대 자리, 299ms 까지 막대 0, 300ms 에 막대와 숨긴 글
//     (라이브 영역은 처음부터, 글만 넣고 뺀다 — LA1 ①). 받으면 줄 자리가 진짜 줄로, 설명 막대가 설명으로.
//     300ms 안에 끝나면 막대도 빈 목록 글도 그린 적이 없다.
//   - 실패: 빈 목록 글 대신 「문서 목록을 불러오지 못했어요」 + [다시 시도](목록 화면이라 [목록으로] 없음) → 누르면 다시 읽어 줄이 보인다.
// 밴드 LA1 ②: [다시 시도] 뒤 초점 — 첫 실패에서는 옮기지 않고, 또 실패면 새 [다시 시도], 받으면 제목 줄 h2.
// 가짜 시계는 setTimeout·clearTimeout 만 바꾼다(약속·React 의 effect 는 진짜로 돈다 — 응답은 act 안에서 끝낸다).
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  deferredCalls,
  fakeStore,
} from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { CheckRowsSource } from '../../../entities/greenwash/model/index.ts';
import { ListScreen } from './ListScreen.tsx';

const words = GW_TEXT.list;

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
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const SOURCE: CheckRowsSource = {
  currentUserId: 'me',
  companyName: '회사',
  documents: [
    {
      documentId: 'd1',
      fileName: '가상 보고서.pdf',
      reportYear: 2026,
      previousDocumentId: null,
      pageCount: 12,
      uploadedAt: '2026-10-01T09:00:00+09:00',
      uploadedBy: { userId: 'me', name: '나' },
    },
  ],
  runs: [],
};

/** operator: 설명 줄(작업 회사)은 운영 관리자에게만 있다(시안 댓글 — sid:MARC-ENT-603). 설명 막대 자리도 그때만. */
function renderList(operator = false) {
  const list = deferredCalls<CheckRowsSource>();
  const store = fakeStore({ listCheckRows: list.fn });
  const view = render(
    <ListScreen
      store={store}
      onOpen={vi.fn()}
      onNewCheck={vi.fn()}
      operator={operator}
    />,
  );
  return { list, view };
}

const table = () => screen.queryByRole('table', { name: words.tableLabel });
// 표는 첫 그림부터 있다(머리줄 + 자리 잡은 줄 — sid:MARC-ISSUE-316, 밴드 GL1). 읽는 동안 내내 aria-busy.
const busy = () => table()?.getAttribute('aria-busy') === 'true';
const skeletonRows = () => document.querySelectorAll('[data-skeleton-row]');
// 표 줄의 막대만(설명 자리 막대는 descriptionPending 으로 따로 본다)
const bars = () =>
  document.querySelectorAll('[data-skeleton-row] [data-skeleton-bar]');
const descriptionPending = () =>
  document.querySelector('[data-testid="description-pending"]');

/** 그려진 적이 있는가(지금 없어도): 더해진 마디의 글자와 aria-busy 바뀜을 적는다. */
function watch(root: HTMLElement) {
  const seen = { busy: false, bars: false, texts: [] as string[] };
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (
        record.type === 'attributes' &&
        (record.target as Element).getAttribute('aria-busy') === 'true'
      )
        seen.busy = true;
      record.addedNodes.forEach((node) => {
        seen.texts.push(node.textContent ?? '');
        if (
          node instanceof Element &&
          (node.matches('[data-skeleton-row] [data-skeleton-bar]') ||
            node.querySelector('[data-skeleton-row] [data-skeleton-bar]') !==
              null)
        )
          seen.bars = true;
      });
    }
  });
  observer.observe(root, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ['aria-busy'],
  });
  return { seen, observer };
}

describe('GW-01 불러오기·오류 꼴(밴드 LE1)', () => {
  it('미룬 목록(운영 관리자): 첫 그림부터 aria-busy 표(머리줄 + 줄 자리 5)·설명 막대 자리, 299ms 까지 막대 0, 300ms 에 막대와 숨긴 글. 빈 목록 글은 없다', async () => {
    const { list } = renderList(true);
    // 숨긴 글의 라이브 영역은 처음부터 있고(빈 글) 같은 마디에 글만 들어간다(밴드 LA1 ①)
    const live = screen.getByRole('status');
    expect(live.textContent).toBe('');
    // 316·GL1: 첫 그림부터 머리줄과 자리 잡은 줄(막대는 아직), 설명 줄 자리
    expect(busy()).toBe(true);
    expect(screen.getAllByRole('columnheader').length).toBeGreaterThan(0);
    expect(skeletonRows()).toHaveLength(5);
    expect(bars()).toHaveLength(0);
    expect(descriptionPending()).not.toBeNull();
    act(() => vi.advanceTimersByTime(299));
    expect(busy()).toBe(true);
    expect(bars()).toHaveLength(0);
    expect(screen.queryByText(words.loading)).toBeNull();
    expect(screen.queryByText(words.emptyTitle)).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    expect(busy()).toBe(true);
    expect(bars().length).toBeGreaterThan(0);
    expect(screen.getByRole('status')).toBe(live);
    expect(live.textContent).toBe(words.loading);
    expect(screen.queryByText(words.emptyTitle)).toBeNull();
    await act(async () => list.calls[0]!.resolve(SOURCE));
    expect(busy()).toBe(false);
    expect(screen.queryByText(words.loading)).toBeNull();
    expect(screen.getByRole('status')).toBe(live);
    expect(screen.getByText('가상 보고서.pdf')).toBeTruthy();
    expect(skeletonRows()).toHaveLength(0);
    expect(descriptionPending()).toBeNull();
    expect(screen.getByText(words.metaOperator('회사'))).toBeTruthy();
  });

  it('고객사 사용자: 설명 줄이 없다 — 읽는 동안 설명 막대 자리도, 받은 뒤 「문서 n건 · 실행 n회」 줄도 없다(시안 댓글 — sid:MARC-ENT-603)', async () => {
    const { list } = renderList();
    expect(busy()).toBe(true);
    expect(descriptionPending()).toBeNull();
    await act(async () => list.calls[0]!.resolve(SOURCE));
    expect(busy()).toBe(false);
    expect(screen.getByText('가상 보고서.pdf')).toBeTruthy();
    expect(descriptionPending()).toBeNull();
    expect(screen.queryByText(/문서 \d+건|실행 \d+회|작업 회사/)).toBeNull();
  });

  it('300ms 안에 끝나면 막대도 숨긴 글도 빈 목록 글도 그린 적이 없다(줄 자리만 — 빈 목록이 와도 그때 처음 빈 글)', async () => {
    const { list, view } = renderList();
    const watcher = watch(view.container);
    // 첫 그림부터 바쁜 표(줄 자리만, 막대 0 — 밴드 GL1)
    expect(busy()).toBe(true);
    expect(bars()).toHaveLength(0);
    expect(view.container.textContent).not.toContain(words.emptyTitle);
    act(() => vi.advanceTimersByTime(200));
    await act(async () => list.calls[0]!.resolve({ ...SOURCE, documents: [] }));
    act(() => vi.advanceTimersByTime(500));
    // 남은 기록까지 받는다
    const records = watcher.observer.takeRecords();
    for (const record of records)
      record.addedNodes.forEach((node) =>
        watcher.seen.texts.push(node.textContent ?? ''),
      );
    watcher.observer.disconnect();
    expect(watcher.seen.bars).toBe(false);
    expect(watcher.seen.texts.join('|')).not.toContain(words.loading);
    // 읽은 뒤에야 빈 목록 글
    expect(screen.getByText(words.emptyTitle)).toBeTruthy();
  });

  it('실패: 빈 목록 글 대신 실패 상자(글 + [다시 시도], [목록으로] 없음) → 누르면 다시 읽어 줄이 보인다', async () => {
    const { list } = renderList();
    await act(async () => list.calls[0]!.reject(new Error('망')));
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain(words.loadFailed);
    expect(screen.queryByText(words.emptyTitle)).toBeNull();
    expect(
      screen.queryByRole('button', { name: GW_TEXT.load.toList }),
    ).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    expect(list.fn).toHaveBeenCalledTimes(2);
    // 다시 읽는 동안은 실패 상자가 사라지고 첫 불러오기와 같은 꼴(바쁜 표 + 줄 자리, 300ms 전이라 막대는 아직 — 밴드 GL1)
    expect(screen.queryByRole('alert')).toBeNull();
    expect(busy()).toBe(true);
    expect(skeletonRows()).toHaveLength(5);
    expect(bars()).toHaveLength(0);
    await act(async () => list.calls[1]!.resolve(SOURCE));
    expect(screen.getByText('가상 보고서.pdf')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('다시 시도 뒤 또 실패: loading(300ms 뒤 스켈레톤)을 거쳐 같은 글의 상자를 새로 그린다', async () => {
    const { list } = renderList();
    await act(async () => list.calls[0]!.reject(new Error('망')));
    const first = screen.getByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.retry }));
    act(() => vi.advanceTimersByTime(300));
    expect(busy()).toBe(true);
    await act(async () => list.calls[1]!.reject(new Error('또 망')));
    const second = screen.getByRole('alert');
    expect(second).not.toBe(first);
    expect(second.textContent).toBe(first.textContent);
  });

  it('LA1 ② 초점: 첫 실패에서는 body 그대로 → [다시 시도] → 또 실패면 새 [다시 시도] → [다시 시도] → 받으면 제목 줄 h2', async () => {
    const { list } = renderList();
    await act(async () => list.calls[0]!.reject(new Error('망')));
    expect(document.activeElement).toBe(document.body);
    const first = screen.getByRole('button', { name: GW_TEXT.load.retry });
    fireEvent.click(first);
    await act(async () => list.calls[1]!.reject(new Error('또 망')));
    const second = screen.getByRole('button', { name: GW_TEXT.load.retry });
    expect(second).not.toBe(first);
    expect(document.activeElement).toBe(second);
    fireEvent.click(second);
    await act(async () => list.calls[2]!.resolve(SOURCE));
    expect(screen.getByText('가상 보고서.pdf')).toBeTruthy();
    expect(document.activeElement).toBe(
      screen.getByRole('heading', { level: 2, name: words.title }),
    );
  });
});

// 밴드 GL3(sid:MARC-ISSUE-397·374): 표 자리는 머리줄 + 줄 5 만큼 최소 높이(줄이 적게 와도 아래 안내 띠가 올라오지 않는다 —
// jsdom 은 높이를 재지 못해 같은 마디·같은 최소 높이 클래스를 본다, 잰 값은 e2e greenwash-server.spec.ts 「목록 첫 불러오기」).
// 표는 layout fixed — 로딩·빈·진짜 줄이 같은 colgroup(짧은 칸 폭, 문서명은 남은 폭)을 쓴다.
const COL_WIDTHS = [
  '',
  '80px',
  '115px',
  '84px',
  '153px',
  '62px',
  '66px',
  '66px',
  '149px',
  '122px',
];
const area = () => screen.getByTestId('list-table-area');
const colWidths = () =>
  Array.from(document.querySelectorAll('table colgroup col')).map(
    (col) => (col as HTMLElement).style.width,
  );
const sourceOf = (count: number): CheckRowsSource => ({
  ...SOURCE,
  documents: Array.from({ length: count }, (_, index) => ({
    ...SOURCE.documents[0]!,
    documentId: `d${index + 1}`,
    fileName: `가상 보고서 ${index + 1}.pdf`,
  })),
});

describe('GW-01 표 자리 최소 높이·열 폭(밴드 GL3)', () => {
  it('로딩 중과 줄 2개 받은 뒤: 같은 표 자리 마디에 같은 최소 높이(머리줄 + 줄 5 = 321), 줄은 2개뿐(빈 줄 선·글 없음)', async () => {
    const { list } = renderList();
    const loadingArea = area();
    expect(loadingArea.className).toContain('min-h-[321px]');
    expect(loadingArea.contains(table())).toBe(true);
    expect(skeletonRows()).toHaveLength(5);
    await act(async () => list.calls[0]!.resolve(sourceOf(2)));
    expect(area()).toBe(loadingArea);
    expect(area().className).toContain('min-h-[321px]');
    expect(table()!.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(skeletonRows()).toHaveLength(0);
  });

  it('줄 7개면 줄 7개를 다 그린다 — 최소 높이일 뿐 높이를 박거나 자르지 않는다', async () => {
    const { list } = renderList();
    await act(async () => list.calls[0]!.resolve(sourceOf(7)));
    expect(table()!.querySelectorAll('tbody tr')).toHaveLength(7);
    const classes = area().className.split(/\s+/);
    expect(classes).toContain('min-h-[321px]');
    expect(
      classes.filter((name) => /^(h|max-h)-|overflow-(hidden|y)/.test(name)),
    ).toEqual([]);
  });

  it('빈 상태: 빈 목록 글(Empty)이 표 자리 안 한 칸 줄에 그대로, 최소 높이 같음', async () => {
    const { list } = renderList();
    await act(async () => list.calls[0]!.resolve({ ...SOURCE, documents: [] }));
    const empty = screen.getByText(words.emptyTitle);
    expect(area().contains(empty)).toBe(true);
    expect(area().className).toContain('min-h-[321px]');
    expect(table()!.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(empty.parentElement!.className).toContain('min-h-[200px]');
  });

  it('문서명 칸: 한 줄 말줄임(truncate) + title 에 전체 이름(6c 답)', async () => {
    const { list } = renderList();
    await act(async () => list.calls[0]!.resolve(sourceOf(1)));
    const name = screen.getByText('가상 보고서 1.pdf');
    expect(name.className).toContain('truncate');
    expect(name.getAttribute('title')).toBe('가상 보고서 1.pdf');
  });

  it('칸 폭: 표는 table-fixed + colgroup, 로딩·받은 뒤 같은 폭(문서명만 폭 없음)', async () => {
    const { list } = renderList();
    expect(table()!.className).toContain('table-fixed');
    expect(colWidths()).toEqual(COL_WIDTHS);
    await act(async () => list.calls[0]!.resolve(sourceOf(2)));
    expect(table()!.className).toContain('table-fixed');
    expect(colWidths()).toEqual(COL_WIDTHS);
  });
});
