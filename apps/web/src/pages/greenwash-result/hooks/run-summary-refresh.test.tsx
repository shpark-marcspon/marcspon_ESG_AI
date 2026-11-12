// @vitest-environment jsdom
// (밴드 FS1 ③: pdf-summary-guards.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ④: GW-05 쪽 그림의 PDF 읽기(useDocumentPdf)와 확정 뒤 둘레 다시 읽기(useRunSummary 의 refresh).
import { cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import type { CheckRowsSource } from '../../../entities/greenwash/model/index.ts';
import { useRunSummary } from './useRunSummary.ts';

afterEach(cleanup);

function store(overrides: Partial<GreenwashStore>): GreenwashStore {
  return overrides as GreenwashStore;
}

describe('useRunSummary refresh', () => {
  it('refresh 가 바뀌면 다시 읽고, 다시 읽는 동안은 앞 값을 낸다', async () => {
    let by: string | null = null;
    const source = (): CheckRowsSource => ({
      currentUserId: 'u',
      companyName: '가상 회사',
      documents: [],
      runs: [
        {
          runId: 'run-1',
          documentId: 'doc-1',
          createdAt: '2026-10-15T09:00:00+09:00',
          progress: { state: 'done' } as never,
          levelCounts: null,
          review: {
            state: by === null ? 'in_review' : 'confirmed',
            reviewed: 0,
            total: 1,
            confirmedAt: null,
            confirmedBy: by,
          },
        },
      ],
    });
    const list = vi.fn(async () => source());
    const fake = store({ listCheckRows: list });
    const { result, rerender } = renderHook(
      ({ refresh }) => useRunSummary(fake, 'run-1', refresh),
      { initialProps: { refresh: 'in_review' } },
    );
    await waitFor(() => expect(result.current.state).toBe('ready'));
    by = '지금 사람';
    rerender({ refresh: 'confirmed' });
    expect(result.current.state).toBe('ready');
    await waitFor(() =>
      expect(
        result.current.state === 'ready' &&
          result.current.run?.review?.confirmedBy,
      ).toBe('지금 사람'),
    );
    expect(list).toHaveBeenCalledTimes(2);
  });
});
