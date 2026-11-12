// @vitest-environment jsdom
// 필수 점(밴드 DT1 C4): 글자 없는 4px 주황 점, 화면 읽기에서 숨김.
import { cleanup, render } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { RequiredMark } from './RequiredMark.tsx';

afterEach(cleanup);

describe('RequiredMark', () => {
  it('글자 없는 4px 주황 점(bg-text-brand)이고 aria-hidden', () => {
    const { container } = render(<RequiredMark />);
    const mark = container.querySelector('[data-required-mark]')!;
    expect(mark.textContent).toBe('');
    expect(mark.getAttribute('aria-hidden')).toBe('true');
    expect(mark.className).toContain('size-1');
    expect(mark.className).toContain('rounded-full');
    expect(mark.className).toContain('bg-text-brand');
    expect(mark.className).toContain('ml-1');
  });
});
