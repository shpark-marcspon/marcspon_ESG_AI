// @vitest-environment jsdom
// 한 줄 안내의 주의 꼴(밴드 PD1): tone="caution" 이면 data-tone 과 파랑 두 클래스(시안 g-info--caution — 바탕 #E0EEFF · 글 #1243B7).
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PageInfo } from './PageInfo.tsx';

afterEach(cleanup);

describe('PageInfo', () => {
  it('tone="caution" 이면 data-tone="caution" 과 support-blue-subtle·support-blue-dark', () => {
    render(
      <PageInfo tone="caution" data-testid="info">
        안내
      </PageInfo>,
    );
    const info = screen.getByTestId('info');
    expect(info.getAttribute('data-tone')).toBe('caution');
    expect(info.classList).toContain('bg-support-blue-subtle');
    expect(info.classList).toContain('text-support-blue-dark');
  });
});
