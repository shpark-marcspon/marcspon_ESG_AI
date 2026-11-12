// 검토 표의 화면(표 모양). 얇은 층이다: 헤드리스 훅(useReviewBoard)이 준 것을 그리고, 누른 것을 훅에 넘긴다.
// 규칙(무엇이 되고 안 되는지, 무엇이 대상인지)은 여기 없다. 행들을 스크롤 상자에 놓고 재고 키보드를 받는 구조도 여기 없다
// (headless 의 <RowStack> 과 <RowFrame>). 이 파일에 남은 것은 생김이다: 머리글 줄의 칸, 칸의 배치, 행의 속, 클래스 이름.
// 화면을 다른 UI 라이브러리로 바꿀 때는 ui/ 폴더만 새로 쓴다.
import { useCallback } from 'react';

import { RowStack, useReviewBoard } from '../hooks/index.ts';
import type {
  Calculate,
  ColumnView,
  RenderRow,
  ReviewColumn,
} from '../hooks/index.ts';
import type { ActionResult, ReviewAction, ReviewRow } from '../model/index.ts';
import { RowDetail } from './RowDetail.tsx';
import { Toolbar } from './Toolbar.tsx';
import './review-table.css';

export interface ReviewTableProps {
  /** parseTableInput 을 통과한 행들. 처음 값만 읽는다. 자료가 바뀌면 key 를 바꿔 부품을 새로 만든다. */
  rows: readonly ReviewRow[];
  /** 카테고리를 고칠 때 고를 수 있는 값들. */
  categories: readonly string[];
  /** 열 구성. 이 부품은 열을 정하지 않는다. */
  columns: readonly ReviewColumn[];
  /** 배출량 계산. 서버의 일이라 밖에서 받는다. */
  calculate: Calculate;
  /** 바뀐 행을 알린다. 저장을 붙일 자리. */
  onChange?: (changed: readonly ReviewRow[]) => void;
  /**
   * 행 하나가 다시 그려질 때마다 불린다. 제품의 기능이 아니라 들여다보는 구멍이다: 측정(tools/measure-table.ts)과
   * 「한 행만 다시 그린다」 테스트(ReviewTable.test.tsx)가 쓴다. 공개 부품에 붙어 있는 것이 어색하지만,
   * 떼면 그 테스트가 볼 곳이 없어진다(React 의 Profiler 는 행 하나하나를 가르지 못한다). 그래서 두었다.
   * 세는 자리는 헤드리스의 <RowFrame> 이다(memo 가 거기 있다).
   */
  onRenderRow?: (rowId: string) => void;
}

/** 접힌 행의 높이(px). review-table.css 의 .rt-row(칸 35 + 테두리 1)와 같아야 한다. */
const ROW_HEIGHT = 36;
/** 헤드리스 컴포넌트에 입히는 클래스 이름. 생김은 review-table.css 에 있다. */
const STACK_CLASSES = { grid: 'rt-grid', scroller: 'rt-scroll', row: 'rt-row' };

export function ReviewTable({
  rows,
  categories,
  columns,
  calculate,
  onChange,
  onRenderRow,
}: ReviewTableProps) {
  const board = useReviewBoard({
    rows,
    columns,
    calculate,
    onChange,
    estimateRowHeight: ROW_HEIGHT,
  });
  const { table, window, act, retry } = board;
  const { toggleSelected, allSelected } = table;
  const { toggleExpanded, setActiveId } = window;

  // 칸의 배치: 고르기 칸, 펼치기 칸, 그리고 입력으로 받은 열들. 머리글 줄과 행의 칸 줄이 같은 값을 쓴다.
  const template = [
    '32px',
    '32px',
    ...table.columns.map((column) =>
      column.width ? `${column.width}px` : 'minmax(0, 1fr)',
    ),
  ].join(' ');

  // 행 하나의 속. ★ useCallback: 이 함수가 새로 만들어지면 그려진 행이 전부 다시 그려진다(headless/RowFrame.tsx 머리말).
  // 아래 목록에서 바뀌는 것은 열(정렬을 바꿀 때)과 칸의 배치뿐이다. 나머지는 훅이 늘 같은 함수로 내준다.
  const tableColumns = table.columns;
  const renderRow = useCallback<RenderRow>(
    (row, state) => (
      <RowBody
        row={row}
        selected={state.selected}
        expanded={state.expanded}
        columns={tableColumns}
        template={template}
        categories={categories}
        act={act}
        retry={retry}
        toggleSelected={toggleSelected}
        toggleExpanded={toggleExpanded}
        setActiveId={setActiveId}
      />
    ),
    [
      tableColumns,
      template,
      categories,
      act,
      retry,
      toggleSelected,
      toggleExpanded,
      setActiveId,
    ],
  );

  // 머리글 줄의 속. 줄 자체(role="row", 순서 1)와 그것을 grid 안에 넣는 일은 <RowStack> 이 한다. 여기서는 칸을 그린다.
  // 칸은 전부 columnheader 다(고르기 칸과 펼치기 칸도). aria-sort 는 열의 머리글 칸에만 뜻이 있어 거기에만 붙인다.
  const header = (
    <div className="rt-head" style={{ gridTemplateColumns: template }}>
      <span role="columnheader">
        <input
          type="checkbox"
          aria-label="걸러 본 결과 모두 고르기"
          checked={allSelected}
          onChange={() => table.selectAll(!allSelected)}
        />
      </span>
      {/* 펼치기 칸의 머리글은 글자가 없다. 화면 읽기 프로그램이 읽을 이름만 단다. */}
      <span role="columnheader" aria-label="펼치기" />
      {table.columns.map((column) => (
        <span
          key={column.id}
          role="columnheader"
          className={column.align === 'right' ? 'rt-right' : undefined}
          aria-sort={
            column.sorted === 'asc' ? 'ascending'
            : column.sorted === 'desc' ?
              'descending'
            : 'none'
          }
        >
          {column.sortable ?
            <button
              type="button"
              className="rt-sort"
              onClick={column.toggleSort}
            >
              {column.header}
              {column.sorted === 'asc' ?
                ' ▲'
              : column.sorted === 'desc' ?
                ' ▼'
              : ''}
            </button>
          : column.header}
        </span>
      ))}
    </div>
  );

  return (
    <div className="rt">
      <Toolbar board={board} categories={categories} />

      <RowStack
        window={window}
        rowCount={table.rows.length}
        selectedIds={table.selectedIds}
        classNames={STACK_CLASSES}
        header={header}
        renderRow={renderRow}
        onRenderRow={onRenderRow}
      />
    </div>
  );
}

interface RowBodyProps {
  row: ReviewRow;
  selected: boolean;
  expanded: boolean;
  columns: readonly ColumnView[];
  template: string;
  categories: readonly string[];
  act(rowId: string, action: ReviewAction): ActionResult;
  retry(rowId: string): boolean;
  toggleSelected(rowId: string): void;
  toggleExpanded(rowId: string): void;
  setActiveId(rowId: string): void;
}

/** 행의 속: 칸 한 줄과, 펼쳤으면 그 아래의 속. 바깥 요소(role="row" 와 상태 표시)는 <RowFrame> 이 만든다. */
function RowBody({
  row,
  selected,
  expanded,
  columns,
  template,
  categories,
  act,
  retry,
  toggleSelected,
  toggleExpanded,
  setActiveId,
}: RowBodyProps) {
  return (
    <>
      <div
        className="rt-cells"
        style={{ gridTemplateColumns: template }}
        onClick={() => setActiveId(row.id)}
      >
        <span role="gridcell">
          <input
            type="checkbox"
            aria-label="행 고르기"
            checked={selected}
            onChange={() => toggleSelected(row.id)}
          />
        </span>
        <span role="gridcell">
          <button
            type="button"
            className="rt-expand"
            aria-label={expanded ? '접기' : '펼치기'}
            aria-expanded={expanded}
            onClick={() => toggleExpanded(row.id)}
          >
            {expanded ? '▾' : '▸'}
          </button>
        </span>
        {columns.map((column) => (
          <span
            key={column.id}
            role="gridcell"
            data-column={column.id}
            className={column.align === 'right' ? 'rt-right' : undefined}
          >
            {column.render ? column.render(row) : (column.value(row) ?? '—')}
          </span>
        ))}
      </div>
      {expanded && (
        <RowDetail row={row} categories={categories} act={act} retry={retry} />
      )}
    </>
  );
}
