// 받을 형식의 이름(거부 사유 문구의 {형식}). 밴드 FW1 ⓪.
import { describe, expect, it } from 'vitest';

import { formatsLabel } from './judge.ts';

describe('formatsLabel', () => {
  it('확장자를 점 없이 대문자로, 받은 차례대로 가운뎃점으로 잇는다', () => {
    expect(formatsLabel(['.pdf'])).toBe('PDF');
    expect(formatsLabel(['.xlsx', '.csv'])).toBe('XLSX·CSV');
    expect(formatsLabel([' .Xlsx ', '.PDF'])).toBe('XLSX·PDF');
  });

  it('겹친 확장자는 한 번만', () => {
    expect(formatsLabel(['.pdf', '.PDF'])).toBe('PDF');
  });

  it('확장자가 아닌 항목(MIME·와일드카드)이 하나라도 있으면 undefined(실제보다 좁게 말하지 않는다)', () => {
    expect(formatsLabel(['.pdf', '.PDF', 'application/pdf'])).toBeUndefined();
    expect(formatsLabel(['image/*', '.png'])).toBeUndefined();
  });

  it('확장자가 하나도 없으면 undefined(값 없는 문구를 쓴다)', () => {
    expect(formatsLabel(undefined)).toBeUndefined();
    expect(formatsLabel([])).toBeUndefined();
    expect(formatsLabel(['application/pdf', 'image/*'])).toBeUndefined();
    expect(formatsLabel(['.'])).toBeUndefined();
  });
});
