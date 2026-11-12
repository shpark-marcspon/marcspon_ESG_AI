// 양식 줄 꼴(밴드 DT1 ③): 상수 다섯(index.ts 가 그대로 낸다 — 공개 표면이 PARTS_TEXT 를 내보내지 않는 것은 layers.test 가 본다).
import { describe, expect, it } from 'vitest';

import * as surface from './formRows.ts';

describe('form-rows 꼴', () => {
  it('클래스 상수 다섯만 낸다(PARTS_TEXT 없음)', () => {
    expect(Object.keys(surface).sort()).toEqual([
      'FORM_LABEL_CLASS',
      'FORM_ROWS_CLASS',
      'FORM_ROW_CLASS',
      'FORM_VALUE_BODY_CLASS',
      'FORM_VALUE_CLASS',
    ]);
    for (const value of Object.values(surface))
      expect(typeof value).toBe('string');
  });

  it('묶음은 m-0 을 더한 것 말고 사본과 같은 꼴 · 라벨 160(w-40) · 줄 높이 64 이상(min-h-16)', () => {
    expect(surface.FORM_ROWS_CLASS.split(' ')).toEqual([
      'm-0',
      'flex',
      'flex-col',
      'border-0',
      'border-t',
      'border-solid',
      'border-border-tertiary',
    ]);
    expect(surface.FORM_LABEL_CLASS.split(' ')).toContain('w-40');
    expect(surface.FORM_ROW_CLASS.split(' ')).toContain('min-h-16');
    expect(surface.FORM_VALUE_BODY_CLASS.split(' ')).toContain(
      'text-style-pre-body-03',
    );
  });
});
