// @vitest-environment jsdom
// headless 의 결과·검토 바닥(밴드 FW2 ① §3): 시작·[다시 실행] 거절(sid:MARC-ISSUE-99 1), 구독 차례(같은 이슈 2 — 늦게 온 값이 덮지 않음),
// pageCount 채우기([R5]), 결과 읽기(불러오는 중·없음·꼴 오류), 검토 쓰기(PUT 뒤 반영·실패·409·확정).
// 밴드 LE1 ①: 결과·검토 읽기의 retry([다시 시도] — 늘 loading 을 거친다).
// 목 저장소 대신 시험 안의 가짜 저장소를 쓴다(headless 는 mock 을 모른다).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../api/index.ts';
import type { GreenwashStore, RunSnapshot } from '../api/index.ts';
import type { GreenwashReview, RunProgress } from '../model/index.ts';
import { useRerun } from './useRerun.ts';
import { useResult } from './useResult.ts';
import { useReview } from './useReview.ts';

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

// 계약 예시와 같은 꼴의 아주 작은 결과(모든 칸). 값은 지어낸 것.
const resultJson = {
  schemaVersion: 'greenwash.result@1',
  source: { fileName: 'a.pdf', sha256: 'b'.repeat(64), pageCount: 3 },
  config: {
    checker: {
      maxCandidatesPerPage: 3,
      maxCharsPageText: 1,
      evidenceK: 1,
      maxCharsPerChunk: 1,
      useEvidenceFailopen: false,
      maxCharsEvidenceTotal: 1,
      reportLevels: ['High'],
      debug: false,
      debugPages: 0,
      batchEval: false,
      promptVersion: 'v',
    },
    chunking: {
      chunkSize: 1,
      chunkOverlap: 0,
      separators: [],
      normalize: true,
      embeddingBatchSize: 1,
    },
    chat: { temperature: 0, maxTokens: 1 },
  },
  models: { chat: 'c', embedding: 'e' },
  promptVersion: 'v',
  parts: [{ name: 'CEO 메시지', pages: [1] }],
  pages: [1],
  extraTerms: [],
  items: [0, 1, 2].map((i) => ({
    page: 1,
    parts: ['CEO 메시지'],
    sentence: `문장 ${i}`,
    level: 'Mid',
    riskTags: ['근거 부족'],
    confirmedInEvidence: [],
    missingFields: [],
    reasonBullets: [],
    fixParagraph: '방향',
    evidencePages: [],
    evidenceInternal: '',
    position: null,
    exampleSentence: null,
  })),
  candidateStats: {
    raw: 3,
    hardDropped: 0,
    nonEnvDropped: 0,
    promoDropped: 0,
    tableDropped: 0,
    kept: 3,
    failedPages: [],
  },
  counts: {
    total: 3,
    byLevel: { High: 0, Mid: 3, Low: 0 },
    byPart: { 'CEO 메시지': { High: 0, Mid: 3, Low: 0 } },
  },
  wordCounts: { total: [], pages: [] },
  dryRun: null,
  report: { file: 'greenwash-report.xlsx' },
};

const reviewJson = (
  state: GreenwashReview['state'],
  marks: GreenwashReview['marks'] = [],
): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  evidence: [],
  rejudges: [],
  runId: 1,
  state,
  confirmedAt: state === 'confirmed' ? '2026-10-16T10:00:00+09:00' : null,
  confirmedBy: state === 'confirmed' ? { id: 1, name: '가상 사람' } : null,
  marks,
  edits: [],
});

function reviewStore(start: GreenwashReview) {
  let current = start;
  const bodies: unknown[] = [];
  const store = baseStore({
    getReview: vi.fn(async () => current),
    putReview: vi.fn(async (_runId, update) => {
      bodies.push(update);
      if (current.state === 'confirmed')
        throw new StoreError('review_locked', '확정됨');
      current = {
        ...current,
        // 서버 규칙(결함 D1): 표시가 있으면 pending → in_review, confirmed 면 확정.
        state:
          update.state === 'confirmed' ? 'confirmed'
          : current.state === 'pending' && update.marks.length > 0 ? 'in_review'
          : current.state,
        confirmedAt:
          update.state === 'confirmed' ? '2026-10-16T10:00:00+09:00' : null,
        marks: [...update.marks],
      };
      return current;
    }),
  });
  return { store, bodies, set: (next: GreenwashReview) => (current = next) };
}

describe('시작·[다시 실행] 거절(sid:MARC-ISSUE-99 1)', () => {
  it('useRerun: 거절되면 null 과 startError, 받으면 새 runId. 다른 실행으로 바뀌면 앞 거절은 보이지 않는다', async () => {
    const rerun = vi
      .fn<GreenwashStore['rerun']>()
      .mockRejectedValueOnce(new StoreError('rejected', '실패가 아님'))
      .mockResolvedValueOnce({ runId: 'run-9' });
    const store = baseStore({ rerun });
    const hook = renderHook(({ id }) => useRerun(store, id), {
      initialProps: { id: 'run-1' },
    });
    let next: string | null = 'x';
    await act(async () => {
      next = await hook.result.current.rerun();
    });
    expect(next).toBeNull();
    expect(hook.result.current.startError).toBe('rejected');
    expect(hook.result.current.rerunning).toBe(false);
    hook.rerender({ id: 'run-3' });
    expect(hook.result.current.startError).toBeNull();
    await act(async () => {
      next = await hook.result.current.rerun();
    });
    expect(next).toBe('run-9');
    expect(rerun).toHaveBeenLastCalledWith(
      'run-3',
      expect.stringMatching(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      ),
    );
  });
});

describe('useResult', () => {
  it('불러오는 중 → 꼴을 지난 결과', async () => {
    const store = baseStore({ getResult: vi.fn(async () => resultJson) });
    const hook = renderHook(() => useResult(store, 'run-1'));
    expect(hook.result.current.status.state).toBe('loading');
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.result.items).toHaveLength(3);
  });

  it('없음(not_found) → missing, 그 밖의 거절 → failed, 꼴 오류 → invalid', async () => {
    const missingStore = baseStore({
      getResult: vi.fn(async () => {
        throw new StoreError('not_found', '없음');
      }),
    });
    const missing = renderHook(() => useResult(missingStore, 'run-1'));
    await waitFor(() =>
      expect(missing.result.current.status.state).toBe('missing'),
    );
    const failedStore = baseStore({
      getResult: vi.fn(async () => {
        throw new Error('망');
      }),
    });
    const failed = renderHook(() => useResult(failedStore, 'run-1'));
    await waitFor(() =>
      expect(failed.result.current.status.state).toBe('failed'),
    );
    // 맨 위의 모르는 키는 버리고 지난다(결함 D10, 밴드 WC1 ①). 필수 칸이 빠지면 꼴 오류.
    const extraStore = baseStore({
      getResult: vi.fn(async () => ({ ...resultJson, surprise: 1 })),
    });
    const extra = renderHook(() => useResult(extraStore, 'run-1'));
    await waitFor(() =>
      expect(extra.result.current.status.state).toBe('ready'),
    );
    const withoutWords: Record<string, unknown> = { ...resultJson };
    delete withoutWords.wordCounts;
    const invalidStore = baseStore({
      getResult: vi.fn(async () => withoutWords),
    });
    const invalid = renderHook(() => useResult(invalidStore, 'run-1'));
    await waitFor(() =>
      expect(invalid.result.current.status.state).toBe('invalid'),
    );
    const now = invalid.result.current.status;
    // 두 갈래 union 이라 zod 는 「(맨 위): Invalid input」 한 줄을 낸다 — 글은 개발자용이라 비어 있지 않은지만 본다.
    expect(now.state === 'invalid' ? now.issues.length : 0).toBeGreaterThan(0);
  });
});

describe('useReview', () => {
  it('채택은 PUT 이 끝난 뒤 반영, 첫 표시 본문에 state 없음(결함 D1)·저장소가 돌려준 in_review, 둘째 표시 본문에 첫 표시가 남는다', async () => {
    const { store, bodies } = reviewStore(reviewJson('pending'));
    const hook = renderHook(() => useReview(store, 'run-1'));
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    let saved = false;
    await act(async () => {
      saved = await hook.result.current.mark({
        itemIndex: 1,
        decision: 'adopted',
      });
    });
    expect(saved).toBe(true);
    await act(async () => {
      await hook.result.current.mark({
        itemIndex: 0,
        decision: 'excluded',
        reason: '등급이 맞지 않음',
      });
    });
    expect(bodies).toEqual([
      {
        marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
      },
      {
        marks: [
          {
            itemIndex: 0,
            decision: 'excluded',
            excludeReason: '등급이 맞지 않음',
          },
          { itemIndex: 1, decision: 'adopted', excludeReason: null },
        ],
      },
    ]);
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.state).toBe('in_review');
    expect(now.state === 'ready' && now.review.marks).toHaveLength(2);
  });

  it('PUT 이 실패하면 검토는 그대로, saveError = rejected', async () => {
    const { store } = reviewStore(reviewJson('pending'));
    vi.mocked(store.putReview).mockRejectedValueOnce(new Error('망'));
    const hook = renderHook(() => useReview(store, 'run-1'));
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    let saved = true;
    await act(async () => {
      saved = await hook.result.current.mark({
        itemIndex: 0,
        decision: 'adopted',
      });
    });
    expect(saved).toBe(false);
    expect(hook.result.current.saveError).toBe('rejected');
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.marks).toEqual([]);
  });

  it('409(review_locked)면 다시 읽어 잠긴 상태로, saveError = review_locked', async () => {
    const { store, set } = reviewStore(reviewJson('in_review'));
    const hook = renderHook(() => useReview(store, 'run-1'));
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    // 다른 자리에서 확정됐다
    set(
      reviewJson('confirmed', [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
      ]),
    );
    await act(async () => {
      await hook.result.current.mark({ itemIndex: 0, decision: 'adopted' });
    });
    expect(hook.result.current.saveError).toBe('review_locked');
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.state).toBe('confirmed');
    expect(store.getReview).toHaveBeenCalledTimes(2);
  });

  it.each(['run_not_done', 'no_review'] as const)(
    '409(%s)면 다시 읽지 않고 saveError 에 그 code 를 단다',
    async (code) => {
      const { store } = reviewStore(reviewJson('in_review'));
      store.putReview = vi.fn(async () => {
        throw new StoreError(code, '409');
      });
      const hook = renderHook(() => useReview(store, 'run-1'));
      await waitFor(() =>
        expect(hook.result.current.status.state).toBe('ready'),
      );
      await act(async () => {
        await hook.result.current.mark({ itemIndex: 0, decision: 'adopted' });
      });
      expect(hook.result.current.saveError).toBe(code);
      expect(store.getReview).toHaveBeenCalledTimes(1);
    },
  );

  it('확정: 미검토를 채택으로 채운 본문 하나, 돌려받은 검토를 넣는다', async () => {
    const { store, bodies } = reviewStore(
      reviewJson('in_review', [
        { itemIndex: 1, decision: 'excluded', excludeReason: '기타: x' },
      ]),
    );
    const hook = renderHook(() => useReview(store, 'run-1'));
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    await act(async () => {
      await hook.result.current.confirm(3);
    });
    expect(bodies).toEqual([
      {
        state: 'confirmed',
        marks: [
          { itemIndex: 0, decision: 'adopted', excludeReason: null },
          { itemIndex: 1, decision: 'excluded', excludeReason: '기타: x' },
          { itemIndex: 2, decision: 'adopted', excludeReason: null },
        ],
      },
    ]);
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.state).toBe('confirmed');
  });

  it('돌려받은 검토가 꼴을 지나지 못하면 saveError = invalid, 검토는 그대로', async () => {
    const { store } = reviewStore(reviewJson('pending'));
    vi.mocked(store.putReview).mockResolvedValueOnce({ nope: true });
    const hook = renderHook(() => useReview(store, 'run-1'));
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    await act(async () => {
      await hook.result.current.mark({ itemIndex: 0, decision: 'adopted' });
    });
    expect(hook.result.current.saveError).toBe('invalid');
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.state).toBe('pending');
  });

  it('읽기: 없음 → missing, 꼴 오류 → invalid', async () => {
    const missingStore = baseStore({
      getReview: vi.fn(async () => {
        throw new StoreError('not_found', '없음');
      }),
    });
    const missing = renderHook(() => useReview(missingStore, 'run-1'));
    await waitFor(() =>
      expect(missing.result.current.status.state).toBe('missing'),
    );
    // 맨 위의 모르는 키는 버리고 지난다(결함 D10, 밴드 WC1 ①). 필수 칸(confirmedBy)이 빠지면 꼴 오류.
    const extraStore = baseStore({
      getReview: vi.fn(async () => ({ ...reviewJson('pending'), x: 1 })),
    });
    const extra = renderHook(() => useReview(extraStore, 'run-1'));
    await waitFor(() =>
      expect(extra.result.current.status.state).toBe('ready'),
    );
    const withoutBy: Record<string, unknown> = { ...reviewJson('pending') };
    delete withoutBy.confirmedBy;
    const invalidStore = baseStore({
      getReview: vi.fn(async () => withoutBy),
    });
    const invalid = renderHook(() => useReview(invalidStore, 'run-1'));
    await waitFor(() =>
      expect(invalid.result.current.status.state).toBe('invalid'),
    );
  });
});

describe('retry(밴드 LE1 ①)', () => {
  it('useResult: invalid(useLoad 에서는 ready) 에서 retry → loading → ready', async () => {
    const withoutWords: Record<string, unknown> = { ...resultJson };
    delete withoutWords.wordCounts;
    const getResult = vi
      .fn<GreenwashStore['getResult']>()
      .mockResolvedValueOnce(withoutWords as never)
      .mockResolvedValueOnce(resultJson as never);
    const fake = baseStore({ getResult });
    const hook = renderHook(() => useResult(fake, 'run-1'));
    await waitFor(() =>
      expect(hook.result.current.status.state).toBe('invalid'),
    );
    act(() => hook.result.current.retry());
    expect(hook.result.current.status.state).toBe('loading');
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    expect(getResult).toHaveBeenCalledTimes(2);
  });

  it('useResult: failed 에서 retry → loading → 또 failed(같은 갈래)', async () => {
    const getResult = vi.fn<GreenwashStore['getResult']>(async () => {
      throw new Error('망');
    });
    const fake = baseStore({ getResult });
    const hook = renderHook(() => useResult(fake, 'run-1'));
    await waitFor(() =>
      expect(hook.result.current.status.state).toBe('failed'),
    );
    act(() => hook.result.current.retry());
    expect(hook.result.current.status.state).toBe('loading');
    await waitFor(() =>
      expect(hook.result.current.status.state).toBe('failed'),
    );
    expect(getResult).toHaveBeenCalledTimes(2);
  });

  it('useReview: failed 에서 retry → loading → ready', async () => {
    const getReview = vi
      .fn<GreenwashStore['getReview']>()
      .mockRejectedValueOnce(new Error('망'))
      .mockResolvedValueOnce(reviewJson('pending') as never);
    const fake = baseStore({ getReview });
    const hook = renderHook(() => useReview(fake, 'run-1'));
    await waitFor(() =>
      expect(hook.result.current.status.state).toBe('failed'),
    );
    act(() => hook.result.current.retry());
    expect(hook.result.current.status.state).toBe('loading');
    await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
    expect(getReview).toHaveBeenCalledTimes(2);
  });
});
