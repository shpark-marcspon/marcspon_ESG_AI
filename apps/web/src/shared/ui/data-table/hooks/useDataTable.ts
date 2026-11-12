// 목록 표의 헤드리스 층. TanStack Table v9 를 감싸 머리·몸·정렬 상태를 그리기 좋은 꼴로 낸다. 모양(클래스·색)을 모른다.
// 가상화는 하지 않는다(그린워싱 목록은 짧다. 무효 조건: 수백 줄 목록이 생기면 review-table 의 행 창 같은 것을 더한다).
// 묶음 머리글(2단)은 그리지 않는다: 맨 아래 머리 줄 하나만 낸다(getHeaderGroups 의 마지막).
import type { KeyboardEvent, MouseEvent, ReactNode } from 'react';

import {
  createSortedRowModel,
  flexRender,
  rowSortingFeature,
  tableFeatures,
  useTable,
} from '@tanstack/react-table';
import type {
  ColumnDef,
  ReactTable,
  RowData,
  TableOptions,
} from '@tanstack/react-table';

import {
  CONTROL_SELECTOR,
  alignOf,
  ariaSortOf,
  isActivationKey,
  skeletonOf,
} from '../model/index.ts';
import type {
  AriaSort,
  CellAlign,
  ColumnSkeleton,
  SortState,
} from '../model/index.ts';

/** 열 정의의 meta. 칸 정렬(기본 left)과 열 너비(px. 없으면 표가 나눈다 — 밴드 FW2 ②), 스켈레톤 막대 폭(밴드 LD1 ②). */
export interface DataTableColumnMeta {
  align?: CellAlign;
  /** 열 너비(px). 머리 칸에 width 로 단다. TanStack 의 size 는 columnSizing 기능을 들여야 해서 meta 로 받는다. */
  width?: number;
  /** 로딩 줄의 막대 폭(기본 'long'). 짧은 칸은 6c 값: 연도 40 · 날짜 112 · 쪽 수 [24,32] · 상태 [48,80] · 다음 할 일 [72,88]. */
  skeleton?: ColumnSkeleton;
}

/** 목록 표가 쓰는 TanStack 기능: 정렬 하나. */
export const dataTableFeatures = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  columnMeta: {} as DataTableColumnMeta,
});
export type DataTableFeatures = typeof dataTableFeatures;
/** 목록 표의 열 정의. TanStack ColumnDef 에 우리 기능 묶음을 채운 것. */
export type DataTableColumnDef<TData extends RowData> = ColumnDef<
  DataTableFeatures,
  TData
>;
/** useDataTable 이 돌려주는 TanStack 표. */
export type DataTableInstance<TData extends RowData> = ReactTable<
  DataTableFeatures,
  TData
>;

export type UseDataTableOptions<TData extends RowData> = Omit<
  TableOptions<DataTableFeatures, TData>,
  'features'
>;

/**
 * TanStack 표를 만든다. 정렬 상태는 TanStack 이 갖는다(initialState·state·onSortingChange 로 바꿀 수 있다).
 * 정렬은 열마다 늘 오름차순부터 돈다(TanStack 기본은 숫자 열만 내림차순부터다. review-table 과 같은 선택).
 * 열 정의나 defaultColumn 에 sortDescFirst 를 주면 그것이 이긴다.
 */
export function useDataTable<TData extends RowData>(
  options: UseDataTableOptions<TData>,
): DataTableInstance<TData> {
  return useTable({
    ...options,
    defaultColumn: { sortDescFirst: false, ...options.defaultColumn },
    features: dataTableFeatures,
  });
}

export interface HeaderView {
  id: string;
  content: ReactNode;
  align: CellAlign;
  sortable: boolean;
  sort: SortState;
  /** 정렬할 수 있는 열에만 있다. */
  ariaSort?: AriaSort;
  toggleSort(): void;
  /** 열 정의 meta.width(px). 없으면 undefined. */
  width?: number;
  /** 열 정의 meta.skeleton(로딩 줄 막대 폭). 없으면 'long'. */
  skeleton: ColumnSkeleton;
}
export interface CellView {
  id: string;
  /** 열 id(DataTable 의 rowSpanOf 가 받는다 — 밴드 DT1). */
  columnId: string;
  content: ReactNode;
  align: CellAlign;
}
export interface RowView<TData extends RowData> {
  id: string;
  original: TData;
  cells: CellView[];
}
export interface DataTableView<TData extends RowData> {
  headers: HeaderView[];
  rows: RowView<TData>[];
  columnCount: number;
}

/** 표를 그리기 좋은 꼴로 바꾼다. 머리는 맨 아래 머리 줄 하나다. 그릴 때마다 부른다(목록이 짧아 기억해 두지 않는다). */
export function describeTable<TData extends RowData>(
  table: DataTableInstance<TData>,
): DataTableView<TData> {
  const groups = table.getHeaderGroups();
  const last = groups[groups.length - 1];
  const headers = (last?.headers ?? []).map((header): HeaderView => {
    const column = header.column;
    const sortable = column.getCanSort();
    const sort = column.getIsSorted();
    return {
      id: header.id,
      content:
        header.isPlaceholder ? null : (
          flexRender(column.columnDef.header, header.getContext())
        ),
      align: alignOf(column.columnDef.meta),
      sortable,
      sort,
      ariaSort: sortable ? ariaSortOf(sort) : undefined,
      toggleSort: () => column.toggleSorting(),
      width: widthOf(column.columnDef.meta),
      skeleton: skeletonOf(column.columnDef.meta),
    };
  });
  const rows = table.getRowModel().rows.map((row): RowView<TData> => ({
    id: row.id,
    original: row.original,
    cells: row.getAllCells().map((cell) => ({
      id: cell.id,
      columnId: cell.column.id,
      content: flexRender(cell.column.columnDef.cell, cell.getContext()),
      align: alignOf(cell.column.columnDef.meta),
    })),
  }));
  return { headers, rows, columnCount: headers.length };
}

/** 사건이 줄 안의 컨트롤(버튼·링크·입력·체크·스위치)에서 왔는가. 왔으면 줄 클릭으로 치지 않는다. */
export function isFromControl(
  target: EventTarget | null,
  row: Element,
): boolean {
  if (!target || !(target instanceof Element)) return false;
  const control = target.closest(CONTROL_SELECTOR);
  return control !== null && control !== row && row.contains(control);
}

export interface ClickableRowProps {
  tabIndex: 0;
  onClick(event: MouseEvent<HTMLElement>): void;
  onKeyDown(event: KeyboardEvent<HTMLElement>): void;
}

/**
 * 누를 수 있는 줄의 속성. onClickRow 가 없으면 undefined(줄은 초점도 받지 않는다).
 * 마우스 클릭과 Enter·Space 모두 onClickRow 를 부른다. 칸 안의 컨트롤에서 온 것은 무시한다.
 */
export function clickableRowProps<TData>(
  original: TData,
  onClickRow: ((row: TData) => void) | undefined,
): ClickableRowProps | undefined {
  if (!onClickRow) return undefined;
  return {
    tabIndex: 0,
    onClick: (event) => {
      if (isFromControl(event.target, event.currentTarget)) return;
      onClickRow(original);
    },
    onKeyDown: (event) => {
      if (!isActivationKey(event.key)) return;
      if (event.target !== event.currentTarget) return; // 칸 안 컨트롤의 Enter·Space 는 그 컨트롤 몫이다
      event.preventDefault(); // Space 가 쪽을 내리지 않게
      onClickRow(original);
    },
  };
}

/** 열 정의 meta.width → px(양의 유한수만). */
function widthOf(meta: unknown): number | undefined {
  const width =
    meta && typeof meta === 'object' ?
      (meta as { width?: unknown }).width
    : undefined;
  return typeof width === 'number' && Number.isFinite(width) && width > 0 ?
      width
    : undefined;
}
