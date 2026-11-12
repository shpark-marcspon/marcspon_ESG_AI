// @vitest-environment jsdom
// 시작 전 확인(밴드 TRW0a ②, 발주서 §3-3-4): 파트 줄 = 넘긴 수, 번역 횟수, 스타일 글.
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PreflightCard } from './PreflightCard.tsx';

afterEach(cleanup);

const PAGES = {
  total: 41,
  parts: [
    { part: 'ceo', range: { from: 1, to: 3 }, count: 3 },
    { part: 'story', range: { from: 4, to: 41 }, count: 38 },
  ],
} as const;

describe('PreflightCard', () => {
  it('번역할 쪽: 합계 · 파트마다 구간(쪽 수)', () => {
    render(<PreflightCard pages={PAGES} runs={2} style="B" />);
    expect(screen.getByTestId('preflight').textContent).toContain(
      '총 41페이지 · CEO 메시지 1~3페이지(총 3페이지) · 스토리 4~41페이지(총 38페이지)',
    );
  });

  it('번역 횟수와 스타일 글(A·B 하나 / A · B 견주기)', () => {
    const { rerender } = render(
      <PreflightCard pages={PAGES} runs={2} style="B" />,
    );
    expect(screen.getByTestId('preflight').textContent).toContain(
      '2번 · 파트마다 한 번 · 스타일 B',
    );
    rerender(<PreflightCard pages={PAGES} runs={2} style="AB" />);
    expect(screen.getByTestId('preflight').textContent).toContain(
      '2번(파트마다 한 번) · 번역마다 A · B 두 스타일로 옮겨 82페이지 분량',
    );
  });

  it('「비용」 말이 없다(sid:MARC-ENT-334)', () => {
    render(<PreflightCard pages={PAGES} runs={2} style="A" />);
    expect(screen.getByTestId('preflight').textContent).not.toContain('비용');
  });
});
