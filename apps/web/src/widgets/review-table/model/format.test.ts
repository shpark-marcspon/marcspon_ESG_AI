// 배출량 숫자의 꼴(sid:MARC-ENT-272): 소수 셋째까지, 끝 0 뺌, 0 < 값 < 0.0005 는 「<0.001」.
import { describe, expect, it } from 'vitest';

import { formatEmissionNumber } from './format.ts';

describe('배출량 숫자의 꼴', () => {
  it.each([
    [0, '0'],
    [0.0004, '<0.001'],
    [0.00049999, '<0.001'],
    [0.0005, '0.001'],
    [0.0015, '0.002'],
    [0.28, '0.28'],
    [1.8, '1.8'],
    [80, '80'],
    [12345.6789, '12,345.679'],
    [3 + 0.28, '3.28'], // 부동소수 합(3.2800000000000002)도 셋째에서 끊는다
    [-0.0004, '>-0.001'],
    [-1.2345, '-1.235'],
  ])('%s → %s', (value, text) => {
    expect(formatEmissionNumber(value)).toBe(text);
  });

  it('0 이 아닌 값은 「0」으로 보이지 않는다', () => {
    for (const value of [0.0001, 0.0004, 0.0005, 0.001, 0.049, -0.0001])
      expect(formatEmissionNumber(value)).not.toMatch(/^-?0$/);
  });
});
