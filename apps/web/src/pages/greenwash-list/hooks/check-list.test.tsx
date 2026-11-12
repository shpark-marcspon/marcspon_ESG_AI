// @vitest-environment jsdom
// 밴드 FW2 ②: 목록 훅(useCheckList — 거르기·연도·숫자·[다시 실행] 거절)과 useReview 의 늦은 저장 막기(발주서 덧붙임 3).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import type {
  CheckRowsSource,
  GreenwashReview,
  ListedDocument,
  ListedRun,
} from '../../../entities/greenwash/model/index.ts';
import { useCheckList } from './useCheckList.ts';

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

const doc = (
  documentId: string,
  extra: Partial<ListedDocument> = {},
): ListedDocument => ({
  documentId,
  fileName: `${documentId}.pdf`,
  reportYear: 2026,
  previousDocumentId: null,
  pageCount: 10,
  uploadedAt: '2026-10-01T09:00:00+09:00',
  uploadedBy: { userId: 'me', name: '나' },
  ...extra,
});

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

const SOURCE: CheckRowsSource = {
  currentUserId: 'me',
  companyName: '회사',
  documents: [
    doc('old'),
    doc('new', { previousDocumentId: 'old', reportYear: 2025 }),
    doc('b', { uploadedBy: { userId: 'you', name: '너' }, reportYear: null }),
  ],
  runs: [
    run('r1', 'old', 'done'),
    run('r2', 'new', 'failed'),
    run('r3', 'b', 'running'),
  ],
};

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

describe('useCheckList', () => {
  it('읽으면 줄(판 사슬 마지막만)·숫자·연도, 거르기는 바로 바뀐다', async () => {
    const fake = store({ listCheckRows: vi.fn(async () => SOURCE) });
    const hook = renderHook(() => useCheckList(fake));
    expect(hook.result.current.status.state).toBe('loading');
    expect(hook.result.current.rows).toEqual([]);
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    const now = hook.result.current;
    expect(now.rows.map((row) => row.doc.documentId)).toEqual(['b', 'new']);
    // 문서 = 줄 수, 실행 = 그 줄들 문서의 실행(앞 판 old 의 실행은 세지 않는다)
    expect([now.documentCount, now.runCount]).toEqual([2, 2]);
    expect(now.years).toEqual([2025]);
    expect(now.companyName).toBe('회사');
    act(() => hook.result.current.setMineOnly(true));
    expect(hook.result.current.rows.map((r) => r.doc.documentId)).toEqual([
      'new',
    ]);
    act(() => {
      hook.result.current.setMineOnly(false);
      hook.result.current.setTab('running');
      hook.result.current.setQuery(' B ');
    });
    expect(hook.result.current.rows.map((r) => r.doc.documentId)).toEqual([
      'b',
    ]);
    act(() => hook.result.current.setReportYear(2025));
    expect(hook.result.current.rows).toEqual([]);
    // 거르기는 숫자를 바꾸지 않는다
    expect(hook.result.current.documentCount).toBe(2);
  });

  it('목록을 읽지 못하면 failed', async () => {
    const fake = store({
      listCheckRows: vi.fn(async () => {
        throw new Error('망');
      }),
    });
    const hook = renderHook(() => useCheckList(fake));
    await waitFor(() =>
      expect(hook.result.current.status.state).toBe('failed'),
    );
  });

  it('retry(밴드 LE1 ①): failed 에서 loading 을 거쳐 다시 읽는다', async () => {
    const listCheckRows = vi
      .fn<GreenwashStore['listCheckRows']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockResolvedValueOnce(SOURCE);
    const fake = store({ listCheckRows });
    const hook = renderHook(() => useCheckList(fake));
    await waitFor(() =>
      expect(hook.result.current.status.state).toBe('failed'),
    );
    act(() => hook.result.current.retry());
    expect(hook.result.current.status.state).toBe('loading');
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    expect(hook.result.current.rows.map((row) => row.doc.documentId)).toEqual([
      'b',
      'new',
    ]);
  });

  it('[다시 실행]: 받으면 새 runId, 거절되면 null 과 rerunError(그 실행 id·갈래)', async () => {
    const rerun = vi
      .fn<GreenwashStore['rerun']>()
      .mockRejectedValueOnce(new StoreError('rejected', '안 됨'))
      .mockResolvedValueOnce({ runId: 'r9' });
    const fake = store({ listCheckRows: vi.fn(async () => SOURCE), rerun });
    const hook = renderHook(() => useCheckList(fake));
    let next: string | null = 'x';
    await act(async () => {
      next = await hook.result.current.rerun('r2');
    });
    expect(next).toBeNull();
    expect(hook.result.current.rerunError).toEqual({
      runId: 'r2',
      error: 'rejected',
    });
    await act(async () => {
      next = await hook.result.current.rerun('r2');
    });
    expect(next).toBe('r9');
    expect(hook.result.current.rerunError).toBeNull();
  });
});
