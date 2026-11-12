// @vitest-environment jsdom
// 밴드 FW2 ④: GW-05 쪽 그림의 PDF 읽기(useDocumentPdf)와 확정 뒤 둘레 다시 읽기(useRunSummary 의 refresh).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { useDocumentPdf } from './useDocumentPdf.ts';

afterEach(cleanup);

function store(overrides: Partial<GreenwashStore>): GreenwashStore {
  return overrides as GreenwashStore;
}

describe('useDocumentPdf(store, runId)', () => {
  const snapshot = (documentId: string) => ({ documentId }) as never;

  it('getRun 의 documentId 로 openDocumentPdf: File 이면 ready(file), null 이면 ready(null)', async () => {
    const file = new File(['%PDF'], 'a.pdf');
    for (const [given, expected] of [
      [file, { state: 'ready', file }],
      [null, { state: 'ready', file: null }],
    ] as const) {
      const open = vi.fn(async () => given);
      const fake = store({
        getRun: vi.fn(async () => snapshot('doc-1')),
        openDocumentPdf: open,
      });
      const { result, unmount } = renderHook(() =>
        useDocumentPdf(fake, 'run-1'),
      );
      expect(result.current.status).toEqual({ state: 'loading' });
      await waitFor(() => expect(result.current.status).toEqual(expected));
      expect(open).toHaveBeenCalledWith('doc-1');
      unmount();
    }
  });

  it('실행 읽기가 거절되면 failed — 「불러오는 중」에 머물지 않는다. 목록(listCheckRows)은 부르지 않는다', async () => {
    const list = vi.fn(async () => {
      throw new Error('목록 거절');
    });
    const open = vi.fn(async () => null);
    const fake = store({
      getRun: vi.fn(async () => {
        throw new Error('망');
      }),
      openDocumentPdf: open,
      listCheckRows: list,
    });
    const { result } = renderHook(() => useDocumentPdf(fake, 'run-x'));
    await waitFor(() =>
      expect(result.current.status).toEqual({ state: 'failed' }),
    );
    expect(open).not.toHaveBeenCalled();
    expect(list).not.toHaveBeenCalled();
  });

  it('없음(not_found, 밴드 LA1 ②): 실행 읽기든 PDF 읽기든 404 면 missing(다시 시도 없는 갈래)', async () => {
    for (const [getRun, openDocumentPdf] of [
      [
        vi.fn(async () => {
          throw new StoreError('not_found', '없음');
        }),
        vi.fn(async () => null),
      ],
      [
        vi.fn(async () => snapshot('doc-1')),
        vi.fn(async () => {
          throw new StoreError('not_found', '없음');
        }),
      ],
    ] as const) {
      const fake = store({ getRun, openDocumentPdf });
      const { result, unmount } = renderHook(() =>
        useDocumentPdf(fake, 'run-1'),
      );
      await waitFor(() =>
        expect(result.current.status).toEqual({ state: 'missing' }),
      );
      unmount();
    }
  });

  it('retry(밴드 LE1 ①): failed 에서 loading 을 거쳐 다시 읽고, ready 면 새 File', async () => {
    const file = new File(['%PDF'], 'a.pdf');
    const getRun = vi
      .fn<GreenwashStore['getRun']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockResolvedValue(snapshot('doc-1'));
    const fake = store({ getRun, openDocumentPdf: vi.fn(async () => file) });
    const { result } = renderHook(() => useDocumentPdf(fake, 'run-1'));
    await waitFor(() =>
      expect(result.current.status).toEqual({ state: 'failed' }),
    );
    act(() => result.current.retry());
    expect(result.current.status).toEqual({ state: 'loading' });
    await waitFor(() =>
      expect(result.current.status).toEqual({ state: 'ready', file }),
    );
    expect(getRun).toHaveBeenCalledTimes(2);
  });

  it('runId 가 바뀌면 그 실행의 PDF 가 올 때까지 loading(앞 File 을 내지 않는다)', async () => {
    const first = new File(['1'], '1.pdf');
    let release: (file: File) => void = () => {};
    const fake = store({
      getRun: vi.fn(async (runId: string) => snapshot(`doc-${runId}`)),
      openDocumentPdf: vi.fn((id: string) =>
        id === 'doc-run-1' ?
          Promise.resolve(first)
        : new Promise<File>((resolve) => {
            release = resolve;
          }),
      ),
    });
    const { result, rerender } = renderHook(
      ({ id }) => useDocumentPdf(fake, id),
      { initialProps: { id: 'run-1' } },
    );
    await waitFor(() =>
      expect(result.current.status).toEqual({ state: 'ready', file: first }),
    );
    rerender({ id: 'run-2' });
    expect(result.current.status).toEqual({ state: 'loading' });
    const second = new File(['2'], '2.pdf');
    await waitFor(() => expect(fake.openDocumentPdf).toHaveBeenCalledTimes(2));
    release(second);
    await waitFor(() =>
      expect(result.current.status).toEqual({ state: 'ready', file: second }),
    );
  });
});
