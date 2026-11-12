// @vitest-environment jsdom
// (밴드 FS1 ③: pdf-summary-guards.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ④: GW-05 쪽 그림의 PDF 읽기(useDocumentPdf)와 확정 뒤 둘레 다시 읽기(useRunSummary 의 refresh).
import { act, cleanup, renderHook } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import type { CheckRowsSource } from '../../../entities/greenwash/model/index.ts';
import { useCheckList } from './useCheckList.ts';

afterEach(cleanup);

function store(overrides: Partial<GreenwashStore>): GreenwashStore {
  return overrides as GreenwashStore;
}

describe('겹친 누름 막기', () => {
  it('목록 [다시 실행]: 도는 동안 두 번째 부름은 저장소를 부르지 않고 null, rerunning 은 그 실행', async () => {
    let release: (value: { runId: string }) => void = () => {};
    const rerun = vi.fn(
      () =>
        new Promise<{ runId: string }>((resolve) => {
          release = resolve;
        }),
    );
    const fake = store({
      listCheckRows: vi.fn(async (): Promise<CheckRowsSource> => ({
        currentUserId: 'u',
        companyName: '가상 회사',
        documents: [],
        runs: [],
      })),
      rerun,
    });
    const hook = renderHook(() => useCheckList(fake));
    let first: Promise<string | null> = Promise.resolve(null);
    let second: string | null = 'x';
    await act(async () => {
      first = hook.result.current.rerun('run-9');
      second = await hook.result.current.rerun('run-9');
    });
    expect(second).toBeNull();
    expect(rerun).toHaveBeenCalledTimes(1);
    expect(hook.result.current.rerunning).toBe('run-9');
    await act(async () => {
      release({ runId: 'run-10' });
      expect(await first).toBe('run-10');
    });
    expect(hook.result.current.rerunning).toBeNull();
  });
});
