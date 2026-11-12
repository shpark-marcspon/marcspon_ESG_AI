// Scope 3 상세 셈 시험(밴드 S3W2b ① — 발주서 §3 의 1): 시트 꼴 · 행 번호 · 시트 합 비율 · 0 나눔 · FCF · 검색 · 정렬 · 쪽 경계 · 카테고리 시트.
// 밴드 S3W2c ①: 열 표(발주서 §1-5 「뒤 차례」) · 입력 열(input — 에너지 열 셋 갈래 · 수 글자 · 중량 단위 · 검색·정렬 · 옛 줄 빈 칸). 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import type { RowFactor } from './current.ts';
import {
  PAGE_SIZE,
  SHEET_COLUMNS,
  SHEET_LAYOUTS,
  SORT_COLUMNS,
  TEXT_COLUMNS,
  categorySheets,
  cellOf,
  factorUnitOf,
  fcfPercent,
  filterRows,
  layoutOf,
  pageOf,
  rowNumber,
  searchable,
  shareOf,
  sortRows,
} from './detail.ts';
import type { CellValue, ColumnId } from './detail.ts';
import {
  factorWindowOf,
  isAiGroup,
  openingColumn,
  opensFactorWindow,
} from './factorWindow.ts';
import { INPUT_KEYS } from './result.ts';
import type {
  C12Treatments,
  ResultRow,
  RowDetail,
  RowInput,
  Scope3Done,
} from './result.ts';
import { leadColumn } from './rowEdit.ts';

const basic: RowDetail = { shape: 'basic' };
const row = (
  co2e: string | null,
  detail: RowDetail = basic,
  rowId: string | null = null,
  input: RowInput | null = null,
): ResultRow => ({
  rowId,
  co2e,
  biogenic: null,
  origin: null,
  formula: null,
  detail,
  input,
});
/** 입력 칸 — 다 null 에서 넘긴 칸만. */
const inputOf = (cells: Partial<RowInput>): RowInput => ({
  ...(Object.fromEntries(INPUT_KEYS.map((key) => [key, null])) as RowInput),
  ...cells,
});
const factor = {
  title: '지어낸 연료',
  value: '0.25',
  unit: 'kgCO2e/kg',
  source: null,
};
const amount = { value: '10', unit: 'kg', baseValue: '10', baseUnit: 'kg' };
const activity = (
  kind: 'waste' | 'travel_distance' | 'transport_spend',
  extra: Partial<Extract<RowDetail, { shape: 'activity' }>> = {},
): RowDetail => ({
  shape: 'activity',
  kind,
  activity: amount,
  factor,
  treatment: null,
  mode: null,
  distance: null,
  fcf: null,
  hasBiogenic: false,
  biogenicNote: null,
  ...extra,
});
const purchase = (
  groupName: string,
  source: string | null = 'db_keyword',
): RowDetail => ({
  shape: 'purchase',
  kind: 'purchase',
  groupName,
  groupOrigin: null,
  spendKrw: '1000',
  factor: { ...factor, unit: 'kgCO2e/KRW', source },
  recommendations: [],
});
const leased: RowDetail = {
  shape: 'energy',
  kind: 'leased_asset',
  activity: amount,
  factor,
  hasBiogenic: false,
  biogenicNote: null,
  buildingTotal: '100',
  years: null,
  investment: null,
  fcf: null,
};

describe('layoutOf — 시트 이름 앞머리 → 줄 kind → generic', () => {
  it('앞머리 21(대소문자 무시) — 카테고리가 맞을 때만', () => {
    for (const layout of SHEET_LAYOUTS) {
      const category = `Category${layout.slice(1).split('-')[0]}`;
      expect(layoutOf(`${layout.toLowerCase()}_지어낸`, category, [])).toBe(
        layout,
      );
      expect(layoutOf(`${layout}_지어낸`, category, [])).toBe(layout);
    }
    // c1 은 c13-1 과 섞이지 않는다.
    expect(layoutOf('c13-1_x', 'Category13', [])).toBe('C13-1');
    expect(layoutOf('c1_x', 'Category1', [])).toBe('C1');
    // 앞머리 번호와 카테고리가 다르면 앞머리를 쓰지 않는다.
    expect(layoutOf('c4-1_x', 'Category9', [])).toBe('generic');
  });

  it('이름 안의 꼴 낱말도 고른다(엔진 이름 안 대조 — 가지 리뷰 M1) · 숫자·글자에 붙은 c 는 아님', () => {
    expect(layoutOf('2025_c8-2_지어낸', 'Category8', [row('1', leased)])).toBe(
      'C8-2',
    );
    expect(layoutOf('지어낸 C13-3', 'Category13', [])).toBe('C13-3');
    expect(layoutOf('abc8-2_x', 'Category8', [])).toBe('generic');
    expect(layoutOf('c8-21_x', 'Category8', [])).toBe('generic');
    // 앞 낱말이 다른 카테고리면 다음 낱말.
    expect(layoutOf('c4-1 c8-3', 'Category8', [])).toBe('C8-3');
  });

  it('앞머리를 못 읽으면 첫 줄 kind(시트 여럿 카테고리는 kind 가 가름)', () => {
    expect(
      layoutOf('지어낸', 'Category9', [row('1', activity('transport_spend'))]),
    ).toBe('C9-2');
    expect(
      layoutOf('지어낸', 'Category6', [row('1', activity('travel_distance'))]),
    ).toBe('C6-1');
    expect(
      layoutOf('지어낸', 'Category8', [row('1', basic), row('1', leased)]),
    ).toBe('C8-1');
    expect(layoutOf('지어낸', 'Category1', [row('1')])).toBe('generic');
    expect(layoutOf('c99_x', 'Category99', [])).toBe('generic');
  });

  it('열 표(발주서 §1-5 — 뺀 열 0): 모든 꼴에 행·배출량·비율 · 출처는 C1·C2 만 · 생물기원·FCF 는 C5·C12 만 · C15 계수 0', () => {
    for (const [layout, columns] of Object.entries(SHEET_COLUMNS)) {
      expect(columns.slice(0, 1), layout).toEqual(['row']);
      expect(columns, layout).toContain('co2e');
      expect(columns, layout).toContain('share');
      expect(columns.includes('source'), layout).toBe(
        layout === 'C1' || layout === 'C2',
      );
      expect(columns.includes('biogenic'), layout).toBe(
        layout === 'C5' || layout === 'C12',
      );
      expect(columns.includes('fcf'), layout).toBe(
        layout === 'C5' || layout === 'C12',
      );
      expect(columns.includes('factor'), layout).toBe(layout !== 'C15');
    }
    // ★D 처분: C6-1 편도 km + 왕복계수 열, C9-2 서버 수단(mode) 열 뺌 — 입력 수단(inVehicle)으로 갈음(S3W2c §1-5).
    expect(SHEET_COLUMNS['C6-1']).toEqual(
      expect.arrayContaining(['km', 'roundTrip']),
    );
    expect(SHEET_COLUMNS['C9-2']).not.toContain('mode');
  });

  it('열 표 = 발주서 S3W2c §1-5 「뒤 차례」(21 꼴 + generic — 시트 고유 열 차례 그대로) · 꼬리 S3R3 Q6 · C11 S3R3 Q4', () => {
    const T = ['co2e', 'share', 'factor'];
    const B = ['co2e', 'share', 'biogenic', 'factor', 'fcf'];
    const purchaseHead = ['row', 'inCountry', 'inSite', 'group', 'inName'];
    const leased = ['row', 'inCountry', 'inName', 'inEnergy'];
    expect(SHEET_COLUMNS).toEqual({
      C1: [...purchaseHead, 'spendKrw', 'co2e', 'share', 'factor', 'source'],
      C2: [...purchaseHead, 'spendKrw', 'co2e', 'share', 'factor', 'source'],
      C3: ['row', 'inEnergy', 'activity', ...T],
      'C4-1': ['row', 'inName', 'baseAmount', 'km', ...T],
      'C4-2': ['row', 'inCountry', 'inSite', 'inName', 'activity', ...T],
      C5: ['row', 'inSite', 'inName', 'treatment', 'activity', ...B],
      'C6-1': ['row', 'mode', 'people', 'km', 'roundTrip', 'trips', ...T],
      'C6-2': [
        'row',
        'inCountry',
        'inSite',
        'inVehicle',
        'inPeople',
        'activity',
        ...T,
      ],
      C7: ['row', 'mode', 'km', 'people', 'workdays', ...T],
      'C8-1': [...leased, 'activity', ...T],
      'C8-2': [
        ...leased,
        'inBuildingArea',
        'inUsedArea',
        'buildingTotal',
        ...T,
      ],
      'C8-3': [
        ...leased,
        'inBuildingPeople',
        'inOwnPeople',
        'buildingTotal',
        ...T,
      ],
      'C9-1': ['row', 'mode', 'inName', 'baseAmount', 'km', ...T],
      'C9-2': [
        'row',
        'inCountry',
        'inSite',
        'inName',
        'inVehicle',
        'activity',
        ...T,
      ],
      C11: [
        'row',
        'inName',
        'inProductCount',
        'inEnergy',
        'activity',
        'inUseMonths',
        ...T,
      ],
      C12: ['row', 'inName', 'inSales', 'inWeight', ...B],
      'C13-1': [...leased, 'activity', ...T],
      'C13-2': [
        ...leased,
        'inBuildingArea',
        'inUsedArea',
        'buildingTotal',
        ...T,
      ],
      'C13-3': [
        ...leased,
        'inBuildingPeople',
        'inOwnPeople',
        'buildingTotal',
        ...T,
      ],
      C14: [
        'row',
        'inCountry',
        'inName',
        'inStores',
        'inEnergy',
        'activity',
        ...T,
      ],
      C15: [
        'row',
        'inName',
        'investShare',
        'scope1',
        'scope2',
        'co2e',
        'share',
      ],
      generic: ['row', ...T],
    });
    // 사용기간(년) 열(years)은 S3R3 에서 지웠다 — 어느 꼴에도 없다.
    for (const columns of Object.values(SHEET_COLUMNS))
      expect(columns as readonly string[]).not.toContain('years');
    // 검색 열 = 글 입력 열 다섯 + 앞 글 칸 셋, 정렬 열에 수 입력 열 열(Q4 · S3R3 평균사용기간(개월)).
    expect([...TEXT_COLUMNS].sort()).toEqual(
      [
        'inCountry',
        'inSite',
        'inName',
        'inVehicle',
        'inEnergy',
        'group',
        'treatment',
        'mode',
      ].sort(),
    );
    for (const column of [
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
    ] as ColumnId[])
      expect(SORT_COLUMNS, column).toContain(column);
    for (const column of TEXT_COLUMNS)
      expect(SORT_COLUMNS, column).not.toContain(column);
  });
});

describe('rowNumber — 시트!엑셀줄(#n)', () => {
  it('#n 은 떼고 같은 줄 둘째부터 12-2', () => {
    expect(rowNumber('c1_x!12')).toBe('12');
    expect(rowNumber('c1_x!12#1')).toBe('12');
    expect(rowNumber('c1_x!12#2')).toBe('12-2');
    expect(rowNumber('c1_x!12#3')).toBe('12-3');
    expect(rowNumber('a!b!7')).toBe('7');
  });
  it('엑셀 줄이 없으면 null', () => {
    for (const id of [null, 'c1_x!?', 'c1_x', 'c1_x!', 'c1_x!0', 'c1_x!3#x'])
      expect(rowNumber(id), String(id)).toBeNull();
  });
});

describe('shareOf · fcfPercent', () => {
  it('줄 / 시트 합 × 100 · 합 0·null·줄 수 없음은 null', () => {
    expect(shareOf('1', 4)).toBe(25);
    expect(shareOf('1e-05', 1e-5)).toBe(100);
    expect(shareOf('1', 0)).toBeNull();
    expect(shareOf('1', null)).toBeNull();
    expect(shareOf(null, 4)).toBeNull();
    expect(shareOf('nan', 4)).toBeNull();
  });
  it('FCF 0~1 → % (×100) · 없음 null', () => {
    expect(fcfPercent('0.25')).toBe(25);
    expect(fcfPercent('1')).toBe(100);
    expect(fcfPercent(null)).toBeNull();
  });
});

describe('cellOf — 열마다 칸', () => {
  it('비율은 넘긴 시트 합 기준(카테고리 합이 아님)', () => {
    const one = row('2', basic, 's!3');
    expect(cellOf(one, 'share', 8)).toEqual({
      type: 'number',
      value: 25,
      unit: null,
    });
    expect(cellOf(one, 'row', 8)).toEqual({ type: 'text', text: '3' });
  });
  it('basic 줄은 행·배출량·비율만 — 그 밖 칸은 빈 값', () => {
    const one = row('2');
    for (const column of [
      'group',
      'factor',
      'activity',
      'mode',
    ] as ColumnId[]) {
      const cell = cellOf(one, column, 2);
      expect(cell.type === 'text' ? cell.text : cell.value, column).toBeNull();
    }
  });
  it.each([
    ['manual_keyword', 'usepa'],
    ['db_keyword', 'usepa'],
    ['legacy_fallback', 'usepa'],
    ['manual_title', 'usepa-estimate'],
    ['none', null],
    ['지어낸 코드', null],
    ['constructor', null],
    [null, null],
  ])('출처 코드 %s → 갈래 %s', (code, kind) => {
    expect(cellOf(row('1', purchase('g', code)), 'source', 1)).toEqual({
      type: 'text',
      text: kind,
    });
  });
  it('계수 = 값 + 서버 단위 글자 · 활동량 단위 · 출처는 구매만 · ×1000 0', () => {
    expect(cellOf(row('1', purchase('g')), 'factor', 1)).toEqual({
      type: 'number',
      value: 0.25,
      unit: 'kgCO2e/KRW',
    });
    expect(cellOf(row('1', purchase('g')), 'source', 1)).toEqual({
      type: 'text',
      text: 'usepa',
    });
    expect(cellOf(row('1', activity('waste')), 'source', 1)).toEqual({
      type: 'text',
      text: null,
    });
    expect(cellOf(row('1', activity('waste')), 'activity', 1)).toEqual({
      type: 'number',
      value: 10,
      unit: 'kg',
    });
    expect(cellOf(row('1500', basic), 'co2e', 1)).toMatchObject({
      value: 1500,
    });
    // 생물기원도 tCO2eq 그대로(kg 로 ×1000 0 — Figma kgCO2-eq 를 따르지 않음).
    expect(
      cellOf(
        { ...row('1', activity('waste')), biogenic: '0.75' },
        'biogenic',
        1,
      ),
    ).toEqual({ type: 'number', value: 0.75, unit: null });
    expect(
      cellOf(row('1', activity('waste', { fcf: '0.5' })), 'fcf', 1),
    ).toMatchObject({ value: 50 });
  });
  it('C6-1 거리는 편도 km 그대로(왕복계수를 곱하지 않음) · 왕복계수 열은 따로', () => {
    const one = row(
      '1',
      activity('travel_distance', {
        distance: {
          km: '300',
          roundTrip: '2',
          people: '1',
          trips: '1',
          workdays: null,
        },
      }),
    );
    expect(cellOf(one, 'km', 1)).toMatchObject({ value: 300 });
    expect(cellOf(one, 'roundTrip', 1)).toMatchObject({ value: 2 });
  });
});

describe('C11 두 열(S3R3 Q1·Q4·Q5) — 제품당 연간 에너지 사용량(activity)·평균사용기간(개월)(input.useMonths)', () => {
  const productUse = (value: string | null, unit: string): RowDetail => ({
    shape: 'energy',
    kind: 'product_use',
    activity: { value, unit, baseValue: '920.0', baseUnit: 'kWh' },
    factor,
    buildingTotal: null,
    years: '8.0',
    investment: null,
    fcf: null,
    hasBiogenic: false,
    biogenicNote: null,
  });
  const c11 = (input: RowInput | null, value: string | null = '0.92') =>
    row('1', productUse(value, 'MWh'), 'c11_x!3', input);

  it('activity 칸 = 입력 날값 + 서버 단위(환산값 baseValue 아님) · 옛 줄(input 없음)에서도 보인다', () => {
    expect(cellOf(c11(inputOf({})), 'activity', 1)).toEqual({
      type: 'number',
      value: 0.92,
      unit: 'MWh',
    });
    expect(cellOf(c11(null), 'activity', 1)).toEqual({
      type: 'number',
      value: 0.92,
      unit: 'MWh',
    });
    expect(cellOf(c11(null, null), 'activity', 1)).toMatchObject({
      value: null,
    });
  });

  it('평균사용기간(개월) = input.useMonths 수 칸: 「96.0」·「30.5」·「-0.0」 → 수 · 빈 글·null·수 아닌 글 → 빈 칸 · 옛 줄·키 열다섯 줄 → 빈 칸 · product.years 는 읽지 않음', () => {
    const at = (useMonths: string | null) =>
      cellOf(c11(inputOf({ useMonths })), 'inUseMonths', 1);
    expect(at('96.0')).toEqual({ type: 'number', value: 96, unit: null });
    expect(at('30.5')).toMatchObject({ value: 30.5 });
    expect(at('-0.0')).toMatchObject({ value: 0 });
    expect(at('')).toMatchObject({ value: null });
    expect(at(null)).toMatchObject({ value: null });
    expect(at('지어낸 이삼년')).toMatchObject({ value: null });
    expect(cellOf(c11(null), 'inUseMonths', 1)).toEqual({
      type: 'number',
      value: null,
      unit: null,
    });
  });

  it('평균사용기간(개월) 정렬: 수 차례, 빈 칸은 끝', () => {
    const rows = ['30.5', null, '96.0', '12.0'].map((useMonths, i) =>
      row(
        '1',
        productUse('1', 'kWh'),
        `c11_x!${i + 3}`,
        inputOf({ useMonths }),
      ),
    );
    const order = (direction: 'asc' | 'desc') =>
      sortRows(rows, { column: 'inUseMonths', direction }, 4).map(
        (one) => one.input?.useMonths ?? null,
      );
    expect(order('asc')).toEqual(['12.0', '30.5', '96.0', null]);
    expect(order('desc')).toEqual(['96.0', '30.5', '12.0', null]);
  });
});

describe('입력 열(S3W2c ① — 결과 줄 input, sid:MARC-ENT-539)', () => {
  const leasedRow = (input: RowInput | null) => row('1', leased, 's!3', input);

  it('에너지 열 셋 갈래(Q3): input 의 energy · input 있고 energy null 은 빈 칸 · input 없는 옛 줄은 계수 이름', () => {
    expect(
      cellOf(
        leasedRow(inputOf({ energy: '지어낸 입력 에너지' })),
        'inEnergy',
        1,
      ),
    ).toEqual({ type: 'text', text: '지어낸 입력 에너지' });
    expect(cellOf(leasedRow(inputOf({})), 'inEnergy', 1)).toEqual({
      type: 'text',
      text: null,
    });
    expect(cellOf(leasedRow(null), 'inEnergy', 1)).toEqual({
      type: 'text',
      text: '지어낸 연료',
    });
    // basic 줄의 옛 줄은 계수가 없어 빈 칸.
    expect(cellOf(row('1'), 'inEnergy', 1)).toEqual({
      type: 'text',
      text: null,
    });
  });

  it('글 열은 글자 그대로 · 옛 줄(input null)은 모든 입력 열이 빈 칸 · basic 줄도 input 을 그린다(Q1)', () => {
    const cells = inputOf({
      country: '지어낸 나라',
      site: ' 지어낸 사업장 ',
      name: '지어낸 이름',
      vehicle: '지어낸 수단',
    });
    const one = row('1', basic, 's!3', cells);
    expect(cellOf(one, 'inCountry', 1)).toEqual({
      type: 'text',
      text: '지어낸 나라',
    });
    expect(cellOf(one, 'inSite', 1)).toEqual({
      type: 'text',
      text: ' 지어낸 사업장 ',
    });
    expect(cellOf(one, 'inName', 1)).toMatchObject({ text: '지어낸 이름' });
    expect(cellOf(one, 'inVehicle', 1)).toMatchObject({ text: '지어낸 수단' });
    const old = row('1', purchase('g'), 's!3', null);
    for (const column of [
      'inCountry',
      'inSite',
      'inName',
      'inVehicle',
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
    ] as ColumnId[]) {
      const cell = cellOf(old, column, 1);
      expect(cell.type === 'text' ? cell.text : cell.value, column).toBeNull();
      expect(cell.type, column).toBe(
        TEXT_COLUMNS.includes(column) ? 'text' : 'number',
      );
    }
    // 옛 줄도 줄의 다른 칸은 그대로.
    expect(cellOf(old, 'group', 1)).toMatchObject({ text: 'g' });
  });

  it('수 열(Q4)은 parseNumber 한 곳: 「3.0」·지수·-0.0 → 수 · 빈 글·nan 은 빈 칸 · 중량 단위는 weightUnit', () => {
    const at = (cells: Partial<RowInput>, column: ColumnId) =>
      cellOf(row('1', basic, 's!3', inputOf(cells)), column, 1);
    expect(at({ people: '3.0' }, 'inPeople')).toEqual({
      type: 'number',
      value: 3,
      unit: null,
    });
    expect(at({ sales: '1.25e3' }, 'inSales')).toMatchObject({ value: 1250 });
    expect(at({ stores: '-0.0' }, 'inStores')).toMatchObject({ value: 0 });
    expect(at({ productCount: '' }, 'inProductCount')).toMatchObject({
      value: null,
    });
    expect(at({ buildingArea: 'nan' }, 'inBuildingArea')).toMatchObject({
      value: null,
    });
    expect(
      at(
        { usedArea: '30.0', buildingPeople: '40.0', ownPeople: '4.0' },
        'inUsedArea',
      ),
    ).toMatchObject({ value: 30 });
    expect(at({ buildingPeople: '40.0' }, 'inBuildingPeople')).toMatchObject({
      value: 40,
    });
    expect(at({ ownPeople: '4.0' }, 'inOwnPeople')).toMatchObject({ value: 4 });
    expect(at({ weight: '0.5', weightUnit: 'kg' }, 'inWeight')).toEqual({
      type: 'number',
      value: 0.5,
      unit: 'kg',
    });
    expect(at({ weight: '0.5' }, 'inWeight')).toEqual({
      type: 'number',
      value: 0.5,
      unit: null,
    });
  });

  it('C6-1·C7 인원수는 거리 칸(셈에 쓴 값) 그대로 — input.people 은 C6-2 만(Q5)', () => {
    const one = row(
      '1',
      activity('travel_distance', {
        distance: {
          km: '1',
          roundTrip: '1',
          people: '5',
          trips: '1',
          workdays: null,
        },
      }),
      's!3',
      inputOf({ people: '9.0' }),
    );
    expect(cellOf(one, 'people', 1)).toMatchObject({ value: 5 });
    expect(cellOf(one, 'inPeople', 1)).toMatchObject({ value: 9 });
    expect(SHEET_COLUMNS['C6-1']).not.toContain('inPeople');
    expect(SHEET_COLUMNS.C7).not.toContain('inPeople');
  });

  it('검색은 입력 글 열을 본다 · 정렬은 수 입력 열을 본다(옛 줄은 늘 뒤)', () => {
    const rows = [
      row('1', purchase('g'), 's!1', inputOf({ site: '지어낸 갑', name: 'x' })),
      row('1', purchase('g'), 's!2', inputOf({ site: '지어낸 을', name: 'y' })),
      row('1', purchase('g'), 's!3', null),
    ];
    expect(filterRows(rows, 'C1', '을').map((r) => r.rowId)).toEqual(['s!2']);
    expect(filterRows(rows, 'C1', 'X').map((r) => r.rowId)).toEqual(['s!1']);
    const sales = [
      row('1', basic, 's!1', inputOf({ sales: '20.0' })),
      row('1', basic, 's!2', null),
      row('1', basic, 's!3', inputOf({ sales: '5.0' })),
    ];
    expect(
      sortRows(sales, { column: 'inSales', direction: 'asc' }, 3).map(
        (r) => r.rowId,
      ),
    ).toEqual(['s!3', 's!1', 's!2']);
    expect(
      sortRows(sales, { column: 'inSales', direction: 'desc' }, 3).map(
        (r) => r.rowId,
      ),
    ).toEqual(['s!1', 's!3', 's!2']);
  });
});

describe('계수 단위 — 분모만 온 EF단위는 kgCO2eq/ 를 앞에(값 파일 GX3 ③)', () => {
  const energy = (unit: string | null): RowDetail => ({
    ...leased,
    factor: { ...factor, unit, value: '0.06819' },
  });
  it('C3 줄 「kWh」 → kgCO2eq/kWh · C1 「kgCO2e/KRW」 그대로 · null 은 숫자만', () => {
    expect(cellOf(row('1', energy('kWh')), 'factor', 1)).toEqual({
      type: 'number',
      value: 0.06819,
      unit: 'kgCO2eq/kWh',
    });
    expect(cellOf(row('1', purchase('g')), 'factor', 1)).toMatchObject({
      unit: 'kgCO2e/KRW',
    });
    expect(cellOf(row('1', energy(null)), 'factor', 1)).toMatchObject({
      unit: null,
    });
  });
  it('factorUnitOf: 빈 글은 그대로 · 앞뒤 빈칸 무시', () => {
    expect(factorUnitOf('')).toBe('');
    expect(factorUnitOf(' kg ')).toBe('kgCO2eq/kg');
    expect(factorUnitOf('kgCO2eq/kg')).toBe('kgCO2eq/kg');
    expect(factorUnitOf(undefined)).toBeNull();
  });
});

describe('filterRows · sortRows · pageOf', () => {
  const rows = [
    row('3', purchase('지어낸 묶음 가'), 's!1'),
    row('1', purchase('지어낸 묶음 나'), 's!2'),
    row(null, purchase('Mixed Case'), 's!3'),
    row('2', purchase('지어낸 묶음 가'), 's!4'),
  ];

  it('검색: 그 꼴의 글자 칸 · 대소문자·앞뒤 빈칸 무시 · 빈 낱말은 그대로', () => {
    expect(filterRows(rows, 'C1', ' 묶음 가 ').map((r) => r.rowId)).toEqual([
      's!1',
      's!4',
    ]);
    expect(filterRows(rows, 'C1', 'mixed').map((r) => r.rowId)).toEqual([
      's!3',
    ]);
    expect(filterRows(rows, 'C1', '  ')).toHaveLength(4);
    // 글자 칸이 없는 꼴(generic)은 검색으로 줄이 남지 않는다 — 화면이 검색 칸을 걸지 않는다. C12 는 입력 이름 열로 검색이 닿는다(S3W2c).
    expect(searchable('generic')).toBe(false);
    expect(searchable('C12')).toBe(true);
    expect(searchable('C1')).toBe(true);
    expect(filterRows(rows, 'generic', '묶음')).toEqual([]);
  });

  it('검색: shown 을 주면 화면 글자로 찾는다(수단 이름표 — 값 파일 GX3 ④)', () => {
    const travel = [
      row('1', activity('travel_distance', { mode: 'bus' }), 's!1'),
      row('1', activity('travel_distance', { mode: 'train' }), 's!2'),
    ];
    const label = (cell: CellValue, column: ColumnId) =>
      cell.type === 'text' && column === 'mode' && cell.text === 'bus' ? '버스'
      : cell.type === 'text' ? cell.text
      : null;
    expect(
      filterRows(travel, 'C6-1', '버스', label).map((r) => r.rowId),
    ).toEqual(['s!1']);
    expect(filterRows(travel, 'C6-1', '버스')).toEqual([]);
    expect(filterRows(travel, 'C6-1', 'train').map((r) => r.rowId)).toEqual([
      's!2',
    ]);
  });

  it('정렬: 수 칸 오름·내림 · 수 없는 줄은 늘 뒤 · 같은 값은 행 번호 차례 · 행 칸·null 은 행 번호 차례', () => {
    const asc = sortRows(rows, { column: 'co2e', direction: 'asc' }, 6);
    expect(asc.map((r) => r.rowId)).toEqual(['s!2', 's!4', 's!1', 's!3']);
    const desc = sortRows(rows, { column: 'share', direction: 'desc' }, 6);
    expect(desc.map((r) => r.rowId)).toEqual(['s!1', 's!4', 's!2', 's!3']);
    const ties = sortRows(rows, { column: 'spendKrw', direction: 'desc' }, 6);
    expect(ties.map((r) => r.rowId)).toEqual(['s!1', 's!2', 's!3', 's!4']);
    expect(sortRows(rows, null, 6)).toEqual(rows);
    expect(sortRows(rows, { column: 'row', direction: 'desc' }, 6)).toEqual(
      rows,
    );
  });

  const ids = (list: readonly ResultRow[]) => list.map((r) => r.rowId);
  const at = (rowId: string | null, co2e: string | null = '1') =>
    row(co2e, purchase('지어낸 묶음 가'), rowId);

  it('기본 차례: 엑셀 줄 → #n · 두 자리 줄은 수로(9 < 10) · 서버 차례가 달라도', () => {
    const shuffled = [
      at('s!10'),
      at('s!9#2'),
      at('s!100'),
      at('s!9'),
      at('s!9#10'),
      at('s!2'),
    ];
    const want = ['s!2', 's!9', 's!9#2', 's!9#10', 's!10', 's!100'];
    expect(ids(sortRows(shuffled, null, 6))).toEqual(want);
    expect(
      ids(sortRows(shuffled, { column: 'row', direction: 'desc' }, 6)),
    ).toEqual(want);
    expect(shuffled[0]!.rowId).toBe('s!10');
  });

  it('행 번호 없는 줄은 뒤 · 그 안은 서버 차례 · 시트 이름의 ! 은 끝만 본다', () => {
    const list = [at('옛-b'), at(null), at('a!b!7'), at('옛-a'), at('s!3')];
    expect(ids(sortRows(list, null, 6))).toEqual([
      's!3',
      'a!b!7',
      '옛-b',
      null,
      '옛-a',
    ]);
  });

  it('수 칸 정렬 뒤 같은 값은 오름·내림 모두 행 번호 차례 · 수 없는 줄끼리도', () => {
    const list = [
      at('s!12', '2'),
      at('s!3', '2'),
      at('s!20', null),
      at('s!4', null),
      at('s!1', '5'),
    ];
    expect(
      ids(sortRows(list, { column: 'co2e', direction: 'asc' }, 9)),
    ).toEqual(['s!3', 's!12', 's!1', 's!4', 's!20']);
    expect(
      ids(sortRows(list, { column: 'co2e', direction: 'desc' }, 9)),
    ).toEqual(['s!1', 's!3', 's!12', 's!4', 's!20']);
  });

  it('쪽은 정렬 뒤: 서버 끝에 있던 작은 행 번호가 첫 쪽으로', () => {
    const list = [
      ...Array.from({ length: PAGE_SIZE }, (_, i) => at(`s!${i + 5}`)),
      at('s!4#2'),
      at('s!4'),
    ];
    const first = pageOf(sortRows(list, null, 6), 1);
    expect(ids(first.rows).slice(0, 3)).toEqual(['s!4', 's!4#2', 's!5']);
  });

  it('쪽: 50 이 한 쪽 · 51 이면 둘째 쪽에 하나 · 범위 밖은 끝으로 · 0 줄도 1 쪽', () => {
    const many = Array.from({ length: PAGE_SIZE + 1 }, (_, i) => i);
    expect(PAGE_SIZE).toBe(50);
    expect(pageOf(many.slice(0, 50), 1)).toMatchObject({
      page: 1,
      pageCount: 1,
    });
    expect(pageOf(many.slice(0, 50), 1).rows).toHaveLength(50);
    expect(pageOf(many, 1).rows).toHaveLength(50);
    expect(pageOf(many, 2)).toEqual({ rows: [50], page: 2, pageCount: 2 });
    expect(pageOf(many, 9).page).toBe(2);
    expect(pageOf(many, 0).page).toBe(1);
    expect(pageOf([], 3)).toEqual({ rows: [], page: 1, pageCount: 1 });
  });
});

describe('categorySheets — 카테고리의 시트(서버 차례) · 일부 실패', () => {
  const done: Scope3Done = {
    status: 'done',
    llmCalls: {},
    sheets: [
      {
        status: 'processed',
        sheet: 'c4-1_x',
        category: 'Category4',
        rows: [row('1'), row('3')],
      },
      { status: 'failed', sheet: 'c4-2_x', category: 'Category4' },
      { status: 'empty', sheet: 'c4-3_x', category: 'Category4' },
      { status: 'other' },
      { status: 'processed', sheet: 'c5_x', category: 'Category5', rows: [] },
      {
        status: 'processed',
        sheet: 'c10_x',
        category: 'Category10',
        rows: [row('1')],
      },
    ],
  };

  it('processed(꼴·시트 합) · failed · empty 를 다 싣고 other 는 0', () => {
    const sheets = categorySheets(done, 'C4');
    expect(sheets.map((s) => s.status)).toEqual([
      'processed',
      'failed',
      'empty',
    ]);
    expect(sheets[0]).toMatchObject({ layout: 'C4-1', total: 4 });
    expect(sheets[1]).toEqual({ status: 'failed', sheet: 'c4-2_x' });
    expect(sheets[2]).toEqual({ status: 'empty', sheet: 'c4-3_x' });
  });

  it('시트 합은 시트마다(카테고리 합 아님) — 같은 카테고리 시트 둘의 비율 분모가 다르다', () => {
    const two: Scope3Done = {
      status: 'done',
      llmCalls: {},
      sheets: [
        {
          status: 'processed',
          sheet: 'c8-1_x',
          category: 'Category8',
          rows: [row('1'), row('1')],
        },
        {
          status: 'processed',
          sheet: 'c8-2_x',
          category: 'Category8',
          rows: [row('3'), row('3')],
        },
      ],
    };
    const sheets = categorySheets(two, 'C8');
    expect(
      sheets.map((s) => (s.status === 'processed' ? s.total : null)),
    ).toEqual([2, 6]);
    const first = sheets[0]!;
    if (first.status !== 'processed') throw new Error('processed 아님');
    expect(cellOf(first.rows[0]!, 'share', first.total)).toMatchObject({
      value: 50,
    });
  });

  it('줄 0 시트의 합은 null · C10 은 0(1차 끔) · 시트 없는 카테고리 0', () => {
    expect(categorySheets(done, 'C5')[0]).toMatchObject({ total: null });
    expect(categorySheets(done, 'C10')).toEqual([]);
    expect(categorySheets(done, 'C1')).toEqual([]);
  });
});

describe('S3-12 창 칸(밴드 S3W4 ① — 발주서 §1-6 표·Q1·Q3~Q7)', () => {
  const groupRow = (
    groupOrigin: 'rule' | 'ai' | 'estimate' | null,
    origin: ResultRow['origin'] = null,
  ): ResultRow => ({
    ...row('1', {
      ...(purchase('지어낸 묶음') as Extract<RowDetail, { shape: 'purchase' }>),
      groupOrigin,
    }),
    origin,
  });
  const wasteDetail = (
    extra: Partial<Extract<RowDetail, { shape: 'activity' }>> = {},
  ) => activity('waste', { hasBiogenic: true, ...extra });
  const eol = (
    extra: Partial<Extract<RowDetail, { shape: 'energy' }>> = {},
  ): RowDetail => ({
    ...(leased as Extract<RowDetail, { shape: 'energy' }>),
    kind: 'product_eol',
    hasBiogenic: true,
    ...extra,
  });

  it('별: group 단계 ai 만 — rule·estimate·단계 없음·줄 origin ai·활동·에너지·basic 은 아니다', () => {
    expect(isAiGroup(groupRow('ai'))).toBe(true);
    expect(isAiGroup(groupRow('rule', 'ai'))).toBe(false);
    expect(isAiGroup(groupRow('estimate', 'ai'))).toBe(false);
    expect(isAiGroup(groupRow(null, 'ai'))).toBe(false);
    expect(isAiGroup({ ...row('1', wasteDetail()), origin: 'ai' })).toBe(false);
    expect(isAiGroup({ ...row('1', eol()), origin: 'ai' })).toBe(false);
    expect(isAiGroup({ ...row('1'), origin: 'ai' })).toBe(false);
  });

  it('여는 칸: C1·C2 그룹명 · C5·C12 이름만 — 다른 칸·다른 시트 0', () => {
    const named = row(
      '1',
      purchase('지어낸 묶음'),
      null,
      inputOf({ name: 'x' }),
    );
    const waste = row('1', wasteDetail(), null, inputOf({ name: 'x' }));
    const product = row('1', eol(), null, inputOf({ name: 'x' }));
    for (const layout of ['C1', 'C2'] as const) {
      expect(opensFactorWindow(named, layout, 'group')).toBe(true);
      expect(opensFactorWindow(named, layout, 'inName')).toBe(false);
    }
    expect(opensFactorWindow(waste, 'C5', 'inName')).toBe(true);
    expect(opensFactorWindow(waste, 'C5', 'treatment')).toBe(false);
    expect(opensFactorWindow(product, 'C12', 'inName')).toBe(true);
    expect(opensFactorWindow(product, 'C12', 'factor')).toBe(false);
    // 갈음(S3W3c1): 넷 밖 꼴도 그 꼴의 여는 칸 하나만 연다 — 아래 스물둘 표.
    for (const layout of SHEET_LAYOUTS)
      for (const column of SHEET_COLUMNS[layout])
        if (column !== openingColumn(layout))
          expect(opensFactorWindow(waste, layout, column)).toBe(false);
    expect(opensFactorWindow(named, 'generic', 'group')).toBe(false);
  });

  it.each([
    ['C1', 'group'],
    ['C2', 'group'],
    ['C3', 'inEnergy'],
    ['C4-1', 'inName'],
    ['C4-2', 'inName'],
    ['C5', 'inName'],
    ['C6-1', 'mode'],
    ['C6-2', 'inVehicle'],
    ['C7', 'mode'],
    ['C8-1', 'inName'],
    ['C8-2', 'inName'],
    ['C8-3', 'inName'],
    ['C9-1', 'inName'],
    ['C9-2', 'inName'],
    ['C11', 'inName'],
    ['C12', 'inName'],
    ['C13-1', 'inName'],
    ['C13-2', 'inName'],
    ['C13-3', 'inName'],
    ['C14', 'inName'],
    ['C15', null],
    ['generic', null],
  ] as const)('입구 %s → %s', (layout, column) => {
    expect(openingColumn(layout)).toBe(column);
  });

  it('입구 칸이 그 꼴 열에 있고 C15 는 inName 이 있어도 안 연다 · leadColumn 과 다른 꼴이 있다', () => {
    const named = row(
      '1',
      wasteDetail({ mode: 'x' }),
      null,
      inputOf({ name: 'x', vehicle: 'x', energy: 'x' }),
    );
    expect(SHEET_COLUMNS.C15).toContain('inName');
    expect(opensFactorWindow(named, 'C15', 'inName')).toBe(false);
    expect(leadColumn('C9-1')).toBe('mode');
    expect(opensFactorWindow(named, 'C9-1', 'mode')).toBe(false);
    expect(opensFactorWindow(named, 'C9-1', 'inName')).toBe(true);
    expect(leadColumn('C4-2')).toBe('inCountry');
    expect(opensFactorWindow(named, 'C4-2', 'inName')).toBe(true);
    expect(opensFactorWindow(named, 'C3', 'inEnergy')).toBe(true);
    expect(opensFactorWindow(named, 'C6-1', 'mode')).toBe(true);
    expect(opensFactorWindow(named, 'C6-2', 'inVehicle')).toBe(true);
  });

  it('창의 출처: 구매 줄은 코드 → 갈래 값, 구매 밖은 시트 글자 그대로(코드표를 타지 않는다)', () => {
    expect(factorWindowOf(row('1', purchase('x')))?.source).toEqual({
      type: 'text',
      text: 'usepa',
    });
    const sheet = { ...factor, source: '지어낸 시트' };
    expect(
      factorWindowOf(row('1', wasteDetail({ factor: sheet })))?.source,
    ).toEqual({ type: 'text', text: '지어낸 시트', raw: true });
    expect(
      factorWindowOf(row('1', { ...leased, factor: null } as RowDetail))
        ?.source,
    ).toEqual({ type: 'text', text: null, raw: true });
  });

  describe('고친 줄(edited)', () => {
    const fixed = (over: Partial<RowFactor> = {}): RowFactor => ({
      choice: 'custom',
      rank: null,
      title: '지어낸 고친 제목',
      value: '1e-05',
      source: 'usepa',
      unit: 'kgCO2e/L',
      co2e: '9',
      biogenicCo2e: null,
      ai: { title: null, value: null, source: null, co2e: null },
      ...over,
    });
    const editedRow = (detail: RowDetail, factorEdit = fixed()): ResultRow => ({
      ...row('1', detail),
      formula: '금액 × 0.1 = 100',
      edited: true,
      factorEdit,
    });

    it('계수·출처 칸은 사건 값이고 출처 글이 코드 이름과 같아도 글 그대로', () => {
      const one = editedRow(purchase('x'));
      expect(cellOf(one, 'factor', null)).toEqual({
        type: 'number',
        value: 0.00001,
        unit: 'kgCO2e/L',
      });
      expect(cellOf(one, 'source', null)).toEqual({
        type: 'text',
        text: 'usepa',
        raw: true,
      });
    });

    it('applied 사건만 있는 줄(edited 아님)은 본문 그대로 · 고름은 쥔다', () => {
      const one: ResultRow = {
        ...row('1', purchase('x')),
        formula: '지어낸 식',
        factorEdit: fixed({ choice: 'applied', value: '9', title: '딴 글' }),
      };
      expect(cellOf(one, 'factor', null)).toMatchObject({ value: 0.25 });
      expect(cellOf(one, 'source', null)).toEqual({
        type: 'text',
        text: 'usepa',
      });
      expect(factorWindowOf(one)?.formula).toBe('지어낸 식');
      expect(one.factorEdit?.choice).toBe('applied');
    });

    it('옛 줄(input 없음) 에너지 칸·입구·검색은 본문 제목 — detail.factor.title 을 덮지 않는다', () => {
      const one = editedRow(leased);
      expect(cellOf(one, 'inEnergy', null)).toEqual({
        type: 'text',
        text: factor.title,
      });
      expect(filterRows([one], 'C3', '고친 제목')).toEqual([]);
      expect(filterRows([one], 'C3', factor.title!)).toEqual([one]);
    });

    it('정렬은 고친 값을 본다', () => {
      const small = editedRow(purchase('가'));
      const plain = row('1', purchase('나'));
      expect(
        sortRows([plain, small], { column: 'factor', direction: 'asc' }, null),
      ).toEqual([small, plain]);
    });

    it('창: 제목·값·출처는 한 벌로 사건 값 · 산식은 null · 구매·활동 둘 다', () => {
      for (const detail of [purchase('x'), wasteDetail()]) {
        const window = factorWindowOf(editedRow(detail))!;
        expect(window.formula).toBeNull();
        expect(window.source).toEqual({
          type: 'text',
          text: 'usepa',
          raw: true,
        });
        expect(window.factor).toEqual({
          title: '지어낸 고친 제목',
          value: { type: 'number', value: 0.00001, unit: 'kgCO2e/L' },
        });
      }
    });
  });

  it('여는 칸: 글이 null·빈 글이거나 basic 줄이면 열지 않는다(critic B2)', () => {
    expect(opensFactorWindow(row('1', wasteDetail()), 'C5', 'inName')).toBe(
      false,
    );
    expect(
      opensFactorWindow(
        row('1', wasteDetail(), null, inputOf({ name: '' })),
        'C5',
        'inName',
      ),
    ).toBe(false);
    expect(
      opensFactorWindow(
        row('1', basic, null, inputOf({ name: 'x' })),
        'C5',
        'inName',
      ),
    ).toBe(false);
    expect(opensFactorWindow(row('1', purchase('')), 'C1', 'group')).toBe(
      false,
    );
  });

  it('C12 만 제품명이 빈 줄도 연다(S3Q2 · sid:MARC-ENT-599) · basic 은 여전히 0 · 다른 꼴 빈 글은 0', () => {
    expect(opensFactorWindow(row('1', wasteDetail()), 'C12', 'inName')).toBe(
      true,
    );
    expect(
      opensFactorWindow(
        row('1', wasteDetail(), null, inputOf({ name: '' })),
        'C12',
        'inName',
      ),
    ).toBe(true);
    expect(
      opensFactorWindow(
        row('1', basic, null, inputOf({ name: '' })),
        'C12',
        'inName',
      ),
    ).toBe(false);
    expect(opensFactorWindow(row('1', wasteDetail()), 'C12', 'factor')).toBe(
      false,
    );
    for (const layout of ['C4-1', 'C4-2', 'C5', 'C9-1'] as const) {
      expect(openingColumn(layout)).toBe('inName');
      expect(
        opensFactorWindow(
          row('1', wasteDetail(), null, inputOf({ name: '' })),
          layout,
          'inName',
        ),
      ).toBe(false);
    }
  });

  it('구매 줄: 기준단위 won · 출처 갈래 · 탄소기원 없음 · 계수 칸은 표 계수 칸과 같다', () => {
    const one: ResultRow = { ...groupRow('ai'), formula: '지어낸 식' };
    expect(factorWindowOf(one)).toEqual({
      aiGroup: true,
      base: { kind: 'won' },
      source: { type: 'text', text: 'usepa' },
      formula: '지어낸 식',
      carbon: null,
      factor: { title: '지어낸 연료', value: cellOf(one, 'factor', null) },
      treatments: null, // S3Q1: 구매 줄은 처리방법 표 없음
    });
    expect(cellOf(one, 'factor', null)).toEqual({
      type: 'number',
      value: 0.25,
      unit: 'kgCO2e/KRW',
    });
  });

  it('출처: manual_title 은 갈래 usepa-estimate · none 은 null', () => {
    expect(
      factorWindowOf(row('1', purchase('x', 'manual_title')))?.source,
    ).toEqual({ type: 'text', text: 'usepa-estimate' });
    expect(factorWindowOf(row('1', purchase('x', 'none')))?.source).toEqual({
      type: 'text',
      text: null,
    });
  });

  it('폐기물 줄: 기준단위 baseUnit → unit · 출처 null · FCF %(0 은 0 — null 아님) · note 글자 그대로', () => {
    const window = (extra: Parameters<typeof wasteDetail>[0]) =>
      factorWindowOf(row('1', wasteDetail(extra)));
    expect(window({ fcf: '0', biogenicNote: '지어낸' })).toMatchObject({
      aiGroup: false,
      base: { kind: 'server', unit: 'kg' },
      source: { type: 'text', text: null, raw: true },
      carbon: { fcf: 0, note: '지어낸' },
    });
    expect(
      window({ activity: { ...amount, unit: 'L', baseUnit: 'kg' } })?.base,
    ).toEqual({ kind: 'server', unit: 'kg' });
    expect(window({ fcf: '0.01' })?.carbon?.fcf).toBeCloseTo(1, 10);
    expect(window({ fcf: null })?.carbon).toEqual({ fcf: null, note: null });
    expect(window({ biogenicNote: '' })?.carbon?.note).toBeNull();
    expect(
      window({
        activity: { ...amount, baseUnit: null, unit: 'L' },
      })?.base,
    ).toEqual({ kind: 'server', unit: 'L' });
    expect(
      window({ activity: { ...amount, baseUnit: null, unit: null } })?.base,
    ).toEqual({ kind: 'server', unit: null });
  });

  it('탄소기원: 생물기원 칸이 없는 줄은 null(값이 다 비어도 칸이 있으면 있다)', () => {
    expect(
      factorWindowOf(row('1', wasteDetail({ hasBiogenic: false })))?.carbon,
    ).toBeNull();
    expect(factorWindowOf(row('1', eol()))?.carbon).toEqual({
      fcf: null,
      note: null,
    });
  });

  it('타이틀: factor.title → 처리방법 → null(에너지 줄은 처리방법 칸 없음)', () => {
    const titled = wasteDetail({ treatment: '지어낸 처리' });
    expect(factorWindowOf(row('1', titled))?.factor?.title).toBe('지어낸 연료');
    const blank = { ...factor, title: '' };
    expect(
      factorWindowOf(
        row('1', {
          ...(purchase('x') as Extract<RowDetail, { shape: 'purchase' }>),
          factor: blank,
        }),
      )?.factor?.title,
    ).toBeNull();
    expect(
      factorWindowOf(
        row('1', wasteDetail({ treatment: '지어낸 처리', factor: blank })),
      )?.factor?.title,
    ).toBe('지어낸 처리');
    const untitled = wasteDetail({
      treatment: '지어낸 처리',
      factor: { ...factor, title: null },
    });
    expect(factorWindowOf(row('1', untitled))?.factor?.title).toBe(
      '지어낸 처리',
    );
    expect(
      factorWindowOf(
        row('1', wasteDetail({ factor: { ...factor, title: null } })),
      )?.factor?.title,
    ).toBeNull();
    expect(
      factorWindowOf(row('1', eol({ factor: { ...factor, title: null } })))
        ?.factor?.title,
    ).toBeNull();
  });

  it('계수 없는 에너지 줄은 factor null · 계수 값 없는 줄은 수 칸 null', () => {
    expect(factorWindowOf(row('1', eol({ factor: null })))?.factor).toBeNull();
    expect(
      factorWindowOf(row('1', eol({ factor: { ...factor, value: null } })))
        ?.factor?.value,
    ).toEqual({ type: 'number', value: null, unit: 'kgCO2e/kg' });
  });

  it('산식: 빈 글·없음은 null · 글은 그대로(수로 바꾸지 않음) · ×1000 0', () => {
    const one = row('1', wasteDetail());
    expect(factorWindowOf({ ...one, formula: '' })?.formula).toBeNull();
    expect(factorWindowOf(one)?.formula).toBeNull();
    expect(factorWindowOf({ ...one, formula: '1 × 2' })?.formula).toBe('1 × 2');
    expect(factorWindowOf(one)?.factor?.value).toMatchObject({ value: 0.25 });
  });

  it('basic 줄은 창 칸이 없다', () => {
    expect(factorWindowOf(row('1'))).toBeNull();
  });
});

describe('S3Q1 C12 처리방법별 표(factorWindowOf().treatments — 값 파일 ② · 발주서 Q6~Q8)', () => {
  const treatments: C12Treatments = {
    branch: 'code',
    shareTotal: '1.0',
    code: '91-01-01',
    parts: [
      { treatment: '매립', share: '0.1', factor: '0.013', used: true },
      { treatment: '소각', share: '0.125', factor: '3.4', used: true },
      { treatment: '재활용', share: null, factor: null, used: false },
    ],
  };
  const eol = (
    over: Partial<C12Treatments> | null = {},
    weighted: string | null = '0.5',
  ): RowDetail => ({
    shape: 'energy',
    kind: 'product_eol',
    activity: amount,
    factor: { ...factor, value: weighted, unit: 'kgCO2eq/kg', title: null },
    buildingTotal: null,
    years: null,
    investment: null,
    fcf: '0.01',
    hasBiogenic: true,
    biogenicNote: null,
    ...(over === null ? {} : { treatments: { ...treatments, ...over } }),
  });
  const c12 = (detail: RowDetail, name: string | null = '지어낸 폐용기') =>
    row('1', detail, 'c12_x!3', inputOf({ name }));

  it('줄 셋은 서버 차례 · 비중은 0~1 → % ×100 하나 · 계수는 상세 표 계수 칸 꼴(같은 단위) · 합계는 서버 shareTotal·줄 가중 계수 그대로', () => {
    const one = c12(eol());
    const table = factorWindowOf(one)!.treatments!;
    expect(table.title).toBe('지어낸 폐용기');
    expect(table.code).toBe('91-01-01');
    expect(table.lines.map((line) => line.treatment)).toEqual([
      '매립',
      '소각',
      '재활용',
    ]);
    expect(table.lines.map((line) => line.share)).toEqual([10, 12.5, null]);
    expect(table.lines.map((line) => line.factor)).toEqual([
      { type: 'number', value: 0.013, unit: 'kgCO2eq/kg' },
      { type: 'number', value: 3.4, unit: 'kgCO2eq/kg' },
      { type: 'number', value: null, unit: 'kgCO2eq/kg' },
    ]);
    expect(table.total).toEqual({
      share: 100,
      factor: cellOf(one, 'factor', null),
    });
  });

  it('웹은 합을 셈하지 않는다 — 서버 shareTotal 이 줄 합과 달라도 그 글자 · 서버가 가중 계수를 안 주면 합계 계수 null', () => {
    const table = factorWindowOf(
      c12(eol({ shareTotal: '0.9' }, null)),
    )!.treatments!;
    expect(table.total.share).toBe(90);
    expect(table.total.factor).toEqual({
      type: 'number',
      value: null,
      unit: 'kgCO2eq/kg',
    });
  });

  it('비중 없는 average 줄 · NaN 줄(390): share 「-」(null) · 합 null', () => {
    const average = factorWindowOf(
      c12(
        eol({
          branch: 'average',
          shareTotal: null,
          parts: treatments.parts.map((p) => ({
            ...p,
            share: null,
            used: false,
          })),
        }),
      ),
    )!.treatments!;
    expect(average.lines.map((line) => line.share)).toEqual([null, null, null]);
    expect(average.total.share).toBeNull();
  });

  it('타이틀(Q8 — e6): 제품명 + 코드 · 제품명이 비면(빈 글 포함) 코드만 · 둘 다 없으면 둘 다 null(화면 「-」)', () => {
    expect(factorWindowOf(c12(eol(), ''))!.treatments).toMatchObject({
      title: null,
      code: '91-01-01',
    });
    expect(
      factorWindowOf(c12(eol({ code: null }), null))!.treatments,
    ).toMatchObject({ title: null, code: null });
    const noInput = { ...c12(eol()), input: null };
    expect(factorWindowOf(noInput)!.treatments!.title).toBeNull();
  });

  it('칸 없는 옛 결과·다른 kind·고친 줄은 null(지금 한 줄 표)', () => {
    expect(factorWindowOf(c12(eol(null)))!.treatments).toBeNull();
    expect(factorWindowOf(row('1', leased))!.treatments).toBeNull();
    const edited: ResultRow = {
      ...c12(eol()),
      edited: true,
      factorEdit: {
        choice: 'custom',
        rank: null,
        title: '지어낸 고친 제목',
        value: '0.3',
        source: '지어낸 출처',
        unit: 'kgCO2eq/kg',
        co2e: '9',
        biogenicCo2e: null,
        ai: { title: null, value: null, source: null, co2e: null },
      },
    };
    expect(factorWindowOf(edited)!.treatments).toBeNull();
  });
});
