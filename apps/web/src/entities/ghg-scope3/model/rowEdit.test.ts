// 줄 제외·복구의 셈(밴드 S3W3b): 앞 글 열 꼴 스물둘 · 보낼 줄 섞임 · 고름 · 머리 상태 · 한도. 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import { SHEET_COLUMNS, SHEET_LAYOUTS } from './detail.ts';
import type { SheetLayout } from './detail.ts';
import type { ResultRow } from './result.ts';
import {
  HISTORY_PAGE_SIZE,
  ROW_EDIT_MAX,
  ROW_REASON_MAX,
  leadColumn,
  overRowLimit,
  pick,
  pickState,
  reasonFault,
  rowIdsOf,
  rowsToSend,
} from './rowEdit.ts';

const LEADS: Record<SheetLayout, string> = {
  C1: 'group',
  C2: 'group',
  C3: 'inEnergy',
  'C4-1': 'inName',
  'C4-2': 'inCountry',
  C5: 'inSite',
  'C6-1': 'mode',
  'C6-2': 'inCountry',
  C7: 'mode',
  'C8-1': 'inCountry',
  'C8-2': 'inCountry',
  'C8-3': 'inCountry',
  'C9-1': 'mode',
  'C9-2': 'inCountry',
  C11: 'inName',
  C12: 'inName',
  'C13-1': 'inCountry',
  'C13-2': 'inCountry',
  'C13-3': 'inCountry',
  C14: 'inCountry',
  C15: 'inName',
  generic: 'row',
};

/** 제외 칸은 덧판이 제외한 줄에만 있다(없으면 산정에 든 줄). */
const row = (rowId: string | null, excluded?: true) =>
  ({ rowId, ...(excluded ? { excluded } : {}) }) as ResultRow;

describe('leadColumn', () => {
  it('꼴 스물둘을 빠짐없이 적었다', () => {
    expect(Object.keys(LEADS).sort()).toEqual(
      [...SHEET_LAYOUTS, 'generic'].sort(),
    );
    expect(Object.keys(SHEET_COLUMNS)).toHaveLength(22);
  });

  it.each(Object.entries(LEADS))('%s → %s', (layout, column) => {
    expect(leadColumn(layout as SheetLayout)).toBe(column);
  });
});

describe('rowsToSend', () => {
  const rows = [
    row('a!2'),
    row('a!3', true),
    row('b!2'),
    row(null),
    row('b!3', true),
  ];
  const chosen = new Set(['a!2', 'a!3', 'b!3']);

  it('섞어 고르면 단추마다 해당 줄만', () => {
    expect(rowsToSend(rows, chosen, 'exclude')).toEqual(['a!2']);
    expect(rowsToSend(rows, chosen, 'restore')).toEqual(['a!3', 'b!3']);
  });

  it('안 고른 줄·rowId 없는 줄은 나가지 않고 겹침이 없다', () => {
    const out = rowsToSend(rows, new Set(['b!2', 'b!2']), 'exclude');
    expect(out).toEqual(['b!2']);
    expect(rowsToSend(rows, new Set(), 'exclude')).toEqual([]);
  });
});

describe('고름', () => {
  it('rowIdsOf 는 rowId 없는 줄을 뺀다', () => {
    expect(rowIdsOf([row('a!2'), row(null)])).toEqual(['a!2']);
  });

  it('pick 은 새 모음을 내고 앞 모음을 건드리지 않는다', () => {
    const before = new Set(['a!2']);
    expect([...pick(before, ['a!3'], true)]).toEqual(['a!2', 'a!3']);
    expect([...pick(before, ['a!2'], false)]).toEqual([]);
    expect([...before]).toEqual(['a!2']);
  });

  it('pickState: 없음·일부·전부, 다른 쪽 고름은 세지 않는다', () => {
    const ids = ['a!2', 'a!3'];
    expect(pickState(new Set(['z!9']), ids)).toBe(false);
    expect(pickState(new Set(['a!2']), ids)).toBe('indeterminate');
    expect(pickState(new Set(ids), ids)).toBe(true);
    expect(pickState(new Set(), [])).toBe(false);
  });
});

describe('한도', () => {
  it('서버 한도 값', () => {
    expect(ROW_EDIT_MAX).toBe(2000);
    expect(ROW_REASON_MAX).toBe(300);
    expect(HISTORY_PAGE_SIZE).toBe(20);
  });

  it('2,000 은 지나고 2,001 은 막힌다', () => {
    const ids = (count: number) =>
      Array.from({ length: count }, (_, i) => `a!${i}`);
    expect(overRowLimit(ids(2000))).toBe(false);
    expect(overRowLimit(ids(2001))).toBe(true);
  });

  it('사유: 빈칸만 · 앞뒤 빈칸 걷음 · 300·301자 · 코드 포인트로 셈', () => {
    expect(reasonFault('   ')).toBe('required');
    expect(reasonFault('')).toBe('required');
    expect(reasonFault('가'.repeat(300))).toBeNull();
    expect(reasonFault(`  ${'가'.repeat(300)}  `)).toBeNull();
    expect(reasonFault('가'.repeat(301))).toBe('tooLong');
    expect(reasonFault('😀'.repeat(300))).toBeNull();
  });
});
