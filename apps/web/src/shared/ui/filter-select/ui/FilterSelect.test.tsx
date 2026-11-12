// @vitest-environment jsdom
// 거르기 고르기 칸의 단추 꼴(밴드 AD4R ③ — MARC-ISSUE-197 J2): 모서리 8(rounded-component)·좌우 16(px-4)·최소 140, 쓰는 쪽 너비가 이긴다.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { FilterSelect } from './FilterSelect.tsx';

afterEach(cleanup);

const OPTIONS = [
  { value: 'a', label: '가' },
  { value: 'b', label: '나' },
] as const;

describe('FilterSelect 단추 꼴(J2)', () => {
  it('모서리 8·좌우 16·최소 140 — 옛 rounded-control·px-3 아님, 글은 「앞머리: 값」', () => {
    render(
      <FilterSelect
        label="기간"
        aria-label="기간으로 거르기"
        value="a"
        options={OPTIONS}
        onChange={() => {}}
      />,
    );
    const button = screen.getByRole('button', { name: '기간으로 거르기' });
    expect(button.textContent).toBe('기간: 가');
    const classes = button.className.split(/\s+/);
    expect(classes).toEqual(
      expect.arrayContaining(['rounded-component', 'px-4', 'min-w-[140px]']),
    );
    expect(classes).not.toContain('rounded-control');
    expect(classes).not.toContain('px-3');
    // 글 왼쪽·▾ 오른쪽 끝(양끝 정렬 — 디자인 답 AD4R ④): 글이 첫 자식, ▾ 가 마지막 자식.
    expect(classes).toContain('justify-between');
    expect(button.lastElementChild?.tagName.toLowerCase()).toBe('svg');
    // 글과 ▾ 사이 8(gap-2), ▾ 색 text-tertiary(디자인 대조 B1).
    expect(classes).toContain('gap-2');
    expect(classes).not.toContain('gap-1.5');
    expect(button.querySelector('svg')!.getAttribute('class')).toContain(
      'text-text-tertiary',
    );
  });

  it('쓰는 쪽 className 의 최소 너비가 이긴다(AD-03 시험 세트 칸 280)', () => {
    render(
      <FilterSelect
        aria-label="세트"
        value="b"
        options={OPTIONS}
        onChange={() => {}}
        className="min-w-[280px]"
      />,
    );
    const classes = screen
      .getByRole('button', { name: '세트' })
      .className.split(/\s+/);
    expect(classes).toContain('min-w-[280px]');
    expect(classes).not.toContain('min-w-[140px]');
    expect(classes).toContain('justify-between');
  });
});
