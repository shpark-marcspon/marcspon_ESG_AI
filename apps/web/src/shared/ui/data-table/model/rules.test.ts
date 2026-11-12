// 목록 표 domain: 정렬 상태 → aria-sort, 칸 정렬, 누름 키.
import { describe, expect, it } from 'vitest';

import { alignOf, ariaSortOf, isActivationKey, skeletonOf } from './rules.ts';

describe('목록 표의 규칙', () => {
  it('정렬 상태 → aria-sort', () => {
    expect(ariaSortOf('asc')).toBe('ascending');
    expect(ariaSortOf('desc')).toBe('descending');
    expect(ariaSortOf(false)).toBe('none');
  });

  it('칸 정렬은 기본 왼쪽, meta.align 이 center·right 일 때만 바뀐다', () => {
    expect(alignOf(undefined)).toBe('left');
    expect(alignOf({})).toBe('left');
    expect(alignOf({ align: 'right' })).toBe('right');
    expect(alignOf({ align: 'center' })).toBe('center');
    expect(alignOf({ align: 'middle' })).toBe('left');
    expect(alignOf('right')).toBe('left');
  });

  it('누름 키는 Enter 와 Space 뿐이다', () => {
    expect(isActivationKey('Enter')).toBe(true);
    expect(isActivationKey(' ')).toBe(true);
    expect(isActivationKey('Tab')).toBe(false);
    expect(isActivationKey('Spacebar')).toBe(false);
  });

  it('막대 폭은 기본 long, meta.skeleton 의 양수·양수 짝만 받는다(밴드 LD1)', () => {
    expect(skeletonOf(undefined)).toBe('long');
    expect(skeletonOf({})).toBe('long');
    expect(skeletonOf({ skeleton: 'long' })).toBe('long');
    expect(skeletonOf({ skeleton: 112 })).toBe(112);
    expect(skeletonOf({ skeleton: [24, 32] })).toEqual([24, 32]);
    expect(skeletonOf({ skeleton: 0 })).toBe('long');
    expect(skeletonOf({ skeleton: [24] })).toBe('long');
    expect(skeletonOf({ skeleton: [24, 'x'] })).toBe('long');
  });
});
