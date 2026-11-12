// @vitest-environment jsdom
// (밴드 FS1 ③: pdf-summary-guards.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ④: GW-05 쪽 그림의 PDF 읽기(useDocumentPdf)와 확정 뒤 둘레 다시 읽기(useRunSummary 의 refresh).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GreenwashStore } from '../api/index.ts';
import { useRerun } from './useRerun.ts';
import { useReview } from './useReview.ts';

afterEach(cleanup);

function store(overrides: Partial<GreenwashStore>): GreenwashStore {
  return overrides as GreenwashStore;
}

describe('겹친 누름 막기', () => {
  it('GW-03 [다시 실행](useRerun): 같은 그리기 안의 두 번째 부름은 저장소를 부르지 않는다(목록과 같은 핵심)', async () => {
    let release: (value: { runId: string }) => void = () => {};
    const rerun = vi.fn(
      () =>
        new Promise<{ runId: string }>((resolve) => {
          release = resolve;
        }),
    );
    const hook = renderHook(() => useRerun(store({ rerun }), 'run-9'));
    let first: Promise<string | null> = Promise.resolve(null);
    let second: string | null = 'x';
    await act(async () => {
      first = hook.result.current.rerun();
      second = await hook.result.current.rerun();
    });
    expect(second).toBeNull();
    expect(rerun).toHaveBeenCalledTimes(1);
    expect(hook.result.current.rerunning).toBe(true);
    await act(async () => {
      release({ runId: 'run-10' });
      expect(await first).toBe('run-10');
    });
    expect(hook.result.current.rerunning).toBe(false);
  });
  it('useReview: 같은 그리기 안의 두 번째 mark 는 PUT 을 부르지 않는다(ref 로 막음)', async () => {
    const review = {
      schemaVersion: 'greenwash.review@3',
      evidence: [],
      rejudges: [],
      runId: 1,
      state: 'in_review',
      confirmedAt: null,
      confirmedBy: null,
      marks: [],
      edits: [],
    };
    let release: (value: unknown) => void = () => {};
    const put = vi.fn(
      () =>
        new Promise<unknown>((resolve) => {
          release = resolve;
        }),
    );
    const fake = store({
      getReview: vi.fn(async () => review),
      putReview: put,
    });
    const hook = renderHook(() => useReview(fake, 'run-1'));
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    const { mark } = hook.result.current;
    let second: boolean | null = null;
    await act(async () => {
      void mark({ itemIndex: 0, decision: 'adopted' });
      second = await mark({ itemIndex: 1, decision: 'adopted' });
    });
    expect(second).toBe(false);
    expect(put).toHaveBeenCalledTimes(1);
    await act(async () => {
      release({
        ...review,
        marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
      });
    });
  });
});
