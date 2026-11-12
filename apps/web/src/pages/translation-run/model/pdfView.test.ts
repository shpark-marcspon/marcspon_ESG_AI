// PDF 보기 순수 셈(밴드 TRW6 ③ S3): level 여섯 · 표 칸/테두리 · bbox null 칸 · visual · imageOnly · unplaced · 경고 여섯·문체 · 쪽 목록 셈.
// 값은 전부 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import type {
  LayoutUnit,
  PlacedUnit,
  TranslationLayout,
} from '../../../entities/translation/model/index.ts';
import {
  looseWarningsOf,
  pdfPageLinesOf,
  pdfPageOf,
  stageOf,
  variantLabelsOf,
} from './pdfView.ts';

const box = (y: number) => [50, y, 500, y + 20] as const;
const member = (id: string, y: number, source: string) => ({
  id,
  key: null,
  kind: 'paragraph' as const,
  bbox: box(y),
  source,
});

/** 한 쪽(12)에 상자 종류 전부 + 그림뿐 쪽(13). */
function layout(
  levels: Partial<Record<number, PlacedUnit['level']>> = {},
  extra: Partial<TranslationLayout> = {},
): TranslationLayout {
  const units: LayoutUnit[] = [
    {
      tag: 'BLOCK 1',
      page: 12,
      kind: 'block',
      members: [member('b1', 10, '제목 글'), member('b2', 40, '본문 글')],
    },
    {
      tag: 'BLOCK 2',
      page: 12,
      kind: 'block',
      members: [member('g1', 80, '묶음 앞'), member('g2', 110, '묶음 뒤')],
    },
    {
      tag: 'TABLE 1',
      page: 12,
      kind: 'table',
      members: [{ ...member('t1', 150, '| 구분 | 값 |'), kind: 'table' }],
      cells: [
        { row: 0, col: 0, id: 't1:r0c0', bbox: box(152), source: '구분' },
        { row: 0, col: 1, id: 't1:r0c1', bbox: null, source: '값' },
      ],
      rows: [0],
    },
    {
      tag: 'VISUAL 1',
      page: 12,
      kind: 'visual',
      members: [member('v1', 200, '그림 속 글')],
    },
    {
      tag: null,
      page: 12,
      kind: 'footer',
      members: [member('f1', 800, '꼬리 글')],
    },
    {
      tag: 'BLOCK 3',
      page: 12,
      kind: 'block',
      members: [member('m1', 300, '빠진 글')],
    },
  ];
  const placed = (label: 'A' | 'B'): PlacedUnit[] => [
    {
      tag: 'BLOCK 1',
      page: 12,
      level: levels[0] ?? 'block',
      translations: [`Title ${label}`, `Body ${label}`],
    },
    {
      tag: 'BLOCK 2',
      page: 12,
      level: levels[1] ?? 'group',
      translations: [`Merged ${label}`],
    },
    {
      tag: 'TABLE 1',
      page: 12,
      level: levels[2] ?? 'cell',
      translations: null,
      cells: [
        { row: 0, col: 0, text: `Item ${label}` },
        { row: 0, col: 1, text: `Value ${label}` },
      ],
    },
    {
      tag: 'VISUAL 1',
      page: 12,
      level: 'block',
      translations: [`Figure ${label}`],
    },
    { tag: null, page: 12, level: 'source_only', translations: null },
    { tag: 'BLOCK 3', page: 12, level: 'missing', translations: null },
  ];
  return {
    status: 'done',
    pages: [
      { page: 12, width: 595, height: 842, textLayer: 'present' },
      { page: 13, width: 595, height: 842, textLayer: 'none' },
    ],
    units,
    variants: [
      {
        label: 'A',
        stage: 'autofix',
        units: placed('A'),
        unplaced: [{ page: 12, text: 'Stray A' }],
      },
      { label: 'B', stage: 'translated', units: placed('B'), unplaced: [] },
    ],
    skipped: { emptyTables: [], imageOnlyPages: [13] },
    warnings: [],
    ...extra,
  };
}

describe('pdfPageOf — 상자·짝', () => {
  it('level 여섯: block 은 member 마다, group·table 테두리는 하나, cell 은 bbox 있는 칸만, source_only·missing 은 member 마다', () => {
    const view = pdfPageOf(layout(), 'A', 12);
    expect(view.boxes.map((b) => [b.id, b.look])).toEqual([
      ['b1', 'block'],
      ['b2', 'block'],
      ['g1#group', 'group'],
      ['t1#cell', 'table_border'],
      ['t1:r0c0', 'cell'],
      ['v1', 'block'],
      ['f1', 'source_only'],
      ['m1', 'missing'],
    ]);
    // group 상자는 member 둘을 감싼다.
    expect(view.boxes[2]!.bbox).toEqual([50, 80, 500, 130]);
    // 번역 N곳 = 번역이 붙은 단위(block·group·cell·visual) 넷.
    expect(view.places).toBe(4);
  });

  it('누름 → 짝: block 은 member ↔ 번역 j, group 은 원문 둘 ↔ 번역, 표는 짝 하나(칸 상자도 그 짝 · 칸 글 전부 + 격자)', () => {
    const view = pdfPageOf(layout(), 'A', 12);
    const pairOf = (id: string) =>
      view.pairs[view.boxes.find((b) => b.id === id)!.pair]!;
    expect(pairOf('b2')).toMatchObject({
      kind: 'block',
      source: ['본문 글'],
      translation: ['Body A'],
    });
    expect(pairOf('g1#group')).toMatchObject({
      kind: 'group',
      source: ['묶음 앞', '묶음 뒤'],
      translation: ['Merged A'],
    });
    // 밴드 TRW7 ③b-2(sid:MARC-ENT-488): 칸 짝 따로 0 — 칸 상자도 표 짝을 가리키고 어느 칸인지는 상자의 cell.
    expect(pairOf('t1:r0c0')).toBe(pairOf('t1#cell'));
    expect(view.boxes.find((b) => b.id === 't1:r0c0')!.cell).toEqual({
      row: 0,
      col: 0,
    });
    expect(view.boxes.find((b) => b.id === 't1#cell')!.cell).toBeUndefined();
    expect(pairOf('t1#cell')).toMatchObject({
      kind: 'table',
      translation: ['Item A', 'Value A'],
      grid: {
        rows: 1,
        cols: 2,
        cells: [
          { row: 0, col: 0, source: '구분', translation: 'Item A' },
          { row: 0, col: 1, source: '값', translation: 'Value A' },
        ],
      },
    });
    expect(view.pairs.some((pair) => pair.kind === 'cell')).toBe(false);
    expect(pairOf('v1').visual).toBe(true);
    expect(pairOf('f1')).toMatchObject({
      kind: 'source_only',
      unitKind: 'footer',
      translation: null,
    });
    expect(pairOf('m1')).toMatchObject({ kind: 'missing', translation: null });
  });

  it('표 격자(ENT-488): 원문 빈 칸은 둘 다 비움 · 번역 칸이 없거나 빈 글이면 원문 값 · 짝 수는 표 하나', () => {
    const base = layout();
    const units = base.units.map((unit, i) =>
      i === 2 ?
        {
          ...unit,
          cells: [
            { row: 0, col: 0, id: 't1:r0c0', bbox: box(152), source: '구분' },
            { row: 0, col: 1, id: 't1:r0c1', bbox: box(152), source: '2025' },
            { row: 1, col: 0, id: 't1:r1c0', bbox: box(172), source: '' },
            { row: 1, col: 1, id: 't1:r1c1', bbox: box(172), source: '배출' },
          ],
        }
      : unit,
    );
    const variants = base.variants.map((v) => ({
      ...v,
      units: v.units.map((u, i) =>
        i === 2 ?
          {
            ...u,
            cells: [
              { row: 0, col: 0, text: 'Item' },
              { row: 0, col: 1, text: ' ' },
              { row: 1, col: 0, text: 'Stray' },
            ],
          }
        : u,
      ),
    }));
    const view = pdfPageOf({ ...base, units, variants }, 'A', 12);
    const table = view.boxes.filter((b) => b.unit === 2);
    expect(table.map((b) => b.look)).toEqual([
      'table_border',
      'cell',
      'cell',
      'cell',
      'cell',
    ]);
    expect(new Set(table.map((b) => b.pair)).size).toBe(1);
    expect(view.pairs.filter((pair) => pair.unit === 2)).toHaveLength(1);
    expect(view.pairs[table[0]!.pair]!.grid).toEqual({
      rows: 2,
      cols: 2,
      cells: [
        { row: 0, col: 0, source: '구분', translation: 'Item' },
        { row: 0, col: 1, source: '2025', translation: '2025' },
        { row: 1, col: 0, source: '', translation: '' },
        { row: 1, col: 1, source: '배출', translation: '배출' },
      ],
    });
  });

  it('table level(칸을 못 맞춤): 칸 상자 없이 표 전체 하나, 짝 번역은 translations', () => {
    const view = pdfPageOf(
      {
        ...layout({ 2: 'table' }),
        variants: layout({ 2: 'table' }).variants.map((v) => ({
          ...v,
          units: v.units.map((u, i) =>
            i === 2 ? { ...u, cells: undefined, translations: ['Table'] } : u,
          ),
        })),
      },
      'A',
      12,
    );
    const table = view.boxes.filter((b) => b.unit === 2);
    expect(table.map((b) => b.look)).toEqual(['table']);
    expect(view.pairs[table[0]!.pair]!.translation).toEqual(['Table']);
    expect(view.pairs[table[0]!.pair]!.grid).toBeUndefined();
  });

  it('문체 탭을 바꾸면 그 문체의 level·번역으로 다시 셈', () => {
    const both = layout();
    const changed: TranslationLayout = {
      ...both,
      variants: [
        both.variants[0]!,
        {
          ...both.variants[1]!,
          units: both.variants[1]!.units.map((u, i) =>
            i === 1 ? { ...u, level: 'block', translations: ['X', 'Y'] } : u,
          ),
        },
      ],
    };
    expect(pdfPageOf(changed, 'A', 12).boxes[2]!.look).toBe('group');
    const b = pdfPageOf(changed, 'B', 12);
    expect(b.boxes.filter((x) => x.unit === 1).map((x) => x.look)).toEqual([
      'block',
      'block',
    ]);
    expect(b.pairs[b.boxes[0]!.pair]!.translation).toEqual(['Title B']);
  });

  it('imageOnly 쪽은 상자·짝 0 · unplaced 는 그 문체·그 쪽 것만', () => {
    const image = pdfPageOf(layout(), 'A', 13);
    expect(image.imageOnly).toBe(true);
    expect(image.boxes).toEqual([]);
    expect(image.pairs).toEqual([]);
    expect(pdfPageOf(layout(), 'A', 12).unplaced).toEqual(['Stray A']);
    expect(pdfPageOf(layout(), 'B', 12).unplaced).toEqual([]);
  });

  it('imageOnly 쪽에 단위가 있어도(서버가 실어 보냄) 상자·짝 0', () => {
    const base = layout();
    const strayUnit: LayoutUnit = {
      tag: 'BLOCK 9',
      page: 13,
      kind: 'block',
      members: [member('x1', 10, '그림 위 글')],
    };
    const withStray: TranslationLayout = {
      ...base,
      units: [...base.units, strayUnit],
      variants: base.variants.map((v) => ({
        ...v,
        units: [
          ...v.units,
          { tag: 'BLOCK 9', page: 13, level: 'block', translations: ['X'] },
        ],
      })),
    };
    const view = pdfPageOf(withStray, 'A', 13);
    expect(view.boxes).toEqual([]);
    expect(view.places).toBe(0);
  });

  // 검증 권고 R8: 쪽 거름이 빠지면 다른 쪽 unplaced 가 이 쪽에 섞인다.
  it('unplaced 는 그 쪽 것만 — 다른 쪽(13·14)의 것은 12 에 안 나온다', () => {
    const base = layout();
    const spread: TranslationLayout = {
      ...base,
      variants: base.variants.map((v) =>
        v.label === 'A' ?
          {
            ...v,
            unplaced: [
              { page: 13, text: 'Elsewhere 13' },
              { page: 12, text: 'Stray A' },
              { page: 14, text: 'Elsewhere 14' },
            ],
          }
        : v,
      ),
    };
    expect(pdfPageOf(spread, 'A', 12).unplaced).toEqual(['Stray A']);
    expect(pdfPageOf(spread, 'A', 14).unplaced).toEqual(['Elsewhere 14']);
  });

  // 검증 권고 R9: imageOnlyPages 에 없어도 textLayer none 인 쪽은 글자 없는 쪽.
  it('textLayer none 쪽(imageOnlyPages 에 없음)도 상자·짝 0 · 쪽 목록 imageOnly', () => {
    const base = layout();
    const noText: TranslationLayout = {
      ...base,
      pages: [
        ...base.pages,
        { page: 14, width: 595, height: 842, textLayer: 'none' },
      ],
      units: [
        ...base.units,
        {
          tag: 'BLOCK 8',
          page: 14,
          kind: 'block',
          members: [member('n1', 10, '글자 없는 쪽 글')],
        },
      ],
      variants: base.variants.map((v) => ({
        ...v,
        units: [
          ...v.units,
          { tag: 'BLOCK 8', page: 14, level: 'block', translations: ['N'] },
        ],
      })),
    };
    expect(noText.skipped.imageOnlyPages).not.toContain(14);
    const view = pdfPageOf(noText, 'A', 14);
    expect(view.imageOnly).toBe(true);
    expect(view.boxes).toEqual([]);
    expect(view.pairs).toEqual([]);
    expect(
      pdfPageLinesOf(noText, 'A').find((line) => line.page === 14)?.imageOnly,
    ).toBe(true);
  });

  it('거절(variants 빈 목록)이면 상자 0', () => {
    const rejected = { ...layout(), status: 'rejected' as const, variants: [] };
    expect(pdfPageOf(rejected, 'A', 12).boxes).toEqual([]);
    expect(variantLabelsOf(rejected)).toEqual([]);
  });
});

describe('경고·쪽 목록', () => {
  const warned = layout(
    {},
    {
      warnings: [
        { code: 'tag_missing', page: 12, tag: 'BLOCK 3', variant: 'B' },
        { code: 'tag_shift', page: 12, tag: 'BLOCK 1', variant: 'A' },
        { code: 'tag_shift', page: 12, tag: 'BLOCK 1', variant: 'B' },
        { code: 'tag_extra', page: 12, tag: null, variant: 'B' },
        { code: 'length_ratio', page: 12, tag: 'BLOCK 2', variant: null },
        { code: 'image_only_page', page: 13, tag: null, variant: null },
        { code: 'page_missing', page: null, tag: null, variant: 'B' },
      ],
    },
  );

  it('경고 여섯: 고른 문체 것만 · tag 가 맞으면 그 상자 ⚠ · 한 문체에만이면 only', () => {
    const b = pdfPageOf(warned, 'B', 12);
    expect(b.warnings.map((w) => [w.code, w.only, w.unit])).toEqual([
      ['tag_missing', 'B', 5],
      ['tag_shift', null, 0],
      ['tag_extra', 'B', null],
      ['length_ratio', null, 1],
    ]);
    expect(b.boxes.filter((x) => x.warned).map((x) => x.id)).toEqual([
      'b1',
      'b2',
      'g1#group',
      'm1',
    ]);
    const a = pdfPageOf(warned, 'A', 12);
    expect(a.warnings.map((w) => w.code)).toEqual([
      'tag_shift',
      'length_ratio',
    ]);
    // 그림뿐 경고는 문체와 상관없다.
    expect(pdfPageOf(warned, 'A', 13).warnings.map((w) => w.code)).toEqual([
      'image_only_page',
    ]);
  });

  it('page null 경고는 쪽에 매이지 않는다(짝 칸 위 한 줄)', () => {
    expect(looseWarningsOf(warned, 'B').map((w) => w.code)).toEqual([
      'page_missing',
    ]);
    expect(looseWarningsOf(warned, 'A')).toEqual([]);
  });

  it('쪽 목록: 번역 N곳 · 확인할 곳 N · 「스타일 B 에서만」은 그 쪽 경고가 다 한 문체일 때', () => {
    expect(pdfPageLinesOf(warned, 'B')).toEqual([
      { page: 12, imageOnly: false, places: 4, checks: 4, only: null },
      { page: 13, imageOnly: true, places: 0, checks: 1, only: null },
    ]);
    const onlyB = layout(
      {},
      {
        warnings: [
          { code: 'tag_missing', page: 12, tag: 'BLOCK 3', variant: 'B' },
        ],
      },
    );
    expect(pdfPageLinesOf(onlyB, 'B')[0]!.only).toBe('B');
    expect(pdfPageLinesOf(onlyB, 'A')[0]!.checks).toBe(0);
  });

  it('짝 칸 머리 stage 두 글의 열쇠', () => {
    expect(stageOf(warned, 'A')).toBe('autofix');
    expect(stageOf(warned, 'B')).toBe('translated');
  });
});
