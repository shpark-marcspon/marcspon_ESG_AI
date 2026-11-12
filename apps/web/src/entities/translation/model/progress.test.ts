// 전체 단계 진행 값(밴드 TRP2 TE10, 발주서 §3): 시안 51 · 쪽 없음 · 분모 0.
import { describe, expect, it } from 'vitest';

import { stageProgress } from './progress.ts';

describe('stageProgress', () => {
  it.each([
    [2, { done: 20, total: 38 }, 51],
    [1, undefined, 0],
    [3, undefined, 67],
    [2, { done: 0, total: 0 }, 33],
    [2, { done: 38, total: 38 }, 67],
  ] as const)('(%s, %o) → %s', (stageIndex, pages, expected) => {
    expect(stageProgress(stageIndex, pages)).toBe(expected);
  });
});
