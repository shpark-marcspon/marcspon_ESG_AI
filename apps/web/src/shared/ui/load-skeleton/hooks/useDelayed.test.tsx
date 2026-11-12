// @vitest-environment jsdom
// 늦춘 참(useDelayed, 밴드 LE1 ①): 300ms 이어서 참이어야 참, 거짓이 되면 바로 거짓, 다시 참이면 처음부터 센다.
import { act, cleanup, renderHook } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LOAD_DELAY_MS, useDelayed } from './useDelayed.ts';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('useDelayed', () => {
  it('기본 300ms: 299ms 에는 거짓, 300ms 에는 참', () => {
    expect(LOAD_DELAY_MS).toBe(300);
    const { result } = renderHook(() => useDelayed(true));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(299));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });

  it('300ms 안에 거짓이 되면 한 번도 참을 내지 않는다', () => {
    const seen: boolean[] = [];
    const { rerender } = renderHook(
      ({ on }) => {
        const shown = useDelayed(on);
        seen.push(shown);
        return shown;
      },
      { initialProps: { on: true } },
    );
    act(() => vi.advanceTimersByTime(200));
    rerender({ on: false });
    act(() => vi.advanceTimersByTime(500));
    expect(seen).not.toContain(true);
  });

  it('참이던 것이 거짓이 되면 그 그리기에서 바로 거짓, 다시 참이면 처음부터 센다', () => {
    const { result, rerender } = renderHook(({ on }) => useDelayed(on), {
      initialProps: { on: true },
    });
    act(() => vi.advanceTimersByTime(300));
    expect(result.current).toBe(true);
    rerender({ on: false });
    expect(result.current).toBe(false);
    rerender({ on: true });
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(299));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });

  it('ms 를 받으면 그만큼 기다린다', () => {
    const { result } = renderHook(() => useDelayed(true, 50));
    act(() => vi.advanceTimersByTime(49));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });
});
