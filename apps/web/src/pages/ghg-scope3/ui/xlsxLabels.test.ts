// S3-15 데이터 엑셀의 표시 글·열 차례 대조(밴드 S3D1 ② — critic M1·R1·R5 · 감독 C0 6 처분 · 발주서 P13).
// 서버 apps/api-py/esgapi/inventory/tools/scope3_xlsx_labels.json 이 엑셀 머리·값 글자의 원천이다. 그 글자가 화면 상수·셈과 같아야 한다 —
// 어느 쪽이든 열·머리·수단 이름표·출처 글·단위 앞붙임을 바꾸면 여기서 빨갛다(머리뿐 아니라 값 글자도).
// 출처 코드(SOURCE_KINDS)·생물기원 카테고리(BIOGENIC_CARDS)는 상수끼리 깊은 같음(양쪽 — 웹이 코드를 더해도 빨강, 검증 W1).
// model 공개 표면에 없는 상수(TEXT_COLUMNS·LAYOUT_BY_KIND·INPUT_COLUMNS·FACTOR_NUMERATOR)는 공개 셈(cellOf·layoutOf)의 동작으로 잰다.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  ACTIVITY_KINDS,
  BIOGENIC_CARDS,
  ENERGY_KINDS,
  INPUT_KEYS,
  ROW_KINDS,
  SHEET_COLUMNS,
  SHEET_LAYOUTS,
  SOURCE_KINDS,
  cellOf,
  layoutOf,
} from '../../../entities/ghg-scope3/model/index.ts';
import type {
  ColumnId,
  ResultRow,
  SheetLayout,
} from '../../../entities/ghg-scope3/model/index.ts';
import { cellText, headerOf, rawSourceText } from './detailText.ts';
import { EMISSION_UNIT } from './emission.ts';

interface Labels {
  emissionUnit: string;
  factorNumerator: string;
  layouts: string[];
  sheetLayouts: Record<string, string[]>;
  layoutByKind: Record<string, Record<string, string>>;
  textColumns: string[];
  inputColumns: Record<string, string>;
  inputKeys: string[];
  activityKinds: string[];
  energyKinds: string[];
  columns: Record<string, string>;
  sheetColumns: Record<string, Record<string, string>>;
  sourceKinds: Record<string, string>;
  sourceBooks: Record<string, string>;
  sourceSheets: Record<string, string>;
  sourcePurchasePrefix: string;
  modeLabels: Record<string, string>;
  modeOther: string;
  biogenicCategories: string[];
}

const labels = JSON.parse(
  readFileSync(
    resolve(
      import.meta.dirname,
      '../../../../../api-py/esgapi/inventory/tools/scope3_xlsx_labels.json',
    ),
    'utf-8',
  ),
) as Labels;
const words = S3_TEXT.detail;
const LAYOUTS: SheetLayout[] = [...SHEET_LAYOUTS, 'generic'];

const basicRow = (over: Partial<ResultRow> = {}): ResultRow => ({
  rowId: null,
  co2e: null,
  biogenic: null,
  origin: null,
  formula: null,
  detail: { shape: 'basic' },
  input: null,
  ...over,
});

/** 서버 header_of 와 같은 규칙(JSON 의 글로) — 화면 headerOf 와 견준다. */
const serverHeader = (layout: string, column: string) => {
  const bySheet =
    layout === 'generic' ? {} : (labels.sheetColumns[layout] ?? {});
  const name = bySheet[column] ?? labels.columns[column]!;
  return ['co2e', 'biogenic'].includes(column) ?
      `${name}(${labels.emissionUnit})`
    : name;
};

describe('scope3_xlsx_labels.json ↔ 화면 상수', () => {
  it('열 차례(시트 꼴 21 + generic)와 꼴 이름', () => {
    expect(labels.layouts).toStrictEqual([...SHEET_LAYOUTS]);
    expect(labels.sheetLayouts).toStrictEqual(SHEET_COLUMNS);
  });

  it('머리 글: 공통 글 · 시트별 글 · 배출량 단위 — 꼴마다 열마다 화면 headerOf 와 같다', () => {
    expect(labels.columns).toStrictEqual(words.columns);
    expect(labels.sheetColumns).toStrictEqual(words.sheetColumns);
    expect(labels.emissionUnit).toBe(EMISSION_UNIT);
    for (const layout of LAYOUTS)
      for (const column of SHEET_COLUMNS[layout])
        expect([layout, column, serverHeader(layout, column)]).toStrictEqual([
          layout,
          column,
          headerOf(layout, column),
        ]);
  });

  it('줄 kind·입력 키(서버 detailOf·inputOf 의 닫힌 목록)', () => {
    expect(labels.inputKeys).toStrictEqual([...INPUT_KEYS]);
    expect(labels.activityKinds).toStrictEqual([...ACTIVITY_KINDS]);
    expect(labels.energyKinds).toStrictEqual([...ENERGY_KINDS]);
  });

  it('kind → 시트 꼴(layoutOf 의 둘째 갈래 — 앞머리 못 읽는 시트 이름)', () => {
    for (const kind of ROW_KINDS)
      for (let n = 1; n <= 15; n += 1) {
        const category = `Category${n}`;
        const row = basicRow({
          detail: { shape: 'activity', kind } as ResultRow['detail'],
        });
        expect([kind, category, layoutOf('x', category, [row])]).toStrictEqual([
          kind,
          category,
          labels.layoutByKind[kind]?.[category] ?? 'generic',
        ]);
      }
  });

  it('입력 열 → input 키 · 글 칸 목록(cellOf 가 읽는 자리)', () => {
    const input = Object.fromEntries(
      INPUT_KEYS.map((key, index) => [key, String(index + 1)]),
    ) as ResultRow['input'];
    const columns = Object.keys(words.columns) as ColumnId[];
    const found: Record<string, string> = {};
    const texts: string[] = [];
    for (const column of columns) {
      const cell = cellOf(basicRow({ input }), column, null);
      const value = cell.type === 'text' ? Number(cell.text) : cell.value;
      if (value) found[column] = INPUT_KEYS[value - 1]!;
      if (cell.type === 'text' && column !== 'row' && column !== 'source')
        texts.push(column);
    }
    expect(found).toStrictEqual(labels.inputColumns);
    expect(texts.sort()).toStrictEqual([...labels.textColumns].sort());
  });

  it('값 글자: 출처 코드 → 책 이름 · 고친 출처 글 · 계수 단위 앞붙임', () => {
    expect(labels.sourceKinds).toStrictEqual(SOURCE_KINDS);
    expect(labels.sourceBooks).toStrictEqual(words.sourceBooks);
    expect(labels.sourceSheets).toStrictEqual(words.sourceSheets);
    expect(labels.sourcePurchasePrefix).toBe(words.sourcePurchasePrefix);
    const purchase = (source: string) =>
      basicRow({
        detail: {
          shape: 'purchase',
          kind: 'purchase',
          groupName: '가상',
          groupOrigin: null,
          spendKrw: null,
          factor: { title: null, value: '1', unit: 'kg', source },
          recommendations: [],
        },
      });
    for (const [code, kind] of Object.entries(labels.sourceKinds)) {
      const cell = cellOf(purchase(code), 'source', null);
      expect([code, cell.type === 'text' ? cell.text : null]).toStrictEqual([
        code,
        kind,
      ]);
      expect(cellText(cell, 'source')).toBe(labels.sourceBooks[kind]);
    }
    expect(cellOf(purchase('none'), 'source', null)).toStrictEqual({
      type: 'text',
      text: null,
    });
    for (const [sheet, shown] of Object.entries(labels.sourceSheets))
      expect(rawSourceText(sheet)).toBe(shown);
    expect(rawSourceText(`${labels.sourcePurchasePrefix} 가상 열`)).toBe(
      labels.sourceBooks.usepa,
    );
    const factor = cellOf(purchase('none'), 'factor', null);
    expect(factor).toStrictEqual({
      type: 'number',
      value: 1,
      unit: `${labels.factorNumerator}/kg`,
    });
  });

  it('생물기원 열·합을 두는 카테고리(C5·C12)', () => {
    expect(labels.biogenicCategories).toStrictEqual([...BIOGENIC_CARDS]);
  });

  it('값 글자: 수단 이름표 · 모르는 코드는 「기타」', () => {
    expect(labels.modeLabels).toStrictEqual(words.modeLabels);
    expect(labels.modeOther).toBe(words.modeOther);
    for (const [code, shown] of Object.entries(labels.modeLabels))
      expect(cellText({ type: 'text', text: code }, 'mode')).toBe(shown);
    expect(cellText({ type: 'text', text: '가상_모름' }, 'mode')).toBe(
      labels.modeOther,
    );
  });
});
