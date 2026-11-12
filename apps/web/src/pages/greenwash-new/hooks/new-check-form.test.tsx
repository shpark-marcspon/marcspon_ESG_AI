// @vitest-environment jsdom
// 밴드 FW2 ⓪: 새 점검 폼 훅의 칸 이름. 수정본 대상·이전 문서 목록 시험은 밴드 GW2R ① 에서 지웠다(v115 — 수정본 칸 뺌).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { useNewCheckForm } from './useNewCheckForm.ts';
import type { UploadItem } from './useNewCheckForm.ts';

afterEach(cleanup);

function storeWith(documents: { documentId: string; fileName: string }[]) {
  const store: GreenwashStore = {
    createDocument: vi.fn(async () => ({
      documentId: 'doc-1',
      pageCount: 60,
      hasText: true,
    })),
    createRun: vi.fn(async () => ({ runId: 'run-1' })),
    getRun: vi.fn(async () => {
      throw new Error('없음');
    }),
    subscribeRun: vi.fn(() => () => {}),
    rerun: vi.fn(async () => ({ runId: 'run-2' })),
    listDocuments: vi.fn(async () =>
      documents.map((doc) => ({ ...doc, uploadedAt: '2026-10-01' })),
    ),
    listDefaultTerms: vi.fn(async () => []),
    getDocument: vi.fn(async () => {
      throw new Error('없음');
    }),
    listCheckRows: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    getResult: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    getReview: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    putReview: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    rejudge: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    openDocumentPdf: vi.fn(async () => null),
    getReport: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
  };
  return store;
}

const item: UploadItem = {
  id: 'a',
  name: 'a.pdf',
  date: '2026-10-16',
  file: new File([new Uint8Array([1])], 'a.pdf'),
};

describe('useNewCheckForm: 칸 이름', () => {
  it('돌려주는 칸 이름은 그대로 document(지역 이름만 uploaded 로 바꿈)', async () => {
    const store = storeWith([{ documentId: 'old-1', fileName: '앞.pdf' }]);
    const hook = renderHook(() => useNewCheckForm({ store }));
    act(() => hook.result.current.onChangeItems([item]));
    await waitFor(() =>
      expect(hook.result.current.document?.documentId).toBe('doc-1'),
    );
  });
});
