// @vitest-environment jsdom
// 영문번역 읽기 훅(밴드 TRW1a ① — 발주서 §3-1 6). 진짜 어댑터 + 가짜 서버, 가짜 시계.
//   useBatch 폴링: active 면 계속 · done 이면 멈춤 · 값을 받은 뒤 연속 3번 실패 → failed · 처음 읽기 실패 → 곧바로 failed · 404 → missing ·
//   내려간 뒤에는 부르지 않음. useBatches 는 거른 값마다 다시 읽음, useResult 는 끝나지 않은 실행이면 missing.
import { act, cleanup, renderHook } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDocument,
  fakeLayout,
  fakeOptions,
  fakeRun,
  fakeTranslationServer,
  refusal,
  serverStoreOf,
} from '../api/testing.ts';
import { useBatch } from './useBatch.ts';
import { useBatches } from './useBatches.ts';
import { useLayout } from './useLayout.ts';
import { useResult } from './useResult.ts';
import { useRunInfo } from './useRunInfo.ts';
import { useRunPdf } from './useRunPdf.ts';

const BATCH = '0b9f1a2c-3d4e-4f50-8a6b-7c8d9e0f1a2b';
const PATH = `GET /translation/documents/12/batches/${BATCH}`;
const POLL = 1000;

const seeded = () =>
  fakeTranslationServer({
    documents: [fakeDocument(12)],
    runs: [
      fakeRun(30, 12, fakeOptions('story', 1, 3, BATCH), {
        status: 'processing',
      }),
    ],
  });

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

/** 약속을 비우고 시계를 ms 만큼. */
const tick = async (ms = 0) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

describe('useBatch 폴링 (§3-1 6)', () => {
  // [밴드 TRW1b §3-1 4] [이 파트만 다시] 뒤 restart: 받은 값을 들고 다시 구독(loading 으로 떨어지지 않음 — sid:MARC-ENT-443 ①).
  it('restart: done 묶음 → 새 실행 → 그동안 loading 0 → active → 폴링 → done 에서 멈춤', async () => {
    const server = fakeTranslationServer({
      documents: [fakeDocument(12)],
      runs: [
        fakeRun(30, 12, fakeOptions('story', 1, 3, BATCH), {
          status: 'failed',
        }),
      ],
      nextRunId: 40,
    });
    const store = serverStoreOf(server, { pollMs: POLL });
    const seen: string[] = [];
    const { result } = renderHook(() => {
      const handle = useBatch(store, '12', BATCH);
      seen.push(handle.status.state);
      return handle;
    });
    await tick();
    const first = result.current.status;
    expect(first.state === 'ready' && first.batch.state).toBe('failed');
    await tick(POLL * 3);
    expect(server.count(PATH)).toBe(1);
    await store.retryPart({
      documentId: '12',
      batchKey: BATCH,
      part: 'story',
      runId: '30',
    });
    seen.length = 0;
    act(() => result.current.restart());
    expect(result.current.status).toBe(first);
    await tick();
    expect(seen).not.toContain('loading');
    const now = result.current.status;
    expect(now.state === 'ready' && now.batch.state).toBe('active');
    expect(server.count(PATH)).toBe(2);
    await tick(POLL);
    expect(server.count(PATH)).toBe(3);
    server.advance(40, { status: 'done' });
    await tick(POLL);
    const done = result.current.status;
    expect(done.state === 'ready' && done.batch.state).toBe('done');
    await tick(POLL * 5);
    expect(server.count(PATH)).toBe(4);
    expect(seen).not.toContain('loading');
  });

  it('retry(실패 화면 [다시 시도])는 그대로 loading 부터', async () => {
    const server = seeded();
    const store = serverStoreOf(server, { pollMs: POLL });
    const { result } = renderHook(() => useBatch(store, '12', BATCH));
    await tick();
    expect(result.current.status.state).toBe('ready');
    act(() => result.current.retry());
    expect(result.current.status.state).toBe('loading');
    await tick();
    expect(result.current.status.state).toBe('ready');
  });

  it('active 면 pollMs 마다 다시, done 이 되면 멈춘다', async () => {
    const server = seeded();
    const store = serverStoreOf(server, { pollMs: POLL });
    const { result } = renderHook(() => useBatch(store, '12', BATCH));
    expect(result.current.status.state).toBe('loading');
    await tick();
    expect(result.current.status.state).toBe('ready');
    expect(server.count(PATH)).toBe(1);
    await tick(POLL);
    expect(server.count(PATH)).toBe(2);
    server.advance(30, { status: 'done' });
    await tick(POLL);
    expect(server.count(PATH)).toBe(3);
    const status = result.current.status;
    expect(status.state === 'ready' && status.batch.state).toBe('done');
    await tick(POLL * 5);
    expect(server.count(PATH)).toBe(3);
  });

  it('값을 받은 뒤 연속 3번 실패 → failed 한 번, 그 뒤 부르지 않음', async () => {
    const server = seeded();
    const store = serverStoreOf(server, { pollMs: POLL });
    const { result } = renderHook(() => useBatch(store, '12', BATCH));
    await tick();
    server.override[PATH] = () => refusal(500, 'INTERNAL');
    await tick(POLL);
    await tick(POLL);
    expect(result.current.status.state).toBe('ready');
    await tick(POLL);
    expect(result.current.status.state).toBe('failed');
    const calls = server.count(PATH);
    await tick(POLL * 5);
    expect(server.count(PATH)).toBe(calls);
  });

  it('실패 둘 뒤 성공이면 셈 0(계속)', async () => {
    const server = seeded();
    const store = serverStoreOf(server, { pollMs: POLL });
    const { result } = renderHook(() => useBatch(store, '12', BATCH));
    await tick();
    server.override[PATH] = [
      () => refusal(500, 'INTERNAL'),
      () => refusal(500, 'INTERNAL'),
    ];
    await tick(POLL * 3);
    expect(result.current.status.state).toBe('ready');
    expect(server.count(PATH)).toBe(4);
  });

  it('처음 읽기 실패 → 곧바로 failed, retry → 다시 읽음', async () => {
    const server = seeded();
    server.override[PATH] = [() => refusal(500, 'INTERNAL')];
    const store = serverStoreOf(server, { pollMs: POLL });
    const { result } = renderHook(() => useBatch(store, '12', BATCH));
    await tick();
    expect(result.current.status.state).toBe('failed');
    act(() => result.current.retry());
    expect(result.current.status.state).toBe('loading');
    await tick();
    expect(result.current.status.state).toBe('ready');
  });

  it('404 → missing, 꼴 밖 열쇠 → 요청 0·missing', async () => {
    const server = seeded();
    const store = serverStoreOf(server, { pollMs: POLL });
    const gone = renderHook(() =>
      useBatch(store, '12', 'aaaaaaaa-0000-4000-8000-000000000000'),
    );
    await tick();
    expect(gone.result.current.status.state).toBe('missing');
    const before = server.calls.length;
    const bad = renderHook(() => useBatch(store, '12', 'BAD'));
    await tick();
    expect(bad.result.current.status.state).toBe('missing');
    expect(server.calls.length).toBe(before);
  });

  it('내려간 뒤에는 부르지 않는다', async () => {
    const server = seeded();
    const store = serverStoreOf(server, { pollMs: POLL });
    const { unmount } = renderHook(() => useBatch(store, '12', BATCH));
    await tick();
    unmount();
    await tick(POLL * 5);
    expect(server.count(PATH)).toBe(1);
  });
});

describe('useBatches · useResult', () => {
  it('거른 값이 바뀌면 다시 읽고, 실패 → failed · retry', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    const { result, rerender } = renderHook(
      ({ mine }: { mine: boolean }) => useBatches(store, { mine, offset: 0 }),
      { initialProps: { mine: false } },
    );
    await tick();
    expect(result.current.status.state).toBe('ready');
    server.override['GET /translation/batches'] = [
      () => refusal(500, 'INTERNAL'),
    ];
    rerender({ mine: true });
    await tick();
    expect(result.current.status.state).toBe('failed');
    expect(server.calls.at(-1)!.query.get('mine')).toBe('true');
    act(() => result.current.retry());
    await tick();
    expect(result.current.status.state).toBe('ready');
  });

  it('useResult: 끝나지 않음 → missing, 끝남 → ready, null 이면 읽지 않음', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    const idle = renderHook(() => useResult(store, null));
    await tick();
    expect(idle.result.current.status.state).toBe('loading');
    expect(server.calls).toHaveLength(0);
    const early = renderHook(() => useResult(store, '30'));
    await tick();
    expect(early.result.current.status.state).toBe('missing');
    server.advance(30, { status: 'done' });
    act(() => early.result.current.retry());
    await tick();
    expect(early.result.current.status.state).toBe('ready');
  });
});

// 밴드 TRW6 ① — PDF 결과 읽기 훅 셋(부재는 판별 유니온, 빈 값으로 메우지 않음).
describe('useLayout · useRunInfo · useRunPdf (TRW6)', () => {
  it('useLayout: 끝나지 않음 not_done · layout 없음 not_found · 있음 ready · 실패 failed · null 이면 읽지 않음', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    const idle = renderHook(() => useLayout(store, null));
    await tick();
    expect(idle.result.current.status.state).toBe('loading');
    expect(server.calls).toHaveLength(0);
    const hook = renderHook(() => useLayout(store, '30'));
    await tick();
    expect(hook.result.current.status.state).toBe('not_done');
    server.advance(30, { status: 'done' });
    act(() => hook.result.current.retry());
    await tick();
    expect(hook.result.current.status.state).toBe('not_found');
    server.runs.get(30)!.layout = fakeLayout(1);
    act(() => hook.result.current.retry());
    await tick();
    const ready = hook.result.current.status;
    expect(ready.state).toBe('ready');
    if (ready.state === 'ready') expect(ready.layout.units).toHaveLength(3);
    server.override['GET /translation/runs/30/layout'] = () =>
      refusal(500, 'INTERNAL');
    act(() => hook.result.current.retry());
    await tick();
    expect(hook.result.current.status.state).toBe('failed');
  });

  it('useRunInfo: ready(flowId) · 없음 not_found', async () => {
    const server = seeded();
    const store = serverStoreOf(server);
    const hook = renderHook(() => useRunInfo(store, '30'));
    await tick();
    const got = hook.result.current.status;
    expect(got.state).toBe('ready');
    if (got.state === 'ready')
      expect(got.info.flowId).toBe('translation.colab@158');
    const missing = renderHook(() => useRunInfo(store, '99'));
    await tick();
    expect(missing.result.current.status.state).toBe('not_found');
  });

  it('useRunPdf: 두 훅이 같은 문서를 읽어도 요청 하나 · missing', async () => {
    const server = fakeTranslationServer({
      documents: [
        fakeDocument(12, { pdf: new Uint8Array([37, 80, 68, 70]) }),
        fakeDocument(13),
      ],
    });
    const store = serverStoreOf(server);
    const a = renderHook(() => useRunPdf(store, '12'));
    const b = renderHook(() => useRunPdf(store, '12'));
    await tick();
    expect(a.result.current.status.state).toBe('ready');
    expect(b.result.current.status.state).toBe('ready');
    expect(server.count('GET /documents/12/file')).toBe(1);
    const none = renderHook(() => useRunPdf(store, '13'));
    await tick();
    expect(none.result.current.status.state).toBe('missing');
  });
});
