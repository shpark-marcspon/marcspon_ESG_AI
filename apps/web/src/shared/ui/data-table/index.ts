// 목록 표의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
//
//   model/     정렬 상태 → aria-sort, 칸 정렬, 누름 키, 칸 안 컨트롤의 목록. 순수 TypeScript
//   hooks/     TanStack Table v9 를 감싼 useDataTable·describeTable, 줄 클릭 판정. 모양을 모른다
//   ui/        DataTable. 클래스 이름은 여기에만 있다
export * from './model/index.ts';
export * from './hooks/index.ts';
export { DataTable, ROW_FOCUS, ROW_HOVER } from './ui/DataTable.tsx';
export type {
  DataTableProps,
  DataTableRowTone,
  RowDataAttributes,
} from './ui/DataTable.tsx';
