// 행 하나의 틀. 모양 없는 컴포넌트다: 행의 바깥 요소와 그 상태 표시를 맡고, 속(칸, 펼친 속)은 쓰는 쪽이 그린다.
// 보통은 직접 쓰지 않는다. <RowStack> 이 그릴 행마다 하나씩 놓는다.
//
//   <div role="row" data-index data-row-id data-status data-calc-failed data-active aria-selected aria-rowindex>     aria-rowindex 는 머리글 줄이 있으면 2부터
//     {renderRow(row, state)}        화면이 그리는 속. 칸에는 화면이 role="gridcell" 을 붙인다
//
// 여기서 맡는 것 셋:
//   1) 한 행만 다시 그리기(memo). 행 객체와 순서·고르기·지금 행·펼침이 그대로면 다시 그리지 않는다.
//      한 행을 바꾸면 그 행만 새 객체가 되므로(useReviewRows) 그 행만 다시 그려진다.
//   2) 상태 표시. 화면의 CSS 와 테스트가 이것을 보고 쓴다(예: [aria-selected="true"], [data-active], [data-status="finalized"]).
//      펼침은 속성으로 내지 않는다. 펼치는 단추(aria-expanded)가 화면의 것이라 state.expanded 로만 넘긴다.
//   3) 높이 재기. ref 와 data-index 를 같이 달아야 TanStack Virtual 이 이 요소가 몇 번째 행인지 안다.
//      언제 재나: (가) 처음 놓일 때(ref) (나) 이 행이 다시 그려진 직후(아래 useLayoutEffect) (다) 그 밖에 크기가 바뀌면(TanStack 의 ResizeObserver).
//      (나)가 없으면 펼친 높이는 (다)로만 들어오는데, 그것은 화면이 그려진 뒤 한두 프레임 늦다. 그 사이 스크롤 길이가 옛 값이라
//      펼친 직후 입력 칸 안의 End(브라우저의 「끝으로」)가 옛 끝에서 멈췄다(sid:MARC-ISSUE-29. f832ce4 를 밴드 PL1 ③ 에서 되살림).
//      (나)에 measureRef 를 다시 부르지 않는 까닭: TanStack 은 한 번 잰 행을 다시 재 달라고 하면 적어 둔 값을 돌려준다(DOM 을 읽지 않는다).
//
// ★ memo 가 뚫리는 길 하나: renderRow 가 그릴 때마다 새 함수면 모든 행이 다시 그려진다.
//   쓰는 쪽은 renderRow 를 useCallback 으로 감싸고, 그 안에서 쓰는 것(열, 동작 함수)을 의존 목록에 적는다.
//   훅이 내주는 동작 함수(act, retry, toggleSelected, toggleExpanded, setActiveId)는 늘 같은 함수라 의존 목록에 넣어도 된다.
import { memo, useCallback, useLayoutEffect, useRef } from 'react';
import type { ReactNode } from 'react';

import { isRecalcFailed } from '../model/index.ts';
import type { ReviewRow } from '../model/index.ts';

/** 행 하나의 화면 상태. 속을 그리는 함수가 받는다. */
export interface RowState {
  /** 걸러 보고 정렬한 결과에서의 순서(0부터). */
  index: number;
  selected: boolean;
  /** 「지금 행」인가(키보드로 옮기는 그 행). */
  active: boolean;
  expanded: boolean;
}

/** 행의 속을 그린다. ★ useCallback 으로 감싸서 넘긴다(위 머리말). */
export type RenderRow = (row: ReviewRow, state: RowState) => ReactNode;

export interface RowFrameProps extends RowState {
  row: ReviewRow;
  /** 표 전체에서 몇 번째 행인가(1부터, 머리글 줄이 있으면 그것까지 센다). aria-rowindex 로 나간다. <RowStack> 이 정한다. */
  rowIndex: number;
  /** useRowWindow 의 measureRef. */
  measureRef(element: Element | null): void;
  /** useRowWindow 의 remeasure. */
  remeasure(element: HTMLElement): void;
  className?: string;
  renderRow: RenderRow;
  /** 이 행이 다시 그려질 때마다 불린다. 재는 데만 쓴다(tools/measure-table.ts, 「한 행만 다시 그린다」 테스트). */
  onRenderRow?: (rowId: string) => void;
}

export const RowFrame = memo(function RowFrame({
  row,
  index,
  rowIndex,
  selected,
  active,
  expanded,
  measureRef,
  remeasure,
  className,
  renderRow,
  onRenderRow,
}: RowFrameProps) {
  onRenderRow?.(row.id);

  // 높이 재기 (나): 이 행이 다시 그려졌으면(펼침, 상태가 바뀌어 속이 달라짐 …) 화면에 칠해지기 전에 높이를 다시 잰다.
  // 의존 목록이 없다: memo 덕에 이 행이 실제로 다시 그려질 때만 돈다. 처음 놓일 때는 ref 가 이미 쟀으므로 건너뛴다
  // (그 건너뛰기를 지우면 스크롤로 들어오는 행마다 높이를 한 번 더 읽는다). 높이가 그대로면 아무 일도 일어나지 않는다.
  const elementRef = useRef<HTMLDivElement | null>(null);
  const placed = useRef(false);
  useLayoutEffect(() => {
    if (placed.current && elementRef.current) remeasure(elementRef.current);
    placed.current = true;
  });
  // ref 둘을 한 요소에: 우리 것(위에서 쓴다)과 TanStack 의 것(처음 재고, 크기 변화를 지켜본다). 함수가 그대로여야 React 가 그릴 때마다 뗐다 붙이지 않는다.
  const attach = useCallback(
    (element: HTMLDivElement | null) => {
      elementRef.current = element;
      measureRef(element);
    },
    [measureRef],
  );
  return (
    <div
      ref={attach}
      role="row"
      className={className}
      data-index={index}
      data-row-id={row.id}
      data-status={row.status}
      data-calc-failed={isRecalcFailed(row) || undefined}
      data-active={active || undefined}
      aria-selected={selected}
      aria-rowindex={rowIndex}
    >
      {renderRow(row, { index, selected, active, expanded })}
    </div>
  );
});
