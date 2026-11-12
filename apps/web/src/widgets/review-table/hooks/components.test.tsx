// @vitest-environment jsdom
// 모양 없는 컴포넌트(RowStack, RowFrame)를 모양 없이 그려 본다. 클래스 이름도 CSS 도 주지 않는다.
// 그래도 (1) 보이는 행만 DOM 에 있고 제자리에 놓이고(인라인 style) (2) 키보드가 훅에 닿되 입력 칸 안에서는 무시되고
// (3) 접근성 속성과 상태 표시가 맞고 (4) 한 행만 다시 그려야 한다.
// 실제 브라우저에서 스크롤 길이와 행의 자리가 맞는지는 e2e/review-table.spec.ts 가 본다(jsdom 에는 배치가 없다).
import { useCallback } from 'react';
import type { ReactNode } from 'react';

import { act, cleanup, fireEvent, render } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fakeLayout } from '../../../shared/lib/testing/layout.ts';
import type { ReviewRow } from '../model/index.ts';
import { alternatingRows } from '../model/testing.ts';
import type { RenderRow } from './RowFrame.tsx';
import { RowStack } from './RowStack.tsx';
import type { RowStackProps } from './RowStack.tsx';
import { useReviewBoard } from './useReviewBoard.ts';
import type { ReviewBoard } from './useReviewBoard.ts';
import type { Calculate } from './useReviewRows.ts';
import type { ReviewColumn } from './useReviewTable.ts';

const COLUMNS: ReviewColumn[] = [
  { id: 'name', header: '품목', value: (row) => row.raw.itemName ?? null },
];
/** fakeLayout 이 정해 주는 값: 스크롤 상자의 높이 400, 행의 높이 40. */
const ROW = 40;
const OVERSCAN = 2;

let restoreLayout: () => void;
beforeEach(() => void (restoreLayout = fakeLayout()));
afterEach(() => {
  cleanup();
  restoreLayout();
});

interface Options {
  rows?: ReviewRow[];
  calculate?: Calculate;
  classNames?: RowStackProps['classNames'];
  /** 머리글 줄의 속. 주면 RowStack 이 grid 를 한 겹 더 만든다. */
  header?: ReactNode;
  /** true 면 renderRow 를 useCallback 으로 감싸지 않는다(하지 말라고 적어 둔 것을 일부러 한다). */
  unstableRenderRow?: boolean;
}

/** 훅 하나와 RowStack 하나만으로 만든 가장 작은 화면. 모양이 하나도 없다. 훅이 돌려준 것은 밖에서 읽을 수 있게 내놓는다. */
function setup({
  rows = alternatingRows(),
  calculate = ({ candidate: picked }) => picked?.emission ?? null,
  classNames,
  header,
  unstableRenderRow = false,
}: Options = {}) {
  const handle: { board?: ReviewBoard } = {};
  const onRenderRow = vi.fn<(rowId: string) => void>();
  function Bare() {
    const board = useReviewBoard({
      rows,
      columns: COLUMNS,
      calculate,
      estimateRowHeight: ROW,
      overscan: OVERSCAN,
    });
    handle.board = board;
    const { toggleExpanded } = board.window;
    const stable = useCallback<RenderRow>(
      (row, state) => (
        <>
          <span role="gridcell" data-testid="cell">
            {String(row.raw.itemName)}|{state.index}|{String(state.selected)}|
            {String(state.active)}|{String(state.expanded)}
          </span>
          <input aria-label="칸 속의 입력" />
          <select aria-label="칸 속의 고르기" />
          <textarea aria-label="칸 속의 글" />
          <button
            type="button"
            aria-label="칸 속의 단추"
            onClick={() => toggleExpanded(row.id)}
          />
        </>
      ),
      [toggleExpanded],
    );
    const renderRow: RenderRow =
      unstableRenderRow ? (row, state) => stable(row, state) : stable;
    return (
      <RowStack
        window={board.window}
        rowCount={board.table.rows.length}
        selectedIds={board.table.selectedIds}
        classNames={classNames}
        header={header}
        renderRow={renderRow}
        onRenderRow={onRenderRow}
      />
    );
  }
  const view = render(<Bare />);
  // 머리글을 안 주면 스크롤 상자가 맨 바깥 요소다. 주면 그 바깥에 grid 가 한 겹 더 있다(아래 「머리글을 받으면」).
  const scroller = view.container.querySelector<HTMLElement>(
    '[data-testid="rt-scroll"]',
  )!;
  const sizer = scroller.firstElementChild as HTMLElement;
  const offset = sizer.firstElementChild as HTMLElement;
  const rowElements = () => [...offset.children] as HTMLElement[];
  const row = (id: string) =>
    view.container.querySelector<HTMLElement>(`[data-row-id="${id}"]`)!;
  const rendered = () => onRenderRow.mock.calls.map(([id]) => id);
  const board = () => handle.board!;
  /** 스크롤 상자를 옮기고 스크롤 이벤트를 낸다(TanStack Virtual 이 그 이벤트를 듣는다). */
  const scrollTo = (top: number) =>
    act(() => {
      scroller.scrollTop = top;
      fireEvent.scroll(scroller);
    });
  return {
    view,
    scroller,
    sizer,
    offset,
    rowElements,
    row,
    rendered,
    onRenderRow,
    board,
    scrollTo,
  };
}

describe('RowStack: 구조와 자리', () => {
  it('스크롤 상자 › 자리 잡는 판 › 행들의 묶음 › 행. 클래스 이름과 모양이 없어도 스스로 스크롤 상자가 되고 높이를 잡는다', () => {
    const { scroller, sizer, offset, rowElements } = setup();
    expect(scroller.style.overflowY).toBe('auto');
    expect(scroller.getAttribute('class')).toBeNull();
    // 판의 높이 = 행을 다 쌓은 높이. 스크롤 막대의 길이가 된다.
    expect(sizer.style.height).toBe(`${100 * ROW}px`);
    expect(sizer.style.position).toBe('relative');
    expect(offset.style.transform).toBe('translateY(0px)');
    // 행에는 자리를 주지 않는다(흐름대로 쌓인다). 클래스도 인라인 style 도 없다.
    for (const element of rowElements()) {
      expect(element.getAttribute('style')).toBeNull();
      expect(element.getAttribute('class')).toBeNull();
    }
  });

  it('100행 가운데 보이는 행과 위아래 여유분만 DOM 에 있다', () => {
    const { rowElements } = setup();
    // 높이 400 에 행 40 → 보이는 행 10, 아래로 여유분 2.
    expect(rowElements().map((element) => element.dataset.rowId)).toEqual(
      Array.from({ length: 10 + OVERSCAN }, (_, i) => `r${i}`),
    );
  });

  it('스크롤하면 그릴 행이 바뀌고, 묶음이 첫 행의 자리만큼 한꺼번에 내려간다. 판의 높이는 그대로다', () => {
    const { rowElements, offset, sizer, scrollTo } = setup();
    scrollTo(30 * ROW);
    const indexes = rowElements().map((element) =>
      Number(element.dataset.index),
    );
    // 30번째부터 10행이 보이고 위아래로 여유분 2.
    expect(indexes).toEqual(
      Array.from({ length: 10 + 2 * OVERSCAN }, (_, i) => 30 - OVERSCAN + i),
    );
    expect(offset.style.transform).toBe(
      `translateY(${(30 - OVERSCAN) * ROW}px)`,
    );
    expect(sizer.style.height).toBe(`${100 * ROW}px`);
  });

  it('걸러서 행이 줄면 판의 높이와 행 수 표시가 따라 준다', () => {
    const { scroller, sizer, rowElements, board } = setup();
    act(() => board().table.setFilter({ statuses: ['accepted'] }));
    expect(scroller.getAttribute('aria-rowcount')).toBe('50');
    expect(sizer.style.height).toBe(`${50 * ROW}px`);
    expect(rowElements()[0]!.dataset.rowId).toBe('r1');
    act(() => board().table.setFilter({ text: '없는 글자' }));
    expect(rowElements()).toHaveLength(0);
    expect(scroller.getAttribute('aria-rowcount')).toBe('0');
    expect(offset(scroller).style.transform).toBe('translateY(0px)');
  });

  it('클래스 이름을 주면 스크롤 상자와 행에 붙는다. 그 밖에는 붙지 않는다', () => {
    const { scroller, sizer, offset, rowElements } = setup({
      classNames: { scroller: 'my-scroll', row: 'my-row' },
    });
    expect(scroller.className).toBe('my-scroll');
    expect(
      rowElements().every((element) => element.className === 'my-row'),
    ).toBe(true);
    expect(sizer.getAttribute('class')).toBeNull();
    expect(offset.getAttribute('class')).toBeNull();
  });
});

/** 스크롤 상자 › 판 › 묶음. */
function offset(scroller: HTMLElement): HTMLElement {
  return scroller.firstElementChild!.firstElementChild as HTMLElement;
}

describe('RowFrame: 다시 그려진 행의 높이를 그 자리에서 다시 잰다(sid:MARC-ISSUE-29, 밴드 PL1 ③)', () => {
  /** 펼친 행(속의 글자가 「…|true」로 끝난다)만 높이 200 으로 보이게 한다. 나머지는 fakeLayout 의 값 그대로(afterEach 가 되돌린다). */
  function tallWhenExpanded() {
    const base = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      'offsetHeight',
    )!;
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
      configurable: true,
      get(this: HTMLElement) {
        if (
          this.dataset.index !== undefined &&
          this.querySelector('[data-testid="cell"]')?.textContent?.endsWith(
            '|true',
          )
        )
          return 200;
        return base.get!.call(this) as number;
      },
    });
  }

  it('행을 펼치면 같은 그리기 안에서 스크롤 길이(판의 높이)가 펼친 높이만큼 늘어난다. 접으면 돌아온다', () => {
    // jsdom 에는 ResizeObserver 가 없다. 그래서 여기서 높이가 반영된다면 「크기가 바뀐 것을 나중에 알려 줘서」가 아니라
    // 행이 다시 그려진 그 자리에서 쟀기 때문이다. 브라우저에서는 이 차이가 「펼친 직후 한두 프레임 동안 스크롤 길이가 옛 값」으로 나타났다
    // (그 사이 입력 칸에서 End 를 누르면 옛 끝까지만 굴러갔다. e2e/review-table.spec.ts 「펼친 직후 … 기다림 없음」).
    const { sizer, board } = setup();
    tallWhenExpanded();
    expect(sizer.style.height).toBe(`${100 * ROW}px`);
    act(() => board().window.toggleExpanded('r0'));
    expect(sizer.style.height).toBe(`${100 * ROW + (200 - ROW)}px`);
    act(() => board().window.toggleExpanded('r0'));
    expect(sizer.style.height).toBe(`${100 * ROW}px`);
  });

  it('높이를 다시 재도 행은 한 번만 다시 그려진다(펼친 그 행). 아래 행들은 밀려날 뿐 다시 그려지지 않는다', () => {
    const { rendered, onRenderRow, board } = setup();
    tallWhenExpanded();
    onRenderRow.mockClear();
    act(() => board().window.toggleExpanded('r0'));
    expect(rendered()).toEqual(['r0']);
  });
});

describe('RowStack · RowFrame: 접근성 속성과 상태 표시', () => {
  it('스크롤 상자는 grid 이고 걸러 본 행의 수를 말하고 초점을 받는다. 테스트가 찾는 이름표가 붙어 있다', () => {
    const { scroller } = setup();
    expect(scroller.getAttribute('role')).toBe('grid');
    expect(scroller.getAttribute('aria-rowcount')).toBe('100');
    expect(scroller.tabIndex).toBe(0);
    expect(scroller.dataset.testid).toBe('rt-scroll');
  });

  it('행은 row 이고 순서(1부터)·id·검토 상태를 달고 있다. 순서 표시는 정렬을 따라간다', () => {
    const { row, board, rowElements } = setup();
    expect(row('r0').getAttribute('role')).toBe('row');
    expect([
      row('r0').dataset.index,
      row('r0').getAttribute('aria-rowindex'),
      row('r0').dataset.status,
    ]).toEqual(['0', '1', 'pending']);
    expect([
      row('r3').dataset.index,
      row('r3').getAttribute('aria-rowindex'),
      row('r3').dataset.status,
    ]).toEqual(['3', '4', 'accepted']);
    // 이름으로 내림 정렬: 「품목 99」 가 맨 위로 온다.
    act(() => board().table.columns[0]!.toggleSort());
    act(() => board().table.columns[0]!.toggleSort());
    expect(rowElements()[0]!.dataset.rowId).toBe('r99');
    expect([
      row('r99').dataset.index,
      row('r99').getAttribute('aria-rowindex'),
    ]).toEqual(['0', '1']);
  });

  it('고르기는 aria-selected 로, 지금 행은 data-active 로 나온다. 아닌 행에는 data-active 가 아예 없다', () => {
    const { row, board, view } = setup();
    expect(row('r1').getAttribute('aria-selected')).toBe('false');
    expect(view.container.querySelectorAll('[data-active]')).toHaveLength(0);
    act(() => board().table.toggleSelected('r1'));
    act(() => board().window.setActiveId('r2'));
    expect(row('r1').getAttribute('aria-selected')).toBe('true');
    expect(row('r0').getAttribute('aria-selected')).toBe('false');
    expect(
      [...view.container.querySelectorAll<HTMLElement>('[data-active]')].map(
        (element) => element.dataset.rowId,
      ),
    ).toEqual(['r2']);
    expect(row('r2').dataset.active).toBe('true');
  });

  it('검토 상태가 바뀌면 data-status 가 바뀌고, 계산이 실패한 행에만 data-calc-failed 가 붙는다', () => {
    const { row, board } = setup({
      calculate: () => {
        throw new Error('서버 오류');
      },
    });
    expect(row('r0').dataset.calcFailed).toBeUndefined();
    act(() => void board().act('r0', { type: 'edit', candidateId: 'b' }));
    expect(row('r0').dataset.status).toBe('edited');
    expect(row('r0').dataset.calcFailed).toBe('true');
    expect(row('r1').dataset.calcFailed).toBeUndefined();
    act(() => void board().act('r2', { type: 'accept' }));
    expect(row('r2').dataset.status).toBe('accepted');
  });

  it('고르기·지금 행·펼침은 하나씩 따로 전해진다(서로 바뀌지 않는다)', () => {
    const { row, board } = setup();
    const cell = (id: string) =>
      row(id).querySelector('[data-testid="cell"]')!.textContent;
    act(() => board().table.toggleSelected('r1'));
    act(() => board().window.setActiveId('r2'));
    act(() => board().window.toggleExpanded('r3'));
    expect(cell('r1')).toBe('품목 1|1|true|false|false');
    expect(cell('r2')).toBe('품목 2|2|false|true|false');
    expect(cell('r3')).toBe('품목 3|3|false|false|true');
  });

  it('행 객체가 그대로여도 순서가 바뀌면 순서 표시가 따라간다(걸러서 앞의 행이 빠질 때)', () => {
    const { row, board } = setup();
    const kept = board().table.rows[3]!;
    expect([
      row('r3').dataset.index,
      row('r3').getAttribute('aria-rowindex'),
    ]).toEqual(['3', '4']);
    // 반영(홀수째)만 남기면 r3 은 둘째가 된다. 행 객체는 같은 것이다.
    act(() => board().table.setFilter({ statuses: ['accepted'] }));
    expect(board().table.rows[1]).toBe(kept);
    expect([
      row('r3').dataset.index,
      row('r3').getAttribute('aria-rowindex'),
    ]).toEqual(['1', '2']);
    expect(row('r3').querySelector('[data-testid="cell"]')!.textContent).toBe(
      '품목 3|1|false|false|false',
    );
  });

  it('행의 요소는 순서가 아니라 행을 따라간다: 정렬이 바뀌어도 속의 입력에 적던 글자가 그 행에 남는다', () => {
    const { row, board, rowElements } = setup({ rows: alternatingRows(8) });
    const input = (id: string) =>
      row(id).querySelector<HTMLInputElement>('[aria-label="칸 속의 입력"]')!;
    const element = row('r2');
    fireEvent.change(input('r2'), { target: { value: '적던 글' } });
    // 이름으로 내림 정렬: r7 이 맨 위, r2 는 여섯째로 간다.
    act(() => board().table.columns[0]!.toggleSort());
    act(() => board().table.columns[0]!.toggleSort());
    expect(rowElements()[0]!.dataset.rowId).toBe('r7');
    expect(row('r2').dataset.index).toBe('5');
    expect(row('r2')).toBe(element);
    expect(input('r2').value).toBe('적던 글');
    expect(input('r7').value).toBe('');
  });

  it('속을 그리는 함수는 행과 화면 상태(순서, 고르기, 지금 행, 펼침)를 받는다', () => {
    const { row, board } = setup();
    const cell = (id: string) =>
      row(id).querySelector('[data-testid="cell"]')!.textContent;
    expect(cell('r4')).toBe('품목 4|4|false|false|false');
    act(() => board().table.toggleSelected('r4'));
    act(() => board().window.setActiveId('r4'));
    act(() => board().window.toggleExpanded('r4'));
    expect(cell('r4')).toBe('품목 4|4|true|true|true');
    expect(cell('r5')).toBe('품목 5|5|false|false|false');
  });
});

describe('RowStack: 머리글을 받으면', () => {
  const HEADER = (
    <>
      <span role="columnheader">품목</span>
      <button type="button">정렬</button>
    </>
  );

  it('grid 가 머리글 줄과 스크롤 상자를 같이 감싼다. 머리글 줄이 첫 행(1)이고 자료 행은 2부터다. 행 수는 머리글 줄까지 센다', () => {
    const { view, scroller, sizer, row, board } = setup({
      header: HEADER,
      classNames: { grid: 'g', header: 'h', scroller: 's', row: 'r' },
    });
    const grid = view.container.firstElementChild as HTMLElement;
    expect(grid.getAttribute('role')).toBe('grid');
    expect(grid.getAttribute('aria-rowcount')).toBe('101');
    expect(grid.className).toBe('g');
    expect(grid.getAttribute('style')).toBeNull();

    // grid 의 바로 아래는 둘뿐이다: 머리글 줄, 스크롤 상자. 머리글 줄은 스크롤 상자 밖이라 스크롤해도 제자리에 있다.
    const [headerRow, box] = [...grid.children] as HTMLElement[];
    expect(grid.children).toHaveLength(2);
    expect(headerRow!.getAttribute('role')).toBe('row');
    expect(headerRow!.getAttribute('aria-rowindex')).toBe('1');
    expect(headerRow!.className).toBe('h');
    expect(headerRow!.querySelector('[role="columnheader"]')!.textContent).toBe(
      '품목',
    );
    expect(box).toBe(scroller);

    // 스크롤 상자는 grid 가 아니라 행들의 묶음(rowgroup)이 된다. 행 수는 grid 가 말한다. 초점과 이름표, 속의 구조는 그대로다.
    expect(scroller.getAttribute('role')).toBe('rowgroup');
    expect(scroller.hasAttribute('aria-rowcount')).toBe(false);
    expect(scroller.tabIndex).toBe(0);
    expect(scroller.className).toBe('s');
    expect(scroller.style.overflowY).toBe('auto');
    expect(sizer.style.height).toBe(`${100 * ROW}px`);

    expect([
      row('r0').dataset.index,
      row('r0').getAttribute('aria-rowindex'),
    ]).toEqual(['0', '2']);
    expect([
      row('r3').dataset.index,
      row('r3').getAttribute('aria-rowindex'),
    ]).toEqual(['3', '5']);
    // 행(role=row)은 머리글 줄까지 전부 그 grid 안에 있다.
    const rows = [
      ...view.container.querySelectorAll<HTMLElement>('[role="row"]'),
    ];
    expect(rows[0]).toBe(headerRow);
    expect(
      rows.every((element) => element.closest('[role="grid"]') === grid),
    ).toBe(true);

    act(() => board().table.setFilter({ statuses: ['pending'] }));
    expect(grid.getAttribute('aria-rowcount')).toBe('51');
    expect([
      row('r2').dataset.index,
      row('r2').getAttribute('aria-rowindex'),
    ]).toEqual(['1', '3']);
  });

  it('머리글 줄 속의 단추에서 누른 키는 행 창에 닿지 않는다(스크롤 상자 밖이다)', () => {
    const { view, board } = setup({ header: HEADER });
    fireEvent.keyDown(view.container.querySelector('[role="row"] button')!, {
      key: 'ArrowDown',
    });
    expect(board().window.activeId).toBeNull();
  });

  it.each([[false], [null]])(
    '머리글 자리에 %s 가 오면 머리글이 없는 것이다(조건부로 그리는 쓰임: header={조건 && <…/>})',
    (header) => {
      const { view, scroller, row } = setup({ header });
      expect(view.container.firstElementChild).toBe(scroller);
      expect(scroller.getAttribute('role')).toBe('grid');
      expect(scroller.getAttribute('aria-rowcount')).toBe('100');
      expect(row('r0').getAttribute('aria-rowindex')).toBe('1');
      // 빈 머리글 줄이 행으로 세어지지 않는다.
      expect(view.container.querySelectorAll('[role="row"]')).toHaveLength(
        view.container.querySelectorAll('[data-row-id]').length,
      );
    },
  );

  it('머리글을 안 주면 전과 같다: 바깥 요소가 생기지 않고 스크롤 상자가 곧 grid 다. 행은 1부터다', () => {
    const { view, scroller, row } = setup({
      classNames: { grid: 'g', header: 'h' },
    });
    expect(view.container.firstElementChild).toBe(scroller);
    expect(scroller.getAttribute('role')).toBe('grid');
    expect(scroller.getAttribute('aria-rowcount')).toBe('100');
    expect(scroller.getAttribute('class')).toBeNull();
    expect(row('r0').getAttribute('aria-rowindex')).toBe('1');
    expect(view.container.querySelectorAll('[role="row"]')).toHaveLength(
      view.container.querySelectorAll('[data-row-id]').length,
    );
  });
});

describe('RowStack: 키보드', () => {
  const active = (container: HTMLElement) =>
    container.querySelector<HTMLElement>('[data-active]')?.dataset.rowId ??
    null;

  it('스크롤 상자에서 누른 키는 훅에 닿고, 처리된 키는 브라우저의 기본 동작(스크롤)을 막는다. 모르는 키는 그대로 둔다', () => {
    const { scroller, view } = setup();
    // fireEvent 는 기본 동작이 막히지 않았으면 true 를 돌려준다.
    expect(fireEvent.keyDown(scroller, { key: 'ArrowDown' })).toBe(false);
    expect(active(view.container)).toBe('r0');
    expect(fireEvent.keyDown(scroller, { key: 'j' })).toBe(false);
    expect(active(view.container)).toBe('r1');
    expect(fireEvent.keyDown(scroller, { key: 'a' })).toBe(true);
    expect(fireEvent.keyDown(scroller, { key: 'Tab' })).toBe(true);
    expect(active(view.container)).toBe('r1');
  });

  it('Space 는 지금 행을 고르고 Enter 는 펼친다(훅의 handleKey 로 간다)', () => {
    const { scroller, row, board } = setup();
    fireEvent.keyDown(scroller, { key: 'ArrowDown' });
    fireEvent.keyDown(scroller, { key: ' ' });
    expect(row('r0').getAttribute('aria-selected')).toBe('true');
    fireEvent.keyDown(scroller, { key: 'Enter' });
    expect(board().window.expandedIds.has('r0')).toBe(true);
  });

  it('행 속의 입력·고르기·글 칸·단추에서 누른 키는 그쪽의 것이다. 지금 행이 옮겨 가지 않고 기본 동작도 막지 않는다', () => {
    const { scroller, row, view, board } = setup();
    fireEvent.keyDown(scroller, { key: 'ArrowDown' });
    for (const label of [
      '칸 속의 입력',
      '칸 속의 고르기',
      '칸 속의 글',
      '칸 속의 단추',
    ]) {
      const control = row('r0').querySelector<HTMLElement>(
        `[aria-label="${label}"]`,
      )!;
      for (const key of ['j', 'ArrowDown', 'End', ' ', 'Enter'])
        expect(fireEvent.keyDown(control, { key })).toBe(true);
    }
    expect(active(view.container)).toBe('r0');
    expect(row('r0').getAttribute('aria-selected')).toBe('false');
    expect(board().window.expandedIds.size).toBe(0);
  });

  it('행 속의 조작이 아닌 자리(글자)에서 올라온 키는 받는다', () => {
    const { row, view } = setup();
    fireEvent.keyDown(row('r3').querySelector('[data-testid="cell"]')!, {
      key: 'j',
    });
    expect(active(view.container)).toBe('r0');
  });

  it('Ctrl·Meta·Alt 와 같이 누른 키는 받지 않는다(브라우저의 단축키다)', () => {
    const { scroller, view } = setup();
    for (const modifier of ['ctrlKey', 'metaKey', 'altKey'] as const)
      expect(fireEvent.keyDown(scroller, { key: 'j', [modifier]: true })).toBe(
        true,
      );
    expect(active(view.container)).toBeNull();
    // Shift 는 조합키로 치지 않는다.
    fireEvent.keyDown(scroller, { key: 'j', shiftKey: true });
    expect(active(view.container)).toBe('r0');
  });
});

describe('RowFrame: 한 행만 다시 그리기', () => {
  it('처음에는 DOM 에 있는 행을 한 번씩만 그린다', () => {
    const { rendered, rowElements } = setup();
    expect(rendered().sort()).toEqual(
      rowElements()
        .map((element) => element.dataset.rowId)
        .sort(),
    );
  });

  it('한 행의 상태·고르기·펼침을 바꾸면 그 행만 다시 그려진다', () => {
    const { rendered, onRenderRow, board } = setup();
    onRenderRow.mockClear();
    act(() => void board().act('r3', { type: 'finalize' }));
    expect(rendered()).toEqual(['r3']);

    onRenderRow.mockClear();
    act(() => board().table.toggleSelected('r5'));
    expect(rendered()).toEqual(['r5']);

    onRenderRow.mockClear();
    act(() => board().window.toggleExpanded('r7'));
    expect(rendered()).toEqual(['r7']);
  });

  it('지금 행을 옮기면 떠난 행과 닿은 행 둘만 다시 그려진다', () => {
    const { rendered, onRenderRow, scroller } = setup();
    fireEvent.keyDown(scroller, { key: 'ArrowDown' });
    onRenderRow.mockClear();
    fireEvent.keyDown(scroller, { key: 'ArrowDown' });
    expect(rendered().sort()).toEqual(['r0', 'r1']);
  });

  it('일괄 동작은 바뀐 행 가운데 DOM 에 있는 것만 다시 그린다', () => {
    const { rendered, onRenderRow, board, rowElements } = setup();
    onRenderRow.mockClear();
    // 검토대기(짝수째) 50행이 전부 반영으로 바뀐다. DOM 에는 12행(짝수째 6행)이 있다.
    act(() => void board().bulk('filtered', { type: 'accept' }));
    expect(board().lastBulk!.applied).toBe(50);
    expect(rendered().sort()).toEqual(
      rowElements()
        .map((element) => element.dataset.rowId!)
        .filter((id) => Number(id.slice(1)) % 2 === 0)
        .sort(),
    );
    expect(rendered()).toHaveLength(6);
  });

  it('스크롤해도 이미 그린 행은 다시 그리지 않는다. 새로 들어온 행만 그린다', () => {
    const { rendered, onRenderRow, scrollTo, rowElements } = setup();
    const before = new Set(
      rowElements().map((element) => element.dataset.rowId),
    );
    onRenderRow.mockClear();
    scrollTo(3 * ROW);
    const after = rowElements().map((element) => element.dataset.rowId!);
    const entered = after.filter((id) => !before.has(id));
    expect(entered.length).toBeGreaterThan(0);
    expect(rendered().sort()).toEqual(entered.sort());
  });

  it('★ 하지 말라고 적어 둔 것: renderRow 를 useCallback 으로 감싸지 않으면 한 행을 바꿔도 DOM 의 행이 전부 다시 그려진다', () => {
    const { rendered, onRenderRow, board, rowElements } = setup({
      unstableRenderRow: true,
    });
    onRenderRow.mockClear();
    act(() => board().table.toggleSelected('r5'));
    expect(rendered().sort()).toEqual(
      rowElements()
        .map((element) => element.dataset.rowId!)
        .sort(),
    );
  });
});
