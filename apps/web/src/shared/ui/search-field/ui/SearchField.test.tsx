// @vitest-environment jsdom
// 검색 칸(밴드 AV2, 344 SB4): 돋보기는 왼쪽 그림, 글은 40 에서 시작, 단추는 없다. className 은 겉, ref·props 는 input.
import * as React from 'react';

import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { SearchField } from './SearchField.tsx';

afterEach(cleanup);

const classesOf = (element: Element) =>
  (element.getAttribute('class') ?? '').split(/\s+/);

describe('검색 칸', () => {
  it('input 은 왼 40·오른 12·칸 높이를 채우고, 겉은 relative·h-9 에 넘긴 폭', () => {
    render(<SearchField aria-label="검색어" className="w-64" />);
    const input = screen.getByRole('textbox', { name: '검색어' });
    for (const name of ['pl-10', 'pr-3', 'h-full'])
      expect(classesOf(input)).toContain(name);
    expect(classesOf(input)).not.toContain('w-64');
    const outer = classesOf(input.parentElement!);
    for (const name of ['relative', 'h-9', 'w-64'])
      expect(outer).toContain(name);
  });

  it('돋보기는 input 앞 형제 그림(aria-hidden · left-4 · 16 · tertiary)이고 단추는 없다', () => {
    render(<SearchField aria-label="검색어" />);
    const input = screen.getByRole('textbox', { name: '검색어' });
    const icon = input.previousElementSibling!;
    expect(icon.tagName.toLowerCase()).toBe('svg');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    for (const name of ['left-4', 'text-text-tertiary', 'size-4'])
      expect(classesOf(icon)).toContain(name);
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('onChange 가 불리고 maxLength 가 input 에 가며 ref 가 input 에 닿는다', () => {
    const onChange = vi.fn();
    const ref = React.createRef<HTMLInputElement>();
    render(
      <SearchField
        ref={ref}
        aria-label="검색어"
        maxLength={20}
        onChange={onChange}
      />,
    );
    const input = screen.getByRole('textbox', { name: '검색어' });
    fireEvent.change(input, { target: { value: '가나' } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(input.getAttribute('maxlength')).toBe('20');
    expect(ref.current).toBe(input);
  });
});
