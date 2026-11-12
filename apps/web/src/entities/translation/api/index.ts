// 영문번역 api 칸의 공개 표면(밴드 TRW1a ①): 저장소 꼴(store.ts)·실어댑터(server.ts)·계약 거울의 타입·열쇠 꼴(ids.ts).
// 스키마 값·export * 는 내보내지 않는다(app/guards/layers.test.ts). 목 저장소는 없다 — 시험의 가짜 서버는 testing.ts(시험만 직접).
export { GLOSSARY_REJECTION_KINDS } from './contract/index.ts';
export type {
  GlossaryPair,
  GlossaryRead,
  GlossaryRejectionKind,
} from './contract/index.ts';
export { newKey } from './ids.ts';
export type { NewKey } from './ids.ts';
export {
  BATCH_POLL_MS,
  OPTIONS_MAX_OCTETS,
  createTranslationServerStore,
} from './server.ts';
export type { TranslationServerDeps } from './server.ts';
export { TranslationStoreError, storeErrorKind } from './store.ts';
export type {
  ArchiveResult,
  BatchQuery,
  DocumentInfo,
  FileDownload,
  RunInfo,
  RunPdf,
  StartInput,
  StartResult,
  StoreErrorKind,
  TranslationStore,
  UploadedDocument,
  UploadedPdf,
} from './store.ts';
