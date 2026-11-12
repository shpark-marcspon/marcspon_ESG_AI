// TanStack Table(v9)을 감싼다. 정렬, 걸러 보기, 행 고르기, 일괄 동작의 대상 정하기.
// 열 구성은 입력으로 받는다. 마크업과 스타일을 모른다(훅이다). 이 파일 밖으로 TanStack 의 타입이 나가지 않는다.
//
// TanStack 에 맡긴 것: 정렬된·걸러진 행 목록 만들기(행이 바뀌지 않으면 다시 계산하지 않는다), 정렬·고르기 상태.
// 걸러 보기의 조건 자체는 업무 로직(model/filter.ts)의 matchesFilter 다. 여기서는 그것을 TanStack 의 필터 자리에 끼운다.
import { useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';

import {
  columnFilteringFeature,
  createFilteredRowModel,
  createSortedRowModel,
  rowSelectionFeature,
  rowSortingFeature,
  tableFeatures,
  useTable,
} from '@tanstack/react-table';
import type { ColumnDef } from '@tanstack/react-table';

import { NO_FILTER, matchesFilter } from '../model/index.ts';
import type { ReviewRow, RowFilter } from '../model/index.ts';

/** 열 하나. 표를 쓰는 쪽이 정해서 넘긴다. */
export interface ReviewColumn {
  id: string;
  header: string;
  /** 정렬에 쓰는 값. render 가 없으면 이 값이 그대로 보인다. null 은 오름·내림 어느 쪽에서도 맨 뒤로 간다. */
  value(row: ReviewRow): string | number | null;
  /** 칸에 그릴 것. 없으면 value. */
  render?(row: ReviewRow): ReactNode;
  /** 기본은 정렬할 수 있다. */
  sortable?: boolean;
  /** 화면 층에 주는 귀띔. 화면이 무시해도 된다. */
  width?: number;
  align?: 'left' | 'right';
}

export type SortDirection = 'asc' | 'desc';

/** 화면이 머리글을 그릴 때 쓰는 열 정보. */
export interface ColumnView extends ReviewColumn {
  sortable: boolean;
  sorted: SortDirection | null;
  /** 누를 때마다 오름 → 내림 → 정렬 없음으로 돈다. */
  toggleSort(): void;
}

/** 일괄 동작의 대상: 고른 행들(걸러 본 결과 안에 있는 것만) 또는 걸러 본 결과 전체. */
export type BulkScope = 'selected' | 'filtered';

export interface ReviewTable {
  columns: ColumnView[];
  /** 걸러 보고 정렬한 결과 전체. ★ 화면에 그려진 행이 아니다(그것은 useRowWindow 가 고른다). */
  rows: readonly ReviewRow[];
  filter: RowFilter;
  setFilter(patch: Partial<RowFilter>): void;
  /** 고른 행의 id. 걸러서 안 보이게 된 행도 고른 채로 남는다. */
  selectedIds: ReadonlySet<string>;
  toggleSelected(rowId: string): void;
  /** 걸러 본 결과가 전부 골라져 있는가(결과가 비었으면 false). 「모두 고르기」 칸의 표시에 쓴다. */
  allSelected: boolean;
  /** 걸러 본 결과 전체를 고르거나(true) 고르기를 모두 푼다(false). */
  selectAll(selected: boolean): void;
  /** 일괄 동작의 대상이 되는 행의 id. 걸러 본 결과에서 뽑는다. */
  targetIds(scope: BulkScope): string[];
}

const features = tableFeatures({
  rowSortingFeature,
  columnFilteringFeature,
  rowSelectionFeature,
  sortedRowModel: createSortedRowModel(),
  filteredRowModel: createFilteredRowModel(),
});

type Def = ColumnDef<typeof features, ReviewRow>;

/** 걸러 보기용 숨은 열. 값이 행 자체라서, 이 열의 필터가 행 전체를 보고 판단한다. 화면에는 나가지 않는다. */
const FILTER_COLUMN = '__filter';
const filterColumn: Def = {
  id: FILTER_COLUMN,
  accessorFn: (row) => row,
  enableSorting: false,
  filterFn: (row, _columnId, filter: RowFilter) =>
    matchesFilter(row.original, filter),
};

const collator = new Intl.Collator('ko', { numeric: true });

function toColumnDef(column: ReviewColumn): Def {
  return {
    id: column.id,
    // TanStack 은 undefined 를 「값 없음」으로 보고 sortUndefined 로 자리를 정한다.
    accessorFn: (row) => column.value(row) ?? undefined,
    enableSorting: column.sortable ?? true,
    sortUndefined: 'last',
    // TanStack 은 숫자 열을 내림차순부터 시작한다. 열마다 달라지지 않게 늘 오름차순부터 돈다.
    sortDescFirst: false,
    sortFn: (a, b, columnId) => {
      const left = a.getValue(columnId);
      const right = b.getValue(columnId);
      if (typeof left === 'number' && typeof right === 'number')
        return left - right;
      return collator.compare(String(left), String(right));
    },
  };
}

const getRowId = (row: ReviewRow) => row.id;

export function useReviewTable(
  rows: readonly ReviewRow[],
  columns: readonly ReviewColumn[],
): ReviewTable {
  const columnDefs = useMemo(
    () => [filterColumn, ...columns.map(toColumnDef)],
    [columns],
  );
  const table = useTable({
    features,
    data: rows,
    columns: columnDefs,
    getRowId,
  });

  const { sorting, columnFilters, rowSelection } = table.state;
  const filter =
    (columnFilters.find((entry) => entry.id === FILTER_COLUMN)?.value as
      RowFilter | undefined) ?? NO_FILTER;

  // getRowModel 은 TanStack 이 기억해 둔다. 행·정렬·필터가 그대로면 같은 배열이 나온다.
  const modelRows = table.getRowModel().rows;
  const viewRows = useMemo(
    () => modelRows.map((row) => row.original),
    [modelRows],
  );

  const columnViews = useMemo(
    () =>
      columns.map((column): ColumnView => {
        const sort = sorting.find((entry) => entry.id === column.id);
        return {
          ...column,
          sortable: column.sortable ?? true,
          sorted:
            sort ?
              sort.desc ?
                'desc'
              : 'asc'
            : null,
          toggleSort: () => table.getColumn(column.id)?.toggleSorting(),
        };
      }),
    // table 은 상태가 바뀔 때마다 새 참조라 넣지 않는다. 안에서 쓰는 것은 변하지 않는 메서드다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [columns, sorting],
  );

  const selectedIds = useMemo(
    () => new Set(Object.keys(rowSelection)),
    [rowSelection],
  );

  const setFilter = useCallback(
    (patch: Partial<RowFilter>) =>
      table.setColumnFilters([
        { id: FILTER_COLUMN, value: { ...filter, ...patch } },
      ]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filter],
  );

  const toggleSelected = useCallback(
    (rowId: string) =>
      table.setRowSelection((previous) => {
        // 고른 행만 키로 남긴다(TanStack 의 꼴: { [id]: true }).
        const { [rowId]: was, ...rest } = previous;
        return was ? rest : { ...rest, [rowId]: true };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const selectAll = useCallback(
    (selected: boolean) =>
      table.setRowSelection(
        selected ?
          Object.fromEntries(viewRows.map((row) => [row.id, true]))
        : {},
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [viewRows],
  );

  const targetIds = useCallback(
    (scope: BulkScope) => {
      const ids = viewRows.map((row) => row.id);
      return scope === 'filtered' ? ids : (
          ids.filter((id) => selectedIds.has(id))
        );
    },
    [viewRows, selectedIds],
  );

  const allSelected = useMemo(
    () =>
      viewRows.length > 0 && viewRows.every((row) => selectedIds.has(row.id)),
    [viewRows, selectedIds],
  );

  return {
    columns: columnViews,
    rows: viewRows,
    filter,
    setFilter,
    selectedIds,
    toggleSelected,
    allSelected,
    selectAll,
    targetIds,
  };
}
