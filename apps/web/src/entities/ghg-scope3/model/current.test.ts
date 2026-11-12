// 지금 결과 순수 함수(밴드 S3W3a ②). 값은 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import {
  categorySheets,
  cellOf,
  currentCards,
  currentRunIds,
  overlayResult,
} from './index.ts';
import type {
  ResultRow,
  RowEdit,
  RowFactor,
  Scope3Done,
  Scope3Year,
  YearCategory,
} from './index.ts';

const row = (
  rowId: string | null,
  co2e: string | null,
  biogenic: string | null = null,
): ResultRow => ({
  rowId,
  co2e,
  biogenic,
  origin: null,
  formula: null,
  detail: { shape: 'basic' },
  input: null,
});
const done = (category: string, rows: ResultRow[]): Scope3Done => ({
  status: 'done',
  sheets: [{ status: 'processed', sheet: 's', category, rows }],
  llmCalls: {},
});
const factor = (over: Partial<RowFactor> = {}): RowFactor => ({
  choice: 'custom',
  rank: null,
  title: null,
  value: null,
  source: null,
  unit: null,
  co2e: '9',
  biogenicCo2e: '2',
  ai: { title: null, value: null, source: null, co2e: null },
  ...over,
});
const edit = (over: Partial<RowEdit>): RowEdit => ({
  rowId: 'A!2',
  category: 'C1',
  excluded: false,
  factor: null,
  editedAt: '2026-03-01T00:00:01Z',
  editedBy: null,
  ...over,
});
const overlaid = (body: Scope3Done, rows: RowEdit[]) => {
  const sheet = overlayResult(body, { runId: '9', rows }).sheets[0]!;
  if (sheet.status !== 'processed') throw new Error('시트 꼴');
  return sheet.rows;
};

describe('overlayResult', () => {
  it('계수 사건을 줄에 싣는다: applied 도 쥐고 edited 는 아니며 co2e 는 본문 · 사건 없는 줄·제외만인 줄은 없음', () => {
    const body = done('Category1', [row('A!2', '1'), row('A!3', '2')]);
    const applied = factor({ choice: 'applied', co2e: '1' });
    const [one, two] = overlaid(body, [
      edit({ factor: applied }),
      edit({ rowId: 'A!3', excluded: true }),
    ]);
    expect(one).toMatchObject({ co2e: '1', factorEdit: applied });
    expect(one!.edited).toBeUndefined();
    expect(two).not.toHaveProperty('factorEdit');
  });

  it('덧씌워도 detail 은 본문 그대로다(옛 줄 에너지 칸이 계수 제목으로 물러서니 덮지 않는다)', () => {
    const detail: ResultRow['detail'] = {
      shape: 'energy',
      kind: 'leased_asset',
      activity: { value: '1', unit: 'kg', baseValue: '1', baseUnit: 'kg' },
      factor: { title: '지어낸 원안', value: '1', unit: 'kg', source: null },
      buildingTotal: null,
      years: null,
      investment: null,
      fcf: null,
      hasBiogenic: false,
      biogenicNote: null,
    };
    const body = done('Category1', [{ ...row('A!2', '1'), detail }]);
    const picked = factor({ title: '지어낸 새 제목' });
    expect(overlaid(body, [edit({ factor: picked })])[0]!.detail).toEqual(
      detail,
    );
  });

  it('고친 줄은 사건 값을 쥐고 다른 실행 사건은 붙지 않는다(넘긴 판만 본다)', () => {
    const body = done('Category1', [row('A!2', '1')]);
    const picked = factor();
    expect(overlaid(body, [edit({ factor: picked })])[0]).toMatchObject({
      edited: true,
      factorEdit: picked,
    });
    expect(overlaid(body, [])[0]).not.toHaveProperty('factorEdit');
  });

  it('제외 줄은 표에 남고 표시만 선다(값은 그대로)', () => {
    const [one] = overlaid(done('Category1', [row('A!2', '1')]), [
      edit({ excluded: true }),
    ]);
    expect(one).toMatchObject({ co2e: '1', excluded: true });
    expect(one!.edited).toBeUndefined();
  });

  it.each(['recommended', 'custom'] as const)(
    '%s 는 co2e·biogenic 을 사건 값으로',
    (choice) => {
      const [one] = overlaid(done('Category5', [row('A!2', '1', '0.5')]), [
        edit({ category: 'C5', factor: factor({ choice }) }),
      ]);
      expect(one).toMatchObject({ co2e: '9', biogenic: '2', edited: true });
    },
  );

  it('applied 는 본문 그대로 · edited 아님', () => {
    const picked = factor({ choice: 'applied' });
    const [one] = overlaid(done('Category1', [row('A!2', '1', '0.5')]), [
      edit({ factor: picked }),
    ]);
    // 갈음(S3W3c1): 고름만 factorEdit 으로 쥐고 나머지는 본문 그대로다.
    expect(one).toEqual({ ...row('A!2', '1', '0.5'), factorEdit: picked });
  });

  it('제외 + 계수 둘 다인 줄', () => {
    const [one] = overlaid(done('Category1', [row('A!2', '1')]), [
      edit({ excluded: true, factor: factor() }),
    ]);
    expect(one).toMatchObject({ co2e: '9', excluded: true, edited: true });
  });

  it('고친 값이 null 이면 본문으로 물러서지 않는다(서버 co2e_of 는 None 을 쥐고 합에서 빠진다)', () => {
    const body = overlayResult(
      done('Category5', [row('A!2', '1', '0.5'), row('A!3', '4')]),
      {
        runId: '9',
        rows: [
          edit({
            category: 'C5',
            factor: factor({ co2e: null, biogenicCo2e: null }),
          }),
        ],
      },
    );
    const sheet = categorySheets(body, 'C5')[0]!;
    if (sheet.status !== 'processed') throw new Error('시트 꼴');
    expect(sheet.rows[0]).toMatchObject({
      co2e: null,
      biogenic: null,
      edited: true,
    });
    expect(sheet.total).toBe(4);
  });

  it('rowId null 줄은 본문 그대로(서버 _line_value)', () => {
    const [one] = overlaid(done('Category1', [row(null, '1')]), [
      edit({ excluded: true }),
    ]);
    expect(one).toEqual(row(null, '1'));
  });

  it('짝은 rowId + 카테고리 — 다른 카테고리의 같은 rowId 는 안 붙는다', () => {
    const [one] = overlaid(done('Category1', [row('A!2', '1')]), [
      edit({ category: 'C2', excluded: true }),
    ]);
    expect(one).toEqual(row('A!2', '1'));
  });

  it('C11·C12 처럼 두 자리 번호도 짝이 맞는다(Category1 과 섞이지 않음)', () => {
    const [one] = overlaid(done('Category11', [row('A!2', '1')]), [
      edit({ category: 'C1', excluded: true }),
    ]);
    expect(one!.excluded).toBeUndefined();
    const [two] = overlaid(done('Category11', [row('A!2', '1')]), [
      edit({ category: 'C11', excluded: true }),
    ]);
    expect(two!.excluded).toBe(true);
  });

  it('본문을 고치지 않는다', () => {
    const body = done('Category1', [row('A!2', '1')]);
    const before = structuredClone(body);
    overlayResult(body, { runId: '9', rows: [edit({ factor: factor() })] });
    expect(body).toEqual(before);
  });

  it('실패·빈 시트는 그대로 지난다', () => {
    const body: Scope3Done = {
      status: 'done',
      sheets: [
        { status: 'failed', sheet: 'f', category: 'Category1' },
        { status: 'other' },
      ],
      llmCalls: {},
    };
    expect(overlayResult(body, { runId: '9', rows: [] }).sheets).toEqual(
      body.sheets,
    );
  });
});

describe('제외 줄과 시트 합·비율', () => {
  const body = overlayResult(
    done('Category1', [row('A!2', '1'), row('A!3', '3')]),
    { runId: '9', rows: [edit({ excluded: true })] },
  );

  it('비율 분모에서 빠지고 제외 줄 자신의 칸은 빈 값', () => {
    const sheet = categorySheets(body, 'C1')[0]!;
    if (sheet.status !== 'processed') throw new Error('시트 꼴');
    expect(sheet.total).toBe(3);
    expect(cellOf(sheet.rows[0]!, 'share', sheet.total)).toMatchObject({
      value: null,
    });
    expect(cellOf(sheet.rows[1]!, 'share', sheet.total)).toMatchObject({
      value: 100,
    });
    expect(sheet.rows).toHaveLength(2);
  });

  it('제외 + 고친 줄은 제외가 먼저 — 시트 합에서 빠지고 비율 칸 빈 값', () => {
    const both = overlayResult(
      done('Category1', [row('A!2', '1'), row('A!3', '3')]),
      { runId: '9', rows: [edit({ excluded: true, factor: factor() })] },
    );
    const sheet = categorySheets(both, 'C1')[0]!;
    if (sheet.status !== 'processed') throw new Error('시트 꼴');
    expect(sheet.total).toBe(3);
    expect(cellOf(sheet.rows[0]!, 'share', sheet.total)).toMatchObject({
      value: null,
    });
  });

  it('전부 제외면 합 null · 비율 빈 값', () => {
    const all = overlayResult(done('Category1', [row('A!2', '1')]), {
      runId: '9',
      rows: [edit({ excluded: true })],
    });
    const sheet = categorySheets(all, 'C1')[0]!;
    if (sheet.status !== 'processed') throw new Error('시트 꼴');
    expect(sheet.total).toBeNull();
  });
});

const category = (over: Partial<YearCategory>): YearCategory => ({
  category: 'C1',
  current: { runId: '9', total: '12.5', sheets: 2, failedSheets: 1 },
  locked: false,
  lockedAt: null,
  lockedBy: null,
  editedRows: 0,
  ...over,
});
const yearOf = (categories: YearCategory[]): Scope3Year => ({
  year: 2025,
  baseRunId: '9',
  latest: null,
  categories,
  editedRowsUnlocked: 0,
});

describe('currentCards', () => {
  it('카드 15 · 합·시트 수는 서버 값(본문 합이 아니다) · C10 끔', () => {
    const cards = currentCards(yearOf([category({})]), () =>
      done('Category1', [row('A!2', '999')]),
    );
    expect(cards).toHaveLength(15);
    expect(cards[0]).toMatchObject({
      id: 'C1',
      total: 12.5,
      sheets: 2,
      failedSheets: 1,
      off: false,
    });
    expect(cards[9]).toMatchObject({ id: 'C10', off: true, state: null });
  });

  it('current null·없는 카테고리는 빈 카드 · 수 아닌 합은 null', () => {
    const cards = currentCards(
      yearOf([
        category({ current: null }),
        category({
          category: 'C2',
          current: { runId: '9', total: 'nan', sheets: 1, failedSheets: 0 },
        }),
      ]),
      () => undefined,
    );
    expect(cards[0]).toMatchObject({ total: null, sheets: 0, failedSheets: 0 });
    expect(cards[1]).toMatchObject({ total: null, sheets: 1 });
    expect(cards[2]).toMatchObject({ total: null, state: null });
  });

  it('생물기원 합은 그 카테고리 지금 결과 실행의 덧씌운 줄(제외 뺌·고친 값) · C5·C12 만', () => {
    const body = overlayResult(
      done('Category5', [
        row('A!2', '1', '1'),
        row('A!3', '1', '2'),
        row('A!4', '1', '4'),
      ]),
      {
        runId: '7',
        rows: [
          edit({ rowId: 'A!2', category: 'C5', excluded: true }),
          edit({ rowId: 'A!3', category: 'C5', factor: factor() }),
        ],
      },
    );
    const cards = currentCards(
      yearOf([category({ category: 'C5' }), category({ category: 'C1' })]),
      (id) => (id === '9' ? body : undefined),
    );
    expect(cards[4]).toMatchObject({ hasBiogenic: true, biogenic: 6 });
    expect(cards[0]).toMatchObject({ hasBiogenic: false, biogenic: null });
  });

  it('★ 합이 둘: 서버 정확합과 덧씌운 표 합은 상대 오차 1e-9 안(글자·=== 대조 금지)', () => {
    const body = done('Category1', [row('A!2', '0.1'), row('A!3', '0.2')]);
    const [card] = currentCards(
      yearOf([
        category({
          current: { runId: '9', total: '0.3', sheets: 1, failedSheets: 0 },
        }),
      ]),
      () => body,
    );
    const sheet = categorySheets(body, 'C1')[0]!;
    if (sheet.status !== 'processed') throw new Error('시트 꼴');
    expect(sheet.total).not.toBe(card!.total);
    expect(Math.abs(sheet.total! - card!.total!) / card!.total!).toBeLessThan(
      1e-9,
    );
  });
});

describe('currentRunIds', () => {
  it('서로 다른 값만 · null 빼고', () => {
    expect(
      currentRunIds(
        yearOf([
          category({}),
          category({ category: 'C2' }),
          category({
            category: 'C3',
            current: { runId: '7', total: null, sheets: 0, failedSheets: 0 },
          }),
          category({ category: 'C4', current: null }),
        ]),
      ),
    ).toEqual(['9', '7']);
  });
});
