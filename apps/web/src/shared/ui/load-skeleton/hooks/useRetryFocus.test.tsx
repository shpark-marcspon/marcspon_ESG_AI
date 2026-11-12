// @vitest-environment jsdom
// [다시 시도] 뒤 초점(useRetryFocus, 밴드 LA1 ①): 첫 진입에서는 옮기지 않는다, arm 뒤 loading → failed 면 [다시 시도],
// loading → ready 면 받은 마디, 한 번 옮긴 뒤에는 phase 가 또 바뀌어도 옮기지 않는다.
import { act, cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { useRetryFocus } from './useRetryFocus.ts';
import type { RetryFocus, RetryPhase } from './useRetryFocus.ts';

afterEach(cleanup);

let handle: RetryFocus<HTMLHeadingElement> | null = null;

/** 단추와 제목을 늘 함께 그린다(phase 마다 초점이 어디로 가는지만 본다). */
function Probe({ phase }: { phase: RetryPhase }) {
  const focus = useRetryFocus<HTMLHeadingElement>(phase);
  handle = focus;
  return (
    <div>
      <h2 ref={focus.doneRef} tabIndex={-1}>
        제목
      </h2>
      <button type="button" ref={focus.actionRef}>
        다시 시도
      </button>
    </div>
  );
}

const button = () => screen.getByRole('button', { name: '다시 시도' });
const heading = () => screen.getByRole('heading', { name: '제목' });

/** arm 이 낸 처리기를 누른 것처럼 부른다(fn 은 아무것도 안 한다 — phase 는 시험이 rerender 로 준다). */
function press() {
  act(() => handle!.arm(() => {})());
}

describe('useRetryFocus', () => {
  it('첫 phase 가 failed 여도, ready 여도 초점을 옮기지 않는다', () => {
    const failed = render(<Probe phase="failed" />);
    expect(document.activeElement).toBe(document.body);
    failed.unmount();
    const view = render(<Probe phase="loading" />);
    view.rerender(<Probe phase="ready" />);
    expect(document.activeElement).toBe(document.body);
    view.rerender(<Probe phase="failed" />);
    expect(document.activeElement).toBe(document.body);
  });

  it('arm → loading → failed 면 [다시 시도](actionRef)', () => {
    const view = render(<Probe phase="failed" />);
    press();
    view.rerender(<Probe phase="loading" />);
    expect(document.activeElement).toBe(document.body);
    view.rerender(<Probe phase="failed" />);
    expect(document.activeElement).toBe(button());
  });

  it('arm → loading → ready 면 받은 마디(doneRef)', () => {
    const view = render(<Probe phase="failed" />);
    press();
    view.rerender(<Probe phase="loading" />);
    view.rerender(<Probe phase="ready" />);
    expect(document.activeElement).toBe(heading());
  });

  it('arm 이 낸 처리기는 받은 fn 을 부른다', () => {
    render(<Probe phase="failed" />);
    let called = 0;
    act(() => handle!.arm(() => (called += 1))());
    expect(called).toBe(1);
  });

  it('한 번 옮긴 뒤에는 phase 가 또 바뀌어도 옮기지 않는다(다시 누를 때까지)', () => {
    const view = render(<Probe phase="failed" />);
    press();
    view.rerender(<Probe phase="loading" />);
    view.rerender(<Probe phase="failed" />);
    expect(document.activeElement).toBe(button());
    // 초점을 치운 뒤 phase 가 바뀌어도 그대로
    act(() => button().blur());
    view.rerender(<Probe phase="loading" />);
    view.rerender(<Probe phase="ready" />);
    expect(document.activeElement).toBe(document.body);
    view.rerender(<Probe phase="loading" />);
    view.rerender(<Probe phase="failed" />);
    expect(document.activeElement).toBe(document.body);
    // 다시 누르면 다시 옮긴다
    press();
    view.rerender(<Probe phase="loading" />);
    view.rerender(<Probe phase="ready" />);
    expect(document.activeElement).toBe(heading());
  });
});
