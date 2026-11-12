// 칠하기: 누르기 토글과 끌기(밴드 FW1b ①).
import { describe, expect, it } from 'vitest';

import { paintModeAt, paintRange, togglePage } from './paint.ts';

describe('togglePage', () => {
  it('없던 쪽은 넣고(오름차순), 있던 쪽은 뺀다', () => {
    expect(togglePage([4, 7], 5)).toEqual([4, 5, 7]);
    expect(togglePage([4, 5, 7], 5)).toEqual([4, 7]);
    expect(togglePage([], 3)).toEqual([3]);
  });

  it('두 번 누르면 원래대로', () => {
    expect(togglePage(togglePage([4, 5], 9), 9)).toEqual([4, 5]);
    expect(togglePage(togglePage([4, 5], 4), 4)).toEqual([4, 5]);
  });
});

describe('끌기', () => {
  it('시작 쪽이 비었으면 넣기, 칠해져 있으면 빼기', () => {
    expect(paintModeAt([4, 5], 6)).toBe('add');
    expect(paintModeAt([4, 5], 5)).toBe('remove');
  });

  it('넣기: 시작~지금 구간을 넣는다(거꾸로 끌어도)', () => {
    expect(paintRange([1], 'add', 3, 6)).toEqual([1, 3, 4, 5, 6]);
    expect(paintRange([1], 'add', 6, 3)).toEqual([1, 3, 4, 5, 6]);
    expect(paintRange([4, 5], 'add', 5, 7)).toEqual([4, 5, 6, 7]);
  });

  it('빼기: 시작~지금 구간을 뺀다', () => {
    expect(paintRange([3, 4, 5, 6, 9], 'remove', 4, 6)).toEqual([3, 9]);
  });

  it('기준은 끌기 시작 때의 집합이다: 되돌아 끌면 지나간 쪽이 원래대로', () => {
    const base = [2];
    expect(paintRange(base, 'add', 3, 8)).toEqual([2, 3, 4, 5, 6, 7, 8]);
    expect(paintRange(base, 'add', 3, 4)).toEqual([2, 3, 4]);
  });
});
