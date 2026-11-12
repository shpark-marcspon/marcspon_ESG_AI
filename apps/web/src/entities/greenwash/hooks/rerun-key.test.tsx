// @vitest-environment jsdom
// 밴드 GR2(sid:MARC-ISSUE-225 웹 몫 · GR1 검증 R2): [다시 실행]은 실행마다 제 열쇠(Idempotency-Key)로 보낸다.
// 끊김(unreachable) 뒤 다시 누르면 같은 열쇠(서버가 앞 실행을 돌려줘 실행은 하나), 성공·다른 거절이면 버려 다음은 새 열쇠.
// GR1 의 lost 막음(끊긴 실행은 소리 없이 null)은 걷었다. 값은 지어낸 것이다.
import { act, cleanup, renderHook } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../api/index.ts';
import type { GreenwashStore } from '../api/index.ts';
import { useRerunAction } from './useRerun.ts';

afterEach(cleanup);

// hooks 칸의 시험은 api/mock/testing.ts 를 못 가져온다(layers) — 여기서 짓는다.
const unused = () =>
  vi.fn(async () => {
    throw new StoreError('rejected', '쓰지 않음');
  });

function fakeStore(rerun: GreenwashStore['rerun']): GreenwashStore {
  return {
    createDocument: unused(),
    createRun: unused(),
    getRun: unused(),
    subscribeRun: vi.fn(() => () => {}),
    rerun,
    listDocuments: vi.fn(async () => []),
    listDefaultTerms: vi.fn(async () => []),
    getDocument: unused(),
    listCheckRows: unused(),
    getResult: unused(),
    getReview: unused(),
    putReview: unused(),
    rejudge: unused(),
    openDocumentPdf: vi.fn(async () => null),
    getReport: unused(),
  };
}

/** 부를 때마다 key-1, key-2 … 를 낸다. */
const counter = () => {
  let n = 0;
  return () => `key-${++n}`;
};

const unreachable = () => new StoreError('unreachable', '지어낸 끊김');

describe('useRerunAction 열쇠(밴드 GR2)', () => {
  it('끊김 뒤 같은 실행을 다시 누르면 같은 열쇠로 부르고(null 로 버리지 않음), 성공하면 버려 다음은 새 열쇠', async () => {
    const rerun = vi
      .fn<GreenwashStore['rerun']>()
      .mockRejectedValueOnce(unreachable())
      .mockResolvedValueOnce({ runId: 'run-9' })
      .mockResolvedValueOnce({ runId: 'run-10' });
    const store = fakeStore(rerun);
    const newKey = counter();
    const { result } = renderHook(() => useRerunAction(store, newKey));
    await act(async () => {
      expect(await result.current.rerun('run-1')).toBeNull();
    });
    expect(result.current.rerunError).toEqual({
      runId: 'run-1',
      error: 'unreachable',
    });
    await act(async () => {
      expect(await result.current.rerun('run-1')).toBe('run-9');
    });
    expect(result.current.rerunError).toBeNull();
    await act(async () => {
      expect(await result.current.rerun('run-1')).toBe('run-10');
    });
    expect(rerun.mock.calls).toEqual([
      ['run-1', 'key-1'],
      ['run-1', 'key-1'],
      ['run-1', 'key-2'],
    ]);
  });

  it('rejected 는 열쇠를 버린다 — 다시 누르면 새 열쇠', async () => {
    const rerun = vi.fn<GreenwashStore['rerun']>(async () => {
      throw new StoreError('rejected', '지어낸 거절');
    });
    const store = fakeStore(rerun);
    const newKey = counter();
    const { result } = renderHook(() => useRerunAction(store, newKey));
    for (let i = 0; i < 2; i++)
      await act(async () => {
        await result.current.rerun('run-1');
      });
    expect(rerun.mock.calls).toEqual([
      ['run-1', 'key-1'],
      ['run-1', 'key-2'],
    ]);
  });

  it('[R2] A 끊김 → B 거절 → A 다시: A 는 제 열쇠 그대로, B 는 따로(B 의 거절이 A 의 열쇠를 지우지 않는다)', async () => {
    const rerun = vi
      .fn<GreenwashStore['rerun']>()
      .mockRejectedValueOnce(unreachable())
      .mockRejectedValueOnce(new StoreError('rejected', '지어낸 거절'))
      .mockResolvedValueOnce({ runId: 'run-9' });
    const store = fakeStore(rerun);
    const newKey = counter();
    const { result } = renderHook(() => useRerunAction(store, newKey));
    await act(async () => {
      await result.current.rerun('run-a');
    });
    await act(async () => {
      await result.current.rerun('run-b');
    });
    expect(result.current.rerunError).toEqual({
      runId: 'run-b',
      error: 'rejected',
    });
    await act(async () => {
      expect(await result.current.rerun('run-a')).toBe('run-9');
    });
    expect(rerun.mock.calls).toEqual([
      ['run-a', 'key-1'],
      ['run-b', 'key-2'],
      ['run-a', 'key-1'],
    ]);
  });

  it('주입하지 않으면 열쇠는 소문자 UUID', async () => {
    const rerun = vi.fn<GreenwashStore['rerun']>(async () => ({
      runId: 'run-9',
    }));
    const store = fakeStore(rerun);
    const { result } = renderHook(() => useRerunAction(store));
    await act(async () => {
      await result.current.rerun('run-1');
    });
    expect(rerun.mock.calls[0]![1]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });
});
