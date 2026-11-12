// @vitest-environment jsdom
// 헤드리스 훅을 화면 없이 돌려 본다. 스크롤 상자만 하나 만들어 붙인다.
import { act, renderHook } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fakeLayout } from '../../../shared/lib/testing/layout.ts';
import { STATUS_LABEL } from '../model/index.ts';
import { boardRows, makeRow } from '../model/testing.ts';
import { useReviewBoard } from './useReviewBoard.ts';
import type { Calculate } from './useReviewRows.ts';
import type { ReviewColumn } from './useReviewTable.ts';

const COLUMNS: ReviewColumn[] = [
  { id: 'name', header: '품목', value: (row) => row.raw.itemName ?? null },
  { id: 'amount', header: '수량', value: (row) => row.raw.amount ?? null },
  { id: 'status', header: '상태', value: (row) => STATUS_LABEL[row.status] },
];

let restoreLayout: () => void;
let scroll: HTMLDivElement;
beforeEach(() => {
  restoreLayout = fakeLayout();
  scroll = document.createElement('div');
  scroll.dataset.testid = 'rt-scroll';
  document.body.append(scroll);
});
afterEach(() => {
  scroll.remove();
  restoreLayout();
});

function setup(
  rows = boardRows(),
  calculate: Calculate = ({ candidate: picked }) => picked?.emission ?? null,
) {
  const onChange = vi.fn();
  const hook = renderHook(() => {
    const board = useReviewBoard({
      rows,
      columns: COLUMNS,
      calculate,
      onChange,
      estimateRowHeight: 40,
      overscan: 2,
    });
    board.window.scrollRef.current = scroll;
    return board;
  });
  // 스크롤 상자를 단 뒤에 한 번 더 그려야 가상 스크롤이 크기를 읽는다.
  hook.rerender();
  return { ...hook, board: () => hook.result.current, onChange };
}

describe('보이는 행만 그리기', () => {
  it('200행 가운데 화면에 드는 만큼만 그린다', () => {
    const { board } = setup();
    expect(board().table.rows).toHaveLength(200);
    expect(board().window.totalSize).toBe(200 * 40);
    // 높이 400 에 행 40 → 열 줄, 아래 여유 두 줄.
    expect(board().window.items.map((item) => item.index)).toEqual([
      0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
    ]);
  });
});

describe('일괄 동작의 대상', () => {
  it('걸러 본 결과 전체가 대상이다. 화면에 그려지지 않은 행도 바뀐다', () => {
    const { board } = setup();
    act(() => board().table.setFilter({ statuses: ['accepted'] }));
    const filtered = board().table.rows.map((row) => row.id);
    expect(filtered).toHaveLength(80);
    expect(board().window.items.length).toBeLessThan(20);

    let outcome!: ReturnType<ReturnType<typeof board>['bulk']>;
    act(() => void (outcome = board().bulk('filtered', { type: 'finalize' })));
    expect(outcome).toMatchObject({ targeted: 80, applied: 80, skipped: [] });

    act(() => board().table.setFilter({ statuses: [] }));
    const finalized = board()
      .table.rows.filter((row) => row.status === 'finalized')
      .map((row) => row.id);
    // 정확히 걸러 본 그 행들만 바뀌었다(화면에 그려졌던 열두 줄이 아니라 80행 전부).
    expect(finalized).toEqual(filtered);
    expect(board().summary.byStatus).toMatchObject({
      finalized: 80,
      accepted: 0,
      pending: 120,
    });
    expect(board().summary.finalTotal).toBe(800);
  });

  it('정렬하고 글자로 걸러 본 뒤에도 대상은 걸러 본 결과와 같다', () => {
    const { board } = setup();
    const before = new Map(board().table.rows.map((row) => [row.id, row]));
    act(() => board().table.columns[1]!.toggleSort());
    act(() => board().table.setFilter({ text: '수지' }));
    const shown = board().table.rows.map((row) => row.id);
    expect(shown).toHaveLength(150);
    expect(board().table.targetIds('filtered')).toEqual(shown);

    act(() => void board().bulk('filtered', { type: 'accept' }));
    // 수지 150행: 홀수째 100행은 검토대기라 반영된다. 짝수째 50행 가운데 후보 없는 10행과 이미 반영인 40행은 건너뛴다.
    expect(board().lastBulk).toMatchObject({ targeted: 150, applied: 100 });
    expect(board().lastBulk!.skipped).toEqual(
      expect.arrayContaining([
        { error: 'no_candidate', status: 'pending', count: 10 },
        { error: 'not_allowed', status: 'accepted', count: 40 },
      ]),
    );
    act(() => board().table.setFilter({ text: '' }));
    // 걸러 본 결과 밖의 행(강판 50행)은 같은 객체 그대로다.
    const untouched = board().table.rows.filter((row) =>
      String(row.raw.itemName).startsWith('강판'),
    );
    expect(untouched).toHaveLength(50);
    expect(untouched.every((row) => row === before.get(row.id))).toBe(true);
  });

  it('고른 행: 걸러 본 결과 안에 있는 것만 대상이다', () => {
    const { board } = setup();
    act(() => {
      board().table.toggleSelected('r2'); // 반영
      board().table.toggleSelected('r4'); // 반영
      board().table.toggleSelected('r199'); // 검토대기. 화면 밖
    });
    expect([...board().table.selectedIds].sort()).toEqual(['r199', 'r2', 'r4']);
    act(() => board().table.setFilter({ statuses: ['accepted'] }));
    expect(board().table.targetIds('selected')).toEqual(['r2', 'r4']);
    act(() => void board().bulk('selected', { type: 'finalize' }));
    expect(board().summary.byStatus.finalized).toBe(2);
    // 걸러서 안 보이던 r199 는 고른 채로 남아 있다.
    expect(board().table.selectedIds.has('r199')).toBe(true);
  });

  it('걸러 보기 조건은 하나씩 바꿔도 나머지가 남는다', () => {
    const { board } = setup();
    act(() => board().table.setFilter({ statuses: ['accepted'] }));
    act(() => board().table.setFilter({ text: '강판' }));
    expect(board().table.filter).toEqual({
      statuses: ['accepted'],
      category: null,
      text: '강판',
    });
    expect(board().table.rows).toHaveLength(40);
  });

  it('모두 고르기는 걸러 본 결과 전체를 고른다', () => {
    const { board } = setup();
    act(() => board().table.setFilter({ text: '강판' }));
    act(() => board().table.selectAll(true));
    expect(board().table.selectedIds.size).toBe(50);
    act(() => board().table.selectAll(false));
    expect(board().table.selectedIds.size).toBe(0);
  });

  it('allSelected: 걸러 본 결과가 전부 골라졌을 때만 참이다. 결과가 비었으면 거짓이다', () => {
    const { board } = setup();
    expect(board().table.allSelected).toBe(false);
    act(() => board().table.setFilter({ text: '강판' }));
    act(() => board().table.selectAll(true));
    expect(board().table.allSelected).toBe(true);
    // 하나를 풀면 거짓, 다시 고르면 참.
    act(() => board().table.toggleSelected('r0'));
    expect(board().table.allSelected).toBe(false);
    act(() => board().table.toggleSelected('r0'));
    expect(board().table.allSelected).toBe(true);
    // 걸러 보기를 풀면 안 골라진 행이 결과에 들어오므로 거짓이 된다.
    act(() => board().table.setFilter({ text: '' }));
    expect(board().table.allSelected).toBe(false);
    // 결과 밖의 행만 골라져 있고 결과가 비었을 때.
    act(() => board().table.setFilter({ text: '없는 글자' }));
    expect(board().table.rows).toHaveLength(0);
    expect(board().table.allSelected).toBe(false);
  });

  it('allSelected: 고른 행의 수가 결과의 행 수와 같아도, 고른 것이 결과 밖의 행이면 거짓이다', () => {
    // 네 행: r0 은 「강판 0」, r1~r3 은 「수지 …」.
    const { board } = setup(boardRows(4));
    act(() => board().table.toggleSelected('r1'));
    act(() => board().table.setFilter({ text: '강판' }));
    // 걸러 본 결과는 r0 하나, 골라 둔 것은 걸러져 안 보이는 r1 하나.
    expect(board().table.rows.map((row) => row.id)).toEqual(['r0']);
    expect([...board().table.selectedIds]).toEqual(['r1']);
    expect(board().table.allSelected).toBe(false);
  });
});

describe('정렬', () => {
  it('누를 때마다 오름 → 내림 → 없음. 값이 없는 행은 어느 쪽에서도 맨 뒤다', () => {
    const { board } = setup();
    const amounts = () => board().table.rows.map((row) => row.raw.amount);
    const original = amounts();
    const numbers = original.filter((value): value is number => value !== null);
    const blanks = original.length - numbers.length;

    act(() => board().table.columns[1]!.toggleSort());
    expect(board().table.columns[1]!.sorted).toBe('asc');
    expect(amounts()).toEqual([
      ...numbers.sort((a, b) => a - b),
      ...Array(blanks).fill(null),
    ]);

    act(() => board().table.columns[1]!.toggleSort());
    expect(board().table.columns[1]!.sorted).toBe('desc');
    expect(amounts()).toEqual([
      ...numbers.sort((a, b) => b - a),
      ...Array(blanks).fill(null),
    ]);

    act(() => board().table.columns[1]!.toggleSort());
    expect(board().table.columns[1]!.sorted).toBeNull();
    expect(amounts()).toEqual(original);
  });
});

describe('키보드 이동', () => {
  it('아래·위·끝·처음으로 지금 행을 옮기고, 화면 밖이면 그리로 스크롤한다', () => {
    const { board } = setup();
    const key = (name: string) => {
      let handled = false;
      act(() => void (handled = board().window.handleKey(name)));
      return handled;
    };
    expect(board().window.activeId).toBeNull();
    expect(key('ArrowDown')).toBe(true);
    expect(board().window.activeId).toBe('r0');
    key('j');
    key('ArrowDown');
    expect(board().window.activeId).toBe('r2');
    key('k');
    expect(board().window.activeId).toBe('r1');
    key('PageDown');
    expect(board().window.activeId).toBe('r11');
    key('End');
    expect(board().window.activeId).toBe('r199');
    key('ArrowDown'); // 끝에서 더 내려가지 않는다
    expect(board().window.activeId).toBe('r199');
    key('Home');
    expect(board().window.activeId).toBe('r0');
    expect(key('x')).toBe(false);
  });

  it('Space 는 지금 행을 고르고, Enter 는 펼친다. 지금 행이 없으면 아무것도 하지 않는다', () => {
    const { board } = setup();
    let handled = true;
    act(() => void (handled = board().window.handleKey(' ')));
    expect(handled).toBe(false);
    act(() => void board().window.handleKey('ArrowDown'));
    act(() => void board().window.handleKey(' '));
    act(() => void board().window.handleKey('Enter'));
    expect([...board().table.selectedIds]).toEqual(['r0']);
    expect([...board().window.expandedIds]).toEqual(['r0']);
  });

  it('걸러서 지금 행이 사라지면 지금 행이 없어지고, 다음 이동은 처음부터다', () => {
    const { board } = setup();
    act(() => void board().window.handleKey('ArrowDown')); // r0 (검토대기)
    act(() => board().table.setFilter({ statuses: ['accepted'] }));
    expect(board().window.activeId).toBeNull();
    act(() => void board().window.handleKey('ArrowDown'));
    expect(board().window.activeId).toBe('r2');
  });
});

describe('한 행 바꾸기와 재계산', () => {
  it('바뀐 행만 새 객체가 되고, 요약이 따라 바뀌고, 바뀐 행을 밖에 알린다', () => {
    const { board, onChange } = setup();
    const before = board().table.rows;
    act(() => void board().act('r2', { type: 'finalize' }));
    const after = board().table.rows;
    expect(
      after.filter((row, index) => row !== before[index]).map((row) => row.id),
    ).toEqual(['r2']);
    expect(board().summary).toMatchObject({
      finalTotal: 10,
      byStatus: { finalized: 1, accepted: 79 },
    });
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ id: 'r2', status: 'finalized' }),
    ]);
  });

  it('처음 받은 행만 읽는다: 나중에 다른 배열을 넘겨도 상태와 자리가 어긋나지 않는다', () => {
    let rows = boardRows(20);
    const hook = renderHook(() =>
      useReviewBoard({
        rows,
        columns: COLUMNS,
        calculate: () => null,
        estimateRowHeight: 40,
      }),
    );
    rows = [...rows].reverse();
    hook.rerender();
    act(() => void hook.result.current.act('r2', { type: 'finalize' }));
    const changed = hook.result.current.table.rows
      .filter((row) => row.status === 'finalized')
      .map((row) => row.id);
    expect(changed).toEqual(['r2']);
    expect(hook.result.current.table.rows.map((row) => row.id)).toEqual(
      boardRows(20).map((row) => row.id),
    );
  });

  it('안 되는 동작은 까닭을 돌려주고 아무것도 바꾸지 않는다', () => {
    const { board, onChange } = setup();
    let result!: ReturnType<ReturnType<typeof board>['act']>;
    act(() => void (result = board().act('r1', { type: 'finalize' })));
    expect(result).toEqual({ ok: false, error: 'not_allowed' });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('계산이 늦게 답하면 그동안 재계산 대기이고 최종 확정이 안 된다. 답이 오면 풀린다', async () => {
    let answer!: (value: number | null) => void;
    const slow: Calculate = () => new Promise((resolve) => (answer = resolve));
    const rows = [makeRow({ id: 'x' })];
    const { board } = setup(rows, slow);

    act(() => void board().act('x', { type: 'edit', candidateId: 'b' }));
    expect(board().table.rows[0]).toMatchObject({
      status: 'edited',
      edit: { recalcPending: true, emission: null },
    });
    expect(board().summary.recalcPending).toBe(1);
    let blocked!: ReturnType<ReturnType<typeof board>['act']>;
    act(() => void (blocked = board().act('x', { type: 'finalize' })));
    expect(blocked).toEqual({ ok: false, error: 'recalc_pending' });

    await act(async () => answer(777));
    expect(board().table.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: 777,
      recalcPending: false,
    });
    // 원본값은 그대로다.
    expect(board().table.rows[0]!.ai.candidates.map((c) => c.emission)).toEqual(
      [100, 250],
    );
    act(() => void board().act('x', { type: 'finalize' }));
    expect(board().summary.finalTotal).toBe(777);
  });

  it('기다리는 동안 다시 고쳤으면 먼저 온 답은 버린다', async () => {
    const answers: ((value: number | null) => void)[] = [];
    const slow: Calculate = () =>
      new Promise((resolve) => answers.push(resolve));
    const { board } = setup([makeRow({ id: 'x' })], slow);
    act(() => void board().act('x', { type: 'edit', candidateId: 'b' }));
    act(() => void board().act('x', { type: 'edit', candidateId: 'a' }));
    await act(async () => answers[0]!(111));
    expect(board().table.rows[0]!.edit).toMatchObject({
      recalcPending: true,
      emission: null,
    });
    await act(async () => answers[1]!(222));
    expect(board().table.rows[0]!.edit).toMatchObject({
      candidateId: 'a',
      recalcPending: false,
      emission: 222,
    });
  });
});

describe('계산 실패', () => {
  /** 부를 때마다 답을 밖에서 정하는 계산 함수. */
  function controlled() {
    const calls: {
      resolve(value: number | null): void;
      reject(error: Error): void;
    }[] = [];
    const calculate: Calculate = () =>
      new Promise<number | null>((resolve, reject) =>
        calls.push({ resolve, reject }),
      );
    return { calls, calculate };
  }
  type Board = ReturnType<typeof setup>['board'];
  const actOn = (
    board: Board,
    action: Parameters<ReturnType<Board>['act']>[1],
  ) => {
    let result!: ReturnType<ReturnType<Board>['act']>;
    act(() => void (result = board().act('x', action)));
    return result;
  };

  it('계산이 거부되면 「계산하지 못했다」가 남고(배출량 없음과 다르다) 최종 확정이 안 된다. 다시 시도해 성공하면 확정된다', async () => {
    const { calls, calculate } = controlled();
    const { board, onChange } = setup([makeRow({ id: 'x' })], calculate);

    actOn(board, { type: 'edit', candidateId: 'b' });
    await act(async () => calls[0]!.reject(new Error('서버 오류')));
    expect(board().table.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: null,
      recalcPending: false,
      recalcFailed: true,
    });
    expect(board().summary).toMatchObject({
      recalcFailed: 1,
      recalcPending: 0,
    });
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({
        id: 'x',
        edit: expect.objectContaining({ recalcFailed: true }),
      }),
    ]);
    expect(actOn(board, { type: 'finalize' })).toEqual({
      ok: false,
      error: 'recalc_failed',
    });

    // 다시 시도: 계산을 한 번 더 부르고, 그동안 재계산 대기다.
    let retried!: boolean;
    act(() => void (retried = board().retry('x')));
    expect(retried).toBe(true);
    expect(calls).toHaveLength(2);
    expect(board().table.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: null,
      recalcPending: true,
    });
    expect(board().summary).toMatchObject({
      recalcFailed: 0,
      recalcPending: 1,
    });

    await act(async () => calls[1]!.resolve(777));
    expect(board().table.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: 777,
      recalcPending: false,
    });
    expect(actOn(board, { type: 'finalize' }).ok).toBe(true);
    expect(board().summary.finalTotal).toBe(777);
  });

  it('바로 던진 예외도 실패다', () => {
    const { board } = setup([makeRow({ id: 'x' })], () => {
      throw new Error('계산 중 예외');
    });
    const result = actOn(board, { type: 'edit', candidateId: 'b' });
    expect(result.ok && result.row.edit).toMatchObject({
      recalcFailed: true,
      recalcPending: false,
      emission: null,
    });
    expect(board().summary.recalcFailed).toBe(1);
  });

  it('계산이 null 을 답하면 실패가 아니라 배출량 없음이다', async () => {
    const { calls, calculate } = controlled();
    const { board } = setup([makeRow({ id: 'x' })], calculate);
    actOn(board, { type: 'edit', candidateId: 'b' });
    await act(async () => calls[0]!.resolve(null));
    expect(board().table.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: null,
      recalcPending: false,
    });
    expect(board().summary.recalcFailed).toBe(0);
    expect(actOn(board, { type: 'finalize' })).toEqual({
      ok: false,
      error: 'no_emission',
    });
    // 실패한 행이 아니라 다시 시도할 것이 없다.
    let retried!: boolean;
    act(() => void (retried = board().retry('x')));
    expect(retried).toBe(false);
    expect(calls).toHaveLength(1);
  });

  it('다시 시도가 또 실패하면 다시 실패로 남는다. 없는 행·실패하지 않은 행의 다시 시도는 아무것도 하지 않는다', async () => {
    const { calls, calculate } = controlled();
    const { board, onChange } = setup(
      [makeRow({ id: 'x' }), makeRow({ id: 'y' })],
      calculate,
    );
    actOn(board, { type: 'edit', candidateId: 'b' });
    await act(async () => calls[0]!.reject(new Error('1')));
    act(() => void board().retry('x'));
    await act(async () => calls[1]!.reject(new Error('2')));
    expect(board().table.rows[0]!.edit).toMatchObject({
      recalcFailed: true,
      recalcPending: false,
    });

    onChange.mockClear();
    let results!: boolean[];
    act(() => void (results = [board().retry('y'), board().retry('없는 행')]));
    expect(results).toEqual([false, false]);
    expect(onChange).not.toHaveBeenCalled();
    expect(calls).toHaveLength(2);
  });

  it('기다리는 동안 다시 고쳤으면 먼저 온 실패는 버린다', async () => {
    const { calls, calculate } = controlled();
    const { board } = setup([makeRow({ id: 'x' })], calculate);
    actOn(board, { type: 'edit', candidateId: 'b' });
    actOn(board, { type: 'edit', candidateId: 'a' });
    await act(async () => calls[0]!.reject(new Error('늦게 온 실패')));
    expect(board().table.rows[0]!.edit).toEqual({
      candidateId: 'a',
      emission: null,
      recalcPending: true,
    });
    await act(async () => calls[1]!.resolve(100));
    expect(board().table.rows[0]!.edit).toEqual({
      candidateId: 'a',
      emission: 100,
      recalcPending: false,
    });
  });

  it('일괄 최종 확정은 실패한 행을 건너뛰고 까닭을 「계산하지 못했다」로 돌려준다', async () => {
    const { calls, calculate } = controlled();
    const { board } = setup(
      [makeRow({ id: 'x' }), makeRow({ id: 'ok', status: 'accepted' })],
      calculate,
    );
    actOn(board, { type: 'edit', candidateId: 'b' });
    await act(async () => calls[0]!.reject(new Error('실패')));
    let outcome!: ReturnType<ReturnType<Board>['bulk']>;
    act(() => void (outcome = board().bulk('filtered', { type: 'finalize' })));
    expect(outcome).toMatchObject({
      targeted: 2,
      applied: 1,
      skipped: [{ error: 'recalc_failed', status: 'edited', count: 1 }],
    });
    expect(board().table.rows.map((row) => row.status)).toEqual([
      'edited',
      'finalized',
    ]);
  });
});

describe('일괄 수정과 재계산', () => {
  it('일괄로 수정하면 바뀐 행마다 계산을 부르고 답을 넣는다(재계산 대기로 남지 않는다)', () => {
    const calculate = vi.fn<Calculate>(({ candidate: picked }) =>
      picked ? picked.emission! * 2 : null,
    );
    const { board } = setup(boardRows(20), calculate);
    let outcome!: ReturnType<ReturnType<typeof board>['bulk']>;
    act(
      () =>
        void (outcome = board().bulk('filtered', {
          type: 'edit',
          category: '나',
        })),
    );
    // 20행 모두 검토대기 또는 반영이라 수정이 된다.
    expect(outcome).toMatchObject({ targeted: 20, applied: 20 });
    expect(calculate).toHaveBeenCalledTimes(20);
    expect(board().summary.recalcPending).toBe(0);
    const withCandidate = board().table.rows.filter(
      (row) => row.ai.candidates.length > 0,
    );
    expect(withCandidate).toHaveLength(18);
    expect(
      withCandidate.every(
        (row) => row.edit?.emission === 20 && row.edit.recalcPending === false,
      ),
    ).toBe(true);
  });
});

describe('정렬: 글자는 한글 사전 순으로, 글자 속 숫자는 수로 견준다', () => {
  it('「수지 9」가 「수지 10」보다 앞이고, 한글이 영문보다 앞이다', () => {
    const names = ['수지 10', 'abc', '수지 9', '강판 2', 'Zinc', '수지 100'];
    const { board } = setup(
      names.map((itemName, i) => makeRow({ id: `n${i}`, raw: { itemName } })),
    );
    act(() => board().table.columns[0]!.toggleSort());
    expect(board().table.rows.map((row) => row.raw.itemName)).toEqual([
      '강판 2',
      '수지 9',
      '수지 10',
      '수지 100',
      'abc',
      'Zinc',
    ]);
    act(() => board().table.columns[0]!.toggleSort());
    expect(board().table.rows.map((row) => row.raw.itemName)).toEqual([
      'Zinc',
      'abc',
      '수지 100',
      '수지 10',
      '수지 9',
      '강판 2',
    ]);
  });
});

describe('잰 높이는 행을 따라간다', () => {
  it('정렬해서 행의 자리가 바뀌어도, 잰 높이는 그 자리가 아니라 그 행에 붙어 있다', () => {
    // 수량: r0 = 30(가장 큼), r1 = 10, r2 = 20. 수량으로 정렬하면 r1, r2, r0 차례가 된다.
    const rows = [30, 10, 20].map((amount, i) =>
      makeRow({ id: `r${i}`, raw: { itemName: `품목 ${i}`, amount } }),
    );
    const { board } = setup(rows);
    // 맨 위의 행(r0)이 펼쳐져 높이 120 으로 재졌다고 하자(나머지는 어림값 40).
    const element = document.createElement('div');
    element.dataset.index = '0';
    Object.defineProperty(element, 'offsetHeight', { value: 120 });
    act(() => board().window.measureRef(element));
    expect(
      board().window.items.map((item) => [item.row.id, item.start]),
    ).toEqual([
      ['r0', 0],
      ['r1', 120],
      ['r2', 160],
    ]);
    expect(board().window.totalSize).toBe(200);

    act(() => board().table.columns[1]!.toggleSort());
    // r0 이 맨 아래로 갔다. 높이 120 은 r0 을 따라가므로, 위의 두 행은 40 씩이다.
    expect(
      board().window.items.map((item) => [item.row.id, item.start]),
    ).toEqual([
      ['r1', 0],
      ['r2', 40],
      ['r0', 80],
    ]);
    expect(board().window.totalSize).toBe(200);
  });
});
