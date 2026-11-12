// 목록 표 headless 의 공개 표면. TanStack 의 flexRender 와 열 타입도 여기서 다시 내보낸다(ui 와 쓰는 쪽은 TanStack 을 직접 부르지 않아도 된다).
export {
  clickableRowProps,
  dataTableFeatures,
  describeTable,
  isFromControl,
  useDataTable,
} from './useDataTable.ts';
export type {
  CellView,
  ClickableRowProps,
  DataTableColumnDef,
  DataTableColumnMeta,
  DataTableFeatures,
  DataTableInstance,
  DataTableView,
  HeaderView,
  RowView,
  UseDataTableOptions,
} from './useDataTable.ts';
export { flexRender } from '@tanstack/react-table';
export type {
  CellContext,
  HeaderContext,
  RowData,
  SortingState,
} from '@tanstack/react-table';
