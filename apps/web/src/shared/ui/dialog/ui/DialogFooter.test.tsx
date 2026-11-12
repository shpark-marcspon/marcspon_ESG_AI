// @vitest-environment jsdom
// 모달 단추 줄(AV2 디자인 대조 N3): 우리 DialogFooter(공개 표면 index.ts 가 내보내는 것)는 키트 Footer 꼴(가운데·사이 8) 위에 pt-2(시안 .e-modal .foot{padding-top:8px}).
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { DialogContent } from './DialogContent.tsx';
import { DialogFooter } from './DialogFooter.tsx';
import { DialogTitle } from './DialogTitle.tsx';
import { Dialog, DialogDescription } from './kit.ts';

afterEach(cleanup);

const classesOf = (element: Element) => element.className.split(/\s+/);

function Sample({ className }: { className?: string }) {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogTitle>제목</DialogTitle>
        <DialogDescription>설명</DialogDescription>
        <DialogFooter data-testid="footer" className={className}>
          버튼 줄
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

describe('모달 단추 줄(N3)', () => {
  it('위 8(pt-2)을 더하고 키트 꼴(flex · gap-2 · justify-center)은 그대로', () => {
    render(<Sample />);
    const footer = classesOf(screen.getByTestId('footer'));
    expect(footer).toContain('pt-2');
    expect(footer).toEqual(
      expect.arrayContaining(['flex', 'gap-2', 'justify-center']),
    );
  });

  it('쓰는 쪽 className 이 위 간격을 덮는다', () => {
    render(<Sample className="pt-0" />);
    const footer = classesOf(screen.getByTestId('footer'));
    expect(footer).toContain('pt-0');
    expect(footer).not.toContain('pt-2');
  });
});
