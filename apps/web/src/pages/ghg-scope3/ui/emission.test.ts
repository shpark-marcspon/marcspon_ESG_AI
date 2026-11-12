// S3-08 카드 표기(밴드 S3W2a ①): review-table model 의 표기 그대로 — 글자로 견준다(표기 사본 0).
import { describe, expect, it } from 'vitest';

import { parseNumber } from '../../../entities/ghg-scope3/model/index.ts';
import { EMISSION_UNIT, emissionText } from './emission.ts';

describe('emissionText', () => {
  it('자리수·작은 값·음의 작은 값 · 없으면 줄표 글자', () => {
    expect(emissionText(1234.5678, '-')).toBe('1,234.568');
    expect(emissionText(0.00001, '-')).toBe('<0.001');
    expect(emissionText(-0.00001, '-')).toBe('>-0.001');
    expect(emissionText(0, '-')).toBe('0');
    expect(emissionText(null, '-')).toBe('-');
    expect(EMISSION_UNIT).toBe('tCO2eq');
  });

  it('발주서 표 1-5: 서버 수 글자 → parseNumber → 표기', () => {
    const shown = (text: string) => emissionText(parseNumber(text), '-');
    expect(shown('1e-05')).toBe('<0.001');
    expect(shown('0.30000000000000004')).toBe('0.3');
    expect(shown('0.0005')).toBe('0.001');
    expect(shown('0.00049999')).toBe('<0.001');
    expect(shown('-0.0')).toBe('0');
    expect(shown('nan')).toBe('-');
  });
});
