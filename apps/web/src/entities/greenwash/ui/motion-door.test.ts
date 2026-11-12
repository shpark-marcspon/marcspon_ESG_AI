// 움직임 문(밴드 TRP4 ①): 그린워싱 표면의 CountUp·useCountUp 은 공용 shared/ui/motion 의 것과 같은 값이고,
// 옛 자리(이 폴더)에 motion.css·CountUp.tsx 사본이 남지 않는다. 그린워싱 화면은 이 표면으로 CSS 까지 함께 받는다.
// 심은 파손: index.ts 의 재수출을 지우면 아래 시험이 빨강이다.
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import * as shared from '../../../shared/ui/motion/index.ts';
import { CountUp, useCountUp } from './index.ts';

const HERE = dirname(fileURLToPath(import.meta.url));

describe('그린워싱 움직임 문', () => {
  it('그린워싱 표면은 공용 움직임 표면과 같은 CountUp·useCountUp 을 내보낸다', () => {
    expect(CountUp).toBe(shared.CountUp);
    expect(useCountUp).toBe(shared.useCountUp);
  });

  it('옛 자리에 motion.css·CountUp.tsx 사본이 남지 않는다', () => {
    expect(existsSync(join(HERE, 'motion.css'))).toBe(false);
    expect(existsSync(join(HERE, 'CountUp.tsx'))).toBe(false);
  });
});
