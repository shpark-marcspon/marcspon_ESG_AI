// @vitest-environment jsdom
// (밴드 FS1 ③: hooks.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 새 점검 폼 훅과 실행 상태 훅(밴드 FW1b ①). 목 저장소 대신 시험 안의 가짜 저장소를 쓴다(headless 는 mock 을 모른다).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { RunSnapshot } from '../../../entities/greenwash/api/index.ts';
import { liveRunStore } from '../../../entities/greenwash/api/mock/testing.ts';
import type { RunProgress } from '../../../entities/greenwash/model/index.ts';
import { useRunStatus } from './useRunStatus.ts';

afterEach(cleanup);

const table: Record<string, { pageCount: number; hasText: boolean }> = {
  'a-60.pdf': { pageCount: 60, hasText: true },
  'scan-24.pdf': { pageCount: 24, hasText: false },
  'big-320.pdf': { pageCount: 320, hasText: true },
};

/** 구독하면 현재값(0쪽 진행)을 먼저 보내는 가짜 저장소. 파일 표의 이름만 올릴 수 있다. */
const liveStore = () =>
  liveRunStore((runId) => snapshot(runId, 0), {
    createDocument: vi.fn(async (file: File) => {
      const known = table[file.name];
      if (!known) throw new Error('모름');
      return { documentId: `doc-${file.name}`, ...known };
    }),
    createRun: vi.fn(async () => ({ runId: 'run-7' })),
    getRun: vi.fn(async (runId: string) => snapshot(runId, 0)),
    rerun: vi.fn(async () => ({ runId: 'run-8' })),
    listDocuments: vi.fn(async () => [
      { documentId: 'old-1', fileName: '앞.pdf', uploadedAt: '2026-01-01' },
    ]),
    listDefaultTerms: vi.fn(async () => ['친환경', 'ESG']),
    getDocument: vi.fn(async (documentId: string) => ({
      documentId,
      fileName: '앞.pdf',
      pageCount: 139,
    })),
  });

const progress = (done: number): RunProgress => ({
  state: 'running',
  stage: 'judge',
  judge: { done, total: 44 },
});

const snapshot = (runId: string, done: number): RunSnapshot => ({
  runId,
  documentId: 'd',
  startedAt: '2026-10-15T14:20:00+09:00',
  pageCount: 139,
  checkedPages: 44,
  progress: progress(done),
  rerunOf: null,
  errorCode: null,
  finishedAt: null,
});

describe('useRunStatus', () => {
  it('읽고, 구독으로 바뀐 것을 받고, 언마운트 때 해제한다', async () => {
    const { store, emit, listeners } = liveStore();
    const hook = renderHook(() => useRunStatus(store, 'run-1'));
    expect(hook.result.current.state).toBe('loading');
    await waitFor(() => expect(hook.result.current.state).toBe('ready'));
    expect(listeners.size).toBe(1);
    act(() => emit(snapshot('run-1', 30)));
    const current = hook.result.current;
    expect(current.state === 'ready' && current.run.progress.judge.done).toBe(
      30,
    );
    hook.unmount();
    expect(listeners.size).toBe(0);
  });

  it('runId 가 바뀌면 앞 구독을 풀고 새로 구독한다. 없는 실행은 missing', async () => {
    const { store, listeners } = liveStore();
    // 없는 실행: 저장소가 onMissing 을 부른다(밴드 FW2 ①. 앞에서는 getRun 거절이었다)
    vi.mocked(store.subscribeRun).mockImplementationOnce(
      (_runId, _listener, onMissing) => {
        onMissing?.();
        return () => {};
      },
    );
    const hook = renderHook(({ id }) => useRunStatus(store, id), {
      initialProps: { id: 'run-1' },
    });
    await waitFor(() => expect(hook.result.current.state).toBe('missing'));
    hook.rerender({ id: 'run-2' });
    await waitFor(() => expect(hook.result.current.state).toBe('ready'));
    expect(listeners.size).toBe(1);
    expect(store.subscribeRun).toHaveBeenCalledTimes(2);
  });
});
