// 쪽 범위 셈(밴드 TRW0a ②, 발주서 §3-2): 글자 칸 읽기·겹침·CEO 한도·끌기·누름(늘림·빼기 — 밴드 TRW3).
import { describe, expect, it } from 'vitest';

import {
  CEO_PAGE_LIMIT,
  ceoError,
  ceoOverLimit,
  extendRange,
  formatRange,
  intersectRange,
  overlapOf,
  pageCountOf,
  paintRange,
  parseRange,
  pressRange,
} from './index.ts';

const LAST = 64;
const ok = (from: number, to: number) => ({ ok: true, range: { from, to } });
const fail = (code: string) => ({ ok: false, error: { code } });

describe('parseRange', () => {
  it.each([
    ['', { ok: true, range: null }],
    ['   ', { ok: true, range: null }],
    ['5', ok(5, 5)],
    ['1~3', ok(1, 3)],
    [' 1 ~ 3 ', ok(1, 3)],
    ['1-3', ok(1, 3)],
    [' 1 - 3 ', ok(1, 3)],
    // 전각 물결 둘(그린워싱 GR2 와 같은 넷 — TRW0b, sid:MARC-ISSUE-307 7)
    ['1～3', ok(1, 3)],
    ['1〜3', ok(1, 3)],
    [' 1 ～ 3 ', ok(1, 3)],
    ['64', ok(64, 64)],
    ['1~64', ok(1, 64)],
  ])('「%s」 → 받음', (text, want) => {
    expect(parseRange(text, LAST)).toEqual(want);
  });

  it.each([
    ['1,3', 'comma'],
    ['1~3, 5', 'comma'],
    ['0~2', 'zero'],
    ['0', 'zero'],
  ])('「%s」 → %s', (text, code) => {
    expect(parseRange(text, LAST)).toEqual(fail(code));
  });

  it('거꾸로는 친 두 쪽을, 숫자 아님은 친 글자(앞뒤 공백 뺌)를 싣는다', () => {
    expect(parseRange('3~1', LAST)).toEqual({
      ok: false,
      error: { code: 'order', from: 3, to: 1 },
    });
    for (const token of ['a', '1~', '-3', '1~3~5', '99999999999999999999'])
      expect(parseRange(` ${token} `, LAST)).toEqual({
        ok: false,
        error: { code: 'not_number', token },
      });
  });

  it('마지막 쪽을 넘으면 over_last — 넘은 쪽(구간 끝)과 마지막 쪽을 싣는다. 마지막 쪽 그 자체는 받는다', () => {
    expect(parseRange('60-65', LAST)).toEqual({
      ok: false,
      error: { code: 'over_last', page: 65, last: LAST },
    });
    expect(parseRange('150', LAST)).toEqual({
      ok: false,
      error: { code: 'over_last', page: 150, last: LAST },
    });
    expect(parseRange('65~70', LAST)).toEqual({
      ok: false,
      error: { code: 'over_last', page: 70, last: LAST },
    });
    expect(parseRange('64', LAST)).toEqual(ok(64, 64));
  });
});

describe('formatRange·pageCountOf·intersectRange', () => {
  it('보일 때는 늘 물결, 한 쪽은 숫자 하나', () => {
    expect(formatRange({ from: 1, to: 3 })).toBe('1~3');
    expect(formatRange({ from: 5, to: 5 })).toBe('5');
    expect(parseRange(formatRange({ from: 4, to: 41 }), LAST)).toEqual(
      ok(4, 41),
    );
  });

  it('쪽 수(없으면 0)', () => {
    expect(pageCountOf(null)).toBe(0);
    expect(pageCountOf({ from: 4, to: 41 })).toBe(38);
    expect(pageCountOf({ from: 7, to: 7 })).toBe(1);
  });

  it('두 구간이 같이 가진 쪽', () => {
    expect(intersectRange({ from: 1, to: 8 }, { from: 7, to: 41 })).toEqual({
      from: 7,
      to: 8,
    });
    expect(intersectRange({ from: 1, to: 3 }, { from: 4, to: 41 })).toBeNull();
    expect(intersectRange(null, { from: 4, to: 41 })).toBeNull();
  });
});

describe('overlapOf', () => {
  it('겹침 0', () => {
    expect(
      overlapOf({
        ceo: { from: 1, to: 3 },
        story: { from: 4, to: 41 },
        general: null,
      }),
    ).toEqual([]);
  });

  it('둘 겹침: 겹친 쪽만 오름차순, 파트는 PART_KEYS 차례', () => {
    expect(
      overlapOf({
        ceo: { from: 1, to: 8 },
        story: { from: 7, to: 41 },
        general: null,
      }),
    ).toEqual([
      { page: 7, parts: ['ceo', 'story'] },
      { page: 8, parts: ['ceo', 'story'] },
    ]);
  });

  it('셋 겹침', () => {
    expect(
      overlapOf({
        general: { from: 5, to: 6 },
        story: { from: 6, to: 9 },
        ceo: { from: 1, to: 6 },
      }),
    ).toEqual([
      { page: 5, parts: ['ceo', 'general'] },
      { page: 6, parts: ['ceo', 'story', 'general'] },
    ]);
  });
});

describe('ceoOverLimit', () => {
  it('한도 6쪽 고정: 6쪽 = 안 넘음, 7쪽 = 넘음(오류 갈래 ceo_over_limit), 없으면 안 넘음', () => {
    expect(CEO_PAGE_LIMIT).toBe(6);
    expect(ceoOverLimit({ from: 1, to: 6 })).toBe(false);
    expect(ceoOverLimit({ from: 1, to: 7 })).toBe(true);
    expect(ceoOverLimit(null)).toBe(false);
    expect(ceoError({ from: 1, to: 6 })).toBeNull();
    expect(ceoError({ from: 3, to: 9 })).toEqual({
      code: 'ceo_over_limit',
      limit: 6,
    });
  });
});

describe('끌기·누름', () => {
  it('extendRange: 없으면 한 쪽, 뒤로·앞으로 늘림, 안이면 그대로', () => {
    expect(extendRange(null, 4)).toEqual({ from: 4, to: 4 });
    expect(extendRange({ from: 2, to: 5 }, 9)).toEqual({ from: 2, to: 9 });
    expect(extendRange({ from: 4, to: 6 }, 1)).toEqual({ from: 1, to: 6 });
    expect(extendRange({ from: 4, to: 6 }, 5)).toEqual({ from: 4, to: 6 });
  });
});

// 밴드 TRW3 §1(그린워싱처럼): 누름은 칠하거나 빼고, 끌기는 시작 쪽이 정한다. 파트마다 이어진 한 구간(sid:MARC-ENT-392).
describe('pressRange · TRW3', () => {
  const r = { from: 4, to: 10 };
  it('구간 없음 → 그 한 쪽', () => {
    expect(pressRange(null, 7)).toEqual({ from: 7, to: 7 });
  });
  it('구간 밖(앞·뒤) → 거기까지 늘림', () => {
    expect(pressRange(r, 1)).toEqual({ from: 1, to: 10 });
    expect(pressRange(r, 15)).toEqual({ from: 4, to: 15 });
  });
  it('앞끝·뒤끝 → 한 쪽 줄어듦', () => {
    expect(pressRange(r, 4)).toEqual({ from: 5, to: 10 });
    expect(pressRange(r, 10)).toEqual({ from: 4, to: 9 });
  });
  it('한 쪽만 남은 쪽 → null(파트 비움)', () => {
    expect(pressRange({ from: 6, to: 6 }, 6)).toBeNull();
  });
  it('가운데: 가까운 끝까지 같이 빠짐, 같으면 뒤쪽을 자름(시작은 남김)', () => {
    // 앞이 가까움: 5 - 4 < 10 - 5
    expect(pressRange(r, 5)).toEqual({ from: 6, to: 10 });
    // 뒤가 가까움: 8 - 4 > 10 - 8
    expect(pressRange(r, 8)).toEqual({ from: 4, to: 7 });
    // 같음: 7 - 4 = 10 - 7
    expect(pressRange(r, 7)).toEqual({ from: 4, to: 6 });
  });
});

describe('paintRange · TRW3', () => {
  const r = { from: 10, to: 20 };
  it('칠하기(시작 쪽이 구간 밖): 구간 없으면 끈 구간, 차례 무관', () => {
    expect(paintRange(null, 5, 2)).toEqual({ from: 2, to: 5 });
    expect(paintRange(null, 3, 3)).toEqual({ from: 3, to: 3 });
  });
  it('칠하기: 떨어진 구간이면 사이도 채움(앞·뒤)', () => {
    expect(paintRange(r, 25, 28)).toEqual({ from: 10, to: 28 });
    expect(paintRange(r, 5, 2)).toEqual({ from: 2, to: 20 });
  });
  it('칠하기: 겹치면 덮는 한 구간', () => {
    expect(paintRange(r, 25, 15)).toEqual({ from: 10, to: 25 });
    expect(paintRange(r, 5, 30)).toEqual({ from: 5, to: 30 });
  });
  it('지우개(시작 쪽이 구간 안): 다 덮으면 null', () => {
    expect(paintRange(r, 10, 20)).toBeNull();
    expect(paintRange({ from: 5, to: 5 }, 5, 5)).toBeNull();
    expect(paintRange(r, 20, 1)).toBeNull();
  });
  it('지우개: 앞끝·뒤끝을 덮으면 그 끝이 줆(칸 밖까지 끌어도)', () => {
    expect(paintRange(r, 12, 10)).toEqual({ from: 13, to: 20 });
    expect(paintRange(r, 18, 25)).toEqual({ from: 10, to: 17 });
    expect(paintRange(r, 15, 3)).toEqual({ from: 16, to: 20 });
  });
  it('지우개 가운데: 작은 쪽이 같이 빠지고, 같으면 앞을 남김', () => {
    // 남는 앞 10~11(2) < 뒤 15~20(6) → 앞이 빠짐
    expect(paintRange(r, 12, 14)).toEqual({ from: 15, to: 20 });
    // 남는 앞 10~16(7) > 뒤 19~20(2) → 뒤가 빠짐
    expect(paintRange(r, 17, 18)).toEqual({ from: 10, to: 16 });
    // 같음: 앞 10~13(4) = 뒤 17~20(4) → 앞을 남김
    expect(paintRange(r, 14, 16)).toEqual({ from: 10, to: 13 });
  });
  it('지우개: 거꾸로 끈 것도 같음', () => {
    expect(paintRange(r, 14, 12)).toEqual(paintRange(r, 12, 14));
    expect(paintRange(r, 16, 14)).toEqual(paintRange(r, 14, 16));
    expect(paintRange(r, 18, 17)).toEqual(paintRange(r, 17, 18));
  });
});
