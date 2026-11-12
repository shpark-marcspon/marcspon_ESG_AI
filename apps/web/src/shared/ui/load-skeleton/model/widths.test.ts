// 표 스켈레톤 막대 폭(밴드 LD1 ②): 정해진 차례(무작위 아님) — long 66·54·78·60·72%, 짝은 가운데·최소·최대·¼·¾, 수는 고정 px.
import { describe, expect, it } from 'vitest';

import { skeletonWidthAt } from './widths.ts';

describe('skeletonWidthAt', () => {
  it('long 은 줄마다 54~78% 를 정해진 차례로, 다섯 줄 뒤 되풀이', () => {
    expect(
      [0, 1, 2, 3, 4, 5].map((row) => skeletonWidthAt('long', row)),
    ).toEqual(['66%', '54%', '78%', '60%', '72%', '66%']);
  });

  it('수는 고정 px, 짝은 줄마다 그 사이(가운데·최소·최대·¼·¾)', () => {
    expect(skeletonWidthAt(112, 3)).toBe('112px');
    expect(
      [0, 1, 2, 3, 4].map((row) => skeletonWidthAt([24, 32], row)),
    ).toEqual(['28px', '24px', '32px', '26px', '30px']);
  });
});
