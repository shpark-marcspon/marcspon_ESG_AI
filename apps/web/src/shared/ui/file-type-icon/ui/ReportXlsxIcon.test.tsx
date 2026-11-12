// @vitest-environment jsdom
// ReportXlsxIcon(밴드 DB2 ③ — e6 ⑥): 그려짐 · viewBox 48 · aria-hidden 기본 · 종이·접힘 색 · 「XLSX」 글자는 패스(넷) · <text> 0.
import { cleanup, render } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { ReportXlsxIcon } from './ReportXlsxIcon.tsx';

afterEach(cleanup);

describe('ReportXlsxIcon', () => {
  it('48 판 · aria-hidden · 종이 #E2F8F0 · 접힘 #1EB96E · 글자 패스 넷 #00A63E · <text> 0', () => {
    const { container } = render(<ReportXlsxIcon className="size-12" />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('viewBox')).toBe('0 0 48 48');
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('class')).toContain('size-12');
    const fills = [...svg.querySelectorAll(':scope > path')].map((path) =>
      path.getAttribute('fill'),
    );
    expect(fills).toEqual(['#E2F8F0', '#1EB96E']);
    const glyphs = svg.querySelector('[data-glyphs="XLSX"]')!;
    expect(glyphs.getAttribute('fill')).toBe('#00A63E');
    expect(glyphs.querySelectorAll('path')).toHaveLength(4);
    expect(svg.querySelector('text')).toBeNull();
  });
});
