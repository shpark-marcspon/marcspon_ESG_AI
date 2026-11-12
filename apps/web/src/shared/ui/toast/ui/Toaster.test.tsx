// @vitest-environment jsdom
// 공용 토스트(밴드 S12Q1 ② — permits 셋: 보임·사라짐·reduced-motion + 두 톤·셋 넘침·멈춤·포털 늦게 붙음 ★D).
// 글은 지어낸 것이다(부품은 글을 모른다 — 부르는 쪽이 넘긴다).
import { StrictMode, useEffect } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../../dialog/index.ts';
import { TOAST_DURATION_MS, TOAST_MAX, Toaster } from './Toaster.tsx';
import { clearToasts, dismissToast, toast } from './store.ts';

const CSS = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'toast.css'),
  'utf8',
).replace(/\/\*[\s\S]*?\*\//g, '');

/** prefers-reduced-motion: reduce 의 답을 정해 둔 matchMedia(motion.test.tsx 꼴). */
function stubMotion(reduce: boolean) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: query.includes('reduce') ? reduce : !reduce,
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

const shown = () => screen.queryAllByTestId('toast');
const texts = () => shown().map((node) => node.textContent);
const tick = (ms: number) =>
  act(() => {
    vi.advanceTimersByTime(ms);
  });

beforeEach(() => {
  vi.useFakeTimers();
  stubMotion(false);
});
afterEach(() => {
  act(() => clearToasts());
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('Toaster — 보임·사라짐', () => {
  it('값: 3초 · 최대 3(e6 ⑤) — 토스트가 없으면 포털도 없다', () => {
    expect([TOAST_DURATION_MS, TOAST_MAX]).toEqual([3000, 3]);
    render(<Toaster />);
    expect(document.querySelector('[data-testid="toaster"]')).toBeNull();
  });

  it('성공 톤: role status · aria-live polite · 글 그대로 · 닫기 단추 0 · 토큰 색 · 머리 아래 24(위 88) 가운데 · z-toast', () => {
    render(<Toaster />);
    act(() => {
      toast({ message: '지어낸 성공 글' });
    });
    const item = screen.getByRole('status');
    expect(item.getAttribute('aria-live')).toBe('polite');
    expect(item.textContent).toBe('지어낸 성공 글');
    expect(item.querySelector('button')).toBeNull();
    for (const name of [
      'bg-background-primary-inverse',
      'text-text-primary-inverse',
      'rounded-component',
      'px-4',
      'py-3',
      'max-w-[480px]',
      'drop-shadow-[0_0_5px_rgba(0,0,0,0.12)]',
      'pointer-events-auto',
    ])
      expect(item.className, name).toContain(name);
    const stack = screen.getByTestId('toaster');
    for (const name of [
      'fixed',
      'top-[88px]',
      'z-toast',
      'items-center',
      'gap-2',
      'pointer-events-none',
    ])
      expect(stack.className, name).toContain(name);
    expect(stack.parentElement).toBe(document.body);
  });

  it('3초 뒤 나가는 움직임(220ms) 뒤 걷힘 · 다 걷히면 포털도 떨어짐', () => {
    render(<Toaster />);
    act(() => {
      toast({ message: '지어낸 글' });
    });
    expect(shown()[0]!.className).toContain('toast-m-in');
    tick(2999);
    expect(shown()).toHaveLength(1);
    tick(1);
    expect(shown()[0]!.className).toContain('toast-m-out');
    tick(220);
    expect(shown()).toHaveLength(0);
    expect(document.querySelector('[data-testid="toaster"]')).toBeNull();
  });

  it('시간 prop(Q15) — duration 을 주면 그만큼', () => {
    render(<Toaster duration={500} />);
    act(() => {
      toast({ message: '지어낸 글' });
    });
    tick(500);
    tick(220);
    expect(shown()).toHaveLength(0);
  });

  it('마우스가 올라 있거나 초점이 안에 있으면 시간이 멈추고, 떠나면 남은 시간부터', () => {
    render(<Toaster />);
    act(() => {
      toast({ message: '지어낸 글' });
    });
    tick(1000);
    fireEvent.mouseEnter(shown()[0]!);
    tick(10_000);
    expect(shown()[0]!.className).toContain('toast-m-in');
    fireEvent.mouseLeave(shown()[0]!);
    tick(1999);
    expect(shown()[0]!.className).toContain('toast-m-in');
    tick(1);
    expect(shown()[0]!.className).toContain('toast-m-out');
    tick(220);
    act(() => {
      toast({ message: '지어낸 둘째' });
    });
    fireEvent.focus(shown()[0]!);
    tick(10_000);
    expect(shown()).toHaveLength(1);
    fireEvent.blur(shown()[0]!);
    tick(3000);
    tick(220);
    expect(shown()).toHaveLength(0);
  });

  it('여럿: 새 것이 위 · 넷째가 오면 가장 오래된 것이 걷힘(최대 3)', () => {
    render(<Toaster />);
    act(() => {
      toast({ message: '지어낸 1' });
      toast({ message: '지어낸 2' });
      toast({ message: '지어낸 3' });
    });
    expect(texts()).toEqual(['지어낸 3', '지어낸 2', '지어낸 1']);
    act(() => {
      toast({ message: '지어낸 4' });
    });
    expect(texts()).toEqual(['지어낸 4', '지어낸 3', '지어낸 2']);
  });

  it('host 가 사라지면 남은 토스트를 걷는다(다른 화면으로 새지 않음)', () => {
    const { unmount } = render(<Toaster />);
    act(() => {
      toast({ message: '지어낸 글' });
    });
    unmount();
    render(<Toaster />);
    expect(shown()).toHaveLength(0);
  });

  it('StrictMode: host 가 띄우는 효과보다 앞(형제 앞)에 있어도 두 번 붙이기 뒤 토스트 하나', () => {
    function Fires() {
      useEffect(() => {
        toast({ message: '지어낸 하나' });
      }, []);
      return null;
    }
    render(
      <StrictMode>
        <Toaster />
        <Fires />
      </StrictMode>,
    );
    expect(texts()).toEqual(['지어낸 하나']);
  });
});

describe('Toaster — 움직임 줄임', () => {
  it('움직임 클래스는 모두 prefers-reduced-motion: no-preference 안 · 220ms · 들어올 때 위에서 8', () => {
    const outside = CSS.replace(
      /@media \(prefers-reduced-motion: no-preference\) \{[\s\S]*\}\s*$/,
      '',
    );
    expect(outside).not.toMatch(/toast-m-|animation/);
    expect(CSS).toContain('220ms cubic-bezier(0.22, 1, 0.36, 1)');
    expect(CSS).toContain('translateY(-8px)');
  });

  it('움직임을 줄였으면 시간이 되면 바로 걷힘(나가는 움직임 0)', () => {
    stubMotion(true);
    render(<Toaster />);
    act(() => {
      toast({ message: '지어낸 글' });
    });
    tick(3000);
    expect(shown()).toHaveLength(0);
  });
});

describe('Toaster — 실패 톤(a8 덧)', () => {
  it('role alert · 앞 아이콘 · ✕ 이름은 prop · 시간으로 사라지지 않음 · ✕ 로 닫힘', () => {
    render(<Toaster />);
    act(() => {
      toast({
        message: '지어낸 실패 글',
        tone: 'error',
        closeLabel: '지어낸 닫기',
      });
    });
    const item = screen.getByRole('alert');
    expect(item.className).toContain('bg-support-error-subtle');
    expect(item.className).toContain('text-support-error-accent');
    expect(item.querySelectorAll('svg').length).toBe(2);
    tick(60_000);
    expect(shown()).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '지어낸 닫기' }));
    tick(220);
    expect(shown()).toHaveLength(0);
  });

  it('실패 톤 ✕ 이름은 넘긴 이름 그대로(이름 없는 ✕ 0) · 실패 톤에 이름이 없으면 타입 오류 · 성공 톤은 ✕ 0', () => {
    // 타입으로만 잼(tsc) — 부르지 않는다.
    const typeOnly = () => {
      // @ts-expect-error 실패 톤은 closeLabel 이 필수(디자인 대조 F8).
      toast({ message: '지어낸 실패', tone: 'error' });
    };
    void typeOnly;
    render(<Toaster />);
    act(() => {
      toast({ message: '지어낸 성공' });
      toast({
        message: '지어낸 실패',
        tone: 'error',
        closeLabel: '지어낸 알림 닫기',
      });
    });
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(1);
    expect(buttons[0]!.getAttribute('aria-label')).toBe('지어낸 알림 닫기');
    expect(within(screen.getByRole('status')).queryByRole('button')).toBeNull();
  });

  it('움직임 줄임이면 ✕ 로 바로 걷힘', () => {
    stubMotion(true);
    render(<Toaster />);
    act(() => {
      toast({
        message: '지어낸 실패',
        tone: 'error',
        closeLabel: '지어낸 닫기',
      });
    });
    fireEvent.click(screen.getByRole('button', { name: '지어낸 닫기' }));
    expect(shown()).toHaveLength(0);
  });

  it('dismissToast(id) 로도 닫힘 · 없는 id 는 그대로', () => {
    render(<Toaster />);
    let id = 0;
    act(() => {
      id = toast({ message: '지어낸 실패', tone: 'error', closeLabel: 'x' });
    });
    act(() => dismissToast(id + 99));
    expect(shown()[0]!.className).toContain('toast-m-in');
    act(() => dismissToast(id));
    tick(220);
    expect(shown()).toHaveLength(0);
  });
});

describe('Toaster — 모달 위(★D)', () => {
  function WithModal() {
    return (
      <>
        <Toaster />
        <Dialog open>
          <DialogContent>
            <DialogTitle>지어낸 창</DialogTitle>
            <DialogDescription>지어낸 설명</DialogDescription>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  it('모달이 열린 뒤 붙은 포털은 aria-hidden 이 아니다 — hidden 없이 role status 로 찾힘 · body 끝 자식', () => {
    render(<WithModal />);
    expect(screen.getByRole('dialog')).toBeTruthy();
    act(() => {
      toast({ message: '지어낸 성공 글' });
    });
    const stack = screen.getByTestId('toaster');
    expect(document.body.lastElementChild).toBe(stack);
    expect(stack.closest('[aria-hidden="true"]')).toBeNull();
    expect(screen.getByRole('status').textContent).toBe('지어낸 성공 글');
  });

  it('모달이 body 에 pointer-events:none 을 걸어도 실패 ✕ 는 눌리고 모달은 열린 채', () => {
    const onOpenChange = vi.fn();
    render(
      <>
        <Toaster />
        <Dialog open onOpenChange={onOpenChange}>
          <DialogContent>
            <DialogTitle>지어낸 창</DialogTitle>
            <DialogDescription>지어낸 설명</DialogDescription>
          </DialogContent>
        </Dialog>
      </>,
    );
    act(() => {
      toast({
        message: '지어낸 실패',
        tone: 'error',
        closeLabel: '지어낸 닫기',
      });
    });
    const close = screen.getByRole('button', { name: '지어낸 닫기' });
    expect(screen.getByRole('alert').className).toContain(
      'pointer-events-auto',
    );
    fireEvent.pointerDown(close);
    fireEvent.click(close);
    tick(220);
    expect(shown()).toHaveLength(0);
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});
