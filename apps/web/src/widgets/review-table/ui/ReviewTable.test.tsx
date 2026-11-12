// @vitest-environment jsdom
// 표 화면(ui/)에만 있는 것을 본다: 머리글의 모두 고르기, 키보드를 어디서 받는가, 잠긴 조작, 눈에 보이는 글자, 한 행만 다시 그리기.
// 두 화면에 공통인 동작은 pages/demo-table/behavior.test.tsx 가 본다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fakeLayout } from '../../../shared/lib/testing/layout.ts';
import type { Calculate, ReviewColumn } from '../hooks/index.ts';
import type { ReviewRow } from '../model/index.ts';
import { sixRows } from '../model/testing.ts';
import { ReviewTable } from './ReviewTable.tsx';

const COLUMNS: ReviewColumn[] = [
  { id: 'name', header: '품목', value: (row) => row.raw.itemName ?? null },
];
const CATEGORIES = ['가', '나'];

let restoreLayout: () => void;
beforeEach(() => void (restoreLayout = fakeLayout()));
afterEach(() => {
  cleanup();
  restoreLayout();
});

function show(
  calculate: Calculate = ({ candidate: picked }) => picked?.emission ?? null,
  rows: ReviewRow[] = sixRows(),
) {
  const onRenderRow = vi.fn<(rowId: string) => void>();
  render(
    <ReviewTable
      rows={rows}
      categories={CATEGORIES}
      columns={COLUMNS}
      calculate={calculate}
      onRenderRow={onRenderRow}
    />,
  );
  const row = (id: string) =>
    document.querySelector<HTMLElement>(`[data-row-id="${id}"]`)!;
  const expand = (id: string) =>
    fireEvent.click(within(row(id)).getByLabelText('펼치기'));
  const selected = () =>
    [...document.querySelectorAll<HTMLElement>('[data-row-id]')]
      .filter((element) => element.getAttribute('aria-selected') === 'true')
      .map((element) => element.dataset.rowId);
  const activeId = () =>
    document.querySelector<HTMLElement>('[data-active]')?.dataset.rowId ?? null;
  return { row, expand, selected, activeId, onRenderRow };
}

describe('표의 접근성 구조', () => {
  it('머리글 줄이 grid 안의 첫 행이다. 행 수는 머리글 줄까지 세고, 자료 행의 순서는 2부터다', () => {
    const { row } = show();
    const grid = screen.getByRole('grid');
    // 자료 6행 + 머리글 1줄.
    expect(grid.getAttribute('aria-rowcount')).toBe('7');
    const rows = within(grid).getAllByRole('row');
    expect(rows).toHaveLength(7);
    expect(rows[0]!.getAttribute('aria-rowindex')).toBe('1');
    expect(rows[0]!.hasAttribute('data-row-id')).toBe(false);
    expect(
      rows
        .slice(1)
        .map((element) => [
          element.dataset.rowId,
          element.getAttribute('aria-rowindex'),
        ]),
    ).toEqual([
      ['r0', '2'],
      ['r1', '3'],
      ['r2', '4'],
      ['r3', '5'],
      ['r4', '6'],
      ['r5', '7'],
    ]);
    // 표 밖에는 행이 없다(머리글 줄이 grid 밖에 떠 있지 않다).
    expect(screen.getAllByRole('row')).toHaveLength(7);
    // 스크롤 상자(키보드를 받는 곳)는 그 grid 안의 행 묶음이다.
    const box = screen.getByTestId('rt-scroll');
    expect(grid.contains(box)).toBe(true);
    expect(box.getAttribute('role')).toBe('rowgroup');
    expect(box.contains(row('r0'))).toBe(true);
    expect(box.contains(rows[0]!)).toBe(false);
  });

  it('머리글 줄의 칸은 전부 columnheader 다(고르기 칸, 펼치기 칸, 열마다 하나). 정렬 상태(aria-sort)는 열의 머리글 칸에 붙는다', () => {
    show();
    const header = within(screen.getByRole('grid')).getAllByRole('row')[0]!;
    const cells = within(header).getAllByRole('columnheader');
    expect(cells).toHaveLength(2 + COLUMNS.length);
    // 머리글 줄의 바로 아래 칸은 전부 columnheader 다(역할 없는 칸이 끼어 있지 않다).
    expect(
      [...cells[0]!.parentElement!.children].every(
        (element) => element.getAttribute('role') === 'columnheader',
      ),
    ).toBe(true);
    expect(
      within(cells[0]!).getByLabelText('걸러 본 결과 모두 고르기'),
    ).toBeTruthy();
    // 펼치기 칸의 머리글은 글자가 없다. 이름을 따로 단다.
    expect(cells[1]!.getAttribute('aria-label')).toBe('펼치기');
    expect(
      cells.slice(0, 2).map((cell) => cell.hasAttribute('aria-sort')),
    ).toEqual([false, false]);
    expect(
      cells.slice(2).map((cell) => cell.getAttribute('aria-sort')),
    ).toEqual(COLUMNS.map(() => 'none'));
  });
});

describe('표의 접근성 구조: 정렬', () => {
  it('열의 머리글을 누를 때마다 오름 → 내림 → 없음으로 돌고, 그 칸의 aria-sort 가 행이 실제로 놓인 차례와 같은 쪽을 말한다', () => {
    // 받은 차례가 품목 이름의 오름도 내림도 아닌 자료: 품목 2, 품목 0, 품목 1.
    const [r0, r1, r2] = sixRows();
    show(undefined, [r2!, r0!, r1!]);
    const header = () => screen.getByRole('columnheader', { name: /품목/ });
    const order = () =>
      [...document.querySelectorAll<HTMLElement>('[data-row-id]')].map(
        (element) => element.dataset.rowId,
      );
    const press = () => fireEvent.click(within(header()).getByRole('button'));
    expect(order()).toEqual(['r2', 'r0', 'r1']);

    press();
    expect(header().getAttribute('aria-sort')).toBe('ascending');
    expect(order()).toEqual(['r0', 'r1', 'r2']);
    press();
    expect(header().getAttribute('aria-sort')).toBe('descending');
    expect(order()).toEqual(['r2', 'r1', 'r0']);
    press();
    expect(header().getAttribute('aria-sort')).toBe('none');
    expect(order()).toEqual(['r2', 'r0', 'r1']);
  });
});

describe('머리글의 모두 고르기', () => {
  it('누르면 걸러 본 결과 전체가 골라지고, 다시 누르면 전부 풀린다', () => {
    const { selected } = show();
    const all =
      screen.getByLabelText<HTMLInputElement>('걸러 본 결과 모두 고르기');
    expect(all.checked).toBe(false);
    fireEvent.click(all);
    expect(selected()).toEqual(['r0', 'r1', 'r2', 'r3', 'r4', 'r5']);
    expect(all.checked).toBe(true);
    fireEvent.click(all);
    expect(selected()).toEqual([]);
    expect(all.checked).toBe(false);
  });

  it('몇 행만 골라 둔 상태에서 누르면 전부 고른다(푸는 것이 아니다)', () => {
    const { row, selected } = show();
    fireEvent.click(within(row('r1')).getByLabelText('행 고르기'));
    fireEvent.click(screen.getByLabelText('걸러 본 결과 모두 고르기'));
    expect(selected()).toHaveLength(6);
  });
});

describe('키보드를 받는 자리', () => {
  it('펼친 행 속의 입력에서 친 글자는 그 입력의 것이다. 지금 행이 옮겨 가지 않는다', () => {
    const { row, expand, activeId } = show();
    expand('r0');
    fireEvent.click(row('r0').querySelector('.rt-cells')!);
    expect(activeId()).toBe('r0');
    const reason = within(row('r0')).getByLabelText('반려 사유');
    for (const key of ['j', 'k', 'ArrowDown', 'End', ' ', 'Enter'])
      fireEvent.keyDown(reason, { key });
    expect(activeId()).toBe('r0');
    // Enter 가 행을 접지도 않았다.
    expect(within(row('r0')).getByLabelText('접기')).toBeTruthy();
    // 단추와 고르기 칸에서 누른 Space·Enter 도 그쪽의 것이다.
    fireEvent.keyDown(within(row('r0')).getByLabelText('행 고르기'), {
      key: 'ArrowDown',
    });
    fireEvent.keyDown(within(row('r0')).getByRole('button', { name: '반영' }), {
      key: 'j',
    });
    fireEvent.keyDown(within(row('r0')).getByLabelText('카테고리 수정'), {
      key: 'ArrowDown',
    });
    expect(activeId()).toBe('r0');
  });

  it('표 자체에 초점이 있을 때는 옮겨 간다. Ctrl·Meta·Alt 와 같이 누른 키는 받지 않는다', () => {
    const { activeId } = show();
    const box = screen.getByTestId('rt-scroll');
    fireEvent.keyDown(box, { key: 'j' });
    expect(activeId()).toBe('r0');
    fireEvent.keyDown(box, { key: 'j', ctrlKey: true });
    fireEvent.keyDown(box, { key: 'j', metaKey: true });
    fireEvent.keyDown(box, { key: 'ArrowDown', altKey: true });
    expect(activeId()).toBe('r0');
    fireEvent.keyDown(box, { key: 'j' });
    expect(activeId()).toBe('r1');
  });
});

describe('전이표가 수정을 허용하지 않는 상태에서는 고치는 조작이 잠긴다', () => {
  it('최종확정 행: 후보 고르기와 카테고리 고치기가 잠겨 있다. 검토대기 행은 열려 있다', () => {
    const { row, expand } = show();
    expand('r4');
    const radios = within(row('r4')).getAllByRole<HTMLInputElement>('radio');
    expect(radios).toHaveLength(2);
    expect(radios.every((radio) => radio.disabled)).toBe(true);
    expect(
      within(row('r4')).getByLabelText<HTMLSelectElement>('카테고리 수정')
        .disabled,
    ).toBe(true);

    expand('r0');
    expect(
      within(row('r0'))
        .getAllByRole<HTMLInputElement>('radio')
        .every((radio) => !radio.disabled),
    ).toBe(true);
    expect(
      within(row('r0')).getByLabelText<HTMLSelectElement>('카테고리 수정')
        .disabled,
    ).toBe(false);
  });
});

describe('눈에 보이는 글자', () => {
  it('일괄 동작 뒤에 건너뛴 개수와 까닭이 글자로 나온다', () => {
    show();
    fireEvent.click(screen.getByRole('button', { name: '일괄 최종 확정' }));
    const text = screen.getByTestId('rt-bulk-result').textContent!;
    expect(text).toContain('대상 6 · 적용 1 · 건너뜀 5');
    expect(text).toContain(
      '검토대기 3개: 지금 상태에서는 할 수 없는 동작이다.',
    );
    expect(text).toContain(
      '최종확정 1개: 지금 상태에서는 할 수 없는 동작이다.',
    );
    expect(text).toContain(
      '반영 1개: 배출량이 없다(계산해도 값이 나오지 않는다).',
    );
  });

  it('건너뛴 것이 없으면 까닭의 괄호가 없다', () => {
    show();
    fireEvent.change(screen.getByLabelText('글자로 걸러 보기'), {
      target: { value: '품목 3' },
    });
    fireEvent.click(screen.getByRole('button', { name: '일괄 최종 확정' }));
    expect(screen.getByTestId('rt-bulk-result').textContent).toBe(
      '일괄 최종 확정: 대상 1 · 적용 1 · 건너뜀 0',
    );
  });

  it('반려한 행을 펼치면 반려 사유가 보인다. 되돌리면 사라진다', () => {
    const { row, expand } = show();
    expand('r0');
    fireEvent.change(within(row('r0')).getByLabelText('반려 사유'), {
      target: { value: '  단위가 다르다 ' },
    });
    fireEvent.click(within(row('r0')).getByRole('button', { name: '반려' }));
    expect(row('r0').dataset.status).toBe('rejected');
    expect(row('r0').textContent).toContain('반려 사유: 단위가 다르다');
    fireEvent.click(
      within(row('r0')).getByRole('button', { name: '되돌리기' }),
    );
    expect(row('r0').textContent).not.toContain('반려 사유: 단위가 다르다');
  });
});

describe('한 행만 다시 그리기', () => {
  it('한 행을 펼치거나 바꾸면 그 행만 다시 그려진다', () => {
    const { row, expand, onRenderRow } = show();
    const rendered = () => onRenderRow.mock.calls.map(([id]) => id);
    expect(new Set(rendered())).toEqual(
      new Set(['r0', 'r1', 'r2', 'r3', 'r4', 'r5']),
    );

    onRenderRow.mockClear();
    expand('r3');
    expect(rendered()).toEqual(['r3']);

    onRenderRow.mockClear();
    fireEvent.click(
      within(row('r3')).getByRole('button', { name: '최종 확정' }),
    );
    expect(rendered()).toEqual(['r3']);

    onRenderRow.mockClear();
    fireEvent.click(within(row('r3')).getByLabelText('행 고르기'));
    expect(rendered()).toEqual(['r3']);

    // 다른 행을 누르면 「지금 행」이 r3 에서 r1 로 옮겨 간다. 그 둘만 다시 그려진다.
    onRenderRow.mockClear();
    fireEvent.click(within(row('r1')).getByLabelText('행 고르기'));
    expect(rendered().sort()).toEqual(['r1', 'r3']);
  });
});

describe('계산 실패의 표시', () => {
  it('실패한 행에 「계산하지 못했다」와 다시 계산 단추가 나오고, 최종 확정이 잠기고, 요약에 개수가 나온다. 다시 계산해 성공하면 사라진다', async () => {
    const calls: {
      resolve(value: number | null): void;
      reject(error: Error): void;
    }[] = [];
    const { row, expand } = show(
      () =>
        new Promise<number | null>((resolve, reject) =>
          calls.push({ resolve, reject }),
        ),
    );
    const summary = () => screen.getByTestId('rt-summary');
    expand('r0');
    fireEvent.click(within(row('r0')).getByLabelText('후보 2 고르기'));
    expect(row('r0').textContent).toContain('재계산 대기');
    expect(within(row('r0')).queryByTestId('rt-calc-failed')).toBeNull();

    await act(async () => calls[0]!.reject(new Error('서버 오류')));
    expect(row('r0').dataset.calcFailed).toBe('true');
    expect(
      within(row('r0')).getByTestId('rt-calc-failed').textContent,
    ).toContain('배출량을 계산하지 못했다');
    expect(within(row('r0')).getByTestId('rt-edited').textContent).toContain(
      '배출량 계산하지 못했다',
    );
    expect(summary().getAttribute('data-recalc-failed')).toBe('1');
    expect(summary().textContent).toContain('계산 실패 1');
    const finalize = within(row('r0')).getByRole<HTMLButtonElement>('button', {
      name: '최종 확정',
    });
    expect(finalize.disabled).toBe(true);
    expect(finalize.title).toContain('계산하지 못했다');

    fireEvent.click(
      within(row('r0')).getByRole('button', { name: '다시 계산' }),
    );
    expect(calls).toHaveLength(2);
    expect(within(row('r0')).queryByTestId('rt-calc-failed')).toBeNull();
    expect(row('r0').textContent).toContain('재계산 대기');
    await act(async () => calls[1]!.resolve(250));
    expect(row('r0').dataset.calcFailed).toBeUndefined();
    expect(summary().getAttribute('data-recalc-failed')).toBe('0');
    expect(summary().textContent).not.toContain('계산 실패');
    expect(
      within(row('r0')).getByRole<HTMLButtonElement>('button', {
        name: '최종 확정',
      }).disabled,
    ).toBe(false);
  });

  it('계산이 null 을 답한 행(배출량 없음)에는 실패 표시도 다시 계산 단추도 없다', () => {
    const { row, expand } = show(() => null);
    expand('r0');
    fireEvent.click(within(row('r0')).getByLabelText('후보 2 고르기'));
    expect(row('r0').dataset.calcFailed).toBeUndefined();
    expect(within(row('r0')).queryByTestId('rt-calc-failed')).toBeNull();
    expect(
      within(row('r0')).queryByRole('button', { name: '다시 계산' }),
    ).toBeNull();
    expect(
      screen.getByTestId('rt-summary').getAttribute('data-recalc-failed'),
    ).toBe('0');
    expect(
      within(row('r0')).getByRole<HTMLButtonElement>('button', {
        name: '최종 확정',
      }).title,
    ).toContain('배출량이 없다');
  });
});

/** 공용 NativeSelect 꼴인가: 감싼 span 안에 appearance-none select 와 꺾쇠 svg(aria-hidden) 형제(sid:MARC-ENT-430). */
function isNativeSelect(select: HTMLElement) {
  const wrap = select.parentElement!;
  return (
    select.tagName === 'SELECT' &&
    select.className.split(/\s+/).includes('appearance-none') &&
    wrap.tagName === 'SPAN' &&
    wrap.querySelector(':scope > svg[aria-hidden="true"]') !== null
  );
}

describe('고르기 칸은 공용 NativeSelect(202)', () => {
  it('도구 줄 셋(상태·카테고리·일괄 대상)과 펼친 행의 카테고리 수정', () => {
    const { expand } = show();
    for (const name of [
      '상태로 걸러 보기',
      '카테고리로 걸러 보기',
      '일괄 대상',
    ])
      expect(isNativeSelect(screen.getByRole('combobox', { name }))).toBe(true);
    expand('r0');
    expect(
      isNativeSelect(screen.getByRole('combobox', { name: '카테고리 수정' })),
    ).toBe(true);
  });
});
