// 온실가스 Scope 3 api 칸의 공개 표면(밴드 S3W1 ①): 실어댑터 하나(server.ts)와 그 결과 꼴.
// 스키마 값·export * 는 내보내지 않는다(app/guards/layers.test.ts). 시험의 가짜 서버는 testing.ts(시험만 직접).
export {
  EXPORT_FILE_NAME,
  ORIGINAL_FILE_NAME,
  RUN_POLL_MS,
  SCOPE3_WRITE_CODES,
  TEMPLATE_FILE_NAME,
  createScope3Port,
} from './server.ts';
export type {
  CompanyRefusal,
  CreateScope3PortOptions,
  EditHistoryQuery,
  ExportOutcome,
  LatestOutcome,
  ReadOutcome,
  Scope3File,
  Scope3Port,
  Scope3Template,
  Scope3WriteCode,
  SendUpload,
  WriteOutcome,
} from './server.ts';
