// @vitest-environment jsdom
// 위험 등급 표시(밴드 TRW0a ① — 그린워싱에서 shared 로 올림): 등급 셋의 글자는 PARTS_TEXT.risk, 건수를 붙이고,
// 숫자만 꼴(display="count")의 0 은 등급과 상관없이 회색.
import { cleanup, render } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PARTS_TEXT } from '../../text.ts';
import { RISK_BADGE_LOOK, RISK_LEVELS, RiskBadge } from './RiskBadge.tsx';

afterEach(cleanup);

describe('RiskBadge', () => {
  it('등급 셋의 글자는 PARTS_TEXT.risk', () => {
    expect(RISK_LEVELS).toEqual(['high', 'mid', 'low']);
    for (const level of RISK_LEVELS) {
      expect(RISK_BADGE_LOOK[level].label).toBe(PARTS_TEXT.risk[level]);
      const { container, unmount } = render(<RiskBadge level={level} />);
      expect(container.textContent).toBe(PARTS_TEXT.risk[level]);
      unmount();
    }
  });

  it('count 를 주면 글자 뒤에 건수', () => {
    const { container } = render(<RiskBadge level="mid" count={3} />);
    expect(container.textContent).toBe(`${PARTS_TEXT.risk.mid} 3`);
  });

  it('display="count" 의 0 은 회색(Low 의 변형), 0 이 아니면 등급 색', () => {
    const { container, rerender } = render(
      <RiskBadge level="high" count={0} display="count" />,
    );
    const badge = () => container.querySelector('[data-level]')!;
    expect(container.textContent).toBe('0');
    expect(badge().className).toContain('bg-background-tertiary');
    rerender(<RiskBadge level="high" count={2} display="count" />);
    expect(container.textContent).toBe('2');
    expect(badge().className).toContain('bg-support-error-subtle');
  });

  it('글은 Bold 12/1.4 · 높이 20 · 좌우 6: 키트 바탕 굵기·sm 줄 높이·sm 글·좌우 4 는 빠진다(344 SB1)', () => {
    for (const level of RISK_LEVELS) {
      const { container, unmount } = render(<RiskBadge level={level} />);
      const classes = container
        .querySelector('[data-level]')!
        .className.split(/\s+/);
      for (const name of [
        'font-bold',
        'text-style-pre-caption-01',
        'h-5',
        'px-1.5',
      ])
        expect(classes).toContain(name);
      for (const name of [
        'font-medium',
        'leading-5',
        'text-style-pre-caption-02',
        'px-1',
      ])
        expect(classes).not.toContain(name);
      unmount();
    }
  });
});
