// 온실가스 조직구조 계약 거울(밴드 W12-0a ① — 꼴은 generated api.d.ts 의 BranchOut·BranchDetailOut·BranchFacilityOut·BranchPageOut·
// FacilityCodesOut·FacilityCodeOut·AdminFacilityCodePageOut(+AdminFacilityCodeOut)·CountOut, 정본 apps/api-py/esgapi/organization).
// api 칸 안에서 zod 를 가져오는 자리는 이 폴더뿐이다(app/guards/layers.test.ts). 타입은 generated 그대로 쓰고 이 파일은 받은 값이 그 꼴인지만 본다.
// 응답 id 는 글자다(sid:MARC-ISSUE-92). 모르는 칸은 버리고 지난다(중대성평가 contract/runs.ts 꼴).
import { z } from 'zod';

import type { Schemas } from '../../../../shared/api/index.ts';
import { isPoolLevel } from '../../model/index.ts';
import type {
  Dashboard,
  EntryHistoryPage,
  EntryIndex,
  EntryPeriod,
  EntryRows,
  EntrySaveBody,
  EntryUploadResult,
  EntryYear,
} from '../../model/index.ts';

const count = z.number().int().min(0);
const id = z.string();

const branch = z.object({
  id,
  name: z.string(),
  isHeadquarters: z.boolean(),
  inventoryEnabled: z.boolean(),
  externalId: z.string().nullable(),
  createdAt: z.string(),
});

const branchFacility = z.object({
  id,
  facilityCodeId: id,
  facilityCode: z.string(),
  facilityName: z.string(),
  detailName: z.string(),
});

// updatedAt 은 이 판의 버전(밴드 K1b-3 — PUT 본문에 받은 글자 그대로 돌려준다. 목록 BranchOut 에는 없다).
const branchDetail = branch.extend({
  facilities: z.array(branchFacility),
  updatedAt: z.string(),
});

const pageOf = <T extends z.ZodType>(row: T) =>
  z.object({
    count,
    totalPages: count,
    page: z.number().int().min(1),
    pageSize: z.number().int().min(1),
    hasNext: z.boolean(),
    hasPrevious: z.boolean(),
    results: z.array(row),
  });

const branchPage = pageOf(branch);

const facilityCode = z.object({ id, code: z.string(), name: z.string() });
const facilityCodes = z.object({ items: z.array(facilityCode) });
const adminFacilityCode = facilityCode.extend({ inUse: z.boolean() });
const adminFacilityCodePage = pageOf(adminFacilityCode);
const countOut = z.object({ count });

export type BranchOut = Schemas['BranchOut'];
export type BranchDetailOut = Schemas['BranchDetailOut'];
export type BranchPageOut = Schemas['BranchPageOut'];
export type FacilityCodeOut = Schemas['FacilityCodeOut'];
export type FacilityCodesOut = Schemas['FacilityCodesOut'];
export type AdminFacilityCodePageOut = Schemas['AdminFacilityCodePageOut'];
export type CountOut = Schemas['CountOut'];

const branchDetailSchema: z.ZodType<BranchDetailOut, unknown> = branchDetail;
const branchPageSchema: z.ZodType<BranchPageOut, unknown> = branchPage;
const facilityCodeSchema: z.ZodType<FacilityCodeOut, unknown> = facilityCode;
const facilityCodesSchema: z.ZodType<FacilityCodesOut, unknown> = facilityCodes;
const adminFacilityCodePageSchema: z.ZodType<
  AdminFacilityCodePageOut,
  unknown
> = adminFacilityCodePage;
const countSchema: z.ZodType<CountOut, unknown> = countOut;

/** 꼴이 맞으면 그 값, 아니면 null(실어댑터가 failed 로 받는다). */
const parseWith =
  <T>(schema: z.ZodType<T, unknown>) =>
  (value: unknown): T | null => {
    const parsed = schema.safeParse(value);
    return parsed.success ? parsed.data : null;
  };

export const parseBranchDetail = parseWith(branchDetailSchema);
export const parseBranchPage = parseWith(branchPageSchema);
export const parseFacilityCode = parseWith(facilityCodeSchema);
export const parseFacilityCodes = parseWith(facilityCodesSchema);
export const parseAdminFacilityCodePage = parseWith(
  adminFacilityCodePageSchema,
);
export const parseCount = parseWith(countSchema);

/** 거울이 보는 칸 이름(api/server.test.ts 가 generated openapi.json 의 칸과 맞춘다 — ★E). */
export const MIRRORED: Readonly<Record<string, readonly string[]>> = {
  BranchOut: Object.keys(branch.shape),
  BranchDetailOut: Object.keys(branchDetail.shape),
  BranchFacilityOut: Object.keys(branchFacility.shape),
  BranchPageOut: Object.keys(branchPage.shape),
  FacilityCodesOut: Object.keys(facilityCodes.shape),
  FacilityCodeOut: Object.keys(facilityCode.shape),
  AdminFacilityCodeOut: Object.keys(adminFacilityCode.shape),
  AdminFacilityCodePageOut: Object.keys(adminFacilityCodePage.shape),
  CountOut: Object.keys(countOut.shape),
};

// ── 밴드 W12-0b1 ②: 온실가스 인덱스 풀(S19)·배출계수 풀(S20) — generated GhgNodeOut·GhgNodesOut·GhgFacilityOut·GhgFactorSummaryOut·
//    GhgFactorOut·GhgGasOut·GhgUnitOut·GhgOptionsOut(+GhgCodeNameOut·GhgUnitKindOut·GhgDefaultsOut)·GhgCountOut, 정본 apps/api-py/esgapi/inventory.
//    단 글자는 넷만 받는다(scope·source_type·activity·facility — 모르면 꼴 틀림 → failed). Decimal 은 글자 그대로.
const poolLevel = z.string().refine(isPoolLevel);
const poolNode = z.object({
  id,
  level: poolLevel,
  name: z.string(),
  parentId: id.nullable(),
  sortOrder: z.number().int(),
  childCount: count,
  facilityCode: z.string().nullable().optional(),
  facilityCodeId: id.nullable().optional(),
});
const poolNodes = z.object({ items: z.array(poolNode) });
const poolUnit = z.object({ kind: z.string(), unit: z.string() });
const factorSummary = z.object({
  id,
  name: z.string(),
  inputUnit: poolUnit,
  isDefault: z.boolean(),
  sortOrder: z.number().int(),
  version: z.number().int().min(1),
});
const poolFacility = z.object({
  id,
  parentId: id,
  facilityCodeId: id,
  facilityCode: z.string(),
  facilityName: z.string(),
  unit: poolUnit,
  tooltip: z.string(),
  factors: z.array(factorSummary),
});
const poolGas = z.object({
  gas: z.string(),
  enabled: z.boolean(),
  factor: z.string().nullable(),
  gwp: z.string().nullable(),
});
const poolFactor = z.object({
  id,
  facilityNodeId: id,
  version: z.number().int().min(1),
  versions: z.array(z.number().int().min(1)),
  name: z.string(),
  source: z.string(),
  baseYear: z.number().int(),
  tier: z.number().int(),
  countryCode: z.string(),
  industryCode: z.string(),
  inputUnit: poolUnit,
  emissionUnit: poolUnit,
  ncvEnabled: z.boolean(),
  ncv: z.string().nullable(),
  ncvUnit: poolUnit.nullable(),
  factorUnit: z.string(),
  gases: z.array(poolGas),
  note: z.string(),
  isDefault: z.boolean(),
  sortOrder: z.number().int(),
  seedGwpSetId: z.string().nullable(),
  seedRecordIds: z.array(z.string()),
  createdAt: z.string(),
  updatedAt: z.string(),
});
const codeName = z.object({ code: z.string(), name: z.string() });
const unitKind = z.object({ kind: z.string(), units: z.array(z.string()) });
const poolDefaults = z.object({
  emissionUnit: poolUnit,
  factorUnitWithNcv: z.string(),
  factorUnitWithoutNcv: z.string(),
});
const poolOptions = z.object({
  gases: z.array(z.string()),
  units: z.array(unitKind),
  countries: z.array(codeName),
  industries: z.array(codeName),
  defaults: poolDefaults,
});
const poolCount = z.object({ count });

export type GhgNodeOut = Schemas['GhgNodeOut'];
export type GhgNodesOut = Schemas['GhgNodesOut'];
export type GhgFacilityOut = Schemas['GhgFacilityOut'];
export type GhgFactorOut = Schemas['GhgFactorOut'];
export type GhgOptionsOut = Schemas['GhgOptionsOut'];
export type GhgCountOut = Schemas['GhgCountOut'];

const poolNodesSchema: z.ZodType<GhgNodesOut, unknown> = poolNodes;
const poolNodeSchema: z.ZodType<GhgNodeOut, unknown> = poolNode;
const poolFacilitySchema: z.ZodType<GhgFacilityOut, unknown> = poolFacility;
const poolFactorSchema: z.ZodType<GhgFactorOut, unknown> = poolFactor;
const poolOptionsSchema: z.ZodType<GhgOptionsOut, unknown> = poolOptions;
const poolCountSchema: z.ZodType<GhgCountOut, unknown> = poolCount;

export const parsePoolNodes = parseWith(poolNodesSchema);
export const parsePoolNode = parseWith(poolNodeSchema);
export const parsePoolFacility = parseWith(poolFacilitySchema);
export const parsePoolFactor = parseWith(poolFactorSchema);
export const parsePoolOptions = parseWith(poolOptionsSchema);
export const parsePoolCount = parseWith(poolCountSchema);

/** 풀 거울이 보는 칸 이름(api/pool.test.ts 가 openapi.json 과 맞춘다 — ★E). */
export const POOL_MIRRORED: Readonly<Record<string, readonly string[]>> = {
  GhgNodeOut: Object.keys(poolNode.shape),
  GhgNodesOut: Object.keys(poolNodes.shape),
  GhgUnitOut: Object.keys(poolUnit.shape),
  GhgFactorSummaryOut: Object.keys(factorSummary.shape),
  GhgFacilityOut: Object.keys(poolFacility.shape),
  GhgGasOut: Object.keys(poolGas.shape),
  GhgFactorOut: Object.keys(poolFactor.shape),
  GhgCodeNameOut: Object.keys(codeName.shape),
  GhgUnitKindOut: Object.keys(unitKind.shape),
  GhgDefaultsOut: Object.keys(poolDefaults.shape),
  GhgOptionsOut: Object.keys(poolOptions.shape),
  GhgCountOut: Object.keys(poolCount.shape),
};

// ── 밴드 W12-0b2 ①: 고객사 인덱스 선택(S17) — generated IndexTreeOut·IndexTreeNodeOut·IndexSelectionSaveOut, 정본 apps/api-py/esgapi/inventory
//    (K1b-2b). 단 글자는 넷만(모르면 꼴 틀림 → failed — 스펙 초안의 sourceType 아님). 잎 칸 셋(facilityCodeId·hasFactor·hasData)은 없거나 null.
const treeNode = z.object({
  id,
  level: poolLevel,
  name: z.string(),
  parentId: id.nullable(),
  facilityCodeId: id.nullable().optional(),
  availableCount: count,
  selected: z.boolean(),
  hasFactor: z.boolean().nullable().optional(),
  hasData: z.boolean().nullable().optional(),
});
const indexTree = z.object({
  year: z.number().int(),
  nodes: z.array(treeNode),
});
const selectionSaved = z.object({ selected: count, hiddenWithData: count });

export type IndexTreeOut = Schemas['IndexTreeOut'];
export type IndexSelectionSaveOut = Schemas['IndexSelectionSaveOut'];

const indexTreeSchema: z.ZodType<IndexTreeOut, unknown> = indexTree;
const selectionSavedSchema: z.ZodType<IndexSelectionSaveOut, unknown> =
  selectionSaved;

export const parseIndexTree = parseWith(indexTreeSchema);
export const parseSelectionSaved = parseWith(selectionSavedSchema);

/** 선택 거울이 보는 칸 이름(api/selection.test.ts 가 openapi.json 과 맞춘다 — ★E). */
export const SELECTION_MIRRORED: Readonly<Record<string, readonly string[]>> = {
  IndexTreeNodeOut: Object.keys(treeNode.shape),
  IndexTreeOut: Object.keys(indexTree.shape),
  IndexSelectionSaveOut: Object.keys(selectionSaved.shape),
};

// ── 밴드 W12-1a ②: Scope 1·2 입력(S2·S3·S12 — 서버 S12a) — generated Entry*Out 스무 꼴 · 요청 Entry*In 여섯, 정본 apps/api-py/esgapi/inventory
//    (service/apis/entries.py). 응답 거울은 openapi 의 부분집합(⊆ — S12a-2 가 칸을 더해도 초록, 거울 칸은 다 있어야 함), 요청은 같음(칸이 늘면 빨강 →
//    러너 멈춤). 꼴은 model/entries.ts 의 것으로 낸다 — generated 꼴이 그 꼴에 들어가는지는 아래 함수 둘이 타입으로 본다(Entry 꼴 ⊆ G, 본문 = G).
//    히스토리 kind·actor.kind 는 아무 글자(z.string — 모르는 종류도 판 실패 아님). 금액·배출량은 글자 그대로.
const text = z.string();
const maybe = text.nullable();
const values = z.record(z.string(), maybe);
const entryYear = z.object({ year: z.number().int(), configured: z.boolean() });
const entryYears = z.object({ years: z.array(entryYear) });
const entryListRow = z.object({
  nodeId: id,
  path: z.array(text),
  values,
  hasMemo: z.boolean(),
  estimated: z.boolean(),
  locked: z.boolean(),
});
const entryScope = z.object({
  scopeId: id,
  scopeName: text,
  values,
  rows: z.array(entryListRow),
});
const entryRows = z.object({
  year: z.number().int(),
  years: z.array(z.number().int()),
  decimals: count,
  unit: text,
  configured: z.boolean(),
  scopes: z.array(entryScope),
});
const entryFactor = z.object({
  factorId: id,
  versionId: id,
  version: z.number().int().min(1),
  name: text,
  source: text,
  isCustom: z.boolean(),
  inputUnit: poolUnit,
  ncvEnabled: z.boolean(),
  ncv: maybe,
  ncvUnit: poolUnit.nullable(),
  factorUnit: text,
  gases: z.array(poolGas),
});
const entrySlot = z.object({
  slot: text,
  amount: maybe,
  estimated: z.boolean(),
});
// 밴드 W12-1b ① — S12a-2 가 더한 응답 칸의 거울(더하기만). 직접입력 계수는 판 version 이 없다. slots 는 그 블록 주기의 칸(웹이 셈하지 않는다).
const entryCustomFactor = z.object({
  customId: text,
  name: text,
  source: text,
  baseYear: z.number().int(),
  tier: z.number().int(),
  countryCode: text,
  industryCode: text,
  inputUnit: poolUnit,
  ncvEnabled: z.boolean(),
  ncv: maybe,
  ncvUnit: poolUnit.nullable(),
  factorUnit: text,
  gases: z.array(poolGas),
  note: text,
  isCustom: z.boolean(),
});
const entryFactorRef = z.object({
  versionId: maybe,
  customId: maybe,
  name: text,
  isCustom: z.boolean(),
});
const entryRow = z.object({
  rowId: id,
  siteFacilityId: id,
  detailName: text,
  unit: text,
  na: z.boolean(),
  values: z.array(entrySlot),
  emission: maybe,
  emissionProblem: maybe,
  factor: z.union([entryFactor, entryCustomFactor]).nullable(),
});
const entryFacility = z.object({
  id,
  detailName: text,
  hasRow: z.boolean(),
});
const entrySite = z.object({
  siteId: id,
  siteName: text,
  facilities: z.array(entryFacility),
  rows: z.array(entryRow),
  period: text,
  slots: z.array(text),
});
const entrySiteTotal = z.object({ siteId: id, siteName: text, values });
const entryTotals = z.object({
  years: z.array(z.number().int()),
  all: values,
  bySite: z.array(entrySiteTotal),
});
const entryLockedBy = z.object({ id, name: text });
const entryIndex = z.object({
  year: z.number().int(),
  nodeId: id,
  name: text,
  path: z.array(text),
  decimals: count,
  unit: text,
  unitOptions: z.array(text),
  factor: entryFactor,
  locked: z.boolean(),
  lockedAt: maybe,
  lockedBy: entryLockedBy.nullable(),
  memo: text,
  sites: z.array(entrySite),
  totals: entryTotals,
});
const entryHistoryActor = z.object({
  kind: text,
  id: id.nullable(),
  name: maybe,
});
const entryHistory = z.object({
  historyId: id,
  at: text,
  kind: text,
  slot: maybe,
  unit: text,
  before: maybe,
  after: maybe,
  actor: entryHistoryActor,
  reason: maybe,
  restorable: z.boolean(),
  beforeFactor: entryFactorRef.nullable(),
  afterFactor: entryFactorRef.nullable(),
});
const entryHistoryPage = pageOf(entryHistory);
const entryMemo = z.object({ memo: text });
const entryDecimals = z.object({ decimals: count });
const entryCount = z.object({ count });

/** generated 꼴이 웹 꼴에 들어간다(응답 ⊆ — 칸이 더 있어도 됨, 있는 칸의 꼴은 같아야 함). 부르지 않는다 — 타입 검사 자리. */
export const entryOutFits = (
  out: Schemas['EntryRowsOut'],
  years: Schemas['EntryYearsOut'],
  index: Schemas['EntryIndexOut'],
  history: Schemas['EntryHistoryPageOut'],
): [EntryRows, EntryYear[], EntryIndex, EntryHistoryPage] => [
  out,
  years.years,
  index,
  history,
];
/** 웹 본문이 generated 요청 꼴 그대로 들어간다(요청 = — 칸 이름 같음은 api/entries.test.ts 가 openapi 로 잰다). */
export const entryInFits = (body: EntrySaveBody): Schemas['EntrySaveIn'] =>
  body;
/** 주기·복구 본문(W12-2 ①) — 복구는 늘 {}(사유는 W12-3). */
export const entryPeriodInFits = (
  period: EntryPeriod,
): Schemas['EntryPeriodIn'] => ({ period });
export const entryRestoreInFits = (): Schemas['EntryRestoreIn'] => ({});

const entryRowsSchema: z.ZodType<EntryRows, unknown> = entryRows;
const entryYearsSchema: z.ZodType<{ years: EntryYear[] }, unknown> = entryYears;
const entryIndexSchema: z.ZodType<EntryIndex, unknown> = entryIndex;
const entryHistoryPageSchema: z.ZodType<EntryHistoryPage, unknown> =
  entryHistoryPage;
const entryMemoSchema: z.ZodType<{ memo: string }, unknown> = entryMemo;
const entryDecimalsSchema: z.ZodType<{ decimals: number }, unknown> =
  entryDecimals;
const entryCountSchema: z.ZodType<{ count: number }, unknown> = entryCount;
/** 일괄 올리기 답(W12-5 ①) — 음 아닌 정수 넷. */
const entryUpload = z.object({
  added: count,
  filled: count,
  unchanged: count,
  unresolved: count,
});
const entryUploadSchema: z.ZodType<EntryUploadResult, unknown> = entryUpload;

export const parseEntryRows = parseWith(entryRowsSchema);
export const parseEntryYears = parseWith(entryYearsSchema);
export const parseEntryIndex = parseWith(entryIndexSchema);
export const parseEntryHistoryPage = parseWith(entryHistoryPageSchema);
export const parseEntryMemo = parseWith(entryMemoSchema);
export const parseEntryDecimals = parseWith(entryDecimalsSchema);
export const parseEntryCount = parseWith(entryCountSchema);
export const parseEntryUpload = parseWith(entryUploadSchema);

/** 입력 응답 거울이 보는 칸 이름(api/entries.test.ts 가 openapi.json 과 견준다 — ⊆). */
export const ENTRY_MIRRORED: Readonly<Record<string, readonly string[]>> = {
  EntryYearOut: Object.keys(entryYear.shape),
  EntryYearsOut: Object.keys(entryYears.shape),
  EntryListRowOut: Object.keys(entryListRow.shape),
  EntryScopeOut: Object.keys(entryScope.shape),
  EntryRowsOut: Object.keys(entryRows.shape),
  EntryFactorOut: Object.keys(entryFactor.shape),
  EntrySiteTotalOut: Object.keys(entrySiteTotal.shape),
  EntryTotalsOut: Object.keys(entryTotals.shape),
  EntryFacilityOut: Object.keys(entryFacility.shape),
  EntrySlotOut: Object.keys(entrySlot.shape),
  EntryRowOut: Object.keys(entryRow.shape),
  EntrySiteOut: Object.keys(entrySite.shape),
  EntryLockedByOut: Object.keys(entryLockedBy.shape),
  EntryIndexOut: Object.keys(entryIndex.shape),
  EntryHistoryActorOut: Object.keys(entryHistoryActor.shape),
  EntryHistoryOut: Object.keys(entryHistory.shape),
  EntryHistoryPageOut: Object.keys(entryHistoryPage.shape),
  EntryMemoOut: Object.keys(entryMemo.shape),
  EntryDecimalsOut: Object.keys(entryDecimals.shape),
  EntryCountOut: Object.keys(entryCount.shape),
  EntryCustomFactorOut: Object.keys(entryCustomFactor.shape),
  EntryFactorRefOut: Object.keys(entryFactorRef.shape),
  EntryUploadOut: Object.keys(entryUpload.shape),
};

/** 입력 요청 본문의 칸 이름(api/entries.test.ts 가 openapi.json 과 견준다 — 같음). model/entries.ts 의 본문 꼴과 짝. */
export const ENTRY_REQUEST_FIELDS: Readonly<Record<string, readonly string[]>> =
  {
    EntrySlotIn: ['slot', 'amount', 'estimated'],
    EntryRowIn: ['rowId', 'siteFacilityId', 'unit', 'na', 'values'],
    EntrySaveIn: ['rows'],
    EntryIdsIn: ['ids'],
    EntryMemoIn: ['memo'],
    EntryDecimalsIn: ['decimals'],
    EntryPeriodIn: ['period'],
    EntryRestoreIn: ['reason'],
    EntryRowFactorIn: ['factorId', 'custom', 'reason'],
  };

// ── 밴드 DB1 ②: 대시보드(S1) 거울 — Scope12DashboardOut(+Total·Scope·Source·Site·SiteScope·Category). 정본 inventory/service/schemas/dashboard.py ──
const maybeAmount = z.string().nullable();
const dashboardSource = z.object({
  nodeId: id,
  name: z.string(),
  value: z.string(),
  share: maybeAmount,
});
const dashboardScope = z.object({
  scopeId: id,
  scopeName: z.string(),
  scopeOrder: count,
  value: maybeAmount,
  topSources: z.array(dashboardSource),
});
const dashboardTotal = z.object({
  scope12: maybeAmount,
  scope2Market: maybeAmount,
  scope3: maybeAmount,
  sum: maybeAmount,
  scope3FailedSheets: count,
});
const dashboardSiteScope = z.object({ scopeId: id, value: maybeAmount });
const dashboardSite = z.object({
  siteId: id,
  siteName: z.string(),
  scopes: z.array(dashboardSiteScope),
  scope3: maybeAmount,
});
const dashboardCategory = z.object({
  category: z.string(),
  name: z.string(),
  value: z.string(),
  share: maybeAmount,
});
const dashboard = z.object({
  year: z.number().int(),
  configured: z.boolean(),
  decimals: count,
  basis: z.string(),
  unit: z.string(),
  complete: z.boolean(),
  scopes: z.array(dashboardScope),
  total: dashboardTotal,
  bySite: z.array(dashboardSite),
  scope3Categories: z.array(dashboardCategory),
});

/** generated 꼴이 웹 꼴에 들어간다(응답 ⊆). 부르지 않는다 — 타입 검사 자리. */
export const dashboardOutFits = (
  out: Schemas['Scope12DashboardOut'],
): Dashboard => out;

const dashboardSchema: z.ZodType<Dashboard, unknown> = dashboard;
export const parseDashboard = parseWith(dashboardSchema);

/** 대시보드 거울이 보는 칸 이름(api/dashboard.test.ts 가 openapi.json 과 견준다 — ⊆). */
export const DASHBOARD_MIRRORED: Readonly<Record<string, readonly string[]>> = {
  Scope12DashboardOut: Object.keys(dashboard.shape),
  Scope12DashboardTotalOut: Object.keys(dashboardTotal.shape),
  Scope12DashboardScopeOut: Object.keys(dashboardScope.shape),
  Scope12DashboardSourceOut: Object.keys(dashboardSource.shape),
  Scope12DashboardSiteOut: Object.keys(dashboardSite.shape),
  Scope12DashboardSiteScopeOut: Object.keys(dashboardSiteScope.shape),
  Scope12DashboardCategoryOut: Object.keys(dashboardCategory.shape),
};
