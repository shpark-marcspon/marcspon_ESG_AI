// 행 창: 스크롤 상자와, 그 안에 세로로 쌓은 「지금 그릴 행들」. 모양 없는 컴포넌트다.
//
// 행을 전부 그리지 않는다. 무엇을 그릴지는 useRowWindow(TanStack Virtual)가 정하고, 이 컴포넌트는 그것을 DOM 에 놓는다.
//
//   <div role="grid" aria-rowcount tabIndex=0 onKeyDown>     스크롤 상자. overflow-y: auto 만 스스로 갖는다
//     <div>                                                  자리 잡는 판. 높이 = 행을 다 쌓은 높이(스크롤 막대의 길이가 된다)
//       <div>                                                그릴 행들의 묶음. 첫 행의 자리만큼 한꺼번에 내린다(translateY)
//         <RowFrame> …                                       행마다 하나. 흐름대로 쌓인다
//
// 머리글 줄이 있는 화면(표)은 header 를 준다. 그러면 grid 가 한 겹 바깥으로 나가 머리글 줄과 스크롤 상자를 같이 감싼다:
//
//   <div role="grid" aria-rowcount={행 수 + 1}>              classNames.grid. header 를 줬을 때만 생긴다
//     <div role="row" aria-rowindex=1>{header}</div>         머리글 줄. classNames.header. 속(칸: role="columnheader")은 화면이 그린다
//     <div role="rowgroup" tabIndex=0 onKeyDown>             스크롤 상자. 위와 같은 요소이고 역할만 다르다(행 수는 grid 가 말한다)
//       … 위와 같다. 자료 행의 aria-rowindex 는 2부터
//
//   왜 이 꼴인가: 접근성 규칙에서 행 수(aria-rowcount)와 행의 순서(aria-rowindex)는 머리글 줄까지 센다(WAI-ARIA APG 「Grid and Table Properties」).
//     머리글 줄이 grid 밖에 있으면 그 줄은 표의 행이 아니다. grid 의 아래에는 row 나 rowgroup → row 가 온다(WAI-ARIA 1.2 의 grid).
//   머리글 줄을 스크롤 상자 안에 넣고 위에 붙이는(sticky) 길은 버렸다: 스크롤 길이가 머리글만큼 늘고, 가상 스크롤에 머리글 높이를
//     알려 줘야 하며(화면의 CSS 와 맞출 숫자가 하나 더 생긴다) 어긋나면 「끝으로」에서 마지막 행이 잘린다.
//     지금 꼴은 스크롤 상자와 훅이 그대로다. 머리글 줄은 스크롤 상자 밖이라 스크롤해도 제자리에 있다.
//   값: 초점을 받는 요소(스크롤 상자)가 grid 가 아니라 그 안의 rowgroup 이 된다. 머리글이 없는 화면(카드)은 전과 같다.
//
// 행을 놓는 법은 이것 하나다: 행마다 자리를 주지 않고 묶음을 한 번 내린다.
//   - 스크롤해도 이미 그린 행은 다시 그려지지 않는다(행이 받는 값이 안 바뀐다).
//   - 펼쳐서 높이가 달라진 행 아래의 행들은 브라우저가 밀어낸다. 잰 높이가 반영되기 전에도 겹치지 않는다.
//
// ★ 훅(useRowWindow)과의 선: 뷰어의 <PageStack> 과 달리 훅이 스크롤 요소의 ref 를 쥔다(TanStack Virtual 이 그 요소를
//   직접 지켜보고, 「이 행이 보이게」도 스스로 스크롤한다). 그 ref 를 꽂는 곳이 이 파일과 RowFrame 뿐이다. 화면은 ref 를 만지지 않는다.
// ★ 쓰는 쪽이 해야 할 것 셋:
//   1) 스크롤 상자의 높이가 묶이게 한다(classNames.scroller 로. 예: flex: 1; min-height: 0. 또는 부모가 높이를 묶는다).
//      어디서도 높이가 묶이지 않으면 상자가 행을 다 쌓은 높이만큼 늘어나, 전부 「보이는 행」이 되어 전부 그린다.
//      header 를 주면 바깥의 grid 도 높이가 묶여야 한다(classNames.grid 로. 예: flex: 1; min-height: 0; display: flex; flex-direction: column).
//   2) 접힌 행의 실제 높이를 훅에 준 estimateRowHeight 와 맞춘다(행의 모양은 쓰는 쪽의 것이라 여기서는 모른다).
//   3) renderRow 를 useCallback 으로 감싼다(RowFrame.tsx 머리말).
// 모양을 입히는 길: classNames(스크롤 상자, 행, 그리고 header 를 줬을 때의 grid 와 머리글 줄) + 행의 상태 표시를 보는 CSS + renderRow 가 그리는 속.
import type { KeyboardEvent, ReactNode } from 'react';

import { RowFrame } from './RowFrame.tsx';
import type { RenderRow } from './RowFrame.tsx';
import type { RowWindow } from './useRowWindow.ts';

export interface RowStackProps {
  /** useRowWindow 가 돌려준 것을 통째로(useReviewBoard 의 window). */
  window: RowWindow;
  /** 걸러 보고 정렬한 결과의 행 수(그려진 행의 수가 아니다). useReviewTable 의 rows.length. */
  rowCount: number;
  /** 고른 행의 id. useReviewTable 의 selectedIds. */
  selectedIds: ReadonlySet<string>;
  /** grid 와 header 는 header 를 줬을 때만 쓰인다. */
  classNames?: {
    scroller?: string;
    row?: string;
    grid?: string;
    header?: string;
  };
  /**
   * 머리글 줄의 속(칸들). 화면이 칸마다 role="columnheader" 를 붙여서 준다. 줄 자체(role="row", 순서 1)는 여기서 만든다.
   * 주면 grid 가 머리글 줄과 스크롤 상자를 같이 감싸고, 행 수와 행의 순서가 머리글 줄까지 센다. 안 주면(카드 화면) 스크롤 상자가 곧 grid 다.
   */
  header?: ReactNode;
  /** 행 하나의 속을 그린다. ★ useCallback 으로 감싸서 넘긴다. */
  renderRow: RenderRow;
  /** 행 하나가 다시 그려질 때마다 불린다. 재는 데만 쓴다. */
  onRenderRow?: (rowId: string) => void;
}

export function RowStack({
  window,
  rowCount,
  selectedIds,
  classNames,
  header,
  renderRow,
  onRenderRow,
}: RowStackProps) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    // 글자를 적거나 단추를 누르는 중이면 그쪽의 키다.
    if (
      event.target !== event.currentTarget &&
      (event.target as HTMLElement).closest('input, textarea, select, button')
    )
      return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (window.handleKey(event.key)) event.preventDefault();
  }

  const hasHeader = header !== undefined && header !== null && header !== false;
  // 머리글 줄이 있으면 그것이 첫 행이다. 행 수에 하나를 더하고, 자료 행의 순서는 그 뒤부터 센다.
  const headerRows = hasHeader ? 1 : 0;

  const scroller = (
    // data-testid: 테스트와 측정 스크립트가 스크롤 상자를 찾는 이름표다. 화면마다 다시 붙이지 않게 여기 둔다.
    <div
      ref={window.scrollRef}
      className={classNames?.scroller}
      data-testid="rt-scroll"
      role={hasHeader ? 'rowgroup' : 'grid'}
      aria-rowcount={hasHeader ? undefined : rowCount}
      tabIndex={0}
      onKeyDown={onKeyDown}
      style={{ overflowY: 'auto' }}
    >
      <div style={{ height: window.totalSize, position: 'relative' }}>
        <div
          style={{ transform: `translateY(${window.items[0]?.start ?? 0}px)` }}
        >
          {window.items.map((item) => (
            <RowFrame
              // key 는 행의 id 다. 정렬이 바뀌어도 그 행의 요소(와 펼친 속의 입력값)가 따라간다.
              key={item.row.id}
              row={item.row}
              index={item.index}
              rowIndex={item.index + 1 + headerRows}
              selected={selectedIds.has(item.row.id)}
              active={window.activeId === item.row.id}
              expanded={window.expandedIds.has(item.row.id)}
              measureRef={window.measureRef}
              remeasure={window.remeasure}
              className={classNames?.row}
              renderRow={renderRow}
              onRenderRow={onRenderRow}
            />
          ))}
        </div>
      </div>
    </div>
  );
  if (!hasHeader) return scroller;

  return (
    <div
      role="grid"
      aria-rowcount={rowCount + headerRows}
      className={classNames?.grid}
    >
      <div role="row" aria-rowindex={1} className={classNames?.header}>
        {header}
      </div>
      {scroller}
    </div>
  );
}
