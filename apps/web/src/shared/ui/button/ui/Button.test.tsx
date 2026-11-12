// @vitest-environment jsdom
// 버튼: (1) 모든 variant×shape×size 조합에서 둥글기 클래스가 정확히 하나 (2) 공개 이름 (3) 꺼짐·불러오는 중에는 누를 수 없다
// (4) 아이콘 버튼은 이름이 없으면 타입 오류.
// 실제 높이·둥글기·초점 바깥선 색은 e2e/parts.spec.ts 가 본다(jsdom 에는 CSS 가 없다).
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  BUTTON_SHAPES,
  BUTTON_SIZES,
  BUTTON_VARIANTS,
  Button,
  buttonVariants,
} from './Button.tsx';
import { IconButton } from './IconButton.tsx';

afterEach(cleanup);

/** 공백으로 나눈 클래스 가운데 둥글기 클래스(rounded, rounded-*). hover: 같은 앞붙이가 붙은 것은 세지 않는다. */
const radiusClasses = (className: string) =>
  className.split(/\s+/).filter((token) => /^rounded(-|$)/.test(token));

describe('버튼', () => {
  it('buttonVariants 를 함께 내보낸다(키트 검증 스크립트가 이 이름을 찾는다)', () => {
    expect(typeof buttonVariants).toBe('function');
    expect(Button.displayName).toBe('Button');
  });

  it('모든 variant×shape×size 조합에서 둥글기 클래스가 정확히 하나다(그린 요소 기준)', () => {
    const seen: string[] = [];
    for (const variant of BUTTON_VARIANTS)
      for (const shape of BUTTON_SHAPES)
        for (const size of BUTTON_SIZES) {
          const { container, unmount } = render(
            <Button variant={variant} shape={shape} size={size}>
              x
            </Button>,
          );
          const found = radiusClasses(container.firstElementChild!.className);
          seen.push(`${variant}/${shape}/${size}: ${found.join(',')}`);
          expect(found, `${variant}/${shape}/${size}`).toHaveLength(1);
          unmount();
        }
    expect(seen).toHaveLength(7 * 2 * 4);
  });

  it('둥글기는 shape·size 짝으로 정해진다: round 는 rounded-full, square 는 xs 만 rounded-control', () => {
    expect(
      radiusClasses(buttonVariants({ shape: 'round', size: 'xs' })),
    ).toEqual(['rounded-full']);
    expect(
      radiusClasses(buttonVariants({ shape: 'square', size: 'xs' })),
    ).toEqual(['rounded-control']);
    expect(
      radiusClasses(buttonVariants({ shape: 'square', size: 'md' })),
    ).toEqual(['rounded-component']);
    expect(radiusClasses(buttonVariants({}))).toEqual(['rounded-component']);
  });

  it('solidGrey 의 글자는 text-grey-800(디자이너 값)이다', () => {
    const classes = buttonVariants({ variant: 'solidGrey' }).split(/\s+/);
    expect(classes).toContain('text-grey-800');
    expect(classes).not.toContain('text-text-tertiary');
  });

  it('cn 을 거쳐도 글자 꼴·색·초점 바깥선 클래스가 지워지지 않는다', () => {
    render(<Button variant="solidGrey">x</Button>);
    const classes = screen.getByRole('button').className.split(/\s+/);
    for (const name of [
      'text-style-pre-body-05',
      'text-grey-800',
      'focus-visible:outline-2',
      'focus-visible:outline-border-secondary',
      'gap-0.5',
    ])
      expect(classes).toContain(name);
  });

  it('꺼짐과 불러오는 중에는 누를 수 없다. 불러오는 중에는 도는 표시가 이름과 함께 보인다', () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <Button disabled onClick={onClick}>
        저장
      </Button>,
    );
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
    rerender(
      <Button loading loadingLabel="도는 중" onClick={onClick}>
        저장
      </Button>,
    );
    const button = screen.getByRole('button');
    expect(button).toHaveProperty('disabled', true);
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(screen.getByRole('status').getAttribute('aria-label')).toBe(
      '도는 중',
    );
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
    rerender(<Button onClick={onClick}>저장</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('asChild 가 아니면 기본 type 은 button 이다: form 안에서 눌러도 submit 이 일어나지 않는다. 쓰는 쪽 type 이 이긴다', () => {
    const onSubmit = vi.fn((event: { preventDefault(): void }) =>
      event.preventDefault(),
    );
    render(
      <form onSubmit={onSubmit}>
        <Button>그냥</Button>
        <Button type="submit">보내기</Button>
      </form>,
    );
    const plain = screen.getByRole('button', { name: '그냥' });
    expect(plain.getAttribute('type')).toBe('button');
    fireEvent.click(plain);
    expect(onSubmit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '보내기' }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it('asChild 에 loading·disabled 면 자식의 클릭과 Enter·Space 가 쓰는 쪽 처리기에 닿지 않고 aria-disabled 가 붙는다', () => {
    for (const blocked of [{ loading: true }, { disabled: true }]) {
      const onClick = vi.fn();
      const onKeyDown = vi.fn();
      const { unmount } = render(
        <Button asChild {...blocked}>
          <a href="#x" onClick={onClick} onKeyDown={onKeyDown}>
            링크
          </a>
        </Button>,
      );
      const link = screen.getByRole('link');
      expect(link.getAttribute('aria-disabled')).toBe('true');
      expect(link.hasAttribute('type')).toBe(false);
      fireEvent.click(link);
      const enter = fireEvent.keyDown(link, { key: 'Enter' });
      fireEvent.keyDown(link, { key: ' ' });
      expect(onClick).not.toHaveBeenCalled();
      expect(onKeyDown).not.toHaveBeenCalled();
      expect(enter).toBe(false); // preventDefault: 링크가 Enter 로 열리지 않는다
      // 다른 키(Tab 등)는 막지 않는다
      fireEvent.keyDown(link, { key: 'Tab' });
      expect(onKeyDown).toHaveBeenCalledOnce();
      unmount();
    }
  });

  it('asChild 면 자식 요소를 버튼 꼴로 그리고, 아이콘을 그 안에 넣는다', () => {
    render(
      <Button asChild leftIcon={<svg data-testid="icon" />}>
        <a href="#x">링크</a>
      </Button>,
    );
    const link = screen.getByRole('link');
    expect(link.textContent).toBe('링크');
    expect(link.querySelector('[data-testid="icon"]')).not.toBeNull();
    expect(radiusClasses(link.className)).toHaveLength(1);
  });

  it('아이콘 버튼은 이름을 받고, 둥글기 클래스는 하나다', () => {
    render(
      <IconButton aria-label="지우기" size="sm">
        <svg />
      </IconButton>,
    );
    const button = screen.getByRole('button', { name: '지우기' });
    expect(button.getAttribute('type')).toBe('button');
    expect(radiusClasses(button.className)).toEqual(['rounded-control']);
  });
});

// 이름 없는 아이콘 버튼은 타입 오류여야 한다. typecheck 가 이 줄에서 오류를 내지 않으면 @ts-expect-error 가 남아 typecheck 가 빨강이 된다.
// 그리지는 않는다(값으로만 만든다).
// @ts-expect-error aria-label 이 없다
export const nameless = <IconButton size="sm" />;
