// @vitest-environment jsdom
// 첫 불러오기 판정(useFirstLoad, 밴드 LD1 ①): 첫 응답 전 loading 만 참. ready·failed 를 한 번 본 뒤의 loading 은 거짓.
import { cleanup, renderHook } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { useFirstLoad } from './useFirstLoad.ts';

afterEach(cleanup);

describe('useFirstLoad', () => {
  it('loading → 참 · ready → 거짓 · 다시 loading(거르기·다시 시도) → 거짓', () => {
    const { result, rerender } = renderHook(
      ({ state }) => useFirstLoad(state),
      { initialProps: { state: 'loading' } },
    );
    expect(result.current).toBe(true);
    rerender({ state: 'ready' });
    expect(result.current).toBe(false);
    rerender({ state: 'loading' });
    expect(result.current).toBe(false);
  });

  it('처음 failed 도 거짓, 그 뒤 loading 도 거짓', () => {
    const { result, rerender } = renderHook(
      ({ state }) => useFirstLoad(state),
      { initialProps: { state: 'loading' } },
    );
    rerender({ state: 'failed' });
    expect(result.current).toBe(false);
    rerender({ state: 'loading' });
    expect(result.current).toBe(false);
  });

  it('처음부터 ready 면 거짓, 그 뒤 loading 도 거짓', () => {
    const { result, rerender } = renderHook(
      ({ state }) => useFirstLoad(state),
      { initialProps: { state: 'ready' } },
    );
    expect(result.current).toBe(false);
    rerender({ state: 'loading' });
    expect(result.current).toBe(false);
  });
});
