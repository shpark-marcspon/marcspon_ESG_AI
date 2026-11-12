// 온실가스 풀 model(밴드 W12-0b1 ② — 발주서 §3 6): columnsOf·firstPath · factorDraft(가스 일곱 줄·켠 줄만 글자·순발열량 끔 null) ·
//   validateFactor(필수·켠 가스 ≥1·0 초과 Decimal 글자·순발열량 켬) · facilityChanged(판 [저장] 흐림) · 잎 본문.
import { describe, expect, it } from 'vitest';

import { fakePoolOptions } from '../api/testing.ts';
import {
  columnsOf,
  customFactorFormOf,
  emptyFactorForm,
  facilityChanged,
  facilityFormOf,
  facilitySaveDraft,
  factorDraft,
  factorFormOf,
  factorUnitOf,
  firstPath,
  isPositiveDecimal,
  sameFactorForm,
  validateFacility,
  validateFactor,
} from './index.ts';
import type { FactorForm, PoolFacility, PoolNode } from './index.ts';

const options = fakePoolOptions();
const GASES = options.gases;

const node = (
  id: string,
  level: PoolNode['level'],
  parentId: string | null,
  sortOrder = Number(id),
): PoolNode => ({
  id,
  level,
  name: `n${id}`,
  parentId,
  sortOrder,
  childCount: 0,
  facilityCode: null,
  facilityCodeId: null,
});

const NODES: PoolNode[] = [
  node('2', 'scope', null, 1),
  node('1', 'scope', null, 1),
  node('3', 'source_type', '1'),
  node('4', 'source_type', '2'),
  node('5', 'activity', '3'),
  node('6', 'facility', '5'),
  node('7', 'facility', '5'),
];

describe('columnsOf · firstPath', () => {
  it('열 0 = 부모 없는 범위(sortOrder → id) · 열 i = 고른 길의 자식 · 길이 없으면 빈 열', () => {
    expect(columnsOf(NODES, []).map((c) => c.map((n) => n.id))).toEqual([
      ['1', '2'],
      [],
      [],
      [],
    ]);
    expect(
      columnsOf(NODES, ['1', '3', '5']).map((c) => c.map((n) => n.id)),
    ).toEqual([['1', '2'], ['3'], ['5'], ['6', '7']]);
  });

  it('firstPath: 왼쪽부터 첫 항목 — 배출활동까지(잎은 고르지 않음) · 고른 것이 있으면 그대로 · 사라지면 그 열부터 첫 항목', () => {
    expect(firstPath(NODES, [])).toEqual(['1', '3', '5']);
    expect(firstPath(NODES, ['2'])).toEqual(['2', '4']);
    expect(firstPath(NODES, ['1', '3', '5', '7'])).toEqual([
      '1',
      '3',
      '5',
      '7',
    ]);
    expect(firstPath(NODES, ['9', '3'])).toEqual(['1', '3', '5']);
    expect(firstPath(NODES, ['1', '3', '5', '99'])).toEqual(['1', '3', '5']);
  });
});

const filled = (): FactorForm => ({
  ...emptyFactorForm(options),
  name: ' 지어낸 계수 ',
  source: '지어낸 출처',
  baseYear: '2024',
  tier: '2',
  countryCode: 'KR',
  industryCode: 'other',
  inputKind: 'volume',
  inputUnit: 'kL',
  gases: {
    ...emptyFactorForm(options).gases,
    CO2: { enabled: true, factor: '74100.000', gwp: '1' },
    CH4: { enabled: true, factor: '3.0', gwp: '28' },
  },
});

describe('factorDraft', () => {
  it('가스 일곱 줄(옵션 차례) — 켠 줄만 factor·gwp 글자 그대로, 끈 줄은 {gas, enabled:false} · 순발열량 끔 → ncv·ncvUnit null', () => {
    const body = factorDraft(filled(), GASES);
    expect(body.gases).toEqual([
      { gas: 'CO2', enabled: true, factor: '74100.000', gwp: '1' },
      { gas: 'CH4', enabled: true, factor: '3.0', gwp: '28' },
      { gas: 'N2O', enabled: false },
      { gas: 'HFCs', enabled: false },
      { gas: 'PFCs', enabled: false },
      { gas: 'SF6', enabled: false },
      { gas: 'NF3', enabled: false },
    ]);
    expect(typeof body.gases[0]!.factor).toBe('string');
    expect(body).toMatchObject({
      name: '지어낸 계수',
      baseYear: 2024,
      tier: 2,
      ncvEnabled: false,
      ncv: null,
      ncvUnit: null,
      inputUnit: { kind: 'volume', unit: 'kL' },
      emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
      factorUnit: null,
    });
  });

  it('순발열량 켬 → ncvEnabled true + 값 글자·단위', () => {
    const body = factorDraft(
      {
        ...filled(),
        ncvEnabled: true,
        ncv: '35.30',
        ncvKind: 'energy',
        ncvUnit: 'MJ',
      },
      GASES,
    );
    expect(body).toMatchObject({
      ncvEnabled: true,
      ncv: '35.30',
      ncvUnit: { kind: 'energy', unit: 'MJ' },
    });
  });
});

describe('validateFactor', () => {
  it('빈 판 → 필수 칸 차례 + 켠 가스 0', () => {
    expect(
      validateFactor(emptyFactorForm(options), GASES).map(([f]) => f),
    ).toEqual([
      'name',
      'source',
      'baseYear',
      'tier',
      'countryCode',
      'industryCode',
      'inputUnit',
      'gases',
    ]);
  });

  it('채운 판은 지남 · 켠 줄의 0·음수·지수·빈 칸 → 그 칸', () => {
    expect(validateFactor(filled(), GASES)).toEqual([]);
    const bad = filled();
    bad.gases.CO2 = { enabled: true, factor: '0.000', gwp: '1e3' };
    bad.gases.CH4 = { enabled: true, factor: '-1', gwp: '' };
    expect(validateFactor(bad, GASES)).toEqual([
      ['gases.CO2.factor', 'number'],
      ['gases.CO2.gwp', 'number'],
      ['gases.CH4.factor', 'number'],
      ['gases.CH4.gwp', 'required'],
    ]);
  });

  it('순발열량 켬이면 값(0 초과)·단위 필수 · 끄면 보지 않음', () => {
    const on = { ...filled(), ncvEnabled: true };
    expect(validateFactor(on, GASES)).toEqual([
      ['ncv', 'required'],
      ['ncvUnit', 'required'],
    ]);
    expect(
      validateFactor(
        { ...on, ncv: '0', ncvKind: 'energy', ncvUnit: 'MJ' },
        GASES,
      ),
    ).toEqual([['ncv', 'number']]);
    expect(validateFactor({ ...filled(), ncv: 'x' }, GASES)).toEqual([]);
  });

  it('isPositiveDecimal: 글자 그대로(정수 18·소수 12자리, 지수·부호 없음, 0 초과)', () => {
    expect(isPositiveDecimal('0.0001')).toBe(true);
    expect(isPositiveDecimal('123456789012345678.123456789012')).toBe(true);
    expect(isPositiveDecimal('1234567890123456789')).toBe(false);
    expect(isPositiveDecimal('0')).toBe(false);
    expect(isPositiveDecimal('1e3')).toBe(false);
    expect(isPositiveDecimal('+1')).toBe(false);
    expect(isPositiveDecimal('１')).toBe(false);
  });
});

const FACILITY: PoolFacility = {
  id: '20',
  parentId: '5',
  facilityCodeId: '1',
  facilityCode: 'F0001',
  facilityName: '지어낸 보일러',
  unit: { kind: 'volume', unit: 'kL' },
  tooltip: '툴팁',
  factors: [
    {
      id: '21',
      name: 'a',
      inputUnit: { kind: 'volume', unit: 'kL' },
      isDefault: true,
      sortOrder: 1,
      version: 1,
    },
    {
      id: '23',
      name: 'b',
      inputUnit: { kind: 'volume', unit: 'kL' },
      isDefault: false,
      sortOrder: 2,
      version: 3,
    },
  ],
};

describe('자산/시설 판', () => {
  it('facilityChanged: 고친 것이 없으면 거짓 · 칸 하나·기본 토글만 바꿔도 참', () => {
    const before = facilityFormOf(FACILITY);
    expect(facilityChanged(before, { ...before })).toBe(false);
    expect(facilityChanged(before, { ...before, tooltip: '툴팁 ' })).toBe(true);
    expect(facilityChanged(before, { ...before, defaultFactorId: '23' })).toBe(
      true,
    );
    expect(facilityChanged(before, { ...before, unit: 'L' })).toBe(true);
  });

  it('facilitySaveDraft: 기본은 바뀌었을 때만 싣는다 · 필수 검사', () => {
    const before = facilityFormOf(FACILITY);
    expect(before.defaultFactorId).toBe('21');
    expect(facilitySaveDraft(before, before)).toEqual({
      facilityCodeId: '1',
      unit: { kind: 'volume', unit: 'kL' },
      tooltip: '툴팁',
      defaultFactorId: null,
    });
    expect(
      facilitySaveDraft(before, { ...before, defaultFactorId: '23' })
        .defaultFactorId,
    ).toBe('23');
    expect(validateFacility({ ...before, facilityCodeId: '' })).toBe(
      'facilityCodeId',
    );
    expect(validateFacility({ ...before, unit: '' })).toBe('unit');
    expect(validateFacility(before)).toBeNull();
  });
});

describe('계수 판 읽기', () => {
  it('S12-03a customFactorFormOf: 저장된 직접입력 계수 → 판 → factorDraft 가 값을 글자 그대로 · 배출량 단위는 빈 판 기본 · 안 실린 가스는 끔', () => {
    const custom = {
      customId: '7',
      name: '지어낸 직접 계수',
      source: '지어낸 직접 출처',
      baseYear: 2024,
      tier: 2,
      countryCode: 'KR',
      industryCode: 'other',
      inputUnit: { kind: 'volume', unit: 'kL' },
      ncvEnabled: true,
      ncv: '36.1',
      ncvUnit: { kind: 'energy', unit: 'MJ' },
      factorUnit: 'kgGHG/TJ',
      gases: [{ gas: 'CO2', enabled: true, factor: '1.25', gwp: '1' }],
      note: '지어낸 비고',
      isCustom: true,
    };
    const form = customFactorFormOf(custom, options);
    const empty = emptyFactorForm(options);
    expect(form.emissionKind).toBe(empty.emissionKind);
    expect(form.emissionUnit).toBe(empty.emissionUnit);
    expect(Object.keys(form.gases)).toStrictEqual(Object.keys(empty.gases));
    for (const gas of GASES.filter((one) => one !== 'CO2'))
      expect(form.gases[gas]).toStrictEqual(empty.gases[gas]);
    expect(factorDraft(form, GASES)).toStrictEqual({
      name: '지어낸 직접 계수',
      source: '지어낸 직접 출처',
      baseYear: 2024,
      tier: 2,
      countryCode: 'KR',
      industryCode: 'other',
      inputUnit: { kind: 'volume', unit: 'kL' },
      emissionUnit: { kind: empty.emissionKind, unit: empty.emissionUnit },
      ncvEnabled: true,
      ncv: '36.1',
      ncvUnit: { kind: 'energy', unit: 'MJ' },
      factorUnit: 'kgGHG/TJ',
      note: '지어낸 비고',
      gases: GASES.map((gas) =>
        gas === 'CO2' ?
          { gas, enabled: true, factor: '1.25', gwp: '1' }
        : { gas, enabled: false },
      ),
    });
    // 순발열량 끈 계수 — 칸은 빈 글자(null 아님).
    const off = customFactorFormOf(
      { ...custom, ncvEnabled: false, ncv: null, ncvUnit: null },
      options,
    );
    expect([off.ncvEnabled, off.ncv, off.ncvKind, off.ncvUnit]).toStrictEqual([
      false,
      '',
      '',
      '',
    ]);
    expect(sameFactorForm(form, customFactorFormOf(custom, options))).toBe(
      true,
    );
  });

  it('factorFormOf → factorDraft 는 받은 값을 글자 그대로 돌려준다 · 계수 단위 머리', () => {
    const form = factorFormOf(
      {
        id: '21',
        facilityNodeId: '20',
        version: 2,
        versions: [1, 2],
        name: 'a',
        source: 's',
        baseYear: 2020,
        tier: 3,
        countryCode: 'KR',
        industryCode: 'other',
        inputUnit: { kind: 'volume', unit: 'kL' },
        emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
        ncvEnabled: true,
        ncv: '35.3',
        ncvUnit: { kind: 'energy', unit: 'MJ' },
        factorUnit: 'kg/TJ',
        gases: GASES.map((gas) => ({
          gas,
          enabled: gas === 'N2O',
          factor: gas === 'N2O' ? '0.6' : null,
          gwp: gas === 'N2O' ? '265' : null,
        })),
        note: '',
        isDefault: true,
        sortOrder: 1,
      },
      options,
    );
    expect(factorDraft(form, GASES)).toMatchObject({
      baseYear: 2020,
      tier: 3,
      ncv: '35.3',
      factorUnit: 'kg/TJ',
      gases: expect.arrayContaining([
        { gas: 'N2O', enabled: true, factor: '0.6', gwp: '265' },
      ]),
    });
    expect(factorUnitOf(form, options)).toBe('kg/TJ');
    expect(factorUnitOf(emptyFactorForm(options), options)).toBe(
      options.defaults.factorUnitWithoutNcv,
    );
    expect(
      factorUnitOf({ ...emptyFactorForm(options), ncvEnabled: true }, options),
    ).toBe(options.defaults.factorUnitWithNcv);
  });
});
