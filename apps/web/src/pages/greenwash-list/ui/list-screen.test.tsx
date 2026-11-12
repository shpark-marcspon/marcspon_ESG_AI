// @vitest-environment jsdom
// 밴드 FW2 ②: GW-01 문서 목록 화면. 줄 안 버튼은 줄 누르기를 일으키지 않는다(sid:MARC-ISSUE-85 1), 줄 누르기·다음 할 일의 갈 곳,
// 누를 수 있는 줄의 이름, [다시 실행] 거절 안내, 확정 잠금 표시, 버전 글. 글자는 문구 표(GW_TEXT) 값으로 단언한다.
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

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { fakeStore } from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type {
  CheckRowsSource,
  ListedDocument,
  ListedRun,
} from '../../../entities/greenwash/model/index.ts';
// 위험 라벨은 화면이 그리는 값 하나(RiskBadge 의 글자 = PARTS_TEXT.risk)로 단언한다 — 그린워싱 칸은 shared/ui/text.ts 를 못 가져온다(sid:MARC-ISSUE-308).
import { RISK_BADGE_LOOK } from '../../../shared/ui/risk-badge/index.ts';
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

const words = GW_TEXT.list;

const doc = (
  documentId: string,
  extra: Partial<ListedDocument> = {},
): ListedDocument => ({
  documentId,
  fileName: `${documentId}.pdf`,
  reportYear: 2026,
  previousDocumentId: null,
  pageCount: 12,
  uploadedAt: '2026-10-01T09:00:00+09:00',
  uploadedBy: { userId: 'me', name: '나' },
  ...extra,
});
const counts = { High: 1, Mid: 2, Low: 3 };
const SOURCE: CheckRowsSource = {
  currentUserId: 'me',
  companyName: '회사',
  documents: [
    doc('검토중'),
    doc('실패'),
    doc('확정'),
    doc('앞판'),
    doc('수정본', { previousDocumentId: '앞판' }),
  ],
  runs: [
    {
      runId: 'r1',
      documentId: '검토중',
      createdAt: '2026-10-05T09:00:00+09:00',
      finishedAt: '2026-10-05T15:30:00Z',
      progress: {
        state: 'done',
        stage: 'summarize',
        judge: { done: 2, total: 2 },
      },
      levelCounts: counts,
      review: {
        state: 'in_review',
        reviewed: 1,
        total: 6,
        confirmedAt: null,
        confirmedBy: null,
      },
    },
    {
      runId: 'r2',
      documentId: '실패',
      createdAt: '2026-10-04T09:00:00+09:00',
      finishedAt: '2026-10-04T09:10:00+09:00',
      progress: {
        state: 'failed',
        stage: 'judge',
        judge: { done: 1, total: 2 },
      },
      levelCounts: null,
      review: null,
    },
    {
      runId: 'r3',
      documentId: '확정',
      createdAt: '2026-10-03T09:00:00+09:00',
      finishedAt: '2026-10-03T09:20:00+09:00',
      progress: {
        state: 'done',
        stage: 'summarize',
        judge: { done: 2, total: 2 },
      },
      levelCounts: counts,
      review: {
        state: 'confirmed',
        reviewed: 6,
        total: 6,
        confirmedAt: '2026-10-06T06:00:00Z',
        confirmedBy: '남',
      },
    },
    {
      runId: 'r4',
      documentId: '수정본',
      createdAt: '2026-10-02T09:00:00+09:00',
      finishedAt: '2026-10-02T09:20:00+09:00',
      progress: {
        state: 'done',
        stage: 'summarize',
        judge: { done: 2, total: 2 },
      },
      levelCounts: counts,
      review: {
        state: 'pending',
        reviewed: 0,
        total: 6,
        confirmedAt: null,
        confirmedBy: null,
      },
    },
  ] satisfies ListedRun[],
};

function listStore(rerun?: GreenwashStore['rerun']): GreenwashStore {
  return fakeStore({
    listCheckRows: vi.fn(async () => SOURCE),
    ...(rerun && { rerun }),
  });
}

async function renderList(store = listStore()) {
  const onOpen = vi.fn();
  const onNewCheck = vi.fn();
  render(<ListScreen store={store} onOpen={onOpen} onNewCheck={onNewCheck} />);
  // 고객사 사용자는 설명 줄이 없다(sid:MARC-ENT-603) — 받은 뒤 그려지는 안내 상자와 바쁘지 않은 표로 기다린다
  await waitFor(() =>
    expect(
      screen
        .getByRole('table', { name: words.tableLabel })
        .getAttribute('aria-busy'),
    ).not.toBe('true'),
  );
  return { onOpen, onNewCheck };
}

const rowOf = (name: string) =>
  screen.getAllByRole('row').find((row) => row.textContent?.includes(name))!;

describe('GW-01 문서 목록', () => {
  it('줄 넷(앞 판은 줄이 없다), 버전 칸 없음(v115 — 밴드 GW2R ①), 확정 잠금 표시(한국 시각 MM-DD + 이름), 없는 칸은 –', async () => {
    await renderList();
    const table = screen.getByRole('table', { name: words.tableLabel });
    expect(within(table).getAllByRole('row')).toHaveLength(5);
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((th) => th.textContent),
    ).not.toContain('버전');
    expect(table.textContent).not.toMatch(/v\d 수정본|최초본|이전 버전/);
    expect(rowOf('확정.pdf').textContent).toContain('10-06');
    expect(rowOf('확정.pdf').textContent).toContain('남');
    expect(rowOf('실패.pdf').textContent).toContain(words.none);
    expect(table.textContent).not.toContain('앞판.pdf');
  });

  it('탭 여섯 글자·차례(시안 댓글 1차 반영 — sid:MARC-ENT-603, 멈춤은 맨 끝 별도 탭)와 멈춘 줄 배지 「멈춤」(디자인 답 D6)', async () => {
    await renderList();
    expect(
      within(screen.getByRole('tablist', { name: words.tabsLabel }))
        .getAllByRole('tab')
        .map((tab) => tab.textContent),
    ).toEqual([
      '전체',
      'AI 점검 중',
      '검토 대기',
      '검토 중',
      '검토 완료',
      '멈춤',
    ]);
    expect(
      within(rowOf('실패.pdf')).getByTestId('row-status').textContent,
    ).toBe('멈춤');
  });

  it('열 머리 「담당자」·「AI점검 완료 일자」, 그 칸은 날짜만(YYYY-MM-DD, 한국 시각), 검토 중 배지는 셈 없이 「검토 중」(시안 댓글 — sid:MARC-ENT-603)', async () => {
    await renderList();
    const headers = screen
      .getAllByRole('columnheader')
      .map((header) => header.textContent);
    expect(headers).toContain('담당자');
    expect(headers).toContain('AI점검 완료 일자');
    expect(headers).not.toContain('올린 사람');
    expect(headers).not.toContain('마지막 실행');
    const reviewing = rowOf('검토중.pdf');
    // 마지막 실행이 끝난 때(checks@1 runs[].finishedAt — GCB1)의 한국 날짜, 시각은 뺀다. 만든 때(10-05)가 아니다 —
    // 끝난 때 10-05T15:30Z 는 한국 시각으로 자정을 넘긴 10-06
    expect(reviewing.textContent).toContain('2026-10-06');
    expect(reviewing.textContent).not.toContain('2026-10-05');
    expect(reviewing.textContent).not.toMatch(/2026-10-06 \d{2}:\d{2}/);
    expect(rowOf('확정.pdf').textContent).toContain('2026-10-03');
    // 실패한 마지막 실행은 끝난 때가 있어도 「–」(완료 일자 — 감독 Q-A1 (나))
    expect(rowOf('실패.pdf').textContent).not.toContain('2026-10-04');
    expect(within(reviewing).getByTestId('row-status').textContent).toBe(
      '검토 중',
    );
    expect(
      within(rowOf('수정본.pdf')).getByTestId('row-status').textContent,
    ).toBe('검토 대기');
  });

  it('AI점검 완료 일자: 도는 중이거나 끝난 때가 없는 마지막 실행은 「–」(GCB1 — 감독 Q-A1 (나))', async () => {
    const done = SOURCE.runs[0]!;
    const source: CheckRowsSource = {
      ...SOURCE,
      documents: [doc('도는중'), doc('옛서버')],
      runs: [
        {
          ...done,
          runId: 'r8',
          documentId: '도는중',
          createdAt: '2026-10-07T09:00:00+09:00',
          finishedAt: null,
          progress: {
            state: 'running',
            stage: 'judge',
            judge: { done: 1, total: 2 },
          },
          levelCounts: null,
          review: null,
        },
        {
          // finishedAt 칸이 없는 옛 서버의 끝난 실행
          runId: 'r9',
          documentId: '옛서버',
          createdAt: '2026-10-08T09:00:00+09:00',
          progress: done.progress,
          levelCounts: done.levelCounts,
          review: done.review,
        },
      ],
    };
    await renderList(fakeStore({ listCheckRows: vi.fn(async () => source) }));
    const lastRun = screen
      .getAllByRole('columnheader')
      .findIndex((header) => header.textContent === 'AI점검 완료 일자');
    expect(lastRun).toBeGreaterThan(-1);
    for (const name of ['도는중.pdf', '옛서버.pdf'])
      expect(
        within(rowOf(name)).getAllByRole('cell')[lastRun]!.textContent,
      ).toBe(words.none);
  });

  it('High·Mid·Low 칸은 숫자만 든 등급 칩(열 머리가 등급 이름이다. 디자인 대조 C7)', async () => {
    await renderList();
    const row = rowOf('검토중.pdf');
    expect(
      ['count-high', 'count-mid', 'count-low'].map(
        (id) => within(row).getByTestId(id).textContent,
      ),
    ).toEqual(['1', '2', '3']);
    expect(within(row).getByTestId('count-high').textContent).not.toContain(
      RISK_BADGE_LOOK.high.label,
    );
  });

  it('줄 안 [다음 할 일]은 줄 누르기를 일으키지 않는다. 줄 누르기는 결과 → GW-04, 실패 → GW-03', async () => {
    const { onOpen } = await renderList();
    fireEvent.click(
      within(rowOf('검토중.pdf')).getByRole('button', {
        name: words.next.continue_review,
      }),
    );
    expect(onOpen.mock.calls).toEqual([[{ screen: 'review', runId: 'r1' }]]);
    onOpen.mockClear();
    fireEvent.click(within(rowOf('검토중.pdf')).getAllByRole('cell')[0]!);
    fireEvent.keyDown(rowOf('실패.pdf'), { key: 'Enter' });
    fireEvent.click(
      within(rowOf('확정.pdf')).getByRole('button', {
        name: words.next.view_result,
      }),
    );
    expect(onOpen.mock.calls).toEqual([
      [{ screen: 'result', runId: 'r1' }],
      [{ screen: 'status', runId: 'r2' }],
      [{ screen: 'review', runId: 'r3' }],
    ]);
  });

  it('누를 수 있는 줄에는 이름 단서가 있다', async () => {
    await renderList();
    expect(
      screen.getByRole('row', {
        name: words.rowLabel('검토중.pdf', words.rowOpen.result),
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole('row', {
        name: words.rowLabel('실패.pdf', words.rowOpen.status),
      }),
    ).toBeTruthy();
  });

  it('[다시 실행]: 받으면 새 실행의 GW-03, 거절되면 role="alert" 안내', async () => {
    const rerun = vi
      .fn<GreenwashStore['rerun']>()
      .mockRejectedValueOnce(new StoreError('rejected', '안 됨'))
      .mockResolvedValueOnce({ runId: 'r9' });
    const { onOpen } = await renderList(listStore(rerun));
    const button = () =>
      within(rowOf('실패.pdf')).getByRole('button', { name: words.next.rerun });
    await act(async () => {
      fireEvent.click(button());
    });
    expect(screen.getByTestId('list-rerun-error').getAttribute('role')).toBe(
      'alert',
    );
    expect(onOpen).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.click(button());
    });
    expect(onOpen).toHaveBeenCalledWith({ screen: 'status', runId: 'r9' });
    expect(screen.queryByTestId('list-rerun-error')).toBeNull();
  });

  it('[다시 실행]을 빨리 두 번 눌러도 새 실행은 하나: 도는 동안 aria-disabled·aria-busy, 두 번째 누름은 저장소를 부르지 않는다', async () => {
    let release: (value: { runId: string }) => void = () => {};
    const rerun = vi.fn<GreenwashStore['rerun']>(
      () =>
        new Promise((resolve) => {
          release = resolve;
        }),
    );
    const { onOpen } = await renderList(listStore(rerun));
    // 열 정의를 그릴 때마다 지어 칸이 새로 그려진다 — 버튼은 누를 때마다 다시 찾는다
    const button = () =>
      rowOf('실패.pdf').querySelector<HTMLButtonElement>(
        'button[data-next="rerun"]',
      )!;
    await act(async () => {
      fireEvent.click(button());
    });
    expect(button().getAttribute('aria-disabled')).toBe('true');
    expect(button().getAttribute('aria-busy')).toBe('true');
    await act(async () => {
      fireEvent.click(button());
    });
    expect(rerun).toHaveBeenCalledTimes(1);
    await act(async () => {
      release({ runId: 'r9' });
    });
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith({ screen: 'status', runId: 'r9' });
  });

  it('[다시 실행] 끊김(unreachable, 밴드 GR1·GR2): e9 글 + [새로 불러오기](목록 다시 읽기), 그 줄 [다시 실행]은 켜진 채 다시 누르면 같은 열쇠로 보낸다', async () => {
    const rerun = vi
      .fn<GreenwashStore['rerun']>()
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'))
      .mockResolvedValueOnce({ runId: 'r9' });
    const store = listStore(rerun);
    const { onOpen } = await renderList(store);
    const button = () =>
      rowOf('실패.pdf').querySelector<HTMLButtonElement>(
        'button[data-next="rerun"]',
      )!;
    await act(async () => {
      fireEvent.click(button());
    });
    const alert = screen.getByTestId('list-rerun-error');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.textContent).toContain(GW_TEXT.runUnreachable.rerun);
    expect(button().getAttribute('aria-disabled')).toBeNull();
    expect(store.listCheckRows).toHaveBeenCalledTimes(1);
    await act(async () => {
      fireEvent.click(
        within(alert).getByRole('button', { name: words.reload }),
      );
    });
    await waitFor(() => expect(store.listCheckRows).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(
        screen
          .getByRole('table', { name: words.tableLabel })
          .getAttribute('aria-busy'),
      ).not.toBe('true'),
    );
    // 목록을 다시 읽어도(화면은 그대로) 그 실행의 열쇠는 남는다 — 다시 누르면 같은 열쇠
    await act(async () => {
      fireEvent.click(button());
    });
    expect(rerun).toHaveBeenCalledTimes(2);
    expect(rerun.mock.calls[1]).toEqual(rerun.mock.calls[0]);
    expect(onOpen).toHaveBeenCalledWith({ screen: 'status', runId: 'r9' });
  });

  it('[R2] 실행 A 끊김 → 다른 실행 B 거절 → A 누름은 A 의 열쇠로 보내진다(소리 없는 null 0), B 는 제 열쇠', async () => {
    const failedB: ListedRun = {
      ...SOURCE.runs.find((run) => run.runId === 'r2')!,
      runId: 'r5',
      documentId: '실패둘',
    };
    const source: CheckRowsSource = {
      ...SOURCE,
      documents: [...SOURCE.documents, doc('실패둘')],
      runs: [...SOURCE.runs, failedB],
    };
    const rerun = vi
      .fn<GreenwashStore['rerun']>()
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'))
      .mockRejectedValueOnce(new StoreError('rejected', '지어낸 거절'))
      .mockResolvedValueOnce({ runId: 'r9' });
    const onOpen = vi.fn();
    render(
      <ListScreen
        store={fakeStore({ listCheckRows: vi.fn(async () => source), rerun })}
        onOpen={onOpen}
        onNewCheck={() => {}}
      />,
    );
    await screen.findByText('실패둘.pdf');
    const button = (name: string) =>
      rowOf(name).querySelector<HTMLButtonElement>(
        'button[data-next="rerun"]',
      )!;
    await act(async () => {
      fireEvent.click(button('실패.pdf'));
    });
    await act(async () => {
      fireEvent.click(button('실패둘.pdf'));
    });
    expect(
      screen.getByTestId('list-rerun-error').getAttribute('data-error'),
    ).toBe('rejected');
    await act(async () => {
      fireEvent.click(button('실패.pdf'));
    });
    expect(rerun).toHaveBeenCalledTimes(3);
    const [a1, b, a2] = rerun.mock.calls;
    expect(a1![0]).toBe('r2');
    expect(b![0]).toBe('r5');
    expect(a2).toEqual(a1);
    expect(b![1]).not.toBe(a1![1]);
    expect(onOpen).toHaveBeenCalledWith({ screen: 'status', runId: 'r9' });
  });

  it('[새 점검] 을 부른다, 아래 안내 글', async () => {
    const { onNewCheck } = await renderList();
    fireEvent.click(screen.getByRole('button', { name: words.newCheck }));
    expect(onNewCheck).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('list-notice').textContent).toBe(words.notice);
  });

  it('운영 관리자(operator, sid:MARC-ENT-409): meta 는 「작업 회사 …」, 「내가 올린 것만」 없음. [새 점검]·[다시 실행]·다음 할 일·안내 글은 고객사와 같다', async () => {
    const onNewCheck = vi.fn();
    render(
      <ListScreen
        store={listStore()}
        onOpen={vi.fn()}
        onNewCheck={onNewCheck}
        operator
      />,
    );
    await screen.findByText(words.metaOperator('회사'));
    // 운영 관리자 꼴도 셈·안내 조각은 지웠다(sid:MARC-ENT-603)
    expect(screen.queryByText(/문서 \d+건|실행 \d+회/)).toBeNull();
    expect(screen.queryByText(words.mineOnly)).toBeNull();
    expect(screen.queryByRole('checkbox')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: words.newCheck }));
    expect(onNewCheck).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[data-next="rerun"]')).not.toBeNull();
    expect(document.querySelector('[data-next="review"]')).not.toBeNull();
    expect(screen.getByTestId('list-notice').textContent).toBe(words.notice);
  });

  it('고객사 사용자(operator 기본 거짓): 설명 줄 없음(sid:MARC-ENT-603), 「내가 올린 것만」 있음', async () => {
    await renderList();
    expect(screen.queryByText(words.metaOperator('회사'))).toBeNull();
    expect(screen.queryByText(/문서 \d+건|실행 \d+회/)).toBeNull();
    expect(screen.getByText(words.mineOnly)).toBeTruthy();
  });
});

describe('실행이 없는 문서 줄(검증 N1)', () => {
  it('누를 수 있는 줄이 아니다: tabIndex·이름 단서 없음, 눌러도 아무 데도 가지 않는다', async () => {
    const store = listStore();
    store.listCheckRows = vi.fn(async () => ({
      ...SOURCE,
      documents: [...SOURCE.documents, doc('실행없음')],
    }));
    const { onOpen } = await renderList(store);
    const row = rowOf('실행없음.pdf');
    expect(row.hasAttribute('tabindex')).toBe(false);
    expect(row.hasAttribute('aria-label')).toBe(false);
    fireEvent.click(within(row).getAllByRole('cell')[0]!);
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(onOpen).not.toHaveBeenCalled();
  });
});
