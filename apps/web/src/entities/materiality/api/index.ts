// 중대성평가 api 칸의 공개 표면(밴드 IRW1 ①): 저장소 꼴(store.ts)·실어댑터(server.ts)·열쇠 꼴(ids.ts).
// 스키마 값·export * 는 내보내지 않는다(app/guards/layers.test.ts). 목 저장소는 없다 — 시험의 가짜 서버는 testing.ts(시험만 직접).
export { newKey } from './ids.ts';
export type { NewKey } from './ids.ts';
export { RUN_POLL_MS, createMaterialityServerStore } from './server.ts';
export type { MaterialityServerDeps } from './server.ts';
export {
  MaterialityStoreError,
  RUN_PAGE_LIMIT,
  storeErrorKind,
} from './store.ts';
export type {
  CreateRunResult,
  FileDownload,
  MaterialityRunPage,
  MaterialityRunRow,
  MaterialityStore,
  MaterialityValueChainRead,
  MaterialityValueChainReadRow,
  RerunResult,
  ResultEditChange,
  ResultEditsView,
  RunListQuery,
  SaveEditsResult,
  StoreErrorKind,
} from './store.ts';
