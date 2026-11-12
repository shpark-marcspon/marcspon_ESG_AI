// 온실가스 api 칸의 공개 표면(밴드 W12-0a ①): 실어댑터 둘(server.ts)과 그 결과 꼴.
// 스키마 값·export * 는 내보내지 않는다(app/guards/layers.test.ts). 목 저장소는 없다 — 시험의 가짜 서버는 testing.ts(시험만 직접).
export {
  BRANCH_PAGE_SIZE,
  FACILITY_CODE_PAGE_SIZE,
  WRITE_CODES,
  createFacilityCodeAdminPort,
  createGhgOrganizationPort,
} from './server.ts';
export type {
  BranchListQuery,
  CompanyRefusal,
  CreateGhgPortOptions,
  DetailOutcome,
  FacilityCodeAdminPort,
  GhgOrganizationPort,
  ReadOutcome,
  WriteCode,
  WriteOutcome,
} from './server.ts';
// 밴드 W12-0b1 ②: 인덱스 풀(S19)·배출계수 풀(S20) 실어댑터(운영 관리자만 — 공통 풀).
export { POOL_WRITE_CODES, createGhgPoolAdminPort } from './pool.ts';
export type {
  CreateGhgPoolPortOptions,
  GhgPoolAdminPort,
  PoolNodeCreate,
  PoolNodeQuery,
  PoolRead,
  PoolWrite,
  PoolWriteCode,
} from './pool.ts';
// 밴드 W12-0b2 ①: 고객사 인덱스 선택(S17) 실어댑터(고객사 사용자·운영 관리자 — 서버가 작업 회사를 정한다).
export { SELECTION_WRITE_CODES, createGhgSelectionPort } from './selection.ts';
export type {
  CreateGhgSelectionPortOptions,
  GhgSelectionPort,
  SelectionRead,
  SelectionWrite,
  SelectionWriteCode,
} from './selection.ts';
// 밴드 W12-1a ②: Scope 1·2 입력(S2·S3·S12) 실어댑터(고객사 사용자·운영 관리자 — 서버가 작업 회사를 정한다, 풀기만 운영 관리자).
export {
  ENTRY_HISTORY_PAGE_SIZE,
  ENTRY_WRITE_CODES,
  createGhgEntryPort,
} from './entries.ts';
export type {
  CreateGhgEntryPortOptions,
  EntryFactorTarget,
  EntryFile,
  EntryRead,
  EntryRowsRead,
  EntryUploadSent,
  EntryWrite,
  EntryWriteCode,
  GhgEntryPort,
} from './entries.ts';
// 밴드 DB1 ②: 대시보드(S1) 실어댑터(고객사 사용자·운영 관리자 — 서버가 작업 회사를 정한다).
export { createGhgDashboardPort } from './dashboard.ts';
export type {
  CreateGhgDashboardPortOptions,
  DashboardRead,
  GhgDashboardPort,
} from './dashboard.ts';
