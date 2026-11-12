// @vitest-environment jsdom
// 화면 제목 줄(PageTitle)의 headingRef(밴드 LA1 ①): 받으면 h2 에 ref 와 tabIndex -1(초점을 받는다), 안 받으면 tabindex 속성 없음.
// 받을 때만 Button·IconButton 과 같은 focus-visible 바깥선(밴드 SB2 ①). 제목·설명 자리 잡기 titlePending·descriptionPending(밴드 LD1).
import { createRef } from 'react';

import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PARTS_TEXT } from '../../text.ts';
import { PageTitle } from './Card.tsx';

afterEach(cleanup);

const FOCUS_RING = [
  'focus-visible:outline',
  'focus-visible:outline-2',
  'focus-visible:outline-offset-2',
  'focus-visible:outline-border-secondary',
];

describe('PageTitle', () => {
  it('headingRef 를 안 받으면 h2 에 tabindex 없음', () => {
    render(<PageTitle title="제목" />);
    expect(
      screen.getByRole('heading', { level: 2 }).getAttribute('tabindex'),
    ).toBeNull();
  });

  it('headingRef 를 안 받으면 h2 에 focus-visible 바깥선 클래스 없음', () => {
    render(<PageTitle title="제목" />);
    const classes = screen
      .getByRole('heading', { level: 2 })
      .className.split(/\s+/);
    for (const name of FOCUS_RING) expect(classes).not.toContain(name);
  });

  it('headingRef 를 받으면 h2 에 Button 과 같은 focus-visible 바깥선 클래스', () => {
    render(<PageTitle title="제목" headingRef={createRef()} />);
    const classes = screen
      .getByRole('heading', { level: 2 })
      .className.split(/\s+/);
    for (const name of FOCUS_RING) expect(classes).toContain(name);
  });

  it('headingRef 를 받으면 h2 에 붙고 tabIndex -1 — focus() 가 먹는다', () => {
    const ref = createRef<HTMLHeadingElement>();
    render(<PageTitle title="제목" headingRef={ref} />);
    const heading = screen.getByRole('heading', { level: 2 });
    expect(ref.current).toBe(heading);
    expect(heading.getAttribute('tabindex')).toBe('-1');
    heading.focus();
    expect(document.activeElement).toBe(heading);
  });

  // 자리 잡기(밴드 LD1 ③④): 데이터에서 오는 제목·설명만 막대.
  it('descriptionPending 이면 설명 자리에 막대(aria-hidden), description 이 오면 p 글', () => {
    const { rerender } = render(<PageTitle title="제목" descriptionPending />);
    const slot = screen.getByTestId('description-pending');
    expect(slot.getAttribute('aria-hidden')).toBe('true');
    expect(slot.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['mt-1', 'text-style-pre-body-06']),
    );
    const bar = slot.querySelector('[data-skeleton-bar]')!;
    expect(bar.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['h-3', 'w-[360px]', 'max-w-full']),
    );
    rerender(<PageTitle title="제목" description="설명" descriptionPending />);
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(screen.getByText('설명').tagName).toBe('P');
  });

  it('titlePending 이면 h2 는 그대로(headingRef 유지) 안에 막대 + 숨긴 글, title 은 그리지 않는다', () => {
    const ref = createRef<HTMLHeadingElement>();
    render(
      <PageTitle
        title="파일.pdf"
        titlePending
        pendingLabel="결과를 불러오는 중"
        headingRef={ref}
      />,
    );
    const heading = screen.getByRole('heading', { level: 2 });
    expect(ref.current).toBe(heading);
    expect(heading.getAttribute('tabindex')).toBe('-1');
    expect(heading.textContent).not.toContain('파일.pdf');
    expect(heading.querySelector('.sr-only')!.textContent).toBe(
      '결과를 불러오는 중',
    );
    const bar = heading.querySelector('[data-skeleton-bar]')!;
    expect(bar.getAttribute('aria-hidden')).toBe('true');
    expect(bar.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['h-[22px]', 'w-[28%]']),
    );
    expect(heading.parentElement!.className.split(/\s+/)).toContain('flex-1');
  });

  it('titlePending 숨긴 글 기본은 「불러오는 중」', () => {
    render(<PageTitle title="x" titlePending />);
    expect(
      screen.getByRole('heading', { level: 2 }).querySelector('.sr-only')!
        .textContent,
    ).toBe(PARTS_TEXT.loading);
  });

  it('pending 둘 다 없으면 지금 DOM 그대로(막대 0, 왼쪽 칸 flex-1 없음)', () => {
    const { container } = render(<PageTitle title="제목" />);
    expect(container.querySelector('[data-skeleton-bar]')).toBeNull();
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading.textContent).toBe('제목');
    expect(heading.parentElement!.className).toBe('min-w-0');
    expect(heading.parentElement!.children).toHaveLength(1);
  });
});
