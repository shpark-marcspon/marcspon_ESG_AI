// @vitest-environment jsdom
// 중대성평가 훅(밴드 IRW1 ① — 발주서 §3-1-3). 진짜 어댑터 + 가짜 서버, 가짜 시계.
//   useRun 폴링: queued·processing 이면 계속 · done·failed 면 멈춤 · 값을 받은 뒤 연속 3번 실패 → failed · 404 → missing ·
//   내려간 뒤에는 부르지 않음 · retry 는 다시 구독. useResult 는 done 결과 · 409 not_done · 404 missing · 꼴 틀림 failed.
//   useRerun 은 누르는 동안 한 번 · 거절은 failed.
import { act, cleanup, renderHook } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  doneRun,
  fakeMaterialityServer,
  fakeRun,
  json,
  refusal,
  serverStoreOf,
  unreachable,
} from '../api/testing.ts';
import { useRerun } from './useRerun.ts';
import { useResult } from './useResult.ts';
import { applyChanges, useResultEdits } from './useResultEdits.ts';
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
  it('loading → queued → processing → done 에서 멈춤', async () => {
    const server = fakeMaterialityServer({ runs: [fakeRun(7)] });
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

  it('failed 에서 멈춤 · 값을 받은 뒤 연속 3번 실패 → failed, retry 는 다시 구독', async () => {
    const server = fakeMaterialityServer({
      runs: [
        fakeRun(7, { status: 'processing' }),
        fakeRun(8, { status: 'failed' }),
      ],
    });
    const store = serverStoreOf(server, { pollMs: POLL });
    const failedRun = renderHook(() => useRun(store, '8'));
    await tick(POLL * 3);
    expect(failedRun.result.current.status).toMatchObject({
      run: { status: 'failed' },
    });
    expect(server.count('GET /runs/8')).toBe(1);

    const { result } = renderHook(() => useRun(store, '7'));
    await tick();
    server.override['GET /runs/7'] = [unreachable, unreachable, unreachable];
    await tick(POLL * 3);
    expect(result.current.status).toEqual({ state: 'failed' });
    act(() => result.current.retry());
    expect(result.current.status).toEqual({ state: 'loading' });
    await tick();
    expect(result.current.status).toMatchObject({ state: 'ready' });
  });

  it('404 → missing · 내려간 뒤 부르지 않음', async () => {
    const server = fakeMaterialityServer({ runs: [fakeRun(7)] });
    const store = serverStoreOf(server, { pollMs: POLL });
    const missing = renderHook(() => useRun(store, '99'));
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
  it('ready · not_done · missing · failed(꼴 틀림) · null 은 읽지 않음', async () => {
    const server = fakeMaterialityServer({
      runs: [doneRun(7), fakeRun(8, { status: 'processing' })],
    });
    server.override['GET /materiality/runs/9/result'] = () =>
      json(200, { schemaVersion: 'materiality.result@2' });
    const store = serverStoreOf(server);
    const ready = renderHook(() => useResult(store, '7'));
    const notDone = renderHook(() => useResult(store, '8'));
    const missing = renderHook(() => useResult(store, '99'));
    const bad = renderHook(() => useResult(store, '9'));
    const idle = renderHook(() => useResult(store, null));
    await tick();
    expect(ready.result.current.status.state).toBe('ready');
    expect(notDone.result.current.status).toEqual({ state: 'not_done' });
    expect(missing.result.current.status).toEqual({ state: 'missing' });
    expect(bad.result.current.status).toEqual({ state: 'failed' });
    expect(idle.result.current.status).toEqual({ state: 'loading' });
  });
});

describe('useRerun', () => {
  it('누르는 동안 한 번 · 새 id · 거절은 failed 이고 다시 누르면 지운다', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const store = serverStoreOf(server);
    const { result } = renderHook(() => useRerun(store, '7'));
    let first: Promise<string | null> = Promise.resolve(null);
    act(() => {
      first = result.current.rerun();
      void result.current.rerun();
    });
    expect(result.current.rerunning).toBe(true);
    await tick();
    expect(await first).toBe('30');
    expect(server.posts()).toHaveLength(1);
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    await act(async () => {
      expect(await result.current.rerun()).toBeNull();
    });
    expect(result.current.failed).toBe(true);
    delete server.override['POST /runs'];
    await act(async () => {
      expect(await result.current.rerun()).toBe('31');
    });
    expect(result.current.failed).toBe(false);
  });
});

describe('useResultEdits(밴드 IRW11 Q6·Q7)', () => {
  const DEF = '/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition';
  const defOf = (result: unknown) =>
    (
      result as {
        part2: {
          topics: {
            subtopics: { impact: { rows: { impactDefinition: string }[] } }[];
          }[];
        };
      }
    ).part2.topics[0]!.subtopics[0]!.impact.rows[0]!.impactDefinition;

  it('loading → ready(revision 0) · 저장 200 → revision 오름 · 결과를 다시 읽어 끼움(loading 0)', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const store = serverStoreOf(server);
    const { result } = renderHook(() => useResultEdits(store, '7'));
    expect(result.current.state).toBe('loading');
    await tick();
    expect(result.current.state).toBe('ready');
    expect(result.current.revision).toBe(0);
    const base = await store.getResult('7');
    const states: string[] = [];
    let kind = '';
    await act(async () => {
      const saving = result.current.save(
        [{ pointer: DEF, value: '가상 고침' }],
        base,
      );
      states.push(result.current.state);
      kind = await saving;
    });
    expect(kind).toBe('saved');
    expect(states).toEqual(['ready']);
    expect(result.current.state).toBe('ready');
    expect(result.current.revision).toBe(1);
    expect(result.current.edits.map((e) => e.pointer)).toEqual([DEF]);
    expect(defOf(result.current.result)).toBe('가상 고침');
    expect(server.count('GET /materiality/runs/7/result')).toBe(2);
  });

  it('409 → conflict(쥔 것 그대로) · reload 는 결과·고침을 같이 다시 읽음 · 다시 읽기 실패면 보낸 칸만 덮음', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    const store = serverStoreOf(server);
    const { result } = renderHook(() => useResultEdits(store, '7'));
    await tick();
    const base = await store.getResult('7');
    server.editElsewhere(7, DEF, '다른 사람 글');
    let kind = '';
    await act(async () => {
      kind = await result.current.save(
        [{ pointer: DEF, value: '내 글' }],
        base,
      );
    });
    expect(kind).toBe('conflict');
    expect(result.current.revision).toBe(0);
    let fresh: unknown = null;
    await act(async () => {
      fresh = await result.current.reload();
    });
    expect(defOf(fresh)).toBe('다른 사람 글');
    expect(result.current.revision).toBe(1);
    server.override['GET /materiality/runs/7/result'] = () =>
      refusal(500, 'INTERNAL');
    await act(async () => {
      kind = await result.current.save(
        [{ pointer: DEF, value: '내 글' }],
        base,
      );
    });
    expect(kind).toBe('saved');
    expect(defOf(result.current.result)).toBe('내 글');
  });

  it('고침을 못 읽음 → failed(화면은 읽기 전용) · applyChanges 는 원본을 건드리지 않음', async () => {
    const server = fakeMaterialityServer({ runs: [doneRun(7)] });
    server.override['GET /materiality/runs/7/result/edits'] = () =>
      refusal(500, 'INTERNAL');
    const store = serverStoreOf(server);
    const { result } = renderHook(() => useResultEdits(store, '7'));
    await tick();
    expect(result.current.state).toBe('failed');
    const base = await store.getResult('7');
    const out = applyChanges(base, [{ pointer: DEF, value: null }]);
    expect(defOf(out)).toBeNull();
    expect(defOf(base)).toBe('서브 가 영향');
  });
});
