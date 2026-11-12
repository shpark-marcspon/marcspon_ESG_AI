// 화면의 배출량 글자 = 숫자 꼴 + 단위 글자. 둘 다 model/format.ts 한 곳에서 온다(sid:MARC-ENT-272). 여기서 글자를 따로 박으면 빨강.
import { describe, expect, it } from 'vitest';

import { EMISSION_UNIT, formatEmissionNumber } from '../model/index.ts';
import { formatEmission } from './format.ts';

describe('화면의 배출량 글자', () => {
  it('숫자 꼴 뒤에 단위 글자(EMISSION_UNIT)가 붙는다', () => {
    for (const value of [0.0004, 0.0015, 1.8, 12345.6789])
      expect(formatEmission(value)).toBe(
        `${formatEmissionNumber(value)} ${EMISSION_UNIT}`,
      );
    expect(formatEmission(1.8)).toBe('1.8 tCO2eq');
  });

  it('값이 없으면 줄표', () => {
    expect(formatEmission(null)).toBe('—');
  });
});
