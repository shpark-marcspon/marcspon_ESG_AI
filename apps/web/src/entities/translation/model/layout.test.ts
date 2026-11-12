// PDF 흐름 판별(밴드 TRW6 ①): flowId 접두로만 가른다.
import { describe, expect, it } from 'vitest';

import { LAYOUT_SHAPE, PDF_FLOW_ID, isPdfFlow } from './layout.ts';

describe('isPdfFlow', () => {
  it('translation.pdf@ 로 시작하면 PDF, colab 은 아님', () => {
    expect(isPdfFlow(PDF_FLOW_ID)).toBe(true);
    expect(isPdfFlow('translation.pdf@159')).toBe(true);
    expect(isPdfFlow('translation.colab@158')).toBe(false);
    expect(isPdfFlow('xtranslation.pdf@158')).toBe(false);
  });
  it('layout 꼴 이름', () => {
    expect(LAYOUT_SHAPE).toBe('translation.layout@1');
  });
});
