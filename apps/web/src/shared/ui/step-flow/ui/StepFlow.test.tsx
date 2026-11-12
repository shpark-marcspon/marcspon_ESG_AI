// @vitest-environment jsdom
// 단계 띠(밴드 TRW0a ① — 그린워싱에서 shared 로 올림): 순서 있는 목록, 지금 단계 하나에만 aria-current="step", 범위 밖이면 없음,
// 단계 사이 화살표는 꾸밈(aria-hidden)이라 단계 수 − 1. 단계 이름·목록 이름은 받은 것, 번호 앞 글자의 기본은 PARTS_TEXT.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PARTS_TEXT } from '../../text.ts';
import { StepFlow } from './StepFlow.tsx';

afterEach(cleanup);

const STEPS = ['가', '나', '다', '라'] as const;

describe('StepFlow', () => {
  it('ol 이름과 단계 이름은 받은 것, 지금 단계 하나에만 aria-current="step"', () => {
    const { container } = render(
      <StepFlow current={2} steps={STEPS} label="시험 단계" />,
    );
    const list = screen.getByRole('list', { name: '시험 단계' });
    expect(list.tagName).toBe('OL');
    expect(screen.getAllByRole('listitem')).toHaveLength(4);
    const on = container.querySelectorAll('[aria-current="step"]');
    expect(on).toHaveLength(1);
    expect(on[0]!.textContent).toBe(`${PARTS_TEXT.stepFlow.prefix} 2나`);
  });

  it('범위 밖이면 고른 단계 0', () => {
    for (const current of [0, 5, -1]) {
      const { container, unmount } = render(
        <StepFlow current={current} steps={STEPS} label="시험 단계" />,
      );
      expect(container.querySelectorAll('[aria-current]')).toHaveLength(0);
      unmount();
    }
  });

  it('화살표(aria-hidden svg)는 단계 수 − 1, 번호 앞 글자는 바꿀 수 있다', () => {
    const { container } = render(
      <StepFlow current={1} steps={STEPS} label="시험 단계" prefix="P" />,
    );
    expect(container.querySelectorAll('svg[aria-hidden]')).toHaveLength(
      STEPS.length - 1,
    );
    expect(container.querySelector('b')?.textContent).toBe('P 1');
  });
});
