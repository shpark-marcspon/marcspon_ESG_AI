// @vitest-environment jsdom
// (밴드 FS1 ③: check-list.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ②: 목록 훅(useCheckList — 거르기·연도·숫자·[다시 실행] 거절)과 useReview 의 늦은 저장 막기(발주서 덧붙임 3).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../api/index.ts';
import type { GreenwashStore } from '../api/index.ts';
import type { GreenwashReview, ListedRun } from '../model/index.ts';
import { useReview } from './useReview.ts';

afterEach(cleanup);

const unused = () =>
  vi.fn(async () => {
    throw new StoreError('rejected', '쓰지 않음');
  });

function store(overrides: Partial<GreenwashStore>): GreenwashStore {
  return {
    createDocument: unused(),
    createRun: unused(),
    getRun: unused(),
    subscribeRun: vi.fn(() => () => {}),
    rerun: unused(),
    listDocuments: vi.fn(async () => []),
    listDefaultTerms: vi.fn(async () => []),
    getDocument: unused(),
    listCheckRows: unused(),
    getResult: unused(),
    getReview: unused(),
    putReview: unused(),
    rejudge: unused(),
    openDocumentPdf: vi.fn(async () => null),
    getReport: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    ...overrides,
  };
}

const run = (
  runId: string,
  documentId: string,
  state: 'running' | 'failed' | 'done',
): ListedRun => ({
  runId,
  documentId,
  createdAt: `2026-10-0${runId.slice(-1)}T09:00:00+09:00`,
  progress: { state, stage: 'judge', judge: { done: 1, total: 2 } },
  levelCounts: null,
  review:
    state === 'done' ?
      {
        state: 'pending',
        reviewed: 0,
        total: 1,
        confirmedAt: null,
        confirmedBy: null,
      }
    : null,
});

const review = (runId: number): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  evidence: [],
  rejudges: [],
  runId: runId,
  state: 'pending',
  confirmedAt: null,
  confirmedBy: null,
  marks: [],
  edits: [],
});

describe('useReview 늦은 저장(발주서 덧붙임 3)', () => {
  it('저장이 끝나기 전에 runId 가 바뀌면 늦게 온 저장 결과가 새 실행의 읽기 상태를 덮지 않는다', async () => {
    let finish: ((value: unknown) => void) | null = null;
    const fake = store({
      getReview: vi.fn(async (runId: string) =>
        review(runId === 'run-1' ? 1 : 2),
      ),
      putReview: vi.fn(
        () =>
          new Promise<unknown>((resolve) => {
            finish = resolve;
          }),
      ),
    });
    const hook = renderHook(({ id }) => useReview(fake, id), {
      initialProps: { id: 'run-1' },
    });
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    let saving: Promise<boolean> | null = null;
    act(() => {
      saving = hook.result.current.mark({ itemIndex: 0, decision: 'adopted' });
    });
    hook.rerender({ id: 'run-2' });
    await waitFor(() => {
      const now = hook.result.current.status;
      expect(now.state === 'ready' && now.review.runId).toBe(2);
    });
    await act(async () => {
      finish!({
        ...review(1),
        state: 'in_review',
        marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
      });
      await saving;
    });
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.runId).toBe(2);
    expect(now.state === 'ready' && now.review.marks).toEqual([]);
    expect(hook.result.current.saveError).toBeNull();
  });

  it('409 뒤 다시 읽기도 runId 가 바뀌었으면 버린다', async () => {
    let fail: ((error: unknown) => void) | null = null;
    const fake = store({
      getReview: vi.fn(async (runId: string) =>
        review(runId === 'run-1' ? 1 : 2),
      ),
      putReview: vi.fn(
        () =>
          new Promise<unknown>((_resolve, reject) => {
            fail = reject;
          }),
      ),
    });
    const hook = renderHook(({ id }) => useReview(fake, id), {
      initialProps: { id: 'run-1' },
    });
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    let saving: Promise<boolean> | null = null;
    act(() => {
      saving = hook.result.current.mark({ itemIndex: 0, decision: 'adopted' });
    });
    hook.rerender({ id: 'run-2' });
    await waitFor(() => {
      const now = hook.result.current.status;
      expect(now.state === 'ready' && now.review.runId).toBe(2);
    });
    const reads = vi.mocked(fake.getReview).mock.calls.length;
    await act(async () => {
      fail!(new StoreError('review_locked', '확정됨'));
      expect(await saving).toBe(false);
    });
    expect(vi.mocked(fake.getReview).mock.calls.length).toBe(reads);
    expect(hook.result.current.saveError).toBeNull();
  });
});
