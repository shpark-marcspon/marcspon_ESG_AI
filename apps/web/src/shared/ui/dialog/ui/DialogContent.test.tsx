// @vitest-environment jsdom
// 모달 Content: 키트 Header·Body·Footer 와 함께 실제로 그린다(키트 부품을 바꿔 끼우지 않는다).
// (1) 덮개는 우리 색 하나, 그림자는 shadow/strong 하나 (2) size 가 너비 클래스를 고른다 (3) 루트에 variant 를 주지 않으면
// 키트 Header·Body·Footer 가 default 꼴로 그려진다(★3) (4) 덮개와 본체에 twp 가 붙는다 (5) Esc 로 닫힌다.
// 실제 너비·덮개 색·그림자 값은 e2e/parts.spec.ts 가 잰다(jsdom 에는 CSS 가 없다).
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { DialogContent } from './DialogContent.tsx';
import {
  Dialog,
  DialogBody,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './kit.ts';

afterEach(cleanup);

const classesOf = (element: Element) => element.className.split(/\s+/);

function Sample({ size }: { size?: 'sm' | 'md' | 'lg' }) {
  return (
    <Dialog defaultOpen>
      <DialogTrigger>열기</DialogTrigger>
      <DialogContent size={size}>
        <DialogHeader data-testid="header">
          <DialogTitle>제목</DialogTitle>
        </DialogHeader>
        <DialogDescription>설명</DialogDescription>
        <DialogBody data-testid="body">본문</DialogBody>
        <DialogFooter data-testid="footer">버튼 줄</DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

describe('모달 Content', () => {
  it('덮개 색은 bg-black-transparent-500 하나다(키트의 rgba 는 지워진다). 덮개와 본체에 twp 가 붙는다', () => {
    render(<Sample />);
    const dialog = screen.getByRole('dialog');
    // 덮개는 Portal 안에서 본체 바로 앞에 그려진다(여는 버튼도 data-state="open" 이라 속성으로는 고르지 않는다).
    const overlay = dialog.previousElementSibling!;
    expect(overlay).not.toBeNull();
    const backgrounds = classesOf(overlay).filter((name) =>
      name.startsWith('bg-'),
    );
    expect(backgrounds).toEqual(['bg-black-transparent-500']);
    expect(classesOf(overlay)).toContain('twp');
    expect(classesOf(overlay)).toContain('z-modal');
    expect(classesOf(dialog)).toContain('twp');
  });

  it('그림자는 shadow/strong 하나다(키트 shadow-lg 는 지워진다). 모서리·안쪽은 키트 default 꼴, 겹침 16·글 14 — 344', () => {
    render(<Sample />);
    const classes = classesOf(screen.getByRole('dialog'));
    expect(classes.filter((name) => /^shadow(-|$)/.test(name))).toEqual([
      'shadow-[3px_3px_10px_#00000033]',
    ]);
    for (const name of ['rounded-dialog', 'p-8', 'z-modal', 'gap-4'])
      expect(classes).toContain(name);
    expect(classes).not.toContain('gap-6');
    expect(classes).toContain('text-style-pre-body-06');
  });

  it('size 가 너비를 고른다: 기본 md 640, sm 420, lg 800', () => {
    const widthOf = (size?: 'sm' | 'md' | 'lg') => {
      const { unmount } = render(<Sample size={size} />);
      const widths = classesOf(screen.getByRole('dialog')).filter((name) =>
        /^w-\[/.test(name),
      );
      unmount();
      return widths;
    };
    expect(widthOf()).toEqual(['w-[640px]']);
    expect(widthOf('sm')).toEqual(['w-[420px]']);
    expect(widthOf('md')).toEqual(['w-[640px]']);
    expect(widthOf('lg')).toEqual(['w-[800px]']);
  });

  it('★3 루트에 variant 를 주지 않으면 키트 Header·Body·Footer 가 default 꼴로 그려진다', () => {
    render(<Sample size="sm" />);
    expect(classesOf(screen.getByTestId('header'))).toContain(
      'text-style-pre-heading-02',
    );
    expect(classesOf(screen.getByTestId('body'))).toContain(
      'text-style-pre-body-06',
    );
    const footer = classesOf(screen.getByTestId('footer'));
    expect(footer).toContain('justify-center');
    expect(footer).not.toContain('mt-8');
  });

  it('여닫는 움직임은 움직임 줄이기를 켠 사용자에게 꺼진다: 덮개·본체에 열림·닫힘 각각 motion-reduce animate-none 이 있다(밴드 WM1, sid:MARC-ISSUE-602)', () => {
    // jsdom 은 prefers-reduced-motion 을 재지 못해 클래스 글자로 본다. animate-in·out 은 그대로 두고(motion-safe 로 감싸면 생성 CSS 차례상
    // animate-in 의 150ms 가 duration-200/100 을 이긴다 — WM1 검증 B1) 줄이기 쪽만 덧건다. 같은 특이도라 끝의 reduce 미디어 규칙이 이긴다.
    render(<Sample />);
    const dialog = screen.getByRole('dialog');
    const overlay = dialog.previousElementSibling!;
    for (const element of [overlay, dialog]) {
      const classes = classesOf(element);
      expect(classes).toContain('data-[state=open]:animate-in');
      expect(classes).toContain('data-[state=closed]:animate-out');
      expect(classes).toContain('motion-reduce:data-[state=open]:animate-none');
      expect(classes).toContain(
        'motion-reduce:data-[state=closed]:animate-none',
      );
    }
  });

  it('제목·설명이 대화 상자의 이름·설명으로 이어지고, Esc 로 닫힌다', () => {
    render(<Sample />);
    const dialog = screen.getByRole('dialog', { name: '제목' });
    expect(dialog.getAttribute('aria-describedby')).toBeTruthy();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
