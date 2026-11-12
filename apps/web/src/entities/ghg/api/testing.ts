// 시험용 가짜 온실가스 조직구조 서버(밴드 W12-0a ①). 시험만 쓴다(공개 표면이 아니다). 값은 전부 지어낸 것이다.
// 답의 꼴은 api-py 의 경로 열하나(K1b-1 — /branches·/facility-codes·/admin/facility-codes)를 따르고 서버 규칙을 거르지 않고 따른다:
//   - 응답 id 는 글자, 요청 id(ids[]·facilities[].id·facilityCodeId·경로 id)는 정수만 받는다(글자면 422 VALIDATION_ERROR — sid:MARC-ISSUE-92).
//   - 목록은 본사 먼저, 그다음 만든 차례. q 는 이름 부분 일치(대소문자 무시 — 서버 name__icontains). page·pageSize 로 자른다.
//   - 이름은 앞뒤 공백을 걷는다. 빈 이름 422 fields.name · (코드, 세부시설명) 겹침·같은 줄 id 두 번 422 fields.facilities ·
//     새로 고른(새 줄이거나 코드를 바꾼) 코드가 없거나 지운 것 422 fields.facilityCodeId(서버 _facility_problem).
//   - 본사: 끄기·지우기에 실리면 409 HEADQUARTERS_LOCKED(PUT 의 inventoryEnabled false 도). 없는 id 404 NOT_FOUND.
//   - 사업장을 지우면 목록에서 빠진다(그 자산/시설도).
//   - 코드 지우기는 삭제 표시다(밴드 W12-0b1 ① L3): 두 목록에서 빠지고, 그 코드를 그대로 두는 기존 사업장 줄은 이름 그대로 저장을 지난다.
//     GET /facility-codes = 이름 가나다 → id · /admin/facility-codes = 만든 차례(서버 selectors/facility_codes.py).
//   - /admin/** 은 kind admin 만(admin 옵션이 거짓이면 403 FORBIDDEN). 코드 이름 겹침 422 fields.name(지운 코드는 빼고 셈).
//   - company 옵션을 주면 /branches·/facility-codes 는 그 회사 거절(400)을 낸다.
//   - 판 버전(밴드 K1b-3): 사업장마다 updatedAt(지어낸 µs 글자) — PUT 200·토글·bumpBranch 마다 늘 더 큰 글자로 바뀐다. PUT 본문 updatedAt 이
//     없거나 글자가 아니면 422 fields.updatedAt, 지금 판과 글자가 다르면 409 STALE(없는 id 404 가 먼저). POST 본문에 있으면 422.
// Bearer 는 보지 않는다(세션 가짜 서버의 몫). override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다).
import { createApi } from '../../../shared/api/index.ts';
import type { Schemas } from '../../../shared/api/index.ts';
import {
  ENTRY_PERIODS,
  POOL_LEVELS,
  addAmounts,
  seoulYear,
} from '../model/index.ts';
import type {
  BranchDetail,
  FacilityCode,
  FactorBody,
  FactorGasBody,
  PoolLevel,
  PoolOptions,
  PoolUnit,
} from '../model/index.ts';
import { createGhgDashboardPort } from './dashboard.ts';
import { createGhgEntryPort } from './entries.ts';
import { createGhgPoolAdminPort } from './pool.ts';
import { createGhgSelectionPort } from './selection.ts';
import {
  createFacilityCodeAdminPort,
  createGhgOrganizationPort,
} from './server.ts';

/** 서버 환산표(apps/api-py/esgapi/inventory/data/unit-conversions.json)의 쌍 그대로 「from>to」 — 548 흉내(W12-3 ② · critic R2: 진짜 표에서 옮김). */
export const FAKE_UNIT_PAIRS: readonly string[] = [
  'L>kL',
  'kL>L',
  'm3>L',
  'L>m3',
  'm3>kL',
  'kL>m3',
  'kNm3>Nm3',
  'Nm3>kNm3',
  'g>kg',
  'kg>g',
  'kg>t',
  't>kg',
  'g>t',
  'kWh>MWh',
  'MWh>kWh',
  'GWh>MWh',
  'kWh>MJ',
  'MWh>MJ',
  'MWh>GJ',
  'MJ>GJ',
  'GJ>MJ',
  'MJ>TJ',
  'TJ>MJ',
  'GJ>TJ',
  'TJ>GJ',
];
/** GhgFactorIn 의 칸(서버 StrictIn — 모르는 칸 422 custom.<칸>). */
const FACTOR_IN_FIELDS = [
  'name',
  'source',
  'baseYear',
  'tier',
  'countryCode',
  'industryCode',
  'inputUnit',
  'emissionUnit',
  'ncvEnabled',
  'ncv',
  'ncvUnit',
  'factorUnit',
  'gases',
  'note',
] as const;
/** 서버 REASON_MAX(계수 바꿈·복구의 사유). */
const FAKE_REASON_MAX = 500;
/** 서버 custom_unit_problem(sid:MARC-ISSUE-548) 흉내: 행 단위들 → 투입 → 분모(켬 ncvUnit / 끔 투입) → 분자 → t. */
export function fakeCustomUnitProblem(
  rowUnits: readonly string[],
  custom: FactorBody,
  pairs: readonly string[] = FAKE_UNIT_PAIRS,
): Record<string, string> {
  const ok = (a: string, b: string) => a === b || pairs.includes(`${a}>${b}`);
  const input = custom.inputUnit.unit;
  const factorUnit =
    custom.factorUnit ?? (custom.ncvEnabled ? 'kg/TJ' : `kg/${input}`);
  const [numerator = '', denominator = ''] = factorUnit.split('/');
  const out: Record<string, string> = {};
  if (rowUnits.some((unit) => !ok(unit, input)))
    out['custom.inputUnit'] = '지어낸 단위 어긋남';
  if (custom.ncvEnabled && custom.ncvUnit) {
    if (!ok(custom.ncvUnit.unit, denominator))
      out['custom.ncvUnit'] = '지어낸 단위 어긋남';
  } else if (!ok(input, denominator))
    out['custom.factorUnit'] = '지어낸 단위 어긋남';
  if (!ok(numerator, 't')) out['custom.factorUnit'] = '지어낸 단위 어긋남';
  return out;
}

export interface FakeGhgCall {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
  /** 올리기 경로의 본문 바이트와 Content-Type(W12-5 ① — 다른 경로는 없음). */
  bytes?: Uint8Array;
  contentType?: string | null;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  });
export const unreachable = (): Response => {
  throw new TypeError('fetch failed');
};

/** 일괄 올리기·내려받기 흉내의 값(W12-5 ① — 이름은 지어낸 것, 상한은 서버 올리기 경로의 GHG_UPLOAD_MAX_BYTES 20MB — MARC-ENT-593). */
export const ENTRY_XLSX_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
export const FAKE_UPLOAD_MAX = 20 * 1024 * 1024;
export const FAKE_TEMPLATE_NAME = '지어낸 양식.xlsx';
export const FAKE_EXPORT_NAME = '지어낸 데이터.xlsx';

/** 지어낸 코드 셋(만든 차례). */
export function fakeCodes(): FacilityCode[] {
  return [
    { id: '1', code: 'F0001', name: '지어낸 보일러' },
    { id: '2', code: 'F0002', name: '지어낸 발전기' },
    { id: '3', code: 'F0003', name: '지어낸 사업장 차량' },
  ];
}

/** 고객사 GET /facility-codes 의 차례 — 이름 가나다 → id(서버 selectable_codes, 밴드 W12-0b1 ① L3). */
export const codesByName = <T extends FacilityCode>(rows: readonly T[]): T[] =>
  [...rows].sort(
    (a, b) =>
      (a.name < b.name ? -1
      : a.name > b.name ? 1
      : 0) || Number(a.id) - Number(b.id),
  );

/** 지어낸 본사(씨앗 — 회사마다 하나, 자산/시설 한 줄). */
export function fakeHeadquarters(): BranchDetail {
  return {
    id: '1',
    name: '본사',
    isHeadquarters: true,
    inventoryEnabled: true,
    externalId: null,
    createdAt: '2026-10-28T09:00:00+09:00',
    updatedAt: '2026-10-28T09:00:00.000001+09:00',
    facilities: [
      {
        id: '1',
        facilityCodeId: '1',
        facilityCode: 'F0001',
        facilityName: '지어낸 보일러',
        detailName: '1호기',
      },
    ],
  };
}

/** 지어낸 사업장 하나(자산/시설 없음). */
export function fakeBranch(
  id: number,
  name: string,
  { inventoryEnabled = true }: { inventoryEnabled?: boolean } = {},
): BranchDetail {
  return {
    id: String(id),
    name,
    isHeadquarters: false,
    inventoryEnabled,
    externalId: null,
    createdAt: `2026-10-28T10:${String(id % 60).padStart(2, '0')}:00+09:00`,
    updatedAt: `2026-10-28T10:${String(id % 60).padStart(2, '0')}:00.000001+09:00`,
    facilities: [],
  };
}

const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value > 0;
const isIntList = (value: unknown): value is number[] =>
  Array.isArray(value) && value.length > 0 && value.every(isInt);
const pathId = (text: string): number | null =>
  /^[1-9][0-9]*$/.test(text) ? Number(text) : null;

const pageOf = <T>(rows: T[], page: number, pageSize: number) => {
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  return {
    count: rows.length,
    totalPages,
    page,
    pageSize,
    hasNext: page < totalPages,
    hasPrevious: page > 1,
    results: rows.slice((page - 1) * pageSize, page * pageSize),
  };
};

/** 목록 줄(BranchOut — 자산/시설 없음). */
const outOf = (branch: BranchDetail) => ({
  id: branch.id,
  name: branch.name,
  isHeadquarters: branch.isHeadquarters,
  inventoryEnabled: branch.inventoryEnabled,
  externalId: branch.externalId,
  createdAt: branch.createdAt,
});

// ── 밴드 W12-0b1 ②: 인덱스 풀(S19)·배출계수 풀(S20) 가짜 — /inventory/admin/ghg-index/** · /inventory/admin/ghg-factors/** ·
//    /inventory/admin/ghg-options. 서버 규칙(inventory/service/actions·services·selectors/ghg_pool.py)을 거르지 않고 따른다:
//   - 노드: 단 넷(scope·source_type·activity·facility), 부모 단 = 자기 단 − 1. 목록은 단 → sortOrder → id. q(≤100, 대소문자 무시 —
//     잎은 코드 이름)면 맞는 노드와 조상(parentId 무시). 같은 부모 아래 같은 이름 422 fields.name. 잎은 facilities 로만.
//   - 지우기: 하나라도 없으면 404 · 요청 밖 살아 있는 자식 409 HAS_CHILDREN · 쓰이는 노드·그 잎의 쓰이는 계수 409 IN_USE · 잎이면 계수도.
//   - 잎 PUT: 코드·1차 단위를 바꾸는데 쓰이는 잎이면 409 IN_USE(툴팁·기본만은 지남) · defaultFactorId 가 그 잎의 계수 아니면 422.
//     새로 고른 코드가 없거나 지웠거나 같은 활동 아래 겹치면 422 fields.facilityCodeId(그대로 두면 지운 코드여도 지남).
//   - 계수: 첫 계수가 기본 · PUT 은 늘 새 판(version +1, 옛 판은 ?version= 로) · 지우기 쓰이는 것 409 IN_USE · 기본을 지우면 남은
//     첫 행(sortOrder → id)이 기본. 검사는 S20 규칙(필수·켠 가스 ≥1·켠 줄 0 초과 Decimal 글자·순발열량 켬이면 값·단위, 끔이면 null).
//   - 「쓰이는 표」(inUse): 시험이 poolInUse.nodes·poolInUse.factors 에 id 를 넣어 고객사 선택(S17)이 잡은 잎·계수를 흉내 낸다.
//     밴드 W12-0b2 가 선택 경로를 더하면 그 선택이 이 표를 채운다.
// 밴드 W12-0b2 ①: 고객사 인덱스 선택(S17) 가짜 — 서버 actions/index_selection.py 를 따른다:
//   - 트리: 살아 있는 노드(단 → sortOrder → id). 잎 availableCount = 인벤토리 켠 사업장의 그 코드 줄 수, 위 단 = 아래 합 · hasFactor = 기본 계수 있음 ·
//     hasData = 그 해가 있고 selectionData 에 있음 · 위 단 selected = 아래 고를 수 있는(기본 계수 있는 — S12-05) 잎이 다 골라짐. 해 없음이면 선택 0(GET 은 해를 만들지 않는다).
//   - 저장: 해마다 따로. 연도 1990~올해 밖·글자 422 fields.year · 본문 열쇠가 facilityNodeIds 하나가 아니거나 정수 아님 · 1,000 넘음 · 없는(지운·잎 아닌) id ·
//     새로 고르는 잎의 기본 계수 없음 422 fields.facilityNodeIds(J1 — 이미 고른 잎은 지남. S12-05: 시설 0 은 거절 아님). 빈 목록도 해를 만든다. 뺀 잎은 데이터 있으면 숨김, 아니면 지움.
//   - 선택이 잡은 잎·그 기본 계수는 「쓰이는 표」에 든다(S19 409 IN_USE 와 한 가짜).
// 밴드 W12-1a ②: Scope 1·2 입력(S2·S3·S12) 가짜 — 서버 actions/entries.py 를 따른다(새 옵션은 다 기본 꺼짐 — 앞 시험 그대로):
//   - 입력: 해가 있고 숨기지 않은 고른 잎만(아니면 404). 사업장 블록 = 켠 사업장 가운데 그 잎 코드 줄이 있는 것. 잠긴 잎 쓰기 409 LOCKED.
//   - 행 저장: 하나라도 걸리면 0 씀 — 422 rows.<i>.siteFacilityId(그 사업장·코드 밖·새 행인데 이미 행)·rowId(없음)·unit(단위 밖)·
//     values.<j>.slot(그 블록 slots 밖 — W12-1b)·values.<j>.amount(0 이상 정수 18·소수 6 밖)·estimated. 실린 칸의 빠진 amount 는 null 로 덮는다(칸 단위).
//     금액 바뀜 → 히스토리 value(entryHistoryKind 로 바꿔 심음), N/A 켬·끔 → na_on·na_off, 단위 바뀜 → unit(값 줄보다 먼저 — 서버 470 M2), 추정만은 0. 입력이 생긴 잎은 selectionData(hasData).
//   - 지우기: ids 정수 1~100 · 하나라도 없으면 404(0 지움). 메모 ≤2000 · 자릿수 0~3(없는 해 404) · 풀기는 admin 만(고객사 403 FORBIDDEN).
//   - 리스트: Y-2·Y-1·Y · 숨기지 않은 고른 잎 0 이면 configured 거짓 · q(≤100) 는 경로 이름 부분 일치 · 배출량은 셈하지 않고
//     entryValues·scopeValues 씨앗 글자(없으면 null) · 상세 행 배출량은 지어낸 고정 글자 entryEmission. entryReject 를 주면 행 저장이 그 칸 열쇠로 422.
//   - 상세 총합(W12-2 ①): 해마다 사업장별 = 그 해 행 emission 의 sum_or_none(N/A·빈 행 빠짐, 하나도 없으면 null) · all = 사업장 합의 sum_or_none.
//   - 입력주기(W12-2 ①, PUT X/sites/{s}/period): 404 · 422 fields.period(month·quarter·year 밖)·모르는 칸 · 409 잠김 · 같으면 0 바뀜 ·
//     바뀌면 옛 칸 값은 지우지 않고 숨김(응답 values·emission 은 지금 주기 칸만) · 행마다 period 줄(before/after = 옛/새 주기).
//   - 복구(W12-2 ①, POST X/rows/{r}/history/{h}/restore): 404 → 422 historyId(na_on·na_off·unit) → 403(factor, 운영 관리자 아님) →
//     422 reason(factor 사유 없음) → 422 historyId(맨 위) → 409 LOCKED → 409 RESTORE_STALE(value 칸이 지금 주기 밖·단위 다름) → 새 줄.
//     period 줄 = 블록 주기를 그 줄의 after 로. 히스토리 restorable 은 같은 규칙(종류 → 맨 위 → 잠금 → 낡음)으로 읽을 때 셈.
export const POOL_GASES = ['CO2', 'CH4', 'N2O', 'HFCs', 'PFCs', 'SF6', 'NF3'];
export const POOL_UNITS: Record<string, string[]> = {
  mass: ['g', 'kg', 't'],
  volume: ['L', 'kL', 'm3', 'Nm3', 'kNm3'],
  energy: ['MJ', 'GJ', 'TJ'],
  electricity: ['kWh', 'MWh', 'GWh'],
};

/** 지어낸 선택 목록(GhgOptionsOut — 국가·산업 이름도 지어냄). */
export function fakePoolOptions(): PoolOptions {
  return {
    gases: [...POOL_GASES],
    units: Object.entries(POOL_UNITS).map(([kind, units]) => ({
      kind,
      units: [...units],
    })),
    countries: [
      { code: 'GLOBAL', name: '지어낸 전 세계' },
      { code: 'KR', name: '지어낸 국내' },
    ],
    industries: [
      { code: 'energy_industries', name: '지어낸 에너지' },
      { code: 'other', name: '지어낸 기타' },
    ],
    defaults: {
      emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
      factorUnitWithNcv: 'kg/TJ',
      factorUnitWithoutNcv: 'kg/<투입 단위>',
    },
  };
}

/** 가짜 풀 노드 한 줄(씨앗 — 잎은 facilityCodeId 로 코드 목록을 가리킨다, 이름은 코드에서). */
export interface FakePoolNode {
  id: string;
  level: PoolLevel;
  name: string;
  parentId: string | null;
  sortOrder: number;
  facilityCodeId?: string;
  unit?: PoolUnit;
  tooltip?: string;
}

/** 가짜 계수 한 판(씨앗). */
export interface FakePoolFactor {
  id: string;
  facilityNodeId: string;
  sortOrder: number;
  isDefault: boolean;
  /** 판들(1부터 차례). */
  versions: FactorBody[];
}

/** 지어낸 계수 본문(가스 셋 켬 — 값은 지어냄). */
export function fakeFactorBody(name: string): FactorBody {
  return {
    name,
    source: '지어낸 출처',
    baseYear: 2024,
    tier: 1,
    countryCode: 'KR',
    industryCode: 'energy_industries',
    inputUnit: { kind: 'volume', unit: 'kL' },
    emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
    ncvEnabled: true,
    ncv: '35.3',
    ncvUnit: { kind: 'energy', unit: 'MJ' },
    factorUnit: 'kg/TJ',
    note: '',
    gases: POOL_GASES.map((gas, index) =>
      index < 3 ?
        { gas, enabled: true, factor: `${index + 1}.5`, gwp: `${index + 1}` }
      : { gas, enabled: false },
    ),
  };
}

/**
 * 지어낸 풀 씨앗: 범위 둘 · 유형 둘 · 활동 둘 · 잎 셋 · 계수 둘(잎 「지어낸 보일러」(id 20)에 둘 — 21 기본).
 *   1 지어낸 직접배출 ─ 3 지어낸 고정연소 ─ 5 지어낸 액체연료 ─ 20 잎(코드 1 지어낸 보일러) · 22 잎(코드 2 지어낸 발전기)
 *                     └ 4 지어낸 이동연소 ─ 6 지어낸 도로수송 ─ 24 잎(코드 3 지어낸 사업장 차량, 계수 0)
 *   2 지어낸 간접배출(자식 없음)
 */
export function fakePool(): {
  nodes: FakePoolNode[];
  factors: FakePoolFactor[];
} {
  const leaf = (
    id: string,
    parentId: string,
    facilityCodeId: string,
  ): FakePoolNode => ({
    id,
    level: 'facility',
    name: '',
    parentId,
    sortOrder: Number(id),
    facilityCodeId,
    unit: { kind: 'volume', unit: 'kL' },
    tooltip: '지어낸 툴팁',
  });
  return {
    nodes: [
      {
        id: '1',
        level: 'scope',
        name: '지어낸 직접배출',
        parentId: null,
        sortOrder: 1,
      },
      {
        id: '2',
        level: 'scope',
        name: '지어낸 간접배출',
        parentId: null,
        sortOrder: 2,
      },
      {
        id: '3',
        level: 'source_type',
        name: '지어낸 고정연소',
        parentId: '1',
        sortOrder: 3,
      },
      {
        id: '4',
        level: 'source_type',
        name: '지어낸 이동연소',
        parentId: '1',
        sortOrder: 4,
      },
      {
        id: '5',
        level: 'activity',
        name: '지어낸 액체연료',
        parentId: '3',
        sortOrder: 5,
      },
      {
        id: '6',
        level: 'activity',
        name: '지어낸 도로수송',
        parentId: '4',
        sortOrder: 6,
      },
      leaf('20', '5', '1'),
      leaf('22', '5', '2'),
      leaf('24', '6', '3'),
    ],
    factors: [
      {
        id: '21',
        facilityNodeId: '20',
        sortOrder: 21,
        isDefault: true,
        versions: [fakeFactorBody('지어낸 경유 계수')],
      },
      {
        id: '23',
        facilityNodeId: '20',
        sortOrder: 23,
        isDefault: false,
        versions: [fakeFactorBody('지어낸 등유 계수')],
      },
    ],
  };
}

export interface FakeGhgServerOptions {
  branches?: BranchDetail[];
  codes?: FacilityCode[];
  baseUrl?: string;
  /** 거짓이면 /admin/** 이 403 FORBIDDEN(고객사 사용자). */
  admin?: boolean;
  /** 주면 /branches·/facility-codes 가 이 회사 거절(400)을 낸다. */
  company?: 'COMPANY_AMBIGUOUS' | 'COMPANY_INACTIVE' | 'COMPANY_NOT_FOUND';
  /** 풀 씨앗(밴드 W12-0b1 ② — 없으면 fakePool()). */
  pool?: { nodes: FakePoolNode[]; factors: FakePoolFactor[] };
  /** 고객사 선택(밴드 W12-0b2 ①)의 올해 — 없으면 Asia/Seoul 의 올해(서버 today). */
  thisYear?: number;
  /** 이미 있는 선택 씨앗(해 → 잎 id — 검사 없이 심는다. J1: 지금은 못 고를 잎이 예전에 골라진 꼴). */
  chosen?: Record<number, string[]>;
  /** 입력 리스트의 잎별 해 값 씨앗(잎 id → 해 글자 → 배출량 글자 — 셈 흉내 0, 밴드 W12-1a). */
  entryValues?: Record<string, Record<string, string | null>>;
  /** 입력 리스트의 배출범위별 해 합 씨앗(범위 노드 id → 해 글자 → 글자). */
  scopeValues?: Record<string, Record<string, string | null>>;
  /** 상세 행 배출량(값 있는 행에 늘 이 글자). */
  entryEmission?: string;
  /** 주면 행 저장이 늘 이 칸 열쇠들로 422(화면의 칸 오류 시험용). */
  entryReject?: string[];
  /** 금액 바뀜 히스토리의 kind(기본 value — 모르는 종류 시험용). */
  entryHistoryKind?: string;
  /** 블록별 입력주기 씨앗(사업장 id → 주기, 밴드 W12-1b — 없으면 month). 칸은 서버처럼 주기에서 나온다. PUT period 가 (해·잎·사업장)마다 바꾼다(W12-2). */
  entryPeriod?: Record<string, 'month' | 'quarter' | 'year'>;
  /** 행 계수 심기(자산/시설 id → 응답 행 factor 그대로 — 없으면 null). */
  entryRowFactor?: Record<string, Record<string, unknown>>;
  /** 잎 단위 뒤에 더 고를 단위들(서버 unit_options 의 2차 단위 흉내). */
  entryUnits?: string[];
  /** 올리기 심는 답(W12-5 ① — xlsx 를 읽지 않는다. 앞에서 하나씩 꺼낸다, 비면 넷 다 0 인 200). 값을 바꾼 뒤 던지면 「표를 바꾼 뒤 끊김」. */
  uploadAnswers?: (() => Response)[];
  /** 대시보드(S1) 답 씨앗(해 → Scope12DashboardOut 꼴 그대로 — 밴드 DB1). 없는 해는 dashboardOut(해) — 빈 판(configured 거짓·Scope 3 없음). */
  dashboards?: Record<number, Schemas['Scope12DashboardOut']>;
  /** 대시보드 해별 끊김(밴드 DB2 — 이 해들의 GET 은 늘 끊김. override[KEY] 는 해를 모르고 부름 차례로 꺼내서). */
  dashboardFailures?: number[];
  /** 대시보드 해별 회사 거절(밴드 DB3 — 넘김 R2: 이 해들의 GET 은 그 회사 거절 400). */
  dashboardRefusals?: Record<
    number,
    'COMPANY_AMBIGUOUS' | 'COMPANY_INACTIVE' | 'COMPANY_NOT_FOUND'
  >;
}

/** 대시보드 빈 판(openapi Scope12DashboardOut 꼴 — 설정 안 된 해·Scope 3 결과 없음). 덮을 칸을 준다. */
export function dashboardOut(
  year: number,
  patch: Partial<Schemas['Scope12DashboardOut']> = {},
): Schemas['Scope12DashboardOut'] {
  return {
    year,
    configured: false,
    decimals: 2,
    basis: 'location',
    unit: 'tCO2-eq',
    complete: true,
    scopes: [],
    total: {
      scope12: null,
      scope2Market: null,
      scope3: null,
      sum: null,
      scope3FailedSheets: 0,
    },
    bySite: [],
    scope3Categories: [],
    ...patch,
  };
}

/** 고객사 선택 씨앗(밴드 W12-0b2): 잎 둘을 고를 수 있다 — 22 에 기본 계수 · 제1공장(코드 2·3 줄). 24 는 시설 있고 계수 없음. */
export function fakeSelectionOptions(): FakeGhgServerOptions {
  const pool = fakePool();
  pool.factors.push({
    id: '30',
    facilityNodeId: '22',
    sortOrder: 30,
    isDefault: true,
    versions: [fakeFactorBody('지어낸 발전기 계수')],
  });
  return {
    pool,
    thisYear: 2026,
    branches: [
      fakeHeadquarters(),
      {
        ...fakeBranch(2, '제1공장'),
        facilities: [
          {
            id: '2',
            facilityCodeId: '2',
            facilityCode: 'F0002',
            facilityName: '지어낸 발전기',
            detailName: '2호기',
          },
          {
            id: '3',
            facilityCodeId: '3',
            facilityCode: 'F0003',
            facilityName: '지어낸 사업장 차량',
            detailName: '1호차',
          },
        ],
      },
    ],
  };
}

export function fakeGhgServer({
  branches = [fakeHeadquarters()],
  codes = fakeCodes(),
  baseUrl = 'http://test.local/api',
  admin = true,
  company,
  pool,
  thisYear = seoulYear(new Date()),
  chosen = {},
  entryValues = {},
  scopeValues = {},
  entryEmission = '1.5',
  entryReject = [],
  entryHistoryKind = 'value',
  entryPeriod = {},
  entryRowFactor = {},
  entryUnits = [],
  uploadAnswers = [],
  dashboards = {},
  dashboardFailures = [],
  dashboardRefusals = {},
}: FakeGhgServerOptions = {}) {
  const calls: FakeGhgCall[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  const stored = branches.map((branch) => structuredClone(branch));
  /** 지운 코드도 남긴다(삭제 표시 — deleted). 목록·이름 겹침은 살아 있는 것만. */
  const storedCodes: (FacilityCode & { deleted?: true })[] = codes.map(
    (code) => ({ ...code }),
  );
  const aliveCodes = () => storedCodes.filter((c) => !c.deleted);
  const plainCode = ({ id, code, name }: FacilityCode) => ({ id, code, name });
  let nextBranch = Math.max(0, ...stored.map((b) => Number(b.id))) + 1;
  let nextLine =
    Math.max(
      0,
      ...stored.flatMap((b) => b.facilities.map((line) => Number(line.id))),
    ) + 1;
  let nextCode = Math.max(0, ...storedCodes.map((c) => Number(c.id))) + 1;
  /** 판 버전 — 씨앗(10-28)보다 늘 뒤, 바뀔 때마다 1µs 씩 커진다. */
  let tick = 0;
  const bump = (branch: BranchDetail) => {
    tick += 1;
    branch.updatedAt = `2026-10-29T09:00:00.${String(tick).padStart(6, '0')}+09:00`;
  };

  const sorted = () =>
    [...stored].sort(
      (a, b) =>
        Number(b.isHeadquarters) - Number(a.isHeadquarters) ||
        Number(a.id) - Number(b.id),
    );
  const findBranch = (id: number) => stored.find((b) => b.id === String(id));

  /** 사업장 본문 검사 → 422 거절이나 null. lines 는 고친 뒤 줄. */
  const checkBranch = (
    body: unknown,
    branch: BranchDetail | null,
  ): Response | BranchDetail['facilities'] => {
    const {
      name,
      inventoryEnabled,
      facilities = [],
    } = body as {
      name?: unknown;
      inventoryEnabled?: unknown;
      facilities?: unknown;
    };
    if (typeof name !== 'string' || name.trim() === '')
      return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 빈 이름'] });
    if (
      stored.some(
        (other) => other !== branch && other.name.trim() === name.trim(),
      )
    )
      return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 이름 겹침'] });
    if (typeof inventoryEnabled !== 'boolean' || !Array.isArray(facilities))
      return refusal(422, 'VALIDATION_ERROR');
    const lines: BranchDetail['facilities'] = [];
    const seen = new Set<string>();
    const seenIds = new Set<unknown>();
    for (const raw of facilities as unknown[]) {
      const line = raw as {
        id?: unknown;
        facilityCodeId?: unknown;
        detailName?: unknown;
      };
      if (line.id !== undefined && line.id !== null) {
        // POST 에 id 가 있으면 404, PUT 에서는 그 사업장의 줄이어야 한다.
        if (!isInt(line.id)) return refusal(422, 'VALIDATION_ERROR');
        if (seenIds.has(line.id))
          return refusal(422, 'VALIDATION_ERROR', {
            facilities: ['지어낸 같은 줄 두 번'],
          });
        seenIds.add(line.id);
        if (
          !branch ||
          !branch.facilities.some((old) => old.id === String(line.id))
        )
          return refusal(404, 'NOT_FOUND');
      }
      if (!isInt(line.facilityCodeId))
        return refusal(422, 'VALIDATION_ERROR', {
          facilityCodeId: ['지어낸 정수 아님'],
        });
      const code = storedCodes.find(
        (c) => c.id === String(line.facilityCodeId),
      );
      // 그 줄이 이미 쓰는 코드를 그대로 두면 지운 코드여도 지난다 — 새로 고른 코드만 살아 있어야 한다.
      const kept = branch?.facilities.some(
        (old) =>
          isInt(line.id) &&
          old.id === String(line.id) &&
          old.facilityCodeId === String(line.facilityCodeId),
      );
      if (!code || (code.deleted && !kept))
        return refusal(422, 'VALIDATION_ERROR', {
          facilityCodeId: ['지어낸 없는 코드'],
        });
      if (typeof line.detailName !== 'string' || line.detailName.trim() === '')
        return refusal(422, 'VALIDATION_ERROR', {
          facilities: ['지어낸 빈 세부시설명'],
        });
      const key = `${code.id}/${line.detailName.trim()}`;
      if (seen.has(key))
        return refusal(422, 'VALIDATION_ERROR', {
          facilities: ['지어낸 겹침'],
        });
      seen.add(key);
      const id = isInt(line.id) ? String(line.id) : String(nextLine++);
      lines.push({
        id,
        facilityCodeId: code.id,
        facilityCode: code.code,
        facilityName: code.name,
        detailName: line.detailName.trim(),
      });
    }
    return lines;
  };

  const branchRoutes = (
    key: string,
    url: URL,
    body: unknown,
  ): Response | null => {
    if (key === 'GET /branches') {
      const q = url.searchParams.get('q') ?? '';
      const page = Number(url.searchParams.get('page') ?? 1);
      const pageSize = Number(url.searchParams.get('pageSize') ?? 20);
      if (q.length > 200 || !(page >= 1) || !(pageSize >= 1 && pageSize <= 100))
        return refusal(422, 'VALIDATION_ERROR');
      const rows = sorted()
        .filter((b) => b.name.toLowerCase().includes(q.toLowerCase()))
        .map(outOf);
      return json(200, pageOf(rows, page, pageSize));
    }
    if (key === 'POST /branches') {
      if ((body as object | undefined) && 'updatedAt' in (body as object))
        return refusal(422, 'VALIDATION_ERROR', {
          updatedAt: ['지어낸 모르는 칸'],
        });
      const lines = checkBranch(body, null);
      if (lines instanceof Response) return lines;
      const { name, inventoryEnabled } = body as {
        name: string;
        inventoryEnabled: boolean;
      };
      const made: BranchDetail = {
        ...fakeBranch(nextBranch++, name.trim(), { inventoryEnabled }),
        facilities: lines,
      };
      bump(made);
      stored.push(made);
      return json(201, made);
    }
    if (key === 'POST /branches/inventory') {
      const { ids, enabled } = body as { ids?: unknown; enabled?: unknown };
      if (!isIntList(ids) || typeof enabled !== 'boolean')
        return refusal(422, 'VALIDATION_ERROR');
      const found = ids.map(findBranch);
      if (found.some((b) => !b)) return refusal(404, 'NOT_FOUND');
      if (!enabled && found.some((b) => b!.isHeadquarters))
        return refusal(409, 'HEADQUARTERS_LOCKED');
      for (const b of found) {
        b!.inventoryEnabled = enabled;
        bump(b!);
      }
      return json(200, { count: found.length });
    }
    if (key === 'POST /branches/delete') {
      const { ids } = body as { ids?: unknown };
      if (!isIntList(ids)) return refusal(422, 'VALIDATION_ERROR');
      const found = ids.map(findBranch);
      if (found.some((b) => !b)) return refusal(404, 'NOT_FOUND');
      if (found.some((b) => b!.isHeadquarters))
        return refusal(409, 'HEADQUARTERS_LOCKED');
      for (const b of found) stored.splice(stored.indexOf(b!), 1);
      return json(200, { count: found.length });
    }
    const one = /^(GET|PUT) \/branches\/([^/]+)$/.exec(key);
    if (one) {
      const id = pathId(one[2]!);
      if (id === null) return refusal(422, 'VALIDATION_ERROR');
      // 본문 꼴(판 없음 422)은 서버처럼 404 보다 먼저, 낡은 판(409)은 404 뒤.
      const { updatedAt } = (body ?? {}) as { updatedAt?: unknown };
      if (
        one[1] === 'PUT' &&
        (typeof updatedAt !== 'string' || updatedAt === '')
      )
        return refusal(422, 'VALIDATION_ERROR', {
          updatedAt: ['지어낸 판 없음'],
        });
      const branch = findBranch(id);
      if (!branch) return refusal(404, 'NOT_FOUND');
      if (one[1] === 'GET') return json(200, branch);
      if (updatedAt !== branch.updatedAt) return refusal(409, 'STALE');
      const lines = checkBranch(body, branch);
      if (lines instanceof Response) return lines;
      const { name, inventoryEnabled } = body as {
        name: string;
        inventoryEnabled: boolean;
      };
      if (branch.isHeadquarters && !inventoryEnabled)
        return refusal(409, 'HEADQUARTERS_LOCKED');
      branch.name = name.trim();
      branch.inventoryEnabled = inventoryEnabled;
      branch.facilities = lines;
      bump(branch);
      return json(200, branch);
    }
    if (key === 'GET /facility-codes')
      return json(200, {
        items: codesByName(aliveCodes()).map(plainCode),
      });
    return null;
  };

  const adminRoutes = (
    key: string,
    url: URL,
    body: unknown,
  ): Response | null => {
    const nameOf = (selfId: string | null): string | Response => {
      const { name } = body as { name?: unknown };
      if (typeof name !== 'string' || name.trim() === '')
        return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 빈 이름'] });
      if (aliveCodes().some((c) => c.id !== selfId && c.name === name.trim()))
        return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 겹침'] });
      return name.trim();
    };
    if (key === 'GET /admin/facility-codes') {
      const page = Number(url.searchParams.get('page') ?? 1);
      const pageSize = Number(url.searchParams.get('pageSize') ?? 20);
      if (!(page >= 1) || !(pageSize >= 1 && pageSize <= 100))
        return refusal(422, 'VALIDATION_ERROR');
      const rows = aliveCodes().map((c) => ({ ...plainCode(c), inUse: false }));
      return json(200, pageOf(rows, page, pageSize));
    }
    if (key === 'POST /admin/facility-codes') {
      const name = nameOf(null);
      if (name instanceof Response) return name;
      const id = nextCode++;
      const made = {
        id: String(id),
        code: `F${String(id).padStart(4, '0')}`,
        name,
      };
      storedCodes.push(made);
      return json(201, plainCode(made));
    }
    if (key === 'POST /admin/facility-codes/delete') {
      const { ids } = body as { ids?: unknown };
      if (!isIntList(ids)) return refusal(422, 'VALIDATION_ERROR');
      const found = ids.map((id) =>
        aliveCodes().find((c) => c.id === String(id)),
      );
      if (found.some((c) => !c)) return refusal(404, 'NOT_FOUND');
      for (const c of found) c!.deleted = true;
      return json(200, { count: found.length });
    }
    const one = /^PATCH \/admin\/facility-codes\/([^/]+)$/.exec(key);
    if (one) {
      const id = pathId(one[1]!);
      if (id === null) return refusal(422, 'VALIDATION_ERROR');
      const code = aliveCodes().find((c) => c.id === String(id));
      if (!code) return refusal(404, 'NOT_FOUND');
      const name = nameOf(code.id);
      if (name instanceof Response) return name;
      code.name = name;
      return json(200, plainCode(code));
    }
    return null;
  };

  // ── 밴드 W12-0b1 ②: 풀 경로(/inventory/admin/…) ──
  const poolSeed = pool ?? fakePool();
  const poolNodes = poolSeed.nodes.map((node) => ({
    ...structuredClone(node),
    deleted: false,
  }));
  const poolFactors = poolSeed.factors.map((factor) => ({
    ...structuredClone(factor),
    deleted: false,
  }));
  /** 「쓰이는 표」 — 고객사 선택(S17)이 잡은 잎·계수 id. 시험이 채운다(W12-0b2 의 선택 경로가 채울 자리). */
  const poolInUse = { nodes: new Set<string>(), factors: new Set<string>() };
  let nextNode =
    Math.max(
      0,
      ...poolNodes.map((n) => Number(n.id)),
      ...poolFactors.map((f) => Number(f.id)),
    ) + 1;
  const stamp = '2026-10-29T09:00:00+09:00';

  const aliveNodes = () => poolNodes.filter((n) => !n.deleted);
  const aliveFactors = () => poolFactors.filter((f) => !f.deleted);
  const findNode = (id: number) =>
    aliveNodes().find((n) => n.id === String(id));
  const codeById = (id: string) => storedCodes.find((c) => c.id === id);
  const nodeName = (node: FakePoolNode) =>
    node.level === 'facility' ?
      (codeById(node.facilityCodeId ?? '')?.name ?? '')
    : node.name;
  const childrenOf = (id: string) =>
    aliveNodes().filter((n) => n.parentId === id);
  const nodeOut = (node: FakePoolNode) => ({
    id: node.id,
    level: node.level,
    name: nodeName(node),
    parentId: node.parentId,
    sortOrder: node.sortOrder,
    childCount: childrenOf(node.id).length,
    facilityCode:
      node.level === 'facility' ?
        (codeById(node.facilityCodeId ?? '')?.code ?? '')
      : null,
    facilityCodeId: node.level === 'facility' ? node.facilityCodeId! : null,
  });
  const byPoolOrder = (a: FakePoolNode, b: FakePoolNode) =>
    POOL_LEVELS.indexOf(a.level) - POOL_LEVELS.indexOf(b.level) ||
    a.sortOrder - b.sortOrder ||
    Number(a.id) - Number(b.id);
  const factorsOfLeaf = (leafId: string) =>
    aliveFactors()
      .filter((f) => f.facilityNodeId === leafId)
      .sort((a, b) => a.sortOrder - b.sortOrder || Number(a.id) - Number(b.id));
  const facilityOut = (node: FakePoolNode) => ({
    id: node.id,
    parentId: node.parentId!,
    facilityCodeId: node.facilityCodeId!,
    facilityCode: codeById(node.facilityCodeId!)?.code ?? '',
    facilityName: nodeName(node),
    unit: { ...node.unit! },
    tooltip: node.tooltip ?? '',
    factors: factorsOfLeaf(node.id).map((f) => ({
      id: f.id,
      name: f.versions.at(-1)!.name,
      inputUnit: { ...f.versions.at(-1)!.inputUnit },
      isDefault: f.isDefault,
      sortOrder: f.sortOrder,
      version: f.versions.length,
    })),
  });
  const factorOut = (
    factor: FakePoolFactor,
    version = factor.versions.length,
  ) => {
    const body = factor.versions[version - 1]!;
    return {
      id: factor.id,
      facilityNodeId: factor.facilityNodeId,
      version,
      versions: factor.versions.map((_, index) => index + 1),
      name: body.name,
      source: body.source,
      baseYear: body.baseYear,
      tier: body.tier,
      countryCode: body.countryCode,
      industryCode: body.industryCode,
      inputUnit: { ...body.inputUnit },
      emissionUnit: { ...body.emissionUnit },
      ncvEnabled: body.ncvEnabled,
      ncv: body.ncv,
      ncvUnit: body.ncvUnit,
      factorUnit:
        body.factorUnit ??
        (body.ncvEnabled ? 'kg/TJ' : `kg/${body.inputUnit.unit}`),
      gases: POOL_GASES.map((gas) => {
        const one = body.gases.find((g) => g.gas === gas);
        return {
          gas,
          enabled: one?.enabled ?? false,
          factor: one?.factor ?? null,
          gwp: one?.gwp ?? null,
        };
      }),
      note: body.note,
      isDefault: factor.isDefault,
      sortOrder: factor.sortOrder,
      seedGwpSetId: null,
      seedRecordIds: [],
      createdAt: stamp,
      updatedAt: stamp,
    };
  };
  const isUnit = (value: unknown): value is PoolUnit => {
    const unit = value as PoolUnit | null;
    return (
      typeof unit === 'object' &&
      unit !== null &&
      (POOL_UNITS[unit.kind] ?? []).includes(unit.unit)
    );
  };
  const isDecimalText = (value: unknown): value is string =>
    typeof value === 'string' &&
    /^[0-9]{1,18}(\.[0-9]{1,12})?$/.test(value) &&
    /[1-9]/.test(value);

  /** S20 검사(서버 check_factor 의 줄인 꼴) → {칸: 까닭} 이나 null. */
  const factorProblems = (raw: unknown): Record<string, string[]> | null => {
    const body = raw as Partial<FactorBody> & Record<string, unknown>;
    const errors: Record<string, string[]> = {};
    const text = (key: string, limit: number) => {
      const value = body[key];
      if (
        typeof value !== 'string' ||
        value.trim() === '' ||
        value.length > limit
      )
        errors[key] = ['지어낸 칸 틀림'];
    };
    text('name', 100);
    text('source', 200);
    if (!(
      typeof body.baseYear === 'number' &&
      body.baseYear >= 1990 &&
      body.baseYear <= 2100
    ))
      errors.baseYear = ['지어낸 기준연도'];
    if (![1, 2, 3].includes(body.tier as number)) errors.tier = ['지어낸 Tier'];
    if (!fakePoolOptions().countries.some((c) => c.code === body.countryCode))
      errors.countryCode = ['지어낸 국가'];
    if (!fakePoolOptions().industries.some((c) => c.code === body.industryCode))
      errors.industryCode = ['지어낸 산업'];
    if (!isUnit(body.inputUnit)) errors.inputUnit = ['지어낸 단위'];
    // 배출량 기준단위: 없으면 질량 / tCO2-eq, 있으면 EMISSION_UNITS 안(서버 check_factor).
    const emission = body.emissionUnit ?? { kind: 'mass', unit: 'tCO2-eq' };
    if (
      emission.kind !== 'mass' ||
      !['tCO2-eq', 'kgCO2-eq'].includes(emission.unit)
    )
      errors.emissionUnit = ['지어낸 배출 단위'];
    if (body.ncvEnabled === true) {
      if (!isDecimalText(body.ncv)) errors.ncv = ['지어낸 순발열량'];
      if (!isUnit(body.ncvUnit)) errors.ncvUnit = ['지어낸 단위'];
      else if (body.ncvUnit.kind !== 'energy')
        errors.ncvUnit = ['지어낸 에너지 아님'];
    } else if (
      (body.ncv !== null && body.ncv !== undefined) ||
      (body.ncvUnit !== null && body.ncvUnit !== undefined)
    )
      errors.ncv = ['지어낸 끈 순발열량에 값'];
    // 계수 단위(서버 is_factor_unit·_check_unit_kinds): `<질량>/<단위>` 꼴, 분모 종류 = 켬이면 energy · 끔이면 투입 단위 종류.
    // 비우면 기본값(켬 kg/TJ · 끔 kg/<투입 단위>)을 본다 — 늘 지난다.
    if (body.factorUnit !== null && body.factorUnit !== undefined) {
      const [mass, per, ...more] = String(body.factorUnit).split('/');
      const perKind = Object.entries(POOL_UNITS).find(([, units]) =>
        units.includes(per ?? ''),
      )?.[0];
      if (more.length > 0 || !POOL_UNITS.mass!.includes(mass ?? '') || !perKind)
        errors.factorUnit = ['지어낸 꼴'];
      else if (isUnit(body.inputUnit)) {
        const want = body.ncvEnabled === true ? 'energy' : body.inputUnit.kind;
        if (perKind !== want) errors.factorUnit ??= ['지어낸 분모 종류'];
      }
    }
    if (typeof body.note === 'string' && body.note.length > 1000)
      errors.note = ['지어낸 비고'];
    const gases =
      Array.isArray(body.gases) ? (body.gases as FactorGasBody[]) : [];
    if (
      gases.some((g) => !POOL_GASES.includes(g.gas)) ||
      new Set(gases.map((g) => g.gas)).size !== gases.length
    )
      errors.gases = ['지어낸 가스 꼴'];
    for (const one of gases) {
      if (
        one.factor !== undefined &&
        one.factor !== null &&
        typeof one.factor !== 'string'
      )
        errors[`gases.${one.gas}.factor`] = ['지어낸 숫자 글자 아님'];
      if (
        one.gwp !== undefined &&
        one.gwp !== null &&
        typeof one.gwp !== 'string'
      )
        errors[`gases.${one.gas}.gwp`] = ['지어낸 숫자 글자 아님'];
      if (!one.enabled) continue;
      if (!isDecimalText(one.factor))
        errors[`gases.${one.gas}.factor`] ??= ['지어낸 계수'];
      if (!isDecimalText(one.gwp))
        errors[`gases.${one.gas}.gwp`] ??= ['지어낸 GWP'];
    }
    if (!gases.some((g) => g.enabled)) errors.gases ??= ['지어낸 켠 가스 0'];
    return Object.keys(errors).length > 0 ? errors : null;
  };
  /** 새로 고른 코드가 살아 있고 같은 활동 아래 겹치지 않는가(그대로 두면 지운 코드여도 지남). */
  const codeProblem = (
    parentId: string,
    codeId: unknown,
    keep: string | null,
    selfId: string | null,
  ): Response | null => {
    if (!isInt(codeId))
      return refusal(422, 'VALIDATION_ERROR', {
        facilityCodeId: ['지어낸 정수 아님'],
      });
    const code = codeById(String(codeId));
    if (!code || (code.deleted && String(codeId) !== keep))
      return refusal(422, 'VALIDATION_ERROR', {
        facilityCodeId: ['지어낸 지운 코드'],
      });
    if (
      childrenOf(parentId).some(
        (n) => n.id !== selfId && n.facilityCodeId === String(codeId),
      )
    )
      return refusal(422, 'VALIDATION_ERROR', {
        facilityCodeId: ['지어낸 겹침'],
      });
    return null;
  };

  const poolRoutes = (
    key: string,
    url: URL,
    body: unknown,
  ): Response | null => {
    if (key === 'GET /inventory/admin/ghg-options')
      return json(200, fakePoolOptions());
    if (key === 'GET /inventory/admin/ghg-index/nodes') {
      const q = url.searchParams.get('q');
      const parent = url.searchParams.get('parentId');
      if (q !== null) {
        if (q.length > 100)
          return refusal(422, 'VALIDATION_ERROR', { q: ['지어낸 김'] });
        const hit = new Set(
          aliveNodes()
            .filter((n) => nodeName(n).toLowerCase().includes(q.toLowerCase()))
            .map((n) => n.id),
        );
        for (const id of [...hit]) {
          let up = aliveNodes().find((n) => n.id === id)?.parentId ?? null;
          while (up !== null) {
            hit.add(up);
            up = aliveNodes().find((n) => n.id === up)?.parentId ?? null;
          }
        }
        return json(200, {
          items: aliveNodes()
            .filter((n) => hit.has(n.id))
            .sort(byPoolOrder)
            .map(nodeOut),
        });
      }
      if (parent !== null) {
        const id = pathId(parent);
        if (id === null) return refusal(422, 'VALIDATION_ERROR');
        if (!findNode(id)) return refusal(404, 'NOT_FOUND');
        return json(200, {
          items: childrenOf(String(id)).sort(byPoolOrder).map(nodeOut),
        });
      }
      return json(200, {
        items: aliveNodes()
          .filter((n) => n.parentId === null)
          .sort(byPoolOrder)
          .map(nodeOut),
      });
    }
    if (key === 'POST /inventory/admin/ghg-index/nodes') {
      const {
        level,
        parentId = null,
        name,
      } = body as {
        level?: unknown;
        parentId?: unknown;
        name?: unknown;
      };
      if (
        typeof level !== 'string' ||
        !POOL_LEVELS.slice(0, 3).includes(level as PoolLevel)
      )
        return refusal(422, 'VALIDATION_ERROR', { level: ['지어낸 단'] });
      if (
        typeof name !== 'string' ||
        name.trim() === '' ||
        name.trim().length > 100
      )
        return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 이름'] });
      const wantParent =
        POOL_LEVELS[POOL_LEVELS.indexOf(level as PoolLevel) - 1] ?? null;
      if ((wantParent === null) !== (parentId === null))
        return refusal(422, 'VALIDATION_ERROR', { parentId: ['지어낸 부모'] });
      if (parentId !== null) {
        if (!isInt(parentId))
          return refusal(422, 'VALIDATION_ERROR', {
            parentId: ['지어낸 정수 아님'],
          });
        const parent = findNode(parentId);
        if (!parent) return refusal(404, 'NOT_FOUND');
        if (parent.level !== wantParent)
          return refusal(422, 'VALIDATION_ERROR', {
            parentId: ['지어낸 부모 단'],
          });
      }
      const parentKey = parentId === null ? null : String(parentId);
      if (
        aliveNodes().some(
          (n) => n.parentId === parentKey && nodeName(n) === name.trim(),
        )
      )
        return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 겹침'] });
      const id = String(nextNode++);
      const made = {
        id,
        level: level as PoolLevel,
        name: name.trim(),
        parentId: parentKey,
        sortOrder: Number(id),
        deleted: false,
      };
      poolNodes.push(made);
      return json(201, nodeOut(made));
    }
    if (key === 'POST /inventory/admin/ghg-index/nodes/delete') {
      const { ids } = body as { ids?: unknown };
      if (!isIntList(ids)) return refusal(422, 'VALIDATION_ERROR');
      const found = ids.map(findNode);
      if (found.some((n) => !n)) return refusal(404, 'NOT_FOUND');
      const wanted = new Set(ids.map(String));
      if (found.some((n) => childrenOf(n!.id).some((c) => !wanted.has(c.id))))
        return refusal(409, 'HAS_CHILDREN');
      if (found.some((n) => poolInUse.nodes.has(n!.id)))
        return refusal(409, 'IN_USE');
      const leafFactors = found.flatMap((n) => factorsOfLeaf(n!.id));
      if (leafFactors.some((f) => poolInUse.factors.has(f.id)))
        return refusal(409, 'IN_USE');
      for (const f of leafFactors) f.deleted = true;
      for (const n of found) (n as { deleted: boolean }).deleted = true;
      return json(200, { count: found.length });
    }
    const node = /^PATCH \/inventory\/admin\/ghg-index\/nodes\/([^/]+)$/.exec(
      key,
    );
    if (node) {
      const id = pathId(node[1]!);
      if (id === null) return refusal(422, 'VALIDATION_ERROR');
      const found = findNode(id);
      if (!found || found.level === 'facility')
        return refusal(404, 'NOT_FOUND');
      const { name } = body as { name?: unknown };
      if (
        typeof name !== 'string' ||
        name.trim() === '' ||
        name.trim().length > 100
      )
        return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 이름'] });
      if (
        aliveNodes().some(
          (n) =>
            n !== found &&
            n.parentId === found.parentId &&
            nodeName(n) === name.trim(),
        )
      )
        return refusal(422, 'VALIDATION_ERROR', { name: ['지어낸 겹침'] });
      found.name = name.trim();
      return json(200, nodeOut(found));
    }
    if (key === 'POST /inventory/admin/ghg-index/facilities') {
      const {
        parentId,
        facilityCodeId,
        unit,
        tooltip = '',
      } = body as {
        parentId?: unknown;
        facilityCodeId?: unknown;
        unit?: unknown;
        tooltip?: unknown;
      };
      if (!isUnit(unit))
        return refusal(422, 'VALIDATION_ERROR', { unit: ['지어낸 단위'] });
      if (typeof tooltip !== 'string' || tooltip.length > 1000)
        return refusal(422, 'VALIDATION_ERROR', { tooltip: ['지어낸 툴팁'] });
      if (!isInt(parentId))
        return refusal(422, 'VALIDATION_ERROR', {
          parentId: ['지어낸 정수 아님'],
        });
      const parent = findNode(parentId);
      if (!parent) return refusal(404, 'NOT_FOUND');
      if (parent.level !== 'activity')
        return refusal(422, 'VALIDATION_ERROR', {
          parentId: ['지어낸 부모 단'],
        });
      const problem = codeProblem(parent.id, facilityCodeId, null, null);
      if (problem) return problem;
      const id = String(nextNode++);
      const made = {
        id,
        level: 'facility' as const,
        name: '',
        parentId: parent.id,
        sortOrder: Number(id),
        facilityCodeId: String(facilityCodeId),
        unit: { kind: unit.kind, unit: unit.unit },
        tooltip,
        deleted: false,
      };
      poolNodes.push(made);
      return json(201, facilityOut(made));
    }
    const leafFactors =
      /^POST \/inventory\/admin\/ghg-index\/facilities\/([^/]+)\/factors$/.exec(
        key,
      );
    if (leafFactors) {
      const id = pathId(leafFactors[1]!);
      if (id === null) return refusal(422, 'VALIDATION_ERROR');
      const leaf = findNode(id);
      if (!leaf || leaf.level !== 'facility') return refusal(404, 'NOT_FOUND');
      const problems = factorProblems(body);
      if (problems) return refusal(422, 'VALIDATION_ERROR', problems);
      const factorId = String(nextNode++);
      const made = {
        id: factorId,
        facilityNodeId: leaf.id,
        sortOrder: Number(factorId),
        isDefault: factorsOfLeaf(leaf.id).length === 0,
        versions: [structuredClone(body as FactorBody)],
        deleted: false,
      };
      poolFactors.push(made);
      return json(201, factorOut(made));
    }
    const leaf =
      /^(GET|PUT) \/inventory\/admin\/ghg-index\/facilities\/([^/]+)$/.exec(
        key,
      );
    if (leaf) {
      const id = pathId(leaf[2]!);
      if (id === null) return refusal(422, 'VALIDATION_ERROR');
      const found = findNode(id);
      if (!found || found.level !== 'facility')
        return refusal(404, 'NOT_FOUND');
      if (leaf[1] === 'GET') return json(200, facilityOut(found));
      const {
        facilityCodeId,
        unit,
        tooltip = '',
        defaultFactorId = null,
      } = body as {
        facilityCodeId?: unknown;
        unit?: unknown;
        tooltip?: unknown;
        defaultFactorId?: unknown;
      };
      if (!isUnit(unit))
        return refusal(422, 'VALIDATION_ERROR', { unit: ['지어낸 단위'] });
      if (typeof tooltip !== 'string' || tooltip.length > 1000)
        return refusal(422, 'VALIDATION_ERROR', { tooltip: ['지어낸 툴팁'] });
      const problem = codeProblem(
        found.parentId!,
        facilityCodeId,
        found.facilityCodeId!,
        found.id,
      );
      if (problem) return problem;
      const changesMeaning =
        String(facilityCodeId) !== found.facilityCodeId ||
        unit.kind !== found.unit!.kind ||
        unit.unit !== found.unit!.unit;
      if (changesMeaning && poolInUse.nodes.has(found.id))
        return refusal(409, 'IN_USE');
      let target: (typeof poolFactors)[number] | undefined;
      if (defaultFactorId !== null) {
        target =
          isInt(defaultFactorId) ?
            factorsOfLeaf(found.id).find(
              (f) => f.id === String(defaultFactorId),
            )
          : undefined;
        if (!target)
          return refusal(422, 'VALIDATION_ERROR', {
            defaultFactorId: ['지어낸 그 잎의 계수 아님'],
          });
      }
      found.facilityCodeId = String(facilityCodeId);
      found.unit = { kind: unit.kind, unit: unit.unit };
      found.tooltip = tooltip;
      if (target)
        for (const f of factorsOfLeaf(found.id)) f.isDefault = f === target;
      return json(200, facilityOut(found));
    }
    if (key === 'POST /inventory/admin/ghg-factors/delete') {
      const { ids } = body as { ids?: unknown };
      if (!isIntList(ids)) return refusal(422, 'VALIDATION_ERROR');
      const found = ids.map((id) =>
        aliveFactors().find((f) => f.id === String(id)),
      );
      if (found.some((f) => !f)) return refusal(404, 'NOT_FOUND');
      if (found.some((f) => poolInUse.factors.has(f!.id)))
        return refusal(409, 'IN_USE');
      const orphaned = new Set(
        found.filter((f) => f!.isDefault).map((f) => f!.facilityNodeId),
      );
      for (const f of found) {
        f!.deleted = true;
        f!.isDefault = false;
      }
      for (const leafId of orphaned) {
        const heir = factorsOfLeaf(leafId)[0];
        if (heir) heir.isDefault = true;
      }
      return json(200, { count: found.length });
    }
    const factor = /^(GET|PUT) \/inventory\/admin\/ghg-factors\/([^/]+)$/.exec(
      key,
    );
    if (factor) {
      const id = pathId(factor[2]!);
      if (id === null) return refusal(422, 'VALIDATION_ERROR');
      const found = aliveFactors().find((f) => f.id === String(id));
      if (!found) return refusal(404, 'NOT_FOUND');
      if (factor[1] === 'GET') {
        const version = url.searchParams.get('version');
        if (version === null) return json(200, factorOut(found));
        const n = pathId(version);
        if (n === null || n > found.versions.length)
          return refusal(404, 'NOT_FOUND');
        return json(200, factorOut(found, n));
      }
      const problems = factorProblems(body);
      if (problems) return refusal(422, 'VALIDATION_ERROR', problems);
      found.versions.push(structuredClone(body as FactorBody));
      return json(200, factorOut(found));
    }
    return null;
  };

  // ── 밴드 W12-0b2 ①: 고객사 인덱스 선택(S17) — GET /inventory/scope12/index-tree · PUT /inventory/scope12/index-selections/{year}.
  //    서버 actions/index_selection.py 를 거르지 않고 따른다(위 머리 주석의 「선택」 줄).
  /** 해 → 잎 id → 선택 한 줄(잡은 계수 id · 숨김). 해가 있으면 그 해 행이 있다(빈 선택 저장도 해를 만든다). */
  const selections = new Map<
    number,
    Map<string, { factorId: string; hidden: boolean }>
  >();
  /** 데이터가 있는 잎(시험이 심는다 — 서버 with_data, 지금 서버는 늘 빔·S12a). 해가 있을 때만 hasData 참. */
  const selectionData = new Set<string>();
  const facilityCount = (codeId: string | undefined) =>
    stored
      .filter((b) => b.inventoryEnabled)
      .flatMap((b) => b.facilities)
      .filter((line) => line.facilityCodeId === codeId).length;
  const defaultFactorOf = (leafId: string) =>
    factorsOfLeaf(leafId).find((f) => f.isDefault);
  for (const [year, ids] of Object.entries(chosen))
    selections.set(
      Number(year),
      new Map(
        ids.map((id) => [
          id,
          { factorId: defaultFactorOf(id)?.id ?? '', hidden: false },
        ]),
      ),
    );
  const yearProblem = (text: string): number | Response => {
    const year = /^-?[0-9]+$/.test(text) ? Number(text) : null;
    if (year === null || year < 1990 || year > thisYear)
      return refusal(422, 'VALIDATION_ERROR', { year: ['지어낸 연도'] });
    return year;
  };
  /** 「쓰이는 표」를 선택에서 다시 셈한다(시험이 손으로 넣은 id 는 남긴다 — 선택이 잡았던 것만 뺀다). */
  const heldByChoice = { nodes: new Set<string>(), factors: new Set<string>() };
  const syncInUse = () => {
    for (const id of heldByChoice.nodes) poolInUse.nodes.delete(id);
    for (const id of heldByChoice.factors) poolInUse.factors.delete(id);
    heldByChoice.nodes.clear();
    heldByChoice.factors.clear();
    for (const rows of selections.values())
      for (const [leafId, row] of rows) {
        heldByChoice.nodes.add(leafId);
        if (row.factorId !== '') heldByChoice.factors.add(row.factorId);
      }
    for (const id of heldByChoice.nodes) poolInUse.nodes.add(id);
    for (const id of heldByChoice.factors) poolInUse.factors.add(id);
  };
  syncInUse();
  const treeOut = (year: number) => {
    const nodes = aliveNodes().sort(byPoolOrder);
    const rows = selections.get(year);
    const chosen = new Set(
      [...(rows ?? [])].filter(([, row]) => !row.hidden).map(([id]) => id),
    );
    const memo = new Map<string, [number, number, number]>();
    const tally = (node: (typeof nodes)[number]): [number, number, number] => {
      const known = memo.get(node.id);
      if (known) return known;
      let out: [number, number, number];
      if (node.level === 'facility') {
        const count = facilityCount(node.facilityCodeId);
        const can = defaultFactorOf(node.id) !== undefined; // S12-05: 시설 수는 보지 않는다
        out = [count, Number(can), Number(can && chosen.has(node.id))];
      } else {
        out = [0, 0, 0];
        for (const child of nodes.filter((n) => n.parentId === node.id)) {
          const [count, can, picked] = tally(child);
          out = [out[0] + count, out[1] + can, out[2] + picked];
        }
      }
      memo.set(node.id, out);
      return out;
    };
    return {
      year,
      nodes: nodes.map((node) => {
        const [count, can, picked] = tally(node);
        const line = {
          id: node.id,
          level: node.level,
          name: nodeName(node),
          parentId: node.parentId,
          availableCount: count,
        };
        return node.level === 'facility' ?
            {
              ...line,
              facilityCodeId: node.facilityCodeId!,
              selected: chosen.has(node.id),
              hasFactor: defaultFactorOf(node.id) !== undefined,
              hasData: rows !== undefined && selectionData.has(node.id),
            }
          : {
              ...line,
              facilityCodeId: null,
              selected: can > 0 && picked === can,
            };
      }),
    };
  };
  const selectionRoutes = (
    key: string,
    url: URL,
    body: unknown,
  ): Response | null => {
    if (key === 'GET /inventory/scope12/index-tree') {
      const year = yearProblem(url.searchParams.get('year') ?? '');
      if (year instanceof Response) return year;
      return json(200, treeOut(year));
    }
    const save = /^PUT \/inventory\/scope12\/index-selections\/([^/]+)$/.exec(
      key,
    );
    if (!save) return null;
    const year = yearProblem(save[1]!);
    if (year instanceof Response) return year;
    const raw = body as Record<string, unknown> | undefined;
    const ids = raw?.facilityNodeIds;
    if (
      !raw ||
      Object.keys(raw).some((k) => k !== 'facilityNodeIds') ||
      !Array.isArray(ids) ||
      !ids.every(isInt)
    )
      return refusal(422, 'VALIDATION_ERROR', {
        facilityNodeIds: ['지어낸 꼴'],
      });
    if (ids.length > 1000)
      return refusal(422, 'VALIDATION_ERROR', {
        facilityNodeIds: ['지어낸 1,000 넘음'],
      });
    const wanted = [...new Set(ids.map(String))];
    const current = selections.get(year) ?? new Map();
    const fresh = wanted.filter((id) => !current.has(id));
    const leaves = new Map(
      aliveNodes()
        .filter((n) => n.level === 'facility')
        .map((n) => [n.id, n]),
    );
    if (wanted.some((id) => !leaves.has(id)))
      return refusal(422, 'VALIDATION_ERROR', {
        facilityNodeIds: ['지어낸 잎 아님'],
      });
    if (fresh.some((id) => defaultFactorOf(id) === undefined))
      return refusal(422, 'VALIDATION_ERROR', {
        facilityNodeIds: ['지어낸 기본 계수 없음'],
      });
    const keep = new Set(wanted);
    let hiddenWithData = 0;
    for (const [id, row] of [...current]) {
      if (keep.has(id)) row.hidden = false;
      else if (!row.hidden && selectionData.has(id)) {
        row.hidden = true;
        hiddenWithData += 1;
      } else if (!row.hidden) current.delete(id);
    }
    for (const id of fresh)
      current.set(id, { factorId: defaultFactorOf(id)!.id, hidden: false });
    selections.set(year, current);
    syncInUse();
    return json(200, {
      selected: [...current.values()].filter((row) => !row.hidden).length,
      hiddenWithData,
    });
  };

  // ── 밴드 W12-1a ②: Scope 1·2 입력(S2·S3·S12) — /inventory/scope12/years · /rows · /years/{y}/decimals · X = /years/{y}/indexes/{node}/….
  //    서버 actions/entries.py 를 따른다(위 머리 주석의 「입력」 줄). 행·값·메모·잠금·자릿수·히스토리는 여기 상태에 산다.
  type EntryLine = {
    rowId: string;
    siteFacilityId: string;
    unit: string;
    na: boolean;
    values: Map<string, { amount: string | null; estimated: boolean }>;
    /** 계수 바꿈·복구가 정한 행 계수(응답 factor 꼴 그대로 — null = 선택의 계수). 없으면(undefined) 씨앗 entryRowFactor. W12-3 ②. */
    factor?: Record<string, unknown> | null;
  };
  type EntryIndexState = {
    memo: string;
    lockedAt: string | null;
    rows: Map<string, EntryLine>;
    history: Map<string, Record<string, unknown>[]>;
  };
  /** 해 → 잎 id → 입력 상태(행이 없으면 만들지 않는다). */
  const entryStates = new Map<number, Map<string, EntryIndexState>>();
  const entryDecimals = new Map<number, number>();
  let nextEntryRow = 1;
  let nextHistory = 1;
  const entryStateOf = (year: number, leafId: string) => {
    const byLeaf = entryStates.get(year) ?? new Map<string, EntryIndexState>();
    entryStates.set(year, byLeaf);
    const state = byLeaf.get(leafId) ?? {
      memo: '',
      lockedAt: null,
      rows: new Map<string, EntryLine>(),
      history: new Map<string, Record<string, unknown>[]>(),
    };
    byLeaf.set(leafId, state);
    return state;
  };
  const visibleLeaves = (year: number) =>
    [...(selections.get(year) ?? [])]
      .filter(([, row]) => !row.hidden)
      .map(([id]) => id);
  const leafPath = (leafId: string) => {
    const out: FakePoolNode[] = [];
    let node = aliveNodes().find((n) => n.id === leafId);
    while (node) {
      out.unshift(node);
      const parent: string | null = node.parentId;
      node =
        parent === null ? undefined : aliveNodes().find((n) => n.id === parent);
    }
    return out;
  };
  const shownYears = (year: number) => [year - 2, year - 1, year];
  /** (해·잎·사업장) → 바꾼 입력주기(서버 블록 주기 — 없으면 씨앗 entryPeriod, 그것도 없으면 month). */
  const entryPeriods = new Map<string, string>();
  const periodOf = (year: number, leafId: string, siteId: string) =>
    entryPeriods.get(`${year}:${leafId}:${siteId}`) ??
    entryPeriod[siteId] ??
    'month';
  /** 서버 slots(year, period) 흉내: 월 12 · 분기 4 · 연 1. */
  const slotsIn = (year: number, leafId: string, siteId: string) => {
    const period = periodOf(year, leafId, siteId);
    if (period === 'year') return [`${year}`];
    if (period === 'quarter')
      return [1, 2, 3, 4].map((quarter) => `${year}-Q${quarter}`);
    return Array.from(
      { length: 12 },
      (_, index) => `${year}-${`${index + 1}`.padStart(2, '0')}`,
    );
  };
  /** 서버 StrictIn 흉내: 모르는 본문 칸 → 그 열쇠(field_name 꼴). */
  const unknownFields = (raw: unknown, known: readonly string[], at: string) =>
    typeof raw !== 'object' || raw === null ?
      []
    : Object.keys(raw)
        .filter((key) => !known.includes(key))
        .map((key) => `${at}${key}`);
  const amountOk = (value: unknown) =>
    value === null ||
    (typeof value === 'string' && /^[0-9]{1,18}(\.[0-9]{1,6})?$/.test(value));
  /** 그 잎 코드의 자산/시설이 있는 켠 사업장(서버 상세의 사업장 블록). */
  const entrySites = (leafId: string) => {
    const code = aliveNodes().find((n) => n.id === leafId)?.facilityCodeId;
    return sorted()
      .filter((b) => b.inventoryEnabled)
      .map((b) => ({
        branch: b,
        lines: b.facilities.filter((line) => line.facilityCodeId === code),
      }))
      .filter((site) => site.lines.length > 0);
  };
  const leafUnit = (leafId: string) =>
    aliveNodes().find((n) => n.id === leafId)?.unit?.unit ?? 'kL';
  /** 지금 주기 칸의 값만(옛 주기 칸 값은 숨김 — 서버 set_period). */
  const shownValues = (line: EntryLine, allowed: readonly string[]) =>
    [...line.values]
      .filter(([slot]) => allowed.includes(slot))
      .sort(([a], [b]) => a.localeCompare(b));
  /** 행 계수(바꾼 것 → 씨앗 → null). */
  const rowFactorOf = (line: EntryLine) =>
    line.factor !== undefined ?
      line.factor
    : (entryRowFactor[line.siteFacilityId] ?? null);
  /** 셈 흉내 0 — 지금 칸에 값이 있는 N/A 아닌 행만 지어낸 고정 글자. 계수를 바꾼 행은 계수마다 다른 글자(critic B1 — 풀 2.<id> · 직접입력 3.<id>). */
  const emissionOf = (line: EntryLine, allowed: readonly string[]) => {
    if (
      line.na ||
      !shownValues(line, allowed).some(([, v]) => v.amount !== null)
    )
      return null;
    const factor = line.factor;
    if (!factor) return entryEmission;
    return 'customId' in factor ?
        `3.${factor.customId as string}`
      : `2.${factor.factorId as string}`;
  };
  const lineOut = (
    line: EntryLine,
    detailName: string,
    allowed: readonly string[],
  ) => ({
    rowId: line.rowId,
    siteFacilityId: line.siteFacilityId,
    detailName,
    unit: line.unit,
    na: line.na,
    values: shownValues(line, allowed).map(([slot, value]) => ({
      slot,
      ...value,
    })),
    emission: emissionOf(line, allowed),
    emissionProblem: null,
    factor: rowFactorOf(line),
  });
  /** 서버 sum_or_none: 셈한 값이 하나도 없으면 null. */
  const sumOrNone = (values: readonly (string | null)[]) =>
    values.reduce<string | null>(
      (total, value) =>
        value === null ? total
        : total === null ? value
        : addAmounts(total, value),
      null,
    );
  /** 그 해·잎·사업장 블록 행의 배출량 합(서버 _totals — 그 해의 주기 칸으로 센 행 emission). */
  const siteTotal = (year: number, leafId: string, siteId: string) => {
    const state = entryStates.get(year)?.get(leafId);
    const lines = entrySites(leafId).find((s) => s.branch.id === siteId)?.lines;
    if (!state || !lines) return null;
    const allowed = slotsIn(year, leafId, siteId);
    return sumOrNone(
      [...state.rows.values()]
        .filter((row) => lines.some((line) => line.id === row.siteFacilityId))
        .map((row) => emissionOf(row, allowed)),
    );
  };
  /** 풀 계수의 응답 꼴(EntryFactorOut — 지금 판). 상세 factor 와 행 factor 가 같이 쓴다. */
  const entryFactorOutOf = (factor: FakePoolFactor | undefined) => {
    const body = factor?.versions.at(-1) ?? fakeFactorBody('지어낸 계수');
    return {
      factorId: factor?.id ?? '0',
      versionId: `${factor?.id ?? '0'}0${factor?.versions.length ?? 1}`,
      version: factor?.versions.length ?? 1,
      name: body.name,
      source: body.source,
      isCustom: false,
      inputUnit: body.inputUnit,
      ncvEnabled: body.ncvEnabled,
      ncv: body.ncv,
      ncvUnit: body.ncvUnit,
      factorUnit: body.factorUnit,
      gases: body.gases.map((gas) => ({
        gas: gas.gas,
        enabled: gas.enabled,
        factor: gas.factor ?? null,
        gwp: gas.gwp ?? null,
      })),
    };
  };
  /** 직접입력 본문 → EntryCustomFactorOut 꼴(서버는 늘 새 행 — customId 새로). */
  let nextCustom = 1;
  const customOutOf = (custom: FactorBody) => ({
    customId: `${nextCustom++}`,
    name: custom.name,
    source: custom.source,
    baseYear: custom.baseYear ?? 0,
    tier: custom.tier ?? 0,
    countryCode: custom.countryCode,
    industryCode: custom.industryCode,
    inputUnit: custom.inputUnit,
    ncvEnabled: custom.ncvEnabled,
    ncv: custom.ncvEnabled ? custom.ncv : null,
    ncvUnit: custom.ncvEnabled ? custom.ncvUnit : null,
    factorUnit:
      custom.factorUnit ??
      (custom.ncvEnabled ? 'kg/TJ' : `kg/${custom.inputUnit.unit}`),
    gases: custom.gases.map((gas) => ({
      gas: gas.gas,
      enabled: gas.enabled,
      factor: gas.factor ?? null,
      gwp: gas.gwp ?? null,
    })),
    note: custom.note,
    isCustom: true,
  });
  /** 히스토리 참조(EntryFactorRefOut) — null 행 계수는 선택의 잡은 판(서버 _ref_or_pinned). */
  const refOf = (leafId: string, factor: Record<string, unknown> | null) => {
    const shown = factor ?? entryFactorOutOf(defaultFactorOf(leafId));
    return 'customId' in shown ?
        {
          versionId: null,
          customId: shown.customId,
          name: shown.name,
          isCustom: true,
        }
      : {
          versionId: shown.versionId,
          customId: null,
          name: shown.name,
          isCustom: false,
        };
  };
  /** 참조 열쇠 → 그때의 행 계수 꼴(복구가 그 줄의 afterFactor 로 행을 돌림 — 선택의 판이면 null). */
  const refKey = (ref: Record<string, unknown>) =>
    ref.customId ?
      `c:${ref.customId as string}`
    : `v:${ref.versionId as string}`;
  const factorByRef = new Map<string, Record<string, unknown>>();
  const indexOut = (year: number, leafId: string) => {
    const state = entryStateOf(year, leafId);
    const path = leafPath(leafId);
    const factor = defaultFactorOf(leafId);
    const years = shownYears(year);
    const sites = entrySites(leafId).map(({ branch, lines }) => ({
      siteId: branch.id,
      siteName: branch.name,
      period: periodOf(year, leafId, branch.id),
      slots: slotsIn(year, leafId, branch.id),
      facilities: lines.map((line) => ({
        id: line.id,
        detailName: line.detailName,
        hasRow: [...state.rows.values()].some(
          (row) => row.siteFacilityId === line.id,
        ),
      })),
      rows: [...state.rows.values()]
        .filter((row) => lines.some((line) => line.id === row.siteFacilityId))
        .map((row) =>
          lineOut(
            row,
            lines.find((line) => line.id === row.siteFacilityId)!.detailName,
            slotsIn(year, leafId, branch.id),
          ),
        ),
    }));
    return {
      year,
      nodeId: leafId,
      name: nodeName(path.at(-1)!),
      path: path.map(nodeName),
      decimals: entryDecimals.get(year) ?? 2,
      unit: 'tCO2-eq',
      unitOptions: [leafUnit(leafId), ...entryUnits],
      factor: entryFactorOutOf(factor),
      locked: state.lockedAt !== null,
      lockedAt: state.lockedAt,
      lockedBy:
        state.lockedAt === null ? null : { id: '1', name: '지어낸-사람' },
      memo: state.memo,
      sites,
      totals: (() => {
        const bySite = sites.map((site) => ({
          siteId: site.siteId,
          siteName: site.siteName,
          values: Object.fromEntries(
            years.map((y) => [`${y}`, siteTotal(y, leafId, site.siteId)]),
          ),
        }));
        return {
          years,
          all: Object.fromEntries(
            years.map((y) => [
              `${y}`,
              sumOrNone(bySite.map((site) => site.values[`${y}`] ?? null)),
            ]),
          ),
          bySite,
        };
      })(),
    };
  };
  const rowsOut = (year: number, q: string | null) => {
    const years = shownYears(year);
    const decimals = entryDecimals.get(year) ?? 2;
    const leaves = visibleLeaves(year);
    if (leaves.length === 0)
      return {
        year,
        years,
        decimals,
        unit: 'tCO2-eq',
        configured: false,
        scopes: [],
      };
    const needle = q === null || q === '' ? null : q.toLowerCase();
    const order = new Map(
      aliveNodes()
        .sort(byPoolOrder)
        .map((n, index) => [n.id, index]),
    );
    const groups = new Map<string, Record<string, unknown>[]>();
    for (const leafId of [...leaves].sort(
      (a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0),
    )) {
      const path = leafPath(leafId);
      if (path.length === 0) continue;
      if (
        needle !== null &&
        !path.some((n) => nodeName(n).toLowerCase().includes(needle))
      )
        continue;
      const state = entryStates.get(year)?.get(leafId);
      const seeded = entryValues[leafId] ?? {};
      const line = {
        nodeId: leafId,
        path: path.map(nodeName),
        values: Object.fromEntries(
          years.map((y) => [`${y}`, seeded[`${y}`] ?? null]),
        ),
        hasMemo: (state?.memo ?? '') !== '',
        estimated: [...(state?.rows.values() ?? [])].some((row) =>
          [...row.values.values()].some((v) => v.estimated),
        ),
        locked: (state?.lockedAt ?? null) !== null,
      };
      const list = groups.get(path[0]!.id) ?? [];
      list.push(line);
      groups.set(path[0]!.id, list);
    }
    return {
      year,
      years,
      decimals,
      unit: 'tCO2-eq',
      configured: true,
      scopes: [...groups].map(([scopeId, rows]) => {
        const seeded = scopeValues[scopeId] ?? {};
        return {
          scopeId,
          scopeName: nodeName(aliveNodes().find((n) => n.id === scopeId)!),
          values: Object.fromEntries(
            years.map((y) => [`${y}`, seeded[`${y}`] ?? null]),
          ),
          rows,
        };
      }),
    };
  };
  const bad = (fields: Record<string, string>) =>
    refusal(
      422,
      'VALIDATION_ERROR',
      Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, [v]])),
    );
  const notFound = () => refusal(404, 'NOT_FOUND');
  const record = (
    state: EntryIndexState,
    rowId: string,
    entry: Record<string, unknown>,
  ) => {
    const list = state.history.get(rowId) ?? [];
    list.unshift({
      historyId: `${nextHistory++}`,
      at: '2026-01-02T03:04:05Z',
      actor: {
        kind: admin ? 'admin' : 'service',
        id: '1',
        name: '지어낸-사람',
      },
      slot: null,
      before: null,
      after: null,
      reason: null,
      beforeFactor: null,
      afterFactor: null,
      ...entry,
    });
    state.history.set(rowId, list);
  };
  /** 행 저장(서버 save_rows): 하나라도 걸리면 0 씀. 실린 칸의 빠진 열쇠는 기본값(amount null·estimated 거짓)으로, 행의 빠진 na 는 거짓으로 덮는다(서버 schemas 기본). */
  const saveEntryRows = (
    year: number,
    leafId: string,
    siteId: string,
    body: unknown,
  ): Response => {
    const site = entrySites(leafId).find((s) => s.branch.id === siteId);
    if (!site) return notFound();
    const state = entryStateOf(year, leafId);
    if (state.lockedAt !== null) return refusal(409, 'LOCKED');
    if (entryReject.length > 0)
      return bad(
        Object.fromEntries(entryReject.map((k) => [k, '지어낸 심음'])),
      );
    const rows = (body as { rows?: unknown } | undefined)?.rows;
    if (!Array.isArray(rows) || rows.length > 200)
      return bad({ rows: '지어낸 꼴' });
    const lineIds = new Set(site.lines.map((line) => line.id));
    const units = [leafUnit(leafId), ...entryUnits];
    const allowed = new Set(slotsIn(year, leafId, siteId));
    const problems: Record<string, string> = {};
    for (const key of unknownFields(body, ['rows'], ''))
      problems[key] = '지어낸 모르는 칸';
    const seenLines = new Set<unknown>();
    rows.forEach((raw: Record<string, unknown>, i) => {
      for (const key of unknownFields(
        raw,
        ['rowId', 'siteFacilityId', 'unit', 'na', 'values'],
        `rows.${i}.`,
      ))
        problems[key] = '지어낸 모르는 칸';
      if (seenLines.has(raw.siteFacilityId))
        problems[`rows.${i}.siteFacilityId`] = '지어낸 겹침';
      seenLines.add(raw.siteFacilityId);
      if (!isInt(raw.siteFacilityId) || !lineIds.has(`${raw.siteFacilityId}`))
        problems[`rows.${i}.siteFacilityId`] = '지어낸 자산/시설';
      if (raw.rowId !== undefined && raw.rowId !== null) {
        if (!isInt(raw.rowId) || !state.rows.has(`${raw.rowId}`))
          problems[`rows.${i}.rowId`] = '지어낸 행';
      } else if (
        [...state.rows.values()].some(
          (row) => row.siteFacilityId === `${raw.siteFacilityId}`,
        )
      )
        problems[`rows.${i}.siteFacilityId`] = '지어낸 이미 행 있음';
      if (typeof raw.unit !== 'string' || !units.includes(raw.unit))
        problems[`rows.${i}.unit`] = '지어낸 단위';
      if ('na' in raw && typeof raw.na !== 'boolean')
        problems[`rows.${i}.na`] = '지어낸 N/A';
      const values = raw.values;
      if (!Array.isArray(values)) problems[`rows.${i}.values`] = '지어낸 칸';
      else {
        const seenSlots = new Set<unknown>();
        values.forEach((slot: Record<string, unknown>, j) => {
          for (const key of unknownFields(
            slot,
            ['slot', 'amount', 'estimated'],
            `rows.${i}.values.${j}.`,
          ))
            problems[key] = '지어낸 모르는 칸';
          if (
            typeof slot.slot !== 'string' ||
            !allowed.has(slot.slot) ||
            seenSlots.has(slot.slot)
          )
            problems[`rows.${i}.values.${j}.slot`] = '지어낸 칸';
          seenSlots.add(slot.slot);
          if ('amount' in slot && !amountOk(slot.amount))
            problems[`rows.${i}.values.${j}.amount`] = '지어낸 금액';
          if ('estimated' in slot && typeof slot.estimated !== 'boolean')
            problems[`rows.${i}.values.${j}.estimated`] = '지어낸 추정';
        });
      }
    });
    if (Object.keys(problems).length > 0) return bad(problems);
    for (const raw of rows as Record<string, unknown>[]) {
      let line: EntryLine;
      if (raw.rowId === undefined || raw.rowId === null) {
        line = {
          rowId: `${nextEntryRow++}`,
          siteFacilityId: `${raw.siteFacilityId}`,
          unit: raw.unit as string,
          na: false,
          values: new Map(),
        };
        state.rows.set(line.rowId, line);
      } else line = state.rows.get(`${raw.rowId}`)!;
      if (line.unit !== raw.unit)
        record(state, line.rowId, {
          kind: 'unit',
          unit: raw.unit,
          before: line.unit,
          after: raw.unit,
        });
      line.unit = raw.unit as string;
      const na = (raw.na as boolean | undefined) ?? false;
      if (line.na !== na)
        record(state, line.rowId, {
          kind: na ? 'na_on' : 'na_off',
          unit: line.unit,
        });
      line.na = na;
      for (const slot of raw.values as Record<string, unknown>[]) {
        const was = line.values.get(slot.slot as string);
        const amount = (slot.amount as string | null | undefined) ?? null;
        const flag = (slot.estimated as boolean | undefined) ?? false;
        // 없는 칸을 빈 칸으로 — 바뀜 0(서버 _changes).
        if (was === undefined && amount === null && !flag) continue;
        if ((was?.amount ?? null) !== amount)
          record(state, line.rowId, {
            kind: entryHistoryKind,
            slot: slot.slot,
            unit: line.unit,
            before: was?.amount ?? null,
            after: amount,
          });
        line.values.set(slot.slot as string, {
          amount,
          estimated: (slot.estimated as boolean | undefined) ?? false,
        });
      }
    }
    if (state.rows.size > 0) selectionData.add(leafId);
    return json(200, indexOut(year, leafId));
  };
  /** 그 해 고른 잎 가운데 scope 번째 뿌리 아래의 것(scope 없으면 전부). 뿌리가 없으면 null — 서버 _groups 처럼 풀 트리 n번째다. */
  const leavesOfScope = (year: number, scope: number | null) => {
    const leaves = visibleLeaves(year);
    if (scope === null) return leaves;
    const root = aliveNodes()
      .filter((node) => node.parentId === null)
      .sort(byPoolOrder)[scope - 1];
    if (!root) return null;
    return leaves.filter((leaf) => leafPath(leaf)[0]?.id === root.id);
  };
  /** 양식·데이터 엑셀(서버 actions/scope12_excel.py 차례): scope 422 → 켠 사업장 아닌 siteId 404 → 해 없음·선택 0 404 → 양식은 채울 줄 0 404. */
  const excelFile = (
    yearText: string,
    what: 'template' | 'export',
    url: URL,
  ): Response => {
    const scope = url.searchParams.get('scope');
    const allowed = what === 'template' ? ['1', '2'] : ['all', '1', '2'];
    if (scope !== null && !allowed.includes(scope))
      return bad({ scope: '지어낸 scope' });
    const siteText = url.searchParams.get('siteId');
    const siteId = siteText === null ? null : pathId(siteText);
    if (what === 'template' && siteText !== null) {
      if (siteId === null) return bad({ siteId: '지어낸 정수 아님' });
      if (!stored.some((b) => b.id === `${siteId}` && b.inventoryEnabled))
        return notFound();
    }
    const year = pathId(yearText);
    if (year === null || visibleLeaves(year).length === 0) return notFound();
    const picked = scope === null || scope === 'all' ? null : Number(scope);
    const leaves = leavesOfScope(year, picked);
    if (leaves === null) return notFound();
    if (what === 'template') {
      const lines = leaves.flatMap((leaf) =>
        entrySites(leaf).filter(
          ({ branch }) => siteId === null || branch.id === `${siteId}`,
        ),
      );
      if (lines.length === 0) return notFound();
    }
    const name = what === 'template' ? FAKE_TEMPLATE_NAME : FAKE_EXPORT_NAME;
    return new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), {
      status: 200,
      headers: {
        'Content-Type': ENTRY_XLSX_TYPE,
        'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(name)}`,
        'X-Content-Type-Options': 'nosniff',
      },
    });
  };
  /** 올리기(서버 판정 차례): 회사 거절 400 → 413 → 해 없음·선택 0 404 → 빈 바이트 422 file → 심는 답. */
  const uploadFile = (yearText: string, bytes: Uint8Array): Response => {
    if (company) return refusal(400, company);
    if (bytes.length > FAKE_UPLOAD_MAX) return refusal(413, 'BODY_TOO_LARGE');
    const year = pathId(yearText);
    if (year === null || visibleLeaves(year).length === 0) return notFound();
    if (bytes.length === 0)
      return refusal(422, 'INVALID_UPLOAD', { file: ['지어낸 빈 파일'] });
    const next = uploadAnswers.shift();
    return next ? next() : (
        json(200, { added: 0, filled: 0, unchanged: 0, unresolved: 0 })
      );
  };

  const entryRoutes = (
    key: string,
    url: URL,
    body: unknown,
  ): Response | null => {
    if (key === 'GET /inventory/scope12/dashboard') {
      const year = Number(url.searchParams.get('year'));
      if (!Number.isInteger(year) || url.searchParams.get('year') === '')
        return refusal(422, 'VALIDATION_ERROR', { year: ['정수가 아니에요'] });
      if (dashboardFailures.includes(year)) return unreachable();
      const refused = dashboardRefusals[year];
      if (refused) return refusal(400, refused);
      return json(200, dashboards[year] ?? dashboardOut(year));
    }
    if (key === 'GET /inventory/scope12/years')
      return json(200, {
        years: [...selections.keys()]
          .sort((a, b) => b - a)
          .map((year) => ({
            year,
            configured: visibleLeaves(year).length > 0,
          })),
      });
    if (key === 'GET /inventory/scope12/rows') {
      const year = yearProblem(url.searchParams.get('year') ?? '');
      if (year instanceof Response) return year;
      const q = url.searchParams.get('q');
      if (q !== null && q.length > 100) return bad({ q: '지어낸 100자 넘음' });
      return json(200, rowsOut(year, q));
    }
    const decimals =
      /^PUT \/inventory\/scope12\/years\/([^/]+)\/decimals$/.exec(key);
    if (decimals) {
      const year = pathId(decimals[1]!);
      if (year === null || !selections.has(year)) return notFound();
      const n = (body as { decimals?: unknown } | undefined)?.decimals;
      const stray = unknownFields(body, ['decimals'], '');
      if (stray.length > 0) return bad({ [stray[0]!]: '지어낸 모르는 칸' });
      if (typeof n !== 'number' || !Number.isInteger(n) || n < 0 || n > 3)
        return bad({ decimals: '지어낸 자릿수' });
      entryDecimals.set(year, n);
      return json(200, { decimals: n });
    }
    const excel =
      /^GET \/inventory\/scope12\/years\/([^/]+)\/(template|export)$/.exec(key);
    if (excel)
      return excelFile(excel[1]!, excel[2] as 'template' | 'export', url);
    const index =
      /^(GET|PUT|POST|DELETE) \/inventory\/scope12\/years\/([^/]+)\/indexes\/([^/]+)(\/.*)?$/.exec(
        key,
      );
    if (!index) return null;
    const [, method, yearText, leafText, rest = ''] = index;
    const year = pathId(yearText!);
    const leafId = `${pathId(leafText!) ?? ''}`;
    if (year === null || !visibleLeaves(year).includes(leafId))
      return notFound();
    const state = entryStateOf(year, leafId);
    if (method === 'GET' && rest === '')
      return json(200, indexOut(year, leafId));
    const site = /^\/sites\/([^/]+)\/rows$/.exec(rest);
    if (method === 'PUT' && site) {
      const siteId = pathId(site[1]!);
      return siteId === null ? notFound() : (
          saveEntryRows(year, leafId, `${siteId}`, body)
        );
    }
    if (method === 'POST' && rest === '/rows/delete') {
      const ids = (body as { ids?: unknown } | undefined)?.ids;
      const stray = unknownFields(body, ['ids'], '');
      if (stray.length > 0) return bad({ [stray[0]!]: '지어낸 모르는 칸' });
      if (!isIntList(ids) || ids.length > 100) return bad({ ids: '지어낸 꼴' });
      if (state.lockedAt !== null) return refusal(409, 'LOCKED');
      if (ids.some((id) => !state.rows.has(`${id}`))) return notFound();
      for (const id of ids) state.rows.delete(`${id}`);
      return json(200, { count: ids.length });
    }
    if (method === 'PUT' && rest === '/memo') {
      const memo = (body as { memo?: unknown } | undefined)?.memo;
      const stray = unknownFields(body, ['memo'], '');
      if (stray.length > 0) return bad({ [stray[0]!]: '지어낸 모르는 칸' });
      if (typeof memo !== 'string' || memo.length > 2000)
        return bad({ memo: '지어낸 메모' });
      if (state.lockedAt !== null) return refusal(409, 'LOCKED');
      state.memo = memo;
      return json(200, { memo });
    }
    if (method === 'POST' && rest === '/lock') {
      state.lockedAt ??= '2026-01-02T03:04:05Z';
      return json(200, indexOut(year, leafId));
    }
    if (method === 'DELETE' && rest === '/lock') {
      if (!admin) return refusal(403, 'FORBIDDEN');
      state.lockedAt = null;
      return json(200, indexOut(year, leafId));
    }
    const history = /^\/rows\/([^/]+)\/history$/.exec(rest);
    if (method === 'GET' && history) {
      const rowId = `${pathId(history[1]!) ?? ''}`;
      if (!state.rows.has(rowId)) return notFound();
      const page = pathId(url.searchParams.get('page') ?? '1') ?? 0;
      const size = pathId(url.searchParams.get('pageSize') ?? '20') ?? 0;
      if (page < 1 || size < 1 || size > 100)
        return bad({ pageSize: '지어낸 쪽' });
      const all = (state.history.get(rowId) ?? []).map((line) => ({
        ...line,
        restorable: restoreProblem(year, leafId, rowId, line) === null,
      }));
      const totalPages = Math.max(1, Math.ceil(all.length / size));
      return json(200, {
        count: all.length,
        totalPages,
        page,
        pageSize: size,
        hasNext: page < totalPages,
        hasPrevious: page > 1,
        results: all.slice((page - 1) * size, page * size),
      });
    }
    const period = /^\/sites\/([^/]+)\/period$/.exec(rest);
    if (method === 'PUT' && period) {
      const siteId = `${pathId(period[1]!) ?? ''}`;
      const value = (body as { period?: unknown } | undefined)?.period;
      const stray = unknownFields(body, ['period'], '');
      if (stray.length > 0) return bad({ [stray[0]!]: '지어낸 모르는 칸' });
      if (typeof value !== 'string' || !ENTRY_PERIODS.some((p) => p === value))
        return bad({ period: '지어낸 주기' });
      if (!entrySites(leafId).some((s) => s.branch.id === siteId))
        return notFound();
      if (state.lockedAt !== null) return refusal(409, 'LOCKED');
      changePeriod(year, leafId, siteId, value, null);
      return json(200, indexOut(year, leafId));
    }
    const restore = /^\/rows\/([^/]+)\/history\/([^/]+)\/restore$/.exec(rest);
    if (method === 'POST' && restore) {
      if (typeof body !== 'object' || body === null)
        return bad({ body: '지어낸 본문 없음' });
      const stray = unknownFields(body, ['reason'], '');
      if (stray.length > 0) return bad({ [stray[0]!]: '지어낸 모르는 칸' });
      const rowId = `${pathId(restore[1]!) ?? ''}`;
      const row = state.rows.get(rowId);
      const line = (state.history.get(rowId) ?? []).find(
        (l) => l.historyId === `${pathId(restore[2]!) ?? ''}`,
      );
      if (!row || !line) return notFound();
      const problem = restoreProblem(year, leafId, rowId, line);
      if (problem === 'kind') return bad({ historyId: '지어낸 종류' });
      if (line.kind === 'factor' && !admin) return refusal(403, 'FORBIDDEN');
      const raw = (body as { reason?: unknown }).reason;
      const reason = typeof raw === 'string' ? raw.trim() || null : null;
      if (line.kind === 'factor' && reason === null)
        return bad({ reason: '지어낸 사유 필수' });
      if (reason !== null && reason.length > FAKE_REASON_MAX)
        return bad({ reason: '지어낸 사유 500자 넘음' }); // R4 — 서버 _reason_problem
      if (problem === 'top') return bad({ historyId: '지어낸 맨 위' });
      if (problem === 'locked') return refusal(409, 'LOCKED');
      if (problem === 'stale') return refusal(409, 'RESTORE_STALE');
      if (line.kind === 'value') {
        const slot = line.slot as string;
        const was = row.values.get(slot);
        const amount = (line.after as string | null) ?? null;
        if ((was?.amount ?? null) !== amount) {
          row.values.set(slot, { amount, estimated: was?.estimated ?? false });
          record(state, rowId, {
            kind: 'value',
            slot,
            unit: row.unit,
            before: was?.amount ?? null,
            after: amount,
            reason,
          });
        }
      } else if (line.kind === 'period') {
        const siteId = entrySites(leafId).find(({ lines }) =>
          lines.some((l) => l.id === row.siteFacilityId),
        )!.branch.id;
        const after = line.after as string | null;
        if (after !== null && after !== periodOf(year, leafId, siteId))
          changePeriod(year, leafId, siteId, after, reason);
      } else {
        const after = line.afterFactor as Record<string, unknown> | null;
        const pinned = refOf(leafId, null);
        const target =
          after === null || refKey(after) === refKey(pinned) ?
            null
          : (factorByRef.get(refKey(after)) ??
            factorsOfLeaf(leafId)
              .map((f) => entryFactorOutOf(f))
              .find((out) => out.versionId === after.versionId) ??
            null);
        changeRowFactor(leafId, state, row, target, reason);
      }
      return json(200, indexOut(year, leafId));
    }
    const rowFactor = /^\/rows\/([^/]+)\/factor$/.exec(rest);
    if (method === 'PUT' && rowFactor) {
      // 서버 차례(W12-3 ② · critic R1 실측): 스키마 422 → 403 → 본문 422 → 404 → 422 단위(548) → 409 → 다른 잎 422 → 같은 계수 0 바뀜.
      if (typeof body !== 'object' || body === null)
        return bad({ body: '지어낸 본문 없음' });
      const raw = body as Record<string, unknown>;
      const stray = unknownFields(raw, ['factorId', 'custom', 'reason'], '');
      if (raw.custom !== undefined && raw.custom !== null)
        stray.push(...unknownFields(raw.custom, FACTOR_IN_FIELDS, 'custom.'));
      if (stray.length > 0) return bad({ [stray[0]!]: '지어낸 모르는 칸' });
      const factorId = raw.factorId ?? null;
      if (
        factorId !== null &&
        (typeof factorId !== 'number' ||
          !Number.isInteger(factorId) ||
          factorId < 1)
      )
        return bad({ factorId: '지어낸 정수 아님' });
      if (!admin) return refusal(403, 'FORBIDDEN');
      const reason =
        typeof raw.reason === 'string' ? raw.reason.trim() || null : null;
      const custom = (raw.custom ?? null) as FactorBody | null;
      const problems: Record<string, string> = {};
      if (reason === null) problems.reason = '지어낸 사유 필수';
      else if (reason.length > FAKE_REASON_MAX)
        problems.reason = '지어낸 사유 500자 넘음';
      if ((factorId === null) === (custom === null))
        problems.factorId = '지어낸 하나만';
      else if (custom !== null) {
        if (!custom.name?.trim()) problems['custom.name'] = '지어낸 이름 없음';
        if (custom.emissionUnit && custom.emissionUnit.unit !== 'tCO2-eq')
          problems['custom.emissionUnit'] = '지어낸 배출량 단위';
      }
      if (Object.keys(problems).length > 0) return bad(problems);
      const rowId = `${pathId(rowFactor[1]!) ?? ''}`;
      const row = state.rows.get(rowId);
      if (!row) return notFound();
      if (custom !== null) {
        const mismatch = fakeCustomUnitProblem(
          [leafUnit(leafId), ...entryUnits],
          custom,
        );
        if (Object.keys(mismatch).length > 0) return bad(mismatch); // 548 흉내
      }
      if (state.lockedAt !== null) return refusal(409, 'LOCKED');
      let target: Record<string, unknown> | null;
      if (factorId !== null) {
        const found = factorsOfLeaf(leafId).find((f) => f.id === `${factorId}`);
        if (!found) return bad({ factorId: '지어낸 다른 잎' });
        target = found.isDefault ? null : entryFactorOutOf(found);
      } else target = customOutOf(custom!);
      changeRowFactor(leafId, state, row, target, reason);
      return json(200, indexOut(year, leafId));
    }
    return null;
  };
  /** 서버 _change_factor: 같은 계수면 0 바뀜 · 아니면 factor 줄(before = 그 행 지금 계수 — R3) 하나 + 행 계수 바꿈. */
  const changeRowFactor = (
    leafId: string,
    state: EntryIndexState,
    row: EntryLine,
    target: Record<string, unknown> | null,
    reason: string | null,
  ) => {
    const before = refOf(leafId, rowFactorOf(row));
    const after = refOf(leafId, target);
    if (refKey(before) === refKey(after)) return;
    if (target !== null) factorByRef.set(refKey(after), target);
    record(state, row.rowId, {
      kind: 'factor',
      unit: row.unit,
      reason,
      beforeFactor: before,
      afterFactor: after,
    });
    row.factor = target;
  };
  /** 서버 set_period 의 바꿈: 블록 주기를 바꾸고(옛 칸 값 그대로 — 숨김) 블록의 행마다 period 줄. */
  const changePeriod = (
    year: number,
    leafId: string,
    siteId: string,
    period: string,
    reason: string | null,
  ) => {
    const old = periodOf(year, leafId, siteId);
    if (old === period) return;
    entryPeriods.set(`${year}:${leafId}:${siteId}`, period);
    const state = entryStateOf(year, leafId);
    const lines = entrySites(leafId).find((s) => s.branch.id === siteId)!.lines;
    for (const row of state.rows.values())
      if (lines.some((line) => line.id === row.siteFacilityId))
        record(state, row.rowId, {
          kind: 'period',
          unit: row.unit,
          before: old,
          after: period,
          reason,
        });
  };
  /** 서버 restore_problem — 종류 → 맨 위 → 잠금 → 낡음(value 칸이 지금 주기 밖이거나 단위 다름). null 이면 복구 가능. */
  const restoreProblem = (
    year: number,
    leafId: string,
    rowId: string,
    line: Record<string, unknown>,
  ): 'kind' | 'top' | 'locked' | 'stale' | null => {
    const state = entryStateOf(year, leafId);
    const row = state.rows.get(rowId);
    if (!['value', 'period', 'factor'].includes(line.kind as string))
      return 'kind';
    if (state.history.get(rowId)?.[0]?.historyId === line.historyId)
      return 'top';
    if (state.lockedAt !== null) return 'locked';
    if (line.kind === 'value' && row) {
      const siteId = entrySites(leafId).find(({ lines }) =>
        lines.some((l) => l.id === row.siteFacilityId),
      )?.branch.id;
      const allowed = siteId === undefined ? [] : slotsIn(year, leafId, siteId);
      if (!allowed.includes(line.slot as string) || line.unit !== row.unit)
        return 'stale';
    }
    return null;
  };

  const answer = (key: string, url: URL, body: unknown): Response => {
    const path = key.slice(key.indexOf(' ') + 1);
    if (path.startsWith('/inventory/admin/')) {
      if (!admin) return refusal(403, 'FORBIDDEN');
      const out = poolRoutes(key, url, body);
      if (out) return out;
    } else if (path.startsWith('/admin/')) {
      if (!admin) return refusal(403, 'FORBIDDEN');
      const out = adminRoutes(key, url, body);
      if (out) return out;
    } else {
      if (company) return refusal(400, company);
      const out =
        selectionRoutes(key, url, body) ??
        entryRoutes(key, url, body) ??
        branchRoutes(key, url, body);
      if (out) return out;
    }
    throw new Error(`가짜에 없는 경로: ${key}`);
  };

  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);

  /** 이 가짜가 받는 경로인가(세션 가짜와 이어 붙일 때). */
  const handles = (request: Request) =>
    /^\/(branches|facility-codes|admin\/facility-codes|inventory\/admin\/ghg-(index|factors|options)|inventory\/scope12\/(index-tree|index-selections|years|rows|dashboard))(\/|$)/.test(
      pathOf(request),
    );

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(request);
    const key = `${request.method} ${path}`;
    // 올리기만 맨 바이트다 — JSON 으로 읽지 않고 앞에서 가른다(W12-5 ①).
    const upload = /^POST \/inventory\/scope12\/years\/([^/]+)\/uploads$/.exec(
      key,
    );
    if (upload) {
      const bytes = new Uint8Array(await request.clone().arrayBuffer());
      calls.push({
        method: request.method,
        path,
        query: url.searchParams,
        body: undefined,
        bytes,
        contentType: request.headers.get('Content-Type'),
      });
      return uploadFile(upload[1]!, bytes);
    }
    const text = await request.clone().text();
    const body: unknown = text === '' ? undefined : JSON.parse(text);
    calls.push({ method: request.method, path, query: url.searchParams, body });
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(key, url, body);
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  /** 그 경로로 나간 본문들(차례대로). */
  const bodies = (key: string) =>
    calls
      .filter((call) => `${call.method} ${call.path}` === key)
      .map((call) => call.body);

  return {
    send,
    handles,
    calls,
    count,
    bodies,
    override,
    /** 올리기 심는 답(시험 중에 더 넣는다). */
    uploadAnswers,
    /** 지금 사업장(본사 먼저, 만든 차례). */
    branches: () => sorted().map((b) => structuredClone(b)),
    /** 「다른 탭이 저장」(밴드 K1b-3): 그 사업장의 판을 올리고, line 을 주면 줄 하나를 더한다(코드는 살아 있는 것 — 검사 없음). */
    bumpBranch: (
      id: string,
      line?: { facilityCodeId: string; detailName: string },
    ) => {
      const branch = stored.find((b) => b.id === id);
      if (!branch) throw new Error(`가짜에 없는 사업장: ${id}`);
      if (line) {
        const code = storedCodes.find((c) => c.id === line.facilityCodeId);
        if (!code) throw new Error(`가짜에 없는 코드: ${line.facilityCodeId}`);
        branch.facilities.push({
          id: String(nextLine++),
          facilityCodeId: code.id,
          facilityCode: code.code,
          facilityName: code.name,
          detailName: line.detailName,
        });
      }
      bump(branch);
    },
    /** 「쓰이는 표」(풀 — 밴드 W12-0b1 ②): 시험이 고객사 선택이 잡은 잎·계수 id 를 넣는다. */
    poolInUse,
    /** 데이터가 있는 잎(밴드 W12-0b2 — 시험이 심는다). 그 해 행이 있을 때 hasData 참, 빼며 저장하면 숨김. */
    selectionData,
    /** 그 해의 숨기지 않은 선택 잎 id(id 차례 — 해가 없으면 null). */
    chosenIn: (year: number) => {
      const rows = selections.get(year);
      if (!rows) return null;
      return [...rows]
        .filter(([, row]) => !row.hidden)
        .map(([id]) => id)
        .sort((a, b) => Number(a) - Number(b));
    },
    /** 지금 살아 있는 풀 노드(단 → sortOrder → id). */
    poolNodes: () => aliveNodes().sort(byPoolOrder).map(nodeOut),
    /** 지금 살아 있는 코드(만든 차례 — 지운 것 빼고). */
    codes: () => aliveCodes().map(plainCode),
  };
}

/** 가짜 서버 앞에 둔 실어댑터 둘(시험이 진짜 createApi 로 잇는다 — 중대성평가 serverStoreOf 꼴). */
export function portsOf(
  server: ReturnType<typeof fakeGhgServer>,
  baseUrl = 'http://test.local/api',
) {
  const api = createApi({ baseUrl, fetch: server.send });
  return {
    port: createGhgOrganizationPort({ api }),
    admin: createFacilityCodeAdminPort({ api }),
    pool: createGhgPoolAdminPort({ api }),
    selection: createGhgSelectionPort({ api }),
    entry: createGhgEntryPort({ api }),
    dashboard: createGhgDashboardPort({ api }),
  };
}

/** 입력 씨앗(밴드 W12-1a): 선택 씨앗 위에 제1공장 「1호기」(코드 1 — 잎 20 지어낸 보일러) 줄을 더하고 2025 에 잎 20 을 고름 ·
 *  2024 는 빈 선택(configured 거짓) · 리스트 값 씨앗(지어낸 글자). */
export function fakeEntryOptions(): FakeGhgServerOptions {
  const base = fakeSelectionOptions();
  const [head, plant] = base.branches!;
  return {
    ...base,
    branches: [
      head!,
      {
        ...plant!,
        facilities: [
          ...plant!.facilities,
          {
            id: '4',
            facilityCodeId: '1',
            facilityCode: 'F0001',
            facilityName: '지어낸 보일러',
            detailName: '1호기',
          },
        ],
      },
    ],
    chosen: { 2025: ['20'], 2024: [] },
    entryValues: { '20': { '2024': '7.25', '2025': '12.125' } },
    scopeValues: { '1': { '2024': '7.25', '2025': '12.125' } },
  };
}

/** 거울 ⊆ 판정: 거울(꼴 → 칸 이름)에 있는데 openapi 꼴에 없는 「꼴.칸」(꼴이 없으면 「꼴」). openapi 가 칸을 더해도 빈 목록. */
export function mirrorGaps(
  mirrored: Readonly<Record<string, readonly string[]>>,
  schemas: Readonly<Record<string, { properties: Record<string, unknown> }>>,
): string[] {
  const gaps: string[] = [];
  for (const [name, fields] of Object.entries(mirrored)) {
    const schema = schemas[name];
    if (!schema) {
      gaps.push(name);
      continue;
    }
    for (const field of fields)
      if (!(field in schema.properties)) gaps.push(`${name}.${field}`);
  }
  return gaps;
}

/** 대시보드 값 있는 판 씨앗(밴드 DB1 — openapi Scope12DashboardOut 꼴, 값은 지어낸 글자). 뿌리 둘·사업장 둘·Scope 3 카테고리 둘. */
export function fakeDashboard(
  year: number,
  total: Partial<Schemas['Scope12DashboardTotalOut']> = {},
): Schemas['Scope12DashboardOut'] {
  return dashboardOut(year, {
    configured: true,
    scopes: [
      {
        scopeId: '1',
        scopeName: '지어낸 범위 가',
        scopeOrder: 1,
        value: '60',
        topSources: [
          { nodeId: '11', name: '지어낸 고정연소', value: '45', share: '75.0' },
          { nodeId: '12', name: '지어낸 이동연소', value: '15', share: '25.0' },
        ],
      },
      {
        scopeId: '2',
        scopeName: '지어낸 범위 나',
        scopeOrder: 2,
        value: '30',
        topSources: [
          {
            nodeId: '21',
            name: '지어낸 전기 사용',
            value: '29.8',
            share: '99.3',
          },
          { nodeId: '22', name: '지어낸 열 사용', value: '0.2', share: '0.4' },
        ],
      },
    ],
    total: {
      scope12: '90',
      scope2Market: null,
      scope3: '10',
      sum: '100',
      scope3FailedSheets: 0,
      ...total,
    },
    bySite: [
      {
        siteId: '1',
        siteName: '본사',
        scopes: [
          { scopeId: '1', value: '10' },
          { scopeId: '2', value: '10' },
        ],
        scope3: null,
      },
      {
        siteId: '2',
        siteName: '제1공장',
        scopes: [
          { scopeId: '1', value: '50' },
          { scopeId: '2', value: '20' },
        ],
        scope3: null,
      },
    ],
    scope3Categories: [
      {
        category: 'C4',
        name: '업스트림 운송 및 유통',
        value: '6',
        share: '60.0',
      },
      {
        category: 'C1',
        name: '구매 상품 및 서비스',
        value: '4',
        share: '40.0',
      },
    ],
  });
}

/** 둘째 뿌리(Scope 2) 잎만 고른 회사의 판(DB1 검증 B1 — scopes 하나, scopeOrder 2). */
export function fakeScope2OnlyDashboard(
  year: number,
): Schemas['Scope12DashboardOut'] {
  const full = fakeDashboard(year, { scope12: '30', scope3: null, sum: '30' });
  const second = full.scopes[1]!;
  return {
    ...full,
    scopes: [second],
    bySite: full.bySite.map((site) => ({
      ...site,
      scopes: site.scopes.filter((part) => part.scopeId === second.scopeId),
    })),
    scope3Categories: [],
  };
}
