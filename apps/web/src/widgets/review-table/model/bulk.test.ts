import { describe, expect, it } from 'vitest';

import { applyBulk, describeSkip, skippedCount } from './bulk.ts';
import { NO_FILTER, matchesFilter } from './filter.ts';
import { parseTableInput } from './input.ts';
import { summarize } from './summary.ts';
import { candidate, makeRow } from './testing.ts';

const rows = [
  makeRow({ id: 'pending' }),
  makeRow({ id: 'accepted', status: 'accepted' }),
  makeRow({
    id: 'edited-waiting',
    status: 'edited',
    edit: { candidateId: 'b', emission: null, recalcPending: true },
  }),
  makeRow({
    id: 'edited-done',
    status: 'edited',
    edit: { candidateId: 'b', emission: 250, recalcPending: false },
  }),
  makeRow({ id: 'no-candidate', candidates: [] }),
  makeRow({ id: 'finalized', status: 'finalized' }),
  makeRow({
    id: 'no-emission',
    status: 'accepted',
    candidates: [candidate('x', null)],
  }),
];
const allIds = rows.map((row) => row.id);

describe('일괄 동작', () => {
  it('일괄 최종 확정: 되는 행만 바꾸고, 건너뛴 행을 까닭별로 센다', () => {
    const result = applyBulk(rows, allIds, { type: 'finalize' });
    expect(result.changed.map((row) => row.id)).toEqual([
      'accepted',
      'edited-done',
    ]);
    expect(result.changed.every((row) => row.status === 'finalized')).toBe(
      true,
    );
    expect(result.skipped).toEqual([
      { error: 'not_allowed', status: 'pending', count: 2 }, // 검토대기 둘(후보 없는 행 포함): 반영을 거쳐야 한다
      { error: 'recalc_pending', status: 'edited', count: 1 },
      { error: 'not_allowed', status: 'finalized', count: 1 }, // 이미 확정
      { error: 'no_emission', status: 'accepted', count: 1 },
    ]);
    expect(skippedCount(result)).toBe(5);
    expect(result.changed.length + skippedCount(result)).toBe(allIds.length);
    expect(describeSkip(result.skipped[1]!)).toBe(
      '수정 1개: 재계산을 기다리는 중이다.',
    );
  });

  it('일괄 반영: 후보 없는 행을 건너뛴다', () => {
    const result = applyBulk(rows, allIds, { type: 'accept' });
    expect(result.changed.map((row) => row.id)).toEqual([
      'pending',
      'edited-waiting',
      'edited-done',
    ]);
    expect(result.skipped).toContainEqual({
      error: 'no_candidate',
      status: 'pending',
      count: 1,
    });
  });

  it('대상이 아닌 행은 같은 객체로 남고, 순서가 그대로다', () => {
    const result = applyBulk(rows, ['accepted'], { type: 'finalize' });
    expect(result.rows.map((row) => row.id)).toEqual(allIds);
    expect(
      result.rows
        .filter((row, index) => row !== rows[index])
        .map((row) => row.id),
    ).toEqual(['accepted']);
    expect(rows[1]!.status).toBe('accepted');
  });

  it('없는 id 는 missing 으로 센다', () => {
    expect(
      applyBulk(rows, ['accepted', '없는 행'], { type: 'finalize' }),
    ).toMatchObject({ missing: 1, changed: [{ id: 'accepted' }] });
  });
});

describe('요약', () => {
  it('최종확정 행만 결과 합계(tCO2eq — 입력 하나에 단위 하나라 행끼리 같은 단위)에 든다. 반영·수정은 임시 합계에 따로 든다', () => {
    const summary = summarize(rows);
    expect(summary.total).toBe(7);
    expect(summary.byStatus).toEqual({
      pending: 2,
      accepted: 2,
      declined: 0,
      edited: 2,
      rerequested: 0,
      rejected: 0,
      finalized: 1,
    });
    expect(summary.finalTotal).toBe(100); // finalized 한 행
    expect(summary.provisionalTotal).toBe(100 + 250); // accepted(100) + edited-done(250). 재계산 대기와 배출량 없는 행은 빠진다
    expect(summary.recalcPending).toBe(1);
  });

  it('확정하면 임시 합계에서 결과 합계로 옮겨 간다', () => {
    const after = summarize(applyBulk(rows, allIds, { type: 'finalize' }).rows);
    expect(after.finalTotal).toBe(100 + 100 + 250);
    expect(after.provisionalTotal).toBe(0);
  });

  it('수정한 행은 원본값이 아니라 재계산한 값으로 든다', () => {
    const row = makeRow({
      status: 'finalized',
      edit: { candidateId: 'b', emission: 250, recalcPending: false },
    });
    expect(summarize([row]).finalTotal).toBe(250);
  });
});

describe('걸러 보기', () => {
  const row = makeRow({
    raw: { itemName: '강판 A', quantity: 40 },
    status: 'accepted',
  });
  it('상태, 카테고리, 글자를 모두 만족해야 한다', () => {
    expect(matchesFilter(row, NO_FILTER)).toBe(true);
    expect(
      matchesFilter(row, { ...NO_FILTER, statuses: ['accepted', 'edited'] }),
    ).toBe(true);
    expect(matchesFilter(row, { ...NO_FILTER, statuses: ['pending'] })).toBe(
      false,
    );
    expect(matchesFilter(row, { ...NO_FILTER, category: '가' })).toBe(true);
    expect(matchesFilter(row, { ...NO_FILTER, category: '나' })).toBe(false);
    expect(matchesFilter(row, { ...NO_FILTER, text: '강판 a' })).toBe(true); // 자료는 대문자 A: 대소문자를 가리지 않는다
    expect(matchesFilter(row, { ...NO_FILTER, text: '강판 A' })).toBe(true);
    expect(matchesFilter(row, { ...NO_FILTER, text: '계수 A' })).toBe(true); // 자료는 소문자 a, 찾는 글자가 대문자
    expect(matchesFilter(row, { ...NO_FILTER, text: '계수 a' })).toBe(true); // 지금 후보의 계수 이름
    expect(
      matchesFilter(row, {
        statuses: ['accepted'],
        category: '가',
        text: '없는 글자',
      }),
    ).toBe(false);
  });
  it('카테고리는 수정한 값으로 견준다', () => {
    const edited = {
      ...row,
      edit: { category: '나', emission: null, recalcPending: false },
    };
    expect(matchesFilter(edited, { ...NO_FILTER, category: '나' })).toBe(true);
    expect(matchesFilter(edited, { ...NO_FILTER, category: '가' })).toBe(false);
  });
});

describe('입력 검증', () => {
  const valid = () => ({
    version: 2,
    unit: 'tCO2eq',
    categories: ['가'],
    rows: [
      {
        id: 'r1',
        raw: { itemName: '품목', quantity: 3 },
        ai: { category: '가', candidates: [candidate('a')] },
        review: { status: 'pending' },
      },
    ],
  });
  const errorsOf = (raw: unknown) => {
    const result = parseTableInput(raw);
    return result.ok ? [] : result.errors;
  };

  it('맞는 자료는 행으로 바뀐다', () => {
    const result = parseTableInput(valid());
    expect(result.ok && result.input.rows[0]).toEqual({
      id: 'r1',
      raw: { itemName: '품목', quantity: 3 },
      ai: { category: '가', candidates: [candidate('a')] },
      edit: null,
      status: 'pending',
    });
  });
  it('저장돼 있던 수정값은 재계산이 끝난 것으로 읽는다', () => {
    const raw = valid();
    raw.rows[0]!.review = {
      status: 'edited',
      edit: { category: '나', emission: 5 },
    } as never;
    const result = parseTableInput(raw);
    expect(result.ok && result.input.rows[0]!.edit).toEqual({
      category: '나',
      emission: 5,
      recalcPending: false,
    });
  });
  it('틀린 자료는 까닭을 돌려준다', () => {
    expect(errorsOf({ ...valid(), version: 3 })[0]).toContain('version');
    const twice = valid();
    twice.rows.push(twice.rows[0]!);
    expect(errorsOf(twice)[0]).toContain('둘 이상');
    const rejected = valid();
    rejected.rows[0]!.review = { status: 'rejected' };
    expect(errorsOf(rejected)[0]).toContain('사유가 없다');
    const acceptedWithEdit = valid();
    acceptedWithEdit.rows[0]!.review = {
      status: 'accepted',
      edit: { category: '나', emission: 1 },
    } as never;
    expect(errorsOf(acceptedWithEdit)[0]).toContain('수정값이 있다');
    const finalizedWithout = valid();
    finalizedWithout.rows[0]!.ai.candidates = [candidate('a', null)];
    finalizedWithout.rows[0]!.review = { status: 'finalized' };
    expect(errorsOf(finalizedWithout)[0]).toContain('배출량이 없다');
    const picked = valid();
    picked.rows[0]!.review = {
      status: 'edited',
      edit: { candidateId: '없음', emission: null },
    } as never;
    expect(errorsOf(picked)[0]).toContain('없는 후보');
  });
});
