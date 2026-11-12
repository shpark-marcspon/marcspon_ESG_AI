// @vitest-environment jsdom
// 데이터 검증 읽기 훅(밴드 DV2a ① — 발주서 §3-1-5). 진짜 어댑터 + 가짜 서버, 가짜 시계.
//   useRun 폴링: queued·processing 이면 계속 · done·failed 면 멈춤 · 값을 받은 뒤 연속 3번 실패 → failed · 404 → missing ·
//   내려간 뒤에는 부르지 않음 · retry 는 다시 구독. useResult 는 done 결과 · 409 not_done · 404 missing · 꼴 틀림 failed.
import { act, cleanup, renderHook } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDataverifyServer,
  fakeRun,
  json,
  refusal,
  serverStoreOf,
  unreachable,
} from '../api/testing.ts';
import { useResult } from './useResult.ts';
import { useRun } from './useRun.ts';

const POLL = 1000;

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const tick = (ms = 0) => act(() => vi.advanceTimersByTimeAsync(ms));

describe('useRun', () => {
  it('loading → ready(queued) → processing → done 에서 멈춤', async () => {
    const server = fakeDataverifyServer({ runs: [fakeRun(7)] });
    const store = serverStoreOf(server, { pollMs: POLL });
    const { result } = renderHook(() => useRun(store, '7'));
    expect(result.current.status).toEqual({ state: 'loading' });
    await tick();
    expect(result.current.status).toMatchObject({
      state: 'ready',
      run: { status: 'queued' },
    });
    server.advance(7, { status: 'processing' });
    await tick(POLL);
    expect(result.current.status).toMatchObject({
      run: { status: 'processing' },
    });
    server.advance(7, { status: 'done' });
    await tick(POLL);
    expect(result.current.status).toMatchObject({ run: { status: 'done' } });
    await tick(POLL * 5);
    expect(server.count('GET /runs/7')).toBe(3);
  });

  it('값을 받은 뒤 연속 3번 실패 → failed, retry 는 다시 구독', async () => {
    const server = fakeDataverifyServer({
      runs: [fakeRun(7, { status: 'processing' })],
    });
    const store = serverStoreOf(server, { pollMs: POLL });
    const { result } = renderHook(() => useRun(store, '7'));
    await tick();
    server.override['GET /runs/7'] = [
      unreachable,
      () => refusal(500, 'INTERNAL'),
      () => json(200, { id: 'x' }),
    ];
    await tick(POLL);
    await tick(POLL);
    expect(result.current.status.state).toBe('ready');
    await tick(POLL);
    expect(result.current.status).toEqual({ state: 'failed' });
    await tick(POLL * 3);
    expect(server.count('GET /runs/7')).toBe(4);
    act(() => result.current.retry());
    expect(result.current.status).toEqual({ state: 'loading' });
    await tick();
    expect(result.current.status.state).toBe('ready');
  });

  it('404 → missing · 내려간 뒤 부름 0', async () => {
    const server = fakeDataverifyServer({
      runs: [fakeRun(7, { status: 'processing' })],
    });
    const store = serverStoreOf(server, { pollMs: POLL });
    const missing = renderHook(() => useRun(store, '9'));
    await tick();
    expect(missing.result.current.status).toEqual({ state: 'missing' });
    const { unmount } = renderHook(() => useRun(store, '7'));
    await tick();
    unmount();
    await tick(POLL * 5);
    expect(server.count('GET /runs/7')).toBe(1);
  });
});

describe('useResult', () => {
  it('done → ready · 끝나지 않음 → not_done · 없음 → missing · 꼴 틀림 → failed · null 은 읽지 않음', async () => {
    const server = fakeDataverifyServer({
      runs: [fakeRun(1), fakeRun(2), fakeRun(3)],
    });
    server.advance(1, { status: 'done' });
    server.advance(3, { status: 'done' });
    server.override['GET /dataverify/runs/3/result'] = () => json(200, {});
    const store = serverStoreOf(server);
    const done = renderHook(() => useResult(store, '1'));
    const notDone = renderHook(() => useResult(store, '2'));
    const missing = renderHook(() => useResult(store, '4'));
    const bad = renderHook(() => useResult(store, '3'));
    const idle = renderHook(() => useResult(store, null));
    await tick();
    expect(done.result.current.status).toMatchObject({
      state: 'ready',
      result: { company: { name: '가상건설' } },
    });
    expect(notDone.result.current.status).toEqual({ state: 'not_done' });
    expect(missing.result.current.status).toEqual({ state: 'missing' });
    expect(bad.result.current.status).toEqual({ state: 'failed' });
    expect(idle.result.current.status).toEqual({ state: 'loading' });
    expect(
      server.calls.filter((c) => c.path.startsWith('/dataverify/')),
    ).toHaveLength(4);
  });
});
