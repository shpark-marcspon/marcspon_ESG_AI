// Scope 3 카테고리 상세(S3-09 표 · S3-10 생물기원)의 셈(밴드 S3W2b ① — 발주서 §1-5 표·Q1·Q3·Q6·Q7·Q10). 순수 함수 — React·Intl·표기 0.
// 표 꼴(시트 21)은 시트 이름 앞머리(c4-1_… — 대소문자 무시, 엔진 template.py 의 match_sheet_processor 와 같은 앞머리)로 고르고,
//   못 고르면 줄 kind 로, 그것도 모르면 공통 열(행·계수·배출량·비율)만(감독 C0 처분).
// 결과 꼴에 없는 열은 그리지 않는다(sid:MARC-ENT-538). 표의 출처 칸은 구매 줄뿐이고 서버 코드라 갈래 값(sourceKind)으로만 낸다. 글·뱃지는 pages 쪽이 그린다(밴드 S3WS).
// 고친 줄(edited)은 계수·출처 칸만 사건 값을 본다(S3W3c1 — 정렬이 따라온다). 사건의 출처는 코드가 아니라 글이라 글자 그대로(raw). 입력 열·검색은 결과 본문을 본다 — detail.factor.title 을 덮지 않는다.
// 입력 열(in… — 국가·사업장·이름·수단·에너지·면적·인원·수량·판매량·중량·가맹점 수·평균사용기간(개월) S3R3)은 줄의 input 에서(sid:MARC-ENT-539, 밴드 S3W2c ①).
//   옛 결과(input 없음)는 입력 열이 빈 칸이다(다시 셈하지 않는다). 에너지 열만 옛 줄에서 계수 이름(factor.title — 근사)으로 물러선다(Q3).
//   C5 의 name 은 엔진이 회사별 매핑으로 채운 뒤의 값일 수 있다 — 사용자가 적은 글자 그대로라고 단언하지 않는다(Q6).
// 줄은 서버 줄 그대로(C1·C2 를 그룹으로 합치지 않는다 — Q7). 비율은 그 시트 합 기준(카테고리 합이 아니다).
// 계수 칸 단위는 「/」 없는 EF단위(분모만)면 「kgCO2eq/」를 앞에 붙인다(factorUnitOf — 값 파일 GX3 ③). 검색은 화면 글자로 찾을 수 있다(filterRows 의 shown).
// 수는 parseNumber 한 곳으로 바꾼다. ×1000·÷1000 0(sid:MARC-ENT-264) — FCF 만 0~1 → % 로 ×100(fcfPercent).
import { CATEGORIES } from './category.ts';
import type { CategoryId } from './category.ts';
import type { RowFactor } from './current.ts';
import { parseNumber } from './number.ts';
import { sumOf } from './result.ts';
import type {
  FactorCells,
  InputKey,
  ResultRow,
  RowKind,
  Scope3Done,
} from './result.ts';

/** 시트 꼴 21 + 모르는 시트(generic). */
export const SHEET_LAYOUTS = [
  'C1',
  'C2',
  'C3',
  'C4-1',
  'C4-2',
  'C5',
  'C6-1',
  'C6-2',
  'C7',
  'C8-1',
  'C8-2',
  'C8-3',
  'C9-1',
  'C9-2',
  'C11',
  'C12',
  'C13-1',
  'C13-2',
  'C13-3',
  'C14',
  'C15',
] as const;
export type KnownLayout = (typeof SHEET_LAYOUTS)[number];
export type SheetLayout = KnownLayout | 'generic';

/** 표 열. 머리 글은 config/text.ts(시트마다 글이 다른 열은 시트별 글). */
export type ColumnId =
  | 'row'
  | 'inCountry'
  | 'inSite'
  | 'inName'
  | 'inVehicle'
  | 'inEnergy'
  | 'inPeople'
  | 'inBuildingArea'
  | 'inUsedArea'
  | 'inBuildingPeople'
  | 'inOwnPeople'
  | 'inProductCount'
  | 'inSales'
  | 'inWeight'
  | 'inStores'
  | 'inUseMonths'
  | 'group'
  | 'spendKrw'
  | 'treatment'
  | 'mode'
  | 'activity'
  | 'baseAmount'
  | 'people'
  | 'km'
  | 'roundTrip'
  | 'trips'
  | 'workdays'
  | 'buildingTotal'
  | 'investShare'
  | 'scope1'
  | 'scope2'
  | 'factor'
  | 'source'
  | 'co2e'
  | 'share'
  | 'biogenic'
  | 'fcf';

// 꼬리 차례(S3R3 Q6 — e6 F1, Figma 시트 프레임): 배출량 → 비율 → (생물기원) → 계수 → (FCF) → (출처). C15 는 꼬리가 따로다.
const TAIL: readonly ColumnId[] = ['co2e', 'share', 'factor'];
const BIOGENIC_TAIL: readonly ColumnId[] = [
  'co2e',
  'share',
  'biogenic',
  'factor',
  'fcf',
];
const PURCHASE_TAIL: readonly ColumnId[] = [...TAIL, 'source'];

/** 입력 열 → input 키(에너지 열은 옛 줄에서 계수 이름으로 물러섬 — cellOf). weight 의 단위는 weightUnit. */
const INPUT_COLUMNS: Partial<Record<ColumnId, InputKey>> = {
  inCountry: 'country',
  inSite: 'site',
  inName: 'name',
  inVehicle: 'vehicle',
  inEnergy: 'energy',
  inPeople: 'people',
  inBuildingArea: 'buildingArea',
  inUsedArea: 'usedArea',
  inBuildingPeople: 'buildingPeople',
  inOwnPeople: 'ownPeople',
  inProductCount: 'productCount',
  inSales: 'sales',
  inWeight: 'weight',
  inStores: 'stores',
  inUseMonths: 'useMonths',
};

const LEASED_ENERGY: readonly ColumnId[] = [
  'row',
  'inCountry',
  'inName',
  'inEnergy',
];

/**
 * 시트 꼴마다 열(왼쪽부터). 발주서 S3W2c §1-5 「뒤 차례」(Figma 시트 프레임 머리 차례를 감독이 옮김 — 이 세션은 Figma 대조 못 함).
 * 행 · 시트 고유 열(입력 열 포함) · 배출량 · 비율 · (생물기원) · 계수 · (FCF) · (출처) — 꼬리 차례는 S3R3 Q6(e6 F1).
 * C11 은 제품명 · 제품수량 · 에너지명 · 제품당 연간 에너지 사용량(activity — 입력 날값과 단위) · 평균사용기간(개월)(S3R3 Q4).
 * 서버에 없는 열(C1·C2 밖 출처, C6-1 왕복 이동거리)은 그리지 않는다(Q7). 체크·히스토리 열은 데이터 열이 아니라 화면이 앞뒤로 붙인다(S3W3b).
 */
export const SHEET_COLUMNS: Record<SheetLayout, readonly ColumnId[]> = {
  C1: [
    'row',
    'inCountry',
    'inSite',
    'group',
    'inName',
    'spendKrw',
    ...PURCHASE_TAIL,
  ],
  C2: [
    'row',
    'inCountry',
    'inSite',
    'group',
    'inName',
    'spendKrw',
    ...PURCHASE_TAIL,
  ],
  C3: ['row', 'inEnergy', 'activity', ...TAIL],
  'C4-1': ['row', 'inName', 'baseAmount', 'km', ...TAIL],
  'C4-2': ['row', 'inCountry', 'inSite', 'inName', 'activity', ...TAIL],
  C5: ['row', 'inSite', 'inName', 'treatment', 'activity', ...BIOGENIC_TAIL],
  'C6-1': ['row', 'mode', 'people', 'km', 'roundTrip', 'trips', ...TAIL],
  'C6-2': [
    'row',
    'inCountry',
    'inSite',
    'inVehicle',
    'inPeople',
    'activity',
    ...TAIL,
  ],
  C7: ['row', 'mode', 'km', 'people', 'workdays', ...TAIL],
  'C8-1': [...LEASED_ENERGY, 'activity', ...TAIL],
  'C8-2': [
    ...LEASED_ENERGY,
    'inBuildingArea',
    'inUsedArea',
    'buildingTotal',
    ...TAIL,
  ],
  'C8-3': [
    ...LEASED_ENERGY,
    'inBuildingPeople',
    'inOwnPeople',
    'buildingTotal',
    ...TAIL,
  ],
  'C9-1': ['row', 'mode', 'inName', 'baseAmount', 'km', ...TAIL],
  'C9-2': [
    'row',
    'inCountry',
    'inSite',
    'inName',
    'inVehicle',
    'activity',
    ...TAIL,
  ],
  C11: [
    'row',
    'inName',
    'inProductCount',
    'inEnergy',
    'activity',
    'inUseMonths',
    ...TAIL,
  ],
  C12: ['row', 'inName', 'inSales', 'inWeight', ...BIOGENIC_TAIL],
  'C13-1': [...LEASED_ENERGY, 'activity', ...TAIL],
  'C13-2': [
    ...LEASED_ENERGY,
    'inBuildingArea',
    'inUsedArea',
    'buildingTotal',
    ...TAIL,
  ],
  'C13-3': [
    ...LEASED_ENERGY,
    'inBuildingPeople',
    'inOwnPeople',
    'buildingTotal',
    ...TAIL,
  ],
  C14: [
    'row',
    'inCountry',
    'inName',
    'inStores',
    'inEnergy',
    'activity',
    ...TAIL,
  ],
  C15: ['row', 'inName', 'investShare', 'scope1', 'scope2', 'co2e', 'share'],
  generic: ['row', ...TAIL],
};

/** 글자 칸(검색이 보는 칸 — S3W2b Q6 + 입력 글 열 다섯). */
export const TEXT_COLUMNS: readonly ColumnId[] = [
  'inCountry',
  'inSite',
  'inName',
  'inVehicle',
  'inEnergy',
  'group',
  'treatment',
  'mode',
];
/** 정렬하는 칸(수 칸 — S3W2b Q6 + 입력 수 열 열(S3R3 평균사용기간(개월) 더함)). 행·글자·출처 칸은 정렬하지 않는다. */
export const SORT_COLUMNS: readonly ColumnId[] = [
  'inPeople',
  'inBuildingArea',
  'inUsedArea',
  'inBuildingPeople',
  'inOwnPeople',
  'inProductCount',
  'inSales',
  'inWeight',
  'inStores',
  'inUseMonths',
  'spendKrw',
  'activity',
  'baseAmount',
  'people',
  'km',
  'roundTrip',
  'trips',
  'workdays',
  'buildingTotal',
  'investShare',
  'scope1',
  'scope2',
  'factor',
  'co2e',
  'share',
  'biogenic',
  'fcf',
];

/** 시트 꼴이 정해진 카테고리(시트 이름 앞머리의 번호가 그 카테고리가 아니면 고르지 않는다). */
const LAYOUT_CATEGORY = (layout: KnownLayout) =>
  `Category${layout.slice(1).split('-')[0]}`;

/** 앞머리를 못 읽을 때 줄 kind 로 고르는 꼴(시트가 여럿인 카테고리는 kind 가 시트를 가른다 — C8·C13 셋은 kind 가 같아 -1). */
const LAYOUT_BY_KIND: Record<RowKind, Partial<Record<string, KnownLayout>>> = {
  purchase: { Category1: 'C1', Category2: 'C2' },
  fuel_energy: { Category3: 'C3' },
  transport_distance: { Category4: 'C4-1', Category9: 'C9-1' },
  transport_spend: { Category4: 'C4-2', Category9: 'C9-2' },
  waste: { Category5: 'C5' },
  travel_distance: { Category6: 'C6-1' },
  travel_spend: { Category6: 'C6-2' },
  commute: { Category7: 'C7' },
  leased_asset: { Category8: 'C8-1' },
  product_use: { Category11: 'C11' },
  product_eol: { Category12: 'C12' },
  leased_out_asset: { Category13: 'C13-1' },
  franchise: { Category14: 'C14' },
  investment: { Category15: 'C15' },
};

/**
 * 시트 → 표 꼴. 이름 안의 「c8-2」 꼴 낱말(대소문자 무시 — 엔진 match_sheet_processor 가 이름 안 대조라 앞에 글자가 붙어도 고른다,
 * 가지 리뷰 M1) 가운데 그 카테고리의 꼴인 첫 것 → 첫 줄 kind → generic.
 */
export function layoutOf(
  sheet: string,
  category: string,
  rows: readonly ResultRow[],
): SheetLayout {
  for (const head of sheet.matchAll(
    /(?<![a-z0-9])c(\d{1,2})(?:-(\d))?(?!\d)/gi,
  )) {
    const id = head[2] ? `C${head[1]}-${head[2]}` : `C${head[1]}`;
    const known = (SHEET_LAYOUTS as readonly string[]).includes(id);
    if (known && LAYOUT_CATEGORY(id as KnownLayout) === category)
      return id as KnownLayout;
  }
  for (const row of rows) {
    if (row.detail.shape === 'basic') continue;
    const layout = LAYOUT_BY_KIND[row.detail.kind][category];
    if (layout) return layout;
  }
  return 'generic';
}

/**
 * 행 번호: 「시트!12」 → 「12」, 「시트!12#1」 → 「12」, 「시트!12#2」 → 「12-2」(같은 줄 둘째부터 — Q1 [러너 초안]).
 * 시트 이름에 ! 가 있어도 마지막 ! 뒤를 본다. 엑셀 줄이 없으면(「시트!?」·꼴 틀림) null(화면 「-」).
 */
export function rowNumber(rowId: string | null): string | null {
  const parts = rowParts(rowId);
  if (parts === null) return null;
  return parts.nth === '1' ? parts.line : `${parts.line}-${parts.nth}`;
}

/** rowId 의 엑셀 줄·#n 글자. 꼴이 아니면 null. */
function rowParts(rowId: string | null) {
  if (rowId === null) return null;
  const at = rowId.lastIndexOf('!');
  if (at < 0) return null;
  const match = /^([1-9]\d*)(?:#([1-9]\d*))?$/.exec(rowId.slice(at + 1));
  return match && { line: match[1]!, nth: match[2] ?? '1' };
}

/** 정렬용 행 번호(화면 글자 「12-2」가 아니라 rowId 를 수로). 없으면 null. */
function rowOrder(rowId: string | null) {
  const parts = rowParts(rowId);
  if (parts === null) return null;
  const line = parseNumber(parts.line);
  const nth = parseNumber(parts.nth);
  return line === null || nth === null ? null : { line, nth };
}

/** 상세의 시트 하나. processed 는 줄과 그 시트 합, failed·empty 는 이름만(까닭 글은 화면). */
export type DetailSheet =
  | {
      status: 'processed';
      sheet: string;
      layout: SheetLayout;
      rows: ResultRow[];
      /** 그 시트 co2e 합(비율의 분모). 수가 없으면 null. */
      total: number | null;
    }
  | { status: 'failed'; sheet: string }
  | { status: 'empty'; sheet: string };

/** 카테고리 하나의 시트들(서버 차례 그대로). C10(1차 끔)·not_target·not_yet_supported·모르는 갈래는 0. */
export function categorySheets(
  done: Scope3Done,
  id: CategoryId,
): DetailSheet[] {
  const category = CATEGORIES.find((one) => one.id === id);
  if (!category || category.disabled) return [];
  const name = `Category${category.number}`;
  const out: DetailSheet[] = [];
  for (const sheet of done.sheets) {
    if (sheet.status === 'other' || sheet.category !== name) continue;
    if (sheet.status === 'processed')
      out.push({
        status: 'processed',
        sheet: sheet.sheet,
        layout: layoutOf(sheet.sheet, name, sheet.rows),
        rows: sheet.rows,
        // 제외 줄은 표에 남고 비율 분모에서 빠진다(서버 _line_value 와 같은 재료).
        total: sumOf(
          sheet.rows.filter((row) => !row.excluded).map((row) => row.co2e),
        ),
      });
    else out.push({ status: sheet.status, sheet: sheet.sheet });
  }
  return out;
}

/** 줄 배출량 / 그 시트 합 × 100(%). 합이 0·없음이거나 줄 수가 없으면 null(화면 「-」). */
export function shareOf(
  co2e: string | null,
  total: number | null,
): number | null {
  const value = parseNumber(co2e);
  if (value === null || total === null || total === 0) return null;
  return (value / total) * 100;
}

/** FCF(0~1 글자) → %. 없으면 null. */
export function fcfPercent(fcf: string | null): number | null {
  const value = parseNumber(fcf);
  return value === null ? null : value * 100;
}

/** 칸 값. 수 칸은 수(+ 서버 단위 글자), 글자 칸은 글자. 없으면 null. raw 는 출처 칸에서 갈래 값이 아닌 서버 글자라는 뜻이다. */
export type CellValue =
  | { type: 'text'; text: string | null; raw?: boolean }
  | { type: 'number'; value: number | null; unit: string | null };
/** 출처 칸 값(갈래 값이거나 raw 글자). */
export type SourceCell = Extract<CellValue, { type: 'text' }>;

const text = (value: string | null): CellValue => ({
  type: 'text',
  text: value,
});
const num = (value: number | null, unit: string | null = null): CellValue => ({
  type: 'number',
  value,
  unit,
});
const numText = (
  value: string | null | undefined,
  unit: string | null = null,
) => num(parseNumber(value ?? null), unit);

/** 계수 단위의 분자(값 파일 GX3 ③ — 에너지 계열 줄의 EF단위는 분모만 「kg」·「kWh」라 「0.06819 kg」로 읽혔다). */
export const FACTOR_NUMERATOR = 'kgCO2eq';

/** 계수 단위: 「/」가 없는 서버 글자면 앞에 「kgCO2eq/」(분모만 온 EF단위). 「/」가 있거나 비면 그대로. */
export const factorUnitOf = (unit: string | null | undefined): string | null =>
  unit === null || unit === undefined ? null
  : unit.trim() === '' || unit.includes('/') ? unit
  : `${FACTOR_NUMERATOR}/${unit.trim()}`;

/** 출처 칸의 갈래 값. usepa-estimate 는 맞는 품목이 없어 「기타」 계수로 셈한 줄이다(화면이 추정 뱃지를 단다). */
export const SOURCE_ESTIMATE = 'usepa-estimate';
/** 서버 출처 코드 → 갈래 값(엑셀 scope3_xlsx_labels.json 의 sourceKinds 와 같다 — pages/ghg-scope3/ui/xlsxLabels.test.ts). */
export const SOURCE_KINDS: Readonly<Record<string, string>> = {
  manual_keyword: 'usepa',
  db_keyword: 'usepa',
  legacy_fallback: 'usepa',
  manual_title: SOURCE_ESTIMATE,
};

/** 서버 출처 코드 → 갈래 값. none·모르는 글자·null 은 null. */
export const sourceKind = (code: string | null): string | null =>
  code !== null && Object.hasOwn(SOURCE_KINDS, code) ?
    SOURCE_KINDS[code]!
  : null;

/** 고친 줄의 계수 사건. applied·사건 없는 줄은 null. */
export const fixedFactorOf = (row: ResultRow): RowFactor | null =>
  row.edited ? (row.factorEdit ?? null) : null;

/** 줄 하나의 칸 값(그 열이 그 줄 꼴에 없으면 빈 값 — basic 줄은 행·배출량·비율만). */
export function cellOf(
  row: ResultRow,
  column: ColumnId,
  sheetTotal: number | null,
): CellValue {
  switch (column) {
    case 'row':
      return text(rowNumber(row.rowId));
    case 'co2e':
      return numText(row.co2e);
    case 'share':
      return num(row.excluded ? null : shareOf(row.co2e, sheetTotal));
    case 'biogenic':
      return numText(row.biogenic);
    default:
      break;
  }
  const key = INPUT_COLUMNS[column];
  if (key !== undefined) {
    const input = row.input;
    // 에너지 열: input 이 없는 옛 줄만 계수 이름(근사)으로 — input 이 있고 energy 가 null 이면 빈 칸(Q3).
    if (column === 'inEnergy')
      return text(
        input !== null ? input.energy
        : row.detail.shape === 'basic' ? null
        : (row.detail.factor?.title ?? null),
      );
    if (TEXT_COLUMNS.includes(column)) return text(input?.[key] ?? null);
    return numText(
      input?.[key],
      column === 'inWeight' ? (input?.weightUnit ?? null) : null,
    );
  }
  const fixed = fixedFactorOf(row);
  if (fixed !== null && column === 'factor')
    return numText(fixed.value, factorUnitOf(fixed.unit));
  if (fixed !== null && column === 'source')
    return { type: 'text', text: fixed.source, raw: true };
  const detail = row.detail;
  if (detail.shape === 'basic')
    return TEXT_COLUMNS.includes(column) || column === 'source' ?
        text(null)
      : num(null);
  const factor: FactorCells | null = detail.factor;
  switch (column) {
    case 'factor':
      return factor ?
          numText(factor.value, factorUnitOf(factor.unit))
        : num(null);
    case 'source':
      return text(
        detail.shape === 'purchase' ? sourceKind(detail.factor.source) : null,
      );
    case 'group':
      return text(detail.shape === 'purchase' ? detail.groupName : null);
    case 'spendKrw':
      return detail.shape === 'purchase' ? numText(detail.spendKrw) : num(null);
    case 'fcf':
      return detail.shape === 'purchase' ?
          num(null)
        : num(fcfPercent(detail.fcf));
    default:
      break;
  }
  if (detail.shape === 'purchase') return num(null);
  const amount = detail.activity;
  switch (column) {
    case 'activity':
      return numText(amount.value, amount.unit);
    case 'baseAmount':
      return numText(amount.baseValue, amount.baseUnit);
    default:
      break;
  }
  if (detail.shape === 'activity') {
    const distance = detail.distance;
    switch (column) {
      case 'treatment':
        return text(detail.treatment);
      case 'mode':
        return text(detail.mode);
      case 'km':
        return numText(distance?.km);
      case 'roundTrip':
        return numText(distance?.roundTrip);
      case 'people':
        return numText(distance?.people);
      case 'trips':
        return numText(distance?.trips);
      case 'workdays':
        return numText(distance?.workdays);
      default:
        return TEXT_COLUMNS.includes(column) ? text(null) : num(null);
    }
  }
  switch (column) {
    case 'buildingTotal':
      return numText(detail.buildingTotal);
    case 'investShare':
      return numText(detail.investment?.share);
    case 'scope1':
      return numText(detail.investment?.scope1);
    case 'scope2':
      return numText(detail.investment?.scope2);
    default:
      return TEXT_COLUMNS.includes(column) ? text(null) : num(null);
  }
}

/**
 * 검색: 그 시트 꼴의 글자 칸에 낱말이 들어 있는 줄(대소문자 무시·앞뒤 빈칸 무시). 빈 낱말이면 그대로.
 * shown 을 주면 칸의 화면 글자로 찾는다(수단 칸의 이름표 — 「버스」로 찾음, GX3 값 파일 ④). 없으면 서버 글자.
 */
export function filterRows(
  rows: readonly ResultRow[],
  layout: SheetLayout,
  query: string,
  shown: (cell: CellValue, column: ColumnId) => string | null = (cell) =>
    cell.type === 'text' ? cell.text : null,
): ResultRow[] {
  const word = query.trim().toLowerCase();
  if (word === '') return [...rows];
  const columns = SHEET_COLUMNS[layout].filter((column) =>
    TEXT_COLUMNS.includes(column),
  );
  return rows.filter((row) =>
    columns.some((column) => {
      const cell = cellOf(row, column, null);
      if (cell.type !== 'text' || cell.text === null) return false;
      return (shown(cell, column) ?? '').toLowerCase().includes(word);
    }),
  );
}

/** 그 꼴에 검색할 글자 칸이 있는가(없으면 화면이 검색 칸을 그 표에 걸지 않는다). */
export const searchable = (layout: SheetLayout) =>
  SHEET_COLUMNS[layout].some((column) => TEXT_COLUMNS.includes(column));

export type SortDirection = 'asc' | 'desc';
export interface RowSort {
  column: ColumnId;
  direction: SortDirection;
}

/**
 * 정렬(수 칸만). 수 없는 줄은 늘 뒤. sort 가 없거나 수 칸이 아니면 행 번호 차례(엑셀 줄, 그다음 #n).
 * 같은 값의 바닥도 행 번호 차례(D5). 행 번호 없는 줄은 뒤, 그 안은 서버 차례.
 */
export function sortRows(
  rows: readonly ResultRow[],
  sort: RowSort | null,
  sheetTotal: number | null,
): ResultRow[] {
  const active =
    sort !== null && SORT_COLUMNS.includes(sort.column) ? sort : null;
  const valueOf = (row: ResultRow) => {
    if (active === null) return null;
    const cell = cellOf(row, active.column, sheetTotal);
    return cell.type === 'number' ? cell.value : null;
  };
  const sign = active?.direction === 'desc' ? -1 : 1;
  type Keyed = {
    index: number;
    value: number | null;
    order: ReturnType<typeof rowOrder>;
  };
  const byRow = (a: Keyed, b: Keyed) => {
    if (a.order === null || b.order === null) {
      if (a.order === b.order) return a.index - b.index;
      return a.order === null ? 1 : -1;
    }
    return (
      a.order.line - b.order.line ||
      a.order.nth - b.order.nth ||
      a.index - b.index
    );
  };
  return rows
    .map((row, index) => ({
      row,
      index,
      value: valueOf(row),
      order: rowOrder(row.rowId),
    }))
    .sort((a, b) => {
      if (a.value === null || b.value === null) {
        if (a.value === b.value) return byRow(a, b);
        return a.value === null ? 1 : -1;
      }
      return a.value === b.value ? byRow(a, b) : (a.value - b.value) * sign;
    })
    .map((one) => one.row);
}

/** 쪽 하나의 줄 수(Q6 [추정] — 디자인 확인 거리). */
export const PAGE_SIZE = 50;

export interface RowPage<T> {
  rows: T[];
  /** 1부터. 범위 밖이면 가장 가까운 쪽으로. */
  page: number;
  /** 줄이 0 이어도 1. */
  pageCount: number;
}

/** 쪽 나눔(검색·정렬 뒤에 부른다). */
export function pageOf<T>(
  rows: readonly T[],
  page: number,
  size: number = PAGE_SIZE,
): RowPage<T> {
  const pageCount = Math.max(1, Math.ceil(rows.length / size));
  const at = Math.min(Math.max(1, Math.floor(page) || 1), pageCount);
  return {
    rows: rows.slice((at - 1) * size, at * size),
    page: at,
    pageCount,
  };
}
