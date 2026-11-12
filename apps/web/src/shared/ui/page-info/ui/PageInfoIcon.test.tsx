// @vitest-environment jsdom
// 안내 아이콘(밴드 AV2, 344 SB5): 선 동그라미 i — path 는 칠하지 않고 선만 긋는다. 그림이라 aria-hidden.
import { cleanup, render } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PageInfo } from './PageInfo.tsx';
import { PageInfoIcon } from './PageInfoIcon.tsx';

afterEach(cleanup);

describe('PageInfoIcon', () => {
  it('svg 는 aria-hidden 이고 path 는 fill 없이(또는 none) stroke 만 있다', () => {
    const { container } = render(<PageInfoIcon className="size-4" />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('class')).toContain('size-4');
    const paths = [...svg.querySelectorAll('path')];
    expect(paths.length).toBeGreaterThan(0);
    for (const path of paths) {
      expect([null, 'none']).toContain(path.getAttribute('fill'));
      expect(path.getAttribute('stroke')).toBeTruthy();
    }
  });

  it('PageInfo icon 자리에 svg 하나', () => {
    const { container } = render(
      <PageInfo icon={<PageInfoIcon />}>안내 글</PageInfo>,
    );
    expect(container.querySelectorAll('svg')).toHaveLength(1);
    expect(container.textContent).toBe('안내 글');
  });
});
