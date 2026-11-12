// @vitest-environment jsdom
// 읽기 훅 하나(useLoad)의 바닥 꼴: 늦은 응답 버리기, 언마운트 뒤 버리기, 다시 읽기, 실패의 error 그대로, StrictMode, key null, 늦은 set.
// 밴드 LE1 ①: retry(늘 loading 부터), 늦은 reload·retry(앞 key 그리기의 부름은 아무것도 안 한다).
import { StrictMode, createElement } from 'react';
import type { ReactNode } from 'react';

import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { useLoad } from './useLoad.ts';
import type { LoadKey, LoadState } from './useLoad.ts';

afterEach(cleanup);

/** 밖에서 끝내는 약속. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
}

/** id 마다 부를 때마다 새 약속을 하나씩 낸다. */
function pending() {
  const calls: { id: string; d: ReturnType<typeof deferred<string>> }[] = [];
  const load = vi.fn((id: string) => {
    const d = deferred<string>();
    calls.push({ id, d });
    return d.promise;
  });
  return { calls, load };
}

const ready = (data: string): LoadState<string> => ({ state: 'ready', data });

describe('useLoad', () => {
  it('① key 가 바뀐 뒤 늦게 온 앞 key 의 응답은 버린다', async () => {
    const { calls, load } = pending();
    const { result, rerender } = renderHook(
      ({ id }) => useLoad([id], () => load(id)),
      { initialProps: { id: 'a' } },
    );
    rerender({ id: 'b' });
    expect(result.current.status).toEqual({ state: 'loading' });
    await act(async () => calls.find((c) => c.id === 'b')!.d.resolve('B'));
    expect(result.current.status).toEqual(ready('B'));
    // 앞 key 의 응답이 이제야 온다
    await act(async () => calls.find((c) => c.id === 'a')!.d.resolve('A'));
    expect(result.current.status).toEqual(ready('B'));
  });

  it('① key 가 바뀐 뒤 늦게 온 앞 key 의 응답은 새 key 가 아직 읽는 중이어도 버린다', async () => {
    const { calls, load } = pending();
    const { result, rerender } = renderHook(
      ({ id }) => useLoad([id], () => load(id)),
      { initialProps: { id: 'a' } },
    );
    rerender({ id: 'b' });
    await act(async () => calls[0]!.d.resolve('A'));
    expect(result.current.status).toEqual({ state: 'loading' });
  });

  it('칸이 같은 새 배열은 같은 key 다(그리기마다 다시 읽지 않는다)', async () => {
    const load = vi.fn(async () => 'x');
    const store = {};
    const { result, rerender } = renderHook(
      ({ id }) => useLoad([store, id], load),
      { initialProps: { id: 'a' } },
    );
    await waitFor(() => expect(result.current.status).toEqual(ready('x')));
    rerender({ id: 'a' });
    rerender({ id: 'a' });
    expect(load).toHaveBeenCalledTimes(1);
    expect(result.current.status).toEqual(ready('x'));
  });

  it('② 언마운트 뒤 resolve 되면 상태를 바꾸지 않는다(그리기가 더 없다)', async () => {
    const { calls, load } = pending();
    let renders = 0;
    const { unmount } = renderHook(() => {
      renders++;
      return useLoad(['a'], () => load('a'));
    });
    const before = renders;
    unmount();
    await act(async () => calls[0]!.d.resolve('A'));
    expect(renders).toBe(before);
    // 거절도 같다
    const second = pending();
    const other = renderHook(() => {
      renders++;
      return useLoad(['b'], () => second.load('b'));
    });
    const mid = renders;
    other.unmount();
    await act(async () => second.calls[0]!.d.reject(new Error('늦은 거절')));
    expect(renders).toBe(mid);
  });

  it('③ reload: failed 에서 같은 key 로 다시 부르고 loading → ready 로 간다(다시 시도)', async () => {
    const { calls, load } = pending();
    const { result } = renderHook(() => useLoad(['a'], () => load('a')));
    const boom = new Error('거절');
    await act(async () => calls[0]!.d.reject(boom));
    expect(result.current.status).toEqual({ state: 'failed', error: boom });
    act(() => result.current.reload());
    expect(load).toHaveBeenCalledTimes(2);
    expect(load).toHaveBeenLastCalledWith('a');
    expect(result.current.status).toEqual({ state: 'loading' });
    await act(async () => calls[1]!.d.resolve('A'));
    expect(result.current.status).toEqual(ready('A'));
  });

  it('③ reload: ready 에서는 다시 읽는 동안 앞 값을 내고, 새 값이 오면 갈아 넣는다. 다시 읽기가 거절되면 failed', async () => {
    const { calls, load } = pending();
    const { result } = renderHook(() => useLoad(['a'], () => load('a')));
    await act(async () => calls[0]!.d.resolve('첫 값'));
    act(() => result.current.reload());
    expect(load).toHaveBeenCalledTimes(2);
    expect(result.current.status).toEqual(ready('첫 값'));
    await act(async () => calls[1]!.d.resolve('새 값'));
    expect(result.current.status).toEqual(ready('새 값'));
    act(() => result.current.reload());
    const boom = new Error('다시 읽기 거절');
    await act(async () => calls[2]!.d.reject(boom));
    expect(result.current.status).toEqual({ state: 'failed', error: boom });
  });

  it('③ reload 를 겹쳐 부르면 앞 다시 읽기의 늦은 응답은 버린다', async () => {
    const { calls, load } = pending();
    const { result } = renderHook(() => useLoad(['a'], () => load('a')));
    await act(async () => calls[0]!.d.resolve('0'));
    act(() => result.current.reload());
    act(() => result.current.reload());
    await act(async () => calls[2]!.d.resolve('2'));
    await act(async () => calls[1]!.d.resolve('1'));
    expect(result.current.status).toEqual(ready('2'));
  });

  it('④ 실패면 failed 이고 error 를 받은 그대로 든다(화면이 갈래를 가를 수 있게)', async () => {
    class NotFound extends Error {
      readonly kind = 'not_found';
    }
    const error = new NotFound('없음');
    const { result } = renderHook(() =>
      useLoad(['a'], () => Promise.reject(error)),
    );
    await waitFor(() => expect(result.current.status.state).toBe('failed'));
    const status = result.current.status;
    expect(status.state === 'failed' && status.error).toBe(error);
    // load 가 동기로 던져도 failed 다
    const thrown = new Error('동기');
    const sync = renderHook(() =>
      useLoad<string>(['b'], () => {
        throw thrown;
      }),
    );
    await waitFor(() =>
      expect(sync.result.current.status).toEqual({
        state: 'failed',
        error: thrown,
      }),
    );
  });

  it('⑤ StrictMode 에서도 같은 결과(늦은 응답 버리기·reload 포함)', async () => {
    const { calls, load } = pending();
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(StrictMode, null, children);
    const { result, rerender } = renderHook(
      ({ id }) => useLoad([id], () => load(id)),
      { initialProps: { id: 'a' }, wrapper },
    );
    rerender({ id: 'b' });
    for (const call of calls.filter((c) => c.id === 'b'))
      await act(async () => call.d.resolve('B'));
    for (const call of calls.filter((c) => c.id === 'a'))
      await act(async () => call.d.resolve('A'));
    expect(result.current.status).toEqual(ready('B'));
    act(() => result.current.reload());
    for (const call of calls.slice(-1))
      await act(async () => call.d.resolve('B2'));
    expect(result.current.status).toEqual(ready('B2'));
  });

  it('⑥ key 가 null 이면 load 를 부르지 않고 loading 그대로다. key 가 생기면 읽는다', async () => {
    const load = vi.fn(async () => 'x');
    const { result, rerender } = renderHook(
      ({ key }: { key: LoadKey | null }) => useLoad(key, load),
      { initialProps: { key: null as LoadKey | null } },
    );
    act(() => result.current.reload());
    act(() => result.current.set('y'));
    expect(load).not.toHaveBeenCalled();
    expect(result.current.status).toEqual({ state: 'loading' });
    rerender({ key: ['a'] });
    await waitFor(() => expect(result.current.status).toEqual(ready('x')));
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('⑦ set 은 지금 key 의 값을 갈아 넣고, key 가 바뀐 뒤 늦게 온 set 은 새 상태를 덮지 않는다', async () => {
    const load = vi.fn(async (id: string) => `읽은 ${id}`);
    const { result, rerender } = renderHook(
      ({ id }) => useLoad([id], () => load(id)),
      { initialProps: { id: 'a' } },
    );
    await waitFor(() => expect(result.current.status).toEqual(ready('읽은 a')));
    const setA = result.current.set;
    act(() => setA('저장한 a'));
    expect(result.current.status).toEqual(ready('저장한 a'));
    rerender({ id: 'b' });
    await waitFor(() => expect(result.current.status).toEqual(ready('읽은 b')));
    act(() => setA('늦게 온 a'));
    expect(result.current.status).toEqual(ready('읽은 b'));
  });
  it('⑧ retry: ready 에서도 loading 으로 간 뒤 다시 읽는다(앞 값을 내지 않는다). 거절되면 failed, 또 retry 하면 loading → ready', async () => {
    const { calls, load } = pending();
    const { result } = renderHook(() => useLoad(['a'], () => load('a')));
    // ready 가 꼴 오류를 든 경우(useResult 의 invalid)와 같은 자리
    await act(async () => calls[0]!.d.resolve('꼴 오류'));
    expect(result.current.status).toEqual(ready('꼴 오류'));
    act(() => result.current.retry());
    expect(load).toHaveBeenCalledTimes(2);
    expect(result.current.status).toEqual({ state: 'loading' });
    const boom = new Error('다시 거절');
    await act(async () => calls[1]!.d.reject(boom));
    expect(result.current.status).toEqual({ state: 'failed', error: boom });
    act(() => result.current.retry());
    expect(result.current.status).toEqual({ state: 'loading' });
    await act(async () => calls[2]!.d.resolve('새 값'));
    expect(result.current.status).toEqual(ready('새 값'));
  });

  it('⑨ key A 그리기의 reload·retry 를 key B 뒤에 부르면 아무것도 안 한다(B 를 한 번 더 읽지 않는다)', async () => {
    const load = vi.fn(async (id: string) => `읽은 ${id}`);
    const { result, rerender } = renderHook(
      ({ id }) => useLoad([id], () => load(id)),
      { initialProps: { id: 'a' } },
    );
    await waitFor(() => expect(result.current.status).toEqual(ready('읽은 a')));
    const { reload: reloadA, retry: retryA } = result.current;
    rerender({ id: 'b' });
    await waitFor(() => expect(result.current.status).toEqual(ready('읽은 b')));
    expect(load).toHaveBeenCalledTimes(2);
    act(() => reloadA());
    act(() => retryA());
    expect(load).toHaveBeenCalledTimes(2);
    expect(result.current.status).toEqual(ready('읽은 b'));
    // 지금 key 의 것은 그대로 돈다
    act(() => result.current.retry());
    expect(result.current.status).toEqual({ state: 'loading' });
    await waitFor(() => expect(result.current.status).toEqual(ready('읽은 b')));
    expect(load).toHaveBeenCalledTimes(3);
  });

  it('⑩ key 가 바뀐 그리기에서 바로 새 key 로 본다(앞 key 의 ready 를 한 그리기도 내지 않는다)', async () => {
    const load = vi.fn(async (id: string) => `읽은 ${id}`);
    const seen: LoadState<string>[] = [];
    const { result, rerender } = renderHook(
      ({ id }) => {
        const loaded = useLoad([id], () => load(id));
        seen.push(loaded.status);
        return loaded;
      },
      { initialProps: { id: 'a' } },
    );
    await waitFor(() => expect(result.current.status).toEqual(ready('읽은 a')));
    seen.length = 0;
    rerender({ id: 'b' });
    expect(seen[0]).toEqual({ state: 'loading' });
    await waitFor(() => expect(result.current.status).toEqual(ready('읽은 b')));
    expect(seen).not.toContainEqual(ready('읽은 a'));
  });
});
