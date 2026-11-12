// 밴드 TRW8 ④: 문체를 바꿔도 고른 항목에 머물 자리(samePairIn). 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import { samePairIn } from './pdfSame.ts';
import type { PdfPageView, PdfPair } from './pdfView.ts';

const pair = (unit: number, rest: Partial<PdfPair> = {}): PdfPair => ({
  unit,
  kind: 'block',
  unitKind: 'block',
  visual: false,
  source: ['지어낸 글'],
  translation: ['Made-up'],
  ...rest,
});
const viewOf = (pairs: PdfPair[]): PdfPageView => ({
  page: 3,
  width: 595,
  height: 842,
  imageOnly: false,
  boxes: [],
  pairs,
  places: pairs.length,
  warnings: [],
  unplaced: [],
});
const grid = (cells: [number, number][]) => ({
  rows: 2,
  cols: 2,
  cells: cells.map(([row, col]) => ({
    row,
    col,
    source: '값',
    translation: 'value',
  })),
});

describe('samePairIn (TRW8 ④)', () => {
  it('같은 unit · 같은 member → 그 항목', () => {
    const view = viewOf([
      pair(0, { member: 0 }),
      pair(1, { member: 0 }),
      pair(1, { member: 1 }),
    ]);
    expect(samePairIn(view, pair(1, { member: 1 }), null)).toEqual({
      pair: 2,
      cell: null,
    });
  });

  it('블록(member) → 묶음(member 없음): 같은 unit 의 묶음 · 묶음 → 블록: 같은 unit 첫 항목', () => {
    const grouped = viewOf([
      pair(0, { kind: 'group' }),
      pair(1, { kind: 'group' }),
    ]);
    expect(samePairIn(grouped, pair(1, { member: 2 }), null)).toEqual({
      pair: 1,
      cell: null,
    });
    const blocks = viewOf([
      pair(0, { member: 0 }),
      pair(1, { member: 0 }),
      pair(1, { member: 1 }),
    ]);
    expect(samePairIn(blocks, pair(1, { kind: 'group' }), null)).toEqual({
      pair: 1,
      cell: null,
    });
    // member 가 새 쪽에 없으면 같은 unit 첫 항목.
    expect(samePairIn(blocks, pair(1, { member: 5 }), null)).toEqual({
      pair: 1,
      cell: null,
    });
  });

  it('표 칸: 새 항목 격자에 같은 행·열이 있으면 유지 · 없거나 격자가 없으면 버림', () => {
    const cell = { row: 1, col: 1 };
    const kept = viewOf([
      pair(4, {
        kind: 'table',
        grid: grid([
          [0, 0],
          [1, 1],
        ]),
      }),
    ]);
    expect(samePairIn(kept, pair(4, { kind: 'table' }), cell)).toEqual({
      pair: 0,
      cell,
    });
    const missing = viewOf([pair(4, { kind: 'table', grid: grid([[0, 0]]) })]);
    expect(samePairIn(missing, pair(4, { kind: 'table' }), cell)).toEqual({
      pair: 0,
      cell: null,
    });
    const whole = viewOf([pair(4, { kind: 'table' })]);
    expect(samePairIn(whole, pair(4, { kind: 'table' }), cell)).toEqual({
      pair: 0,
      cell: null,
    });
  });

  it('새 쪽에 그 unit 이 없으면 null', () => {
    expect(
      samePairIn(viewOf([pair(0)]), pair(7, { member: 0 }), null),
    ).toBeNull();
    expect(samePairIn(viewOf([]), pair(0), null)).toBeNull();
  });
});
