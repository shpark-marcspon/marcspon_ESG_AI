// @vitest-environment jsdom
// (밴드 FS1 ③: results-hooks.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// headless 의 결과·검토 바닥(밴드 FW2 ① §3): 시작·[다시 실행] 거절(sid:MARC-ISSUE-99 1), 구독 차례(같은 이슈 2 — 늦게 온 값이 덮지 않음),
// pageCount 채우기([R5]), 결과 읽기(불러오는 중·없음·꼴 오류), 검토 쓰기(PUT 뒤 반영·실패·409·확정).
// 목 저장소 대신 시험 안의 가짜 저장소를 쓴다(headless 는 mock 을 모른다).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type {
  GreenwashStore,
  RunSnapshot,
} from '../../../entities/greenwash/api/index.ts';
import type { RunProgress } from '../../../entities/greenwash/model/index.ts';
import { useRunStatus } from './useRunStatus.ts';

afterEach(cleanup);

/** PUT 을 받아 서버처럼 갈아 끼우는 가짜(본문을 기록한다). */

const progress = (done: number): RunProgress => ({
  state: 'running',
  stage: 'judge',
  judge: { done, total: 44 },
});

const snap = (
  runId: string,
  done: number,
  extra: Partial<RunSnapshot> = {},
): RunSnapshot => ({
  runId,
  documentId: 'doc-a',
  startedAt: '2026-10-16T09:00:00+09:00',
  pageCount: 139,
  checkedPages: 44,
  progress: progress(done),
  rerunOf: null,
  errorCode: null,
  finishedAt: null,
  ...extra,
});

const reject = () =>
  vi.fn(async () => {
    throw new StoreError('rejected', '쓰지 않음');
  });

function baseStore(overrides: Partial<GreenwashStore> = {}): GreenwashStore {
  return {
    createDocument: vi.fn(async () => ({
      documentId: 'doc-a',
      pageCount: 60,
      hasText: true,
    })),
    createRun: vi.fn(async () => ({ runId: 'run-1' })),
    getRun: vi.fn(async (runId: string) => snap(runId, 0)),
    subscribeRun: vi.fn(() => () => {}),
    rerun: vi.fn(async () => ({ runId: 'run-2' })),
    listDocuments: vi.fn(async () => []),
    listDefaultTerms: vi.fn(async () => []),
    getDocument: vi.fn(async (documentId: string) => ({
      documentId,
      fileName: 'a.pdf',
      pageCount: 77,
    })),
    listCheckRows: reject(),
    getResult: reject(),
    getReview: reject(),
    putReview: reject(),
    rejudge: reject(),
    openDocumentPdf: vi.fn(async () => null),
    getReport: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    ...overrides,
  };
}

describe('구독 차례(sid:MARC-ISSUE-99 2)', () => {
  it('getRun 을 부르지 않는다. 현재값(조금 뒤에 온 것)과 그 뒤 값이 차례대로 들고, 늦게 끝난 getRun 이 있어도 덮지 않는다', async () => {
    let send: ((run: RunSnapshot) => void) | null = null;
    let resolveSlow: ((run: RunSnapshot) => void) | null = null;
    const store = baseStore({
      // 저장소 쪽에서 느린 읽기가 늦게 끝나는 꼴. 훅이 이것을 부르면 시험이 잡는다
      getRun: vi.fn(
        () =>
          new Promise<RunSnapshot>((resolve) => {
            resolveSlow = resolve;
          }),
      ),
      subscribeRun: vi.fn((_id, listener) => {
        send = listener;
        return () => {
          send = null;
        };
      }),
    });
    const hook = renderHook(() => useRunStatus(store, 'run-1'));
    expect(hook.result.current.state).toBe('loading');
    act(() => send!(snap('run-1', 10)));
    act(() => send!(snap('run-1', 20)));
    const now = hook.result.current;
    expect(now.state === 'ready' && now.run.progress.judge.done).toBe(20);
    expect(store.getRun).not.toHaveBeenCalled();
    expect(resolveSlow).toBeNull();
    hook.unmount();
    expect(send).toBeNull();
  });

  it('runId 가 바뀌면 새 값을 받기 전까지 loading(앞 실행의 값을 보이지 않는다)', () => {
    const sends = new Map<string, (run: RunSnapshot) => void>();
    const store = baseStore({
      subscribeRun: vi.fn((id, listener) => {
        sends.set(id, listener);
        return () => sends.delete(id);
      }),
    });
    const hook = renderHook(({ id }) => useRunStatus(store, id), {
      initialProps: { id: 'run-1' },
    });
    act(() => sends.get('run-1')!(snap('run-1', 5)));
    expect(hook.result.current.state).toBe('ready');
    hook.rerender({ id: 'run-2' });
    expect(hook.result.current.state).toBe('loading');
    expect(sends.has('run-1')).toBe(false);
    act(() => sends.get('run-2')!(snap('run-2', 1)));
    const now = hook.result.current;
    expect(now.state === 'ready' && now.run.runId).toBe('run-2');
  });
});

describe('pageCount 채우기 [R5]', () => {
  it('실행 응답에 쪽 수가 없으면 문서 조회로 채운다(문서마다 한 번)', async () => {
    let send: ((run: RunSnapshot) => void) | null = null;
    const store = baseStore({
      subscribeRun: vi.fn((_id, listener) => {
        send = listener;
        return () => {};
      }),
    });
    const hook = renderHook(() => useRunStatus(store, 'run-1'));
    act(() => send!(snap('run-1', 1, { pageCount: null })));
    const first = hook.result.current;
    expect(first.state === 'ready' && first.run.pageCount).toBeNull();
    await waitFor(() => {
      const now = hook.result.current;
      expect(now.state === 'ready' && now.run.pageCount).toBe(77);
    });
    act(() => send!(snap('run-1', 2, { pageCount: null })));
    const later = hook.result.current;
    expect(later.state === 'ready' && later.run.pageCount).toBe(77);
    expect(store.getDocument).toHaveBeenCalledTimes(1);
    expect(store.getDocument).toHaveBeenCalledWith('doc-a');
  });

  it('응답에 쪽 수가 있으면 조회하지 않는다. 조회가 거절되면 null 그대로', async () => {
    let send: ((run: RunSnapshot) => void) | null = null;
    const store = baseStore({
      subscribeRun: vi.fn((_id, listener) => {
        send = listener;
        return () => {};
      }),
      getDocument: vi.fn(async () => {
        throw new StoreError('not_found', '없음');
      }),
    });
    const hook = renderHook(() => useRunStatus(store, 'run-1'));
    act(() => send!(snap('run-1', 1)));
    expect(store.getDocument).not.toHaveBeenCalled();
    act(() => send!(snap('run-1', 1, { pageCount: null })));
    await waitFor(() => expect(store.getDocument).toHaveBeenCalled());
    const now = hook.result.current;
    expect(now.state === 'ready' && now.run.pageCount).toBeNull();
  });
});
