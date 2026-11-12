// @vitest-environment jsdom
// 모달 제목(밴드 FW1 ⓪): 기본은 Bold 24(pre-display-04). 쓰는 쪽 className 의 text-style 이 이긴다(Alert 꼴 18).
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { DialogContent } from './DialogContent.tsx';
import { DialogTitle } from './DialogTitle.tsx';
import { Dialog } from './kit.ts';

afterEach(cleanup);

const textStyles = (element: Element) =>
  element.className
    .split(/\s+/)
    .filter((name) => name.startsWith('text-style-'));

describe('모달 제목', () => {
  it('기본 글자 꼴은 text-style-pre-display-04 하나다', () => {
    render(
      <Dialog defaultOpen>
        <DialogContent>
          <DialogTitle>제목</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(textStyles(screen.getByRole('heading', { name: '제목' }))).toEqual([
      'text-style-pre-display-04',
    ]);
  });

  it('쓰는 쪽이 준 text-style 이 기본을 갈아 낀다(둘이 함께 붙지 않는다)', () => {
    render(
      <Dialog defaultOpen>
        <DialogContent>
          <DialogTitle className="text-center text-style-pre-heading-02">
            확인
          </DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    const title = screen.getByRole('heading', { name: '확인' });
    expect(textStyles(title)).toEqual(['text-style-pre-heading-02']);
    expect(title.className.split(/\s+/)).toContain('text-center');
  });
});
