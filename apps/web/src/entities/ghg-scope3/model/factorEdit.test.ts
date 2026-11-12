// 줄 계수 수정의 셈(밴드 S3W3c2 ①): 값 규칙 표 · 제목·출처 코드 포인트 · 같은 고름 · 막힘 차례 · 처음 고름 · 십진 글자 · 보낼 입력 · 순위. 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import type { RowFactor } from './current.ts';
import {
  FACTOR_TEXT_MAX,
  aiRowOf,
  customFaults,
  decimalText,
  factorBlock,
  factorInput,
  factorTextFault,
  factorValueFault,
  initialCustom,
  initialPick,
  recommendable,
  recommendationsOf,
  sameFactorPick,
} from './factorEdit.ts';
import type { ResultRow, RowDetail } from './result.ts';

const factor = {
  title: '지어낸 연료',
  value: '0.25',
  unit: 'kgCO2e/kg',
  source: '지어낸 시트',
};
const amount = { value: '10', unit: 'kg', baseValue: '10', baseUnit: 'kg' };
const activity = (
  kind: 'waste' | 'commute' = 'commute',
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
const energy = (
  kind: 'product_eol' | 'leased_asset',
  cells: typeof factor | null = factor,
): RowDetail => ({
  shape: 'energy',
  kind,
  activity: amount,
  factor: cells,
  buildingTotal: null,
  years: null,
  investment: null,
  fcf: null,
  hasBiogenic: kind === 'product_eol',
  biogenicNote: null,
});
const purchase = (
  recommendations: Extract<
    RowDetail,
    { shape: 'purchase' }
  >['recommendations'] = [],
): RowDetail => ({
  shape: 'purchase',
  kind: 'purchase',
  groupName: '지어낸 그룹',
  groupOrigin: null,
  spendKrw: '1000',
  factor: { ...factor, unit: 'kgCO2e/KRW', source: 'db_keyword' },
  recommendations,
});
const row = (
  detail: RowDetail = activity(),
  over: Partial<ResultRow> = {},
): ResultRow => ({
  rowId: 's!3',
  co2e: '1',
  biogenic: null,
  origin: null,
  formula: null,
  detail,
  input: null,
  ...over,
});
const event = (over: Partial<RowFactor> = {}): RowFactor => ({
  choice: 'custom',
  rank: null,
  title: '지어낸 고친 제목',
  value: '1e-05',
  source: '지어낸 고친 출처',
  unit: 'kgCO2e/kg',
  co2e: '9',
  biogenicCo2e: null,
  ai: { title: '지어낸 연료', value: '0.25', source: '지어낸 시트', co2e: '1' },
  ...over,
});
const empty = { title: '', value: '', source: '' };

describe('factorValueFault — 서버 _check_value 표', () => {
  it.each([
    ['1', null],
    ['0.5', null],
    ['12.0000000001', null],
    ['123456789012345', null],
    ['', 'required'],
    ['   ', 'required'],
    ['0', 'notPositive'],
    ['0.0', 'notPositive'],
    ['-1', 'notPositive'],
    ['1e3', 'notPositive'],
    ['1,000', 'notPositive'],
    ['.5', 'notPositive'],
    ['5.', 'notPositive'],
    [' 5', 'notPositive'],
    ['+5', 'notPositive'],
    ['１', 'notPositive'],
    ['1.00000000001', 'decimals'],
    [`1${'0'.repeat(400)}`, 'notPositive'],
  ])('%j → %s', (text, fault) => {
    expect(factorValueFault(text)).toBe(fault);
  });
});

describe('factorTextFault — 걷고 1~200 코드 포인트', () => {
  it('200 은 받고 201 은 거절 · 아스트랄 글자는 하나로 센다', () => {
    expect(factorTextFault('가'.repeat(FACTOR_TEXT_MAX))).toBeNull();
    expect(factorTextFault('가'.repeat(FACTOR_TEXT_MAX + 1))).toBe('tooLong');
    // 「𝟙」 은 .length 2 — 코드 포인트 200 개는 받는다.
    expect(factorTextFault('𝟙'.repeat(FACTOR_TEXT_MAX))).toBeNull();
    expect(factorTextFault('𝟙'.repeat(FACTOR_TEXT_MAX + 1))).toBe('tooLong');
  });
  it('빈칸만은 required · 앞뒤 빈칸은 걷고 센다', () => {
    expect(factorTextFault('  ')).toBe('required');
    expect(factorTextFault(` ${'가'.repeat(FACTOR_TEXT_MAX)} `)).toBeNull();
  });
  it('customFaults 는 셋을 따로 본다', () => {
    expect(customFaults({ title: '', value: '0', source: '가' })).toEqual({
      title: 'required',
      value: 'notPositive',
    });
    expect(customFaults({ title: '가', value: '1', source: '가' })).toEqual({});
  });
});

describe('decimalText — 지수 꼴을 십진 글자로', () => {
  it.each([
    ['1e-05', '0.00001'],
    ['2.5e-09', '0.0000000025'],
    ['3.0', '3'],
    ['0.125', '0.125'],
    ['12', '12'],
  ])('%s → %s', (text, out) => {
    expect(decimalText(text)).toBe(out);
  });
  it('1e21 이상은 펴지 않고 받은 글자 · 수가 아니면 받은 글자 · null 은 빈 글', () => {
    expect(decimalText('1e+21')).toBe('1e+21');
    expect(decimalText('nan')).toBe('nan');
    expect(decimalText(null)).toBe('');
  });
});

describe('처음 고름(C1)', () => {
  it('사건 없음·applied → 적용 · recommended → 그 순위 · custom → 직접입력 값 채움', () => {
    expect(initialPick(row())).toEqual({ choice: 'applied' });
    expect(
      initialPick(row(undefined, { factorEdit: event({ choice: 'applied' }) })),
    ).toEqual({ choice: 'applied' });
    expect(
      initialPick(
        row(purchase(), {
          factorEdit: event({ choice: 'recommended', rank: 3 }),
        }),
      ),
    ).toEqual({ choice: 'recommended', rank: 3 });
    const custom = row(undefined, { factorEdit: event() });
    expect(initialPick(custom)).toEqual({ choice: 'custom' });
    expect(initialCustom(custom)).toEqual({
      title: '지어낸 고친 제목',
      value: '0.00001',
      source: '지어낸 고친 출처',
    });
    expect(initialCustom(row())).toEqual(empty);
  });
});

describe('sameFactorPick — 얼린 사진으로(C10)', () => {
  it('사건 없으면 적용만 같다', () => {
    expect(sameFactorPick(row(), { choice: 'applied' }, empty)).toBe(true);
    expect(sameFactorPick(row(), { choice: 'custom' }, empty)).toBe(false);
  });
  it('applied 사건은 사건 없음과 같다', () => {
    const one = row(undefined, { factorEdit: event({ choice: 'applied' }) });
    expect(sameFactorPick(one, { choice: 'applied' }, empty)).toBe(true);
  });
  it('recommended 는 순위로', () => {
    const one = row(purchase(), {
      factorEdit: event({ choice: 'recommended', rank: 2 }),
    });
    expect(sameFactorPick(one, { choice: 'recommended', rank: 2 }, empty)).toBe(
      true,
    );
    expect(sameFactorPick(one, { choice: 'recommended', rank: 1 }, empty)).toBe(
      false,
    );
    expect(sameFactorPick(one, { choice: 'applied' }, empty)).toBe(false);
  });
  it('custom 은 걷은 제목·출처와 parseNumber 값 — 「1e-05」 와 「0.00001」 은 같다', () => {
    const one = row(undefined, { factorEdit: event() });
    const draft = {
      title: ' 지어낸 고친 제목 ',
      value: '0.00001',
      source: '지어낸 고친 출처',
    };
    expect(sameFactorPick(one, { choice: 'custom' }, draft)).toBe(true);
    expect(
      sameFactorPick(one, { choice: 'custom' }, { ...draft, title: '딴 제목' }),
    ).toBe(false);
    // 출처만 바뀌어도 다르다(V4).
    expect(
      sameFactorPick(
        one,
        { choice: 'custom' },
        { ...draft, source: '딴 출처' },
      ),
    ).toBe(false);
    expect(
      sameFactorPick(one, { choice: 'custom' }, { ...draft, value: '0.00002' }),
    ).toBe(false);
    expect(
      sameFactorPick(one, { choice: 'custom' }, { ...draft, value: '' }),
    ).toBe(false);
  });
});

describe('factorBlock — 잠김 → C12 → 계수 없음 → 보낼 줄 없음', () => {
  const open = { locked: false, seen: '9' };
  it('차례 하나만', () => {
    expect(
      factorBlock(row(energy('product_eol'), { rowId: null }), {
        locked: true,
        seen: null,
      }),
    ).toBe('locked');
    expect(
      factorBlock(row(energy('product_eol', null), { rowId: null }), open),
    ).toBe('c12');
    expect(factorBlock(row(energy('leased_asset', null)), open)).toBe(
      'noFactor',
    );
    expect(
      factorBlock(
        row(activity('commute', { factor: { ...factor, unit: null } })),
        open,
      ),
    ).toBe('noFactor');
    expect(factorBlock(row(undefined, { rowId: null }), open)).toBe('noTarget');
    expect(factorBlock(row(), { locked: false, seen: null })).toBe('noTarget');
    expect(factorBlock(row(), open)).toBeNull();
  });
  it('C12 는 줄 kind 로 — 시트 이름이 아니다 · 제외 줄은 막지 않는다(C13)', () => {
    expect(factorBlock(row(activity('waste')), open)).toBeNull();
    expect(factorBlock(row(energy('product_eol')), open)).toBe('c12');
    expect(factorBlock(row(undefined, { excluded: true }), open)).toBeNull();
  });
});

describe('추천 순위 = 배열 자리 + 1', () => {
  it('값 null 자리는 못 고르고 뒤 순위는 밀리지 않는다 · 5 순위부터는 못 고른다', () => {
    const items = [
      { title: '지어낸 하나', value: null, expectedCo2e: null },
      { title: '지어낸 둘', value: '0.5', expectedCo2e: '2' },
    ];
    expect(recommendable(items[0]!, 1)).toBe(false);
    expect(recommendable(items[1]!, 2)).toBe(true);
    expect(recommendable(items[1]!, 5)).toBe(false);
    expect(recommendationsOf(row(purchase(items)))).toBe(items);
    expect(recommendationsOf(row(activity('waste')))).toEqual([]);
  });
});

describe('factorInput — 걷은 제목·출처, 입력 글자 그대로 값', () => {
  it('세 갈래', () => {
    expect(factorInput('s!3', { choice: 'applied' }, empty, '사유')).toEqual({
      rowId: 's!3',
      reason: '사유',
      choice: 'applied',
    });
    expect(
      factorInput('s!3', { choice: 'recommended', rank: 2 }, empty, '사유'),
    ).toEqual({ rowId: 's!3', reason: '사유', choice: 'recommended', rank: 2 });
    expect(
      factorInput(
        's!3',
        { choice: 'custom' },
        { title: ' 제목 ', value: '0.50', source: '\t출처 ' },
        '사유',
      ),
    ).toEqual({
      rowId: 's!3',
      reason: '사유',
      choice: 'custom',
      custom: { title: '제목', value: '0.50', source: '출처' },
    });
  });
});

describe('aiRowOf — 적용 칸은 AI 원안', () => {
  it('고친 줄은 edited 를 뗀다 · 안 고친 줄은 그대로', () => {
    const edited = row(undefined, { edited: true, factorEdit: event() });
    expect(aiRowOf(edited).edited).toBe(false);
    const plain = row();
    expect(aiRowOf(plain)).toBe(plain);
  });
});
