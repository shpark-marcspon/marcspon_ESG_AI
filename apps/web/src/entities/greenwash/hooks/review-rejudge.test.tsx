// @vitest-environment jsdom
// 밴드 GRJ1 ③: useReview 의 재판단 — 도는 근거 저장이 서버에 실린 뒤 POST 한다(칸을 벗어나며 [재판단]을 누른 갈래),
// 409 갈래는 다시 읽고 그 code, 누른 뒤 답까지 pressing. 값은 지어낸 것이다.
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../api/index.ts';
import type { GreenwashStore } from '../api/index.ts';
import type { GreenwashReview } from '../model/index.ts';
import { useReview } from './useReview.ts';

afterEach(cleanup);

// hooks 칸의 시험은 api/mock/testing.ts 를 못 가져온다(layers) — 여기서 짓는다.
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
    getReport: unused(),
    ...overrides,
  };
}

const review = (over: Partial<GreenwashReview> = {}): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  runId: 1,
  state: 'in_review',
  confirmedAt: null,
  confirmedBy: null,
  marks: [],
  edits: [],
  evidence: [],
  rejudges: [],
  ...over,
});

describe('useReview 재판단(GRJ1)', () => {
  it('근거 저장이 도는 중에 누르면 그 저장이 끝난 뒤 POST, 끝나면 다시 읽고 pressing 을 비운다', async () => {
    const order: string[] = [];
    let finishPut: (() => void) | null = null;
    const fake = store({
      getReview: vi.fn(async () => {
        order.push('GET');
        return review();
      }),
      putReview: vi.fn(
        () =>
          new Promise<unknown>((resolve) => {
            order.push('PUT 시작');
            finishPut = () => {
              order.push('PUT 끝');
              resolve(review());
            };
          }),
      ),
      rejudge: vi.fn(async () => {
        order.push('POST');
        return { rejudgeRunId: '9001' };
      }),
    });
    const { result } = renderHook(() => useReview(fake, 'run-1'));
    await waitFor(() => expect(result.current.status.state).toBe('ready'));
    order.length = 0;
    let saved: Promise<boolean> | null = null;
    let made: Promise<boolean> | null = null;
    act(() => {
      saved = result.current.evidence({
        itemIndex: 0,
        removed: [0],
        added: [],
      });
      made = result.current.rejudge(0);
    });
    await waitFor(() => expect(result.current.pressing.has(0)).toBe(true));
    expect(fake.rejudge).not.toHaveBeenCalled();
    await act(async () => {
      finishPut!();
      await saved;
      await made;
    });
    expect(order).toEqual(['PUT 시작', 'PUT 끝', 'POST', 'GET']);
    expect(await made!).toBe(true);
    expect(result.current.pressing.size).toBe(0);
    expect(vi.mocked(fake.putReview).mock.calls[0]![1]).toEqual({
      marks: [],
      evidence: [{ itemIndex: 0, removed: [0], added: [] }],
    });
  });

  it('409 rejudge_running·nothing_to_rejudge·review_locked 는 다시 읽고 그 code, 그 밖은 rejected', async () => {
    for (const kind of [
      'rejudge_running',
      'nothing_to_rejudge',
      'review_locked',
      'unreachable',
    ] as const) {
      const fake = store({
        getReview: vi.fn(async () => review()),
        rejudge: vi.fn(async () => {
          throw new StoreError(kind, '지어낸 거절');
        }),
      });
      const { result, unmount } = renderHook(() => useReview(fake, 'run-1'));
      await waitFor(() => expect(result.current.status.state).toBe('ready'));
      const reads = vi.mocked(fake.getReview).mock.calls.length;
      let ok: boolean | null = null;
      await act(async () => {
        ok = await result.current.rejudge(0);
      });
      expect(ok).toBe(false);
      expect(result.current.saveError).toBe(
        kind === 'unreachable' ? 'rejected' : kind,
      );
      expect(vi.mocked(fake.getReview).mock.calls.length).toBe(
        kind === 'unreachable' ? reads : reads + 1,
      );
      unmount();
    }
  });
});
