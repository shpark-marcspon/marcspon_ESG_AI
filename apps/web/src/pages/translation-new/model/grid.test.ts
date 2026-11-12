// 쪽 칸 그리드의 셈(밴드 TRW0a ②): 보이는 칸 수, 칸 하나의 파트·겹침, 보이지 않는 칠한 쪽.
import { describe, expect, it } from 'vitest';

import { GRID_STEP, cellState, hiddenPainted, visibleCount } from './index.ts';

const RANGES = {
  ceo: { from: 1, to: 8 },
  story: { from: 7, to: 41 },
  general: { from: 8, to: 9 },
};

describe('visibleCount', () => {
  it('처음 40, 더 보기마다 40 더, 쪽 수를 넘지 않음', () => {
    expect(visibleCount(64, 0, GRID_STEP)).toBe(40);
    expect(visibleCount(64, 40, GRID_STEP)).toBe(64);
    expect(visibleCount(120, 40, GRID_STEP)).toBe(80);
    expect(visibleCount(12, 0, GRID_STEP)).toBe(12);
  });
});

describe('cellState', () => {
  it('파트 하나·겹침 둘·셋·없음', () => {
    expect(cellState(3, RANGES)).toEqual({ parts: ['ceo'], overlap: false });
    expect(cellState(7, RANGES)).toEqual({
      parts: ['ceo', 'story'],
      overlap: true,
    });
    expect(cellState(8, RANGES)).toEqual({
      parts: ['ceo', 'story', 'general'],
      overlap: true,
    });
    expect(cellState(50, RANGES)).toEqual({ parts: [], overlap: false });
  });
});

describe('hiddenPainted', () => {
  it('보이는 칸 밖에 칠한 부분만', () => {
    expect(hiddenPainted(RANGES, 40)).toEqual([
      { part: 'story', range: { from: 41, to: 41 } },
    ]);
    expect(hiddenPainted(RANGES, 64)).toEqual([]);
    expect(
      hiddenPainted(
        { ceo: null, story: null, general: { from: 50, to: 60 } },
        40,
      ),
    ).toEqual([{ part: 'general', range: { from: 50, to: 60 } }]);
  });
});
