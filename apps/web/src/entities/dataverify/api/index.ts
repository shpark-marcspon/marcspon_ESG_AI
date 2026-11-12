// 데이터 검증 api 칸의 공개 표면(밴드 DV2a ①): 저장소 꼴(store.ts)·실어댑터(server.ts)·열쇠 꼴(ids.ts).
// 스키마 값·export * 는 내보내지 않는다(app/guards/layers.test.ts). 목 저장소는 없다 — 시험의 가짜 서버는 testing.ts(시험만 직접).
export { newKey } from './ids.ts';
export type { NewKey } from './ids.ts';
export {
  EDK_MAX_CELL_CHARS,
  EDK_MAX_ITEMS,
  EDK_XLSX_MAX_BYTES,
} from './contract/index.ts';
export {
  EDK_TEMPLATE_FILE_NAME,
  RUN_POLL_MS,
  createDataverifyServerStore,
} from './server.ts';
export type { DataverifyServerDeps } from './server.ts';
export {
  DataverifyStoreError,
  RUN_PAGE_LIMIT,
  storeErrorKind,
} from './store.ts';
export type {
  DataverifyEdkRead,
  DataverifyEdkReadOk,
  DataverifyEdkReadRejected,
  DataverifyRunPage,
  DataverifyRunRow,
  DataverifyStore,
  EdkReadKind,
  RunListQuery,
  FileDownload,
  StartResult,
  StoreErrorKind,
} from './store.ts';
