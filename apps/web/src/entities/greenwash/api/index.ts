// 그린워싱 api 칸의 공개 표면(밴드 FS1 ②): 저장소 인터페이스(store.ts)와 계약 거울의 parse*·타입, 실어댑터(server.ts, 밴드 GW1R ①). 옛 headless/index.ts 에서 옮겨 왔다. 스키마 값·export * 는 내보내지 않는다(app/guards/layers.test.ts).
export {
  parseResult,
  parseReview,
  parseReviewUpdate,
} from './contract/index.ts';
export type { Parsed } from './contract/index.ts';
export { newIdempotencyKey } from './idempotency.ts';
export type { NewIdempotencyKey } from './idempotency.ts';
export { RUN_POLL_MS, createGreenwashServerStore } from './server.ts';
export type { GreenwashServerControl, GreenwashServerDeps } from './server.ts';
export { StoreError, storeErrorKind } from './store.ts';
export type {
  CreatedDocument,
  DocumentInfo,
  ExistingDocument,
  GreenwashStore,
  ReportFile,
  RunRequest,
  RunSnapshot,
  StoreErrorKind,
} from './store.ts';
