// @vitest-environment jsdom
// 밴드 G1b-3 ③: useReview.edit — 늦은 저장 막기·savedAt·앞 저장 중에 온 고침은 앞 저장이 끝난 뒤 한 번만 보냄(본문은 앞 저장 뒤의 검토에서)·
// 실패면 false + saveError(화면은 칸을 연 채)·확정 전 다시 읽기가 edits 값 차이를 잡음(고친 때·사람 차이는 잡지 않음). 값은 지어낸 것이다.
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../api/index.ts';
import type { GreenwashStore } from '../api/index.ts';
import type {
  GreenwashReview,
  ReviewEdit,
  ReviewUpdate,
} from '../model/index.ts';
import { useReview } from './useReview.ts';

afterEach(cleanup);

// hooks 칸의 시험은 api/mock/testing.ts 를 못 가져온다(layers) — review-late-save.test.tsx 처럼 여기서 짓는다.
const unused = () =>
  vi.fn(async () => {
    throw new StoreError('rejected', '쓰지 않음');
  });

function fakeStore(overrides: Partial<GreenwashStore>): GreenwashStore {
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

/** 부를 때마다 밖에서 끝내는 약속을 하나씩 내는 메서드. calls[n] 이 n 번째 부름의 resolve·reject 다. */
function deferredCalls<T>() {
  const calls: { resolve(value: T): void; reject(error: unknown): void }[] = [];
  const fn = vi.fn(
    () =>
      new Promise<T>((resolve, reject) => {
        calls.push({ resolve, reject });
      }),
  );
  return { fn, calls };
}

const by = { id: 3, name: '가상 고친이' };

const review = (over: Partial<GreenwashReview> = {}): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  evidence: [],
  rejudges: [],
  runId: 1,
  state: 'pending',
  confirmedAt: null,
  confirmedBy: null,
  marks: [],
  edits: [],
  ...over,
});

const levelEdit = (
  value: 'High' | 'Mid' | 'Low',
  editedAt = '2026-10-22T10:00:00+09:00',
): ReviewEdit => ({
  itemIndex: 0,
  level: { value, editedAt, editedBy: by },
  reasonBullets: null,
  fixParagraph: null,
});

async function ready(store: ReturnType<typeof fakeStore>) {
  const hook = renderHook(({ id }) => useReview(store, id), {
    initialProps: { id: 'run-1' },
  });
  await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
  return hook;
}

describe('useReview.edit', () => {
  it('저장되면 서버가 돌려준 검토를 넣고 savedAt 을 단다. 본문은 marks 그대로 + 고침 전부', async () => {
    const saved = review({ state: 'in_review', edits: [levelEdit('Low')] });
    const fake = fakeStore({
      getReview: vi.fn(async () =>
        review({
          marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
        }),
      ),
      putReview: vi.fn(async () => saved),
    });
    const hook = await ready(fake);
    expect(hook.result.current.savedAt).toBeNull();
    let ok: boolean | null = null;
    await act(async () => {
      ok = await hook.result.current.edit({
        itemIndex: 0,
        column: 'level',
        value: 'Low',
      });
    });
    expect(ok).toBe(true);
    expect(vi.mocked(fake.putReview).mock.calls).toEqual([
      [
        'run-1',
        {
          marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
          edits: [
            {
              itemIndex: 0,
              level: 'Low',
              reasonBullets: null,
              fixParagraph: null,
            },
          ],
        },
      ],
    ]);
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.edits).toEqual([
      levelEdit('Low'),
    ]);
    expect(hook.result.current.savedAt).not.toBeNull();
  });

  it('저장이 끝나기 전에 runId 가 바뀌면 늦게 온 고침 저장 결과가 새 실행을 덮지 않는다', async () => {
    const put = deferredCalls<unknown>();
    const fake = fakeStore({
      getReview: vi.fn(async (runId: string) =>
        review({ runId: runId === 'run-1' ? 1 : 2 }),
      ),
      putReview: put.fn,
    });
    const hook = await ready(fake);
    let saving: Promise<boolean> | null = null;
    act(() => {
      saving = hook.result.current.edit({
        itemIndex: 0,
        column: 'fixParagraph',
        value: '가',
      });
    });
    hook.rerender({ id: 'run-2' });
    await waitFor(() => {
      const now = hook.result.current.status;
      expect(now.state === 'ready' && now.review.runId).toBe(2);
    });
    await act(async () => {
      put.calls[0]!.resolve(
        review({ state: 'in_review', edits: [levelEdit('Low')] }),
      );
      await saving;
    });
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.runId).toBe(2);
    expect(now.state === 'ready' && now.review.edits).toEqual([]);
  });

  it('앞 저장 중에 온 고침은 버리지 않고 앞 저장이 끝난 뒤 한 번만 보낸다 — 본문은 앞 저장 뒤의 검토(표시 포함)에서', async () => {
    const put = deferredCalls<unknown>();
    const fake = fakeStore({
      getReview: vi.fn(async () => review()),
      putReview: put.fn,
    });
    const hook = await ready(fake);
    let marking: Promise<boolean> | null = null;
    let editing: Promise<boolean> | null = null;
    act(() => {
      marking = hook.result.current.mark({ itemIndex: 1, decision: 'adopted' });
    });
    act(() => {
      editing = hook.result.current.edit({
        itemIndex: 0,
        column: 'fixParagraph',
        value: '고친 수정 방향',
      });
    });
    // 앞 저장이 도는 동안은 PUT 하나뿐
    expect(put.fn).toHaveBeenCalledTimes(1);
    const afterMark = review({
      state: 'in_review',
      marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
    });
    await act(async () => {
      put.calls[0]!.resolve(afterMark);
      await marking;
    });
    await waitFor(() => expect(put.fn).toHaveBeenCalledTimes(2));
    const second = vi.mocked(put.fn).mock.calls[1] as unknown as [
      string,
      ReviewUpdate,
    ];
    expect(second[1]).toEqual({
      marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
      edits: [
        {
          itemIndex: 0,
          level: null,
          reasonBullets: null,
          fixParagraph: '고친 수정 방향',
        },
      ],
    });
    await act(async () => {
      put.calls[1]!.resolve(afterMark);
      expect(await editing).toBe(true);
    });
    // 그 뒤 더 보내지 않는다
    expect(put.fn).toHaveBeenCalledTimes(2);
  });

  it('앞 저장이 실패해도 기다린 고침은 한 번 보낸다', async () => {
    const put = deferredCalls<unknown>();
    const fake = fakeStore({
      getReview: vi.fn(async () => review()),
      putReview: put.fn,
    });
    const hook = await ready(fake);
    let editing: Promise<boolean> | null = null;
    act(() => {
      void hook.result.current.edit({
        itemIndex: 0,
        column: 'level',
        value: 'Mid',
      });
    });
    act(() => {
      editing = hook.result.current.edit({
        itemIndex: 0,
        column: 'reasonBullets',
        value: ['가'],
      });
    });
    await act(async () => {
      put.calls[0]!.reject(new StoreError('rejected', '400'));
    });
    await waitFor(() => expect(put.fn).toHaveBeenCalledTimes(2));
    // 앞 저장이 안 됐으니 본문은 처음 검토(고침 없음)에서 — 기다린 칸만
    expect((vi.mocked(put.fn).mock.calls[1] as unknown[])[1]).toEqual({
      marks: [],
      edits: [
        {
          itemIndex: 0,
          level: null,
          reasonBullets: ['가'],
          fixParagraph: null,
        },
      ],
    });
    await act(async () => {
      put.calls[1]!.resolve(review());
      expect(await editing).toBe(true);
    });
  });

  it('실패(400 INVALID_REVIEW → rejected)면 false·saveError rejected·검토 그대로', async () => {
    const fake = fakeStore({
      getReview: vi.fn(async () => review()),
      putReview: vi.fn(async () => {
        throw new StoreError('rejected', '판정 사유는 한 줄 이상 있어야 해요');
      }),
    });
    const hook = await ready(fake);
    let ok: boolean | null = null;
    await act(async () => {
      ok = await hook.result.current.edit({
        itemIndex: 0,
        column: 'reasonBullets',
        value: [],
      });
    });
    expect(ok).toBe(false);
    expect(hook.result.current.saveError).toBe('rejected');
    expect(hook.result.current.savedAt).toBeNull();
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.edits).toEqual([]);
  });
});

describe('확정 전 다시 읽기(stale)는 edits 도 본다', () => {
  it('다시 읽은 검토의 고친 값이 다르면 PUT 하지 않고 stale', async () => {
    const reads = [
      review({ state: 'in_review', edits: [levelEdit('Low')] }),
      review({ state: 'in_review', edits: [levelEdit('Mid')] }),
    ];
    const fake = fakeStore({
      getReview: vi.fn(async () => reads.shift() ?? review()),
      putReview: vi.fn(async () => review({ state: 'confirmed' })),
    });
    const hook = await ready(fake);
    let ok: boolean | null = null;
    await act(async () => {
      ok = await hook.result.current.confirm(3);
    });
    expect(ok).toBe(false);
    expect(hook.result.current.saveError).toBe('stale');
    expect(fake.putReview).not.toHaveBeenCalled();
  });

  it('다시 읽은 쪽에만 고침이 있어도 stale', async () => {
    const reads = [
      review({ state: 'in_review' }),
      review({ state: 'in_review', edits: [levelEdit('Low')] }),
    ];
    const fake = fakeStore({
      getReview: vi.fn(async () => reads.shift() ?? review()),
      putReview: vi.fn(async () => review({ state: 'confirmed' })),
    });
    const hook = await ready(fake);
    await act(async () => {
      await hook.result.current.confirm(3);
    });
    expect(hook.result.current.saveError).toBe('stale');
    expect(fake.putReview).not.toHaveBeenCalled();
  });

  it('값이 같고 고친 때·사람만 다르면 stale 아님 — 확정 PUT(edits 없음)', async () => {
    const reads = [
      review({ state: 'in_review', edits: [levelEdit('Low')] }),
      review({
        state: 'in_review',
        edits: [
          {
            ...levelEdit('Low', '2026-10-22T11:11:00+09:00'),
            level: {
              value: 'Low',
              editedAt: '2026-10-22T11:11:00+09:00',
              editedBy: { id: 9, name: '다른 가상 사람' },
            },
          },
        ],
      }),
    ];
    const fake = fakeStore({
      getReview: vi.fn(async () => reads.shift() ?? review()),
      putReview: vi.fn(async () =>
        review({
          state: 'confirmed',
          confirmedAt: '2026-10-22T12:00:00+09:00',
          confirmedBy: by,
        }),
      ),
    });
    const hook = await ready(fake);
    let ok: boolean | null = null;
    await act(async () => {
      ok = await hook.result.current.confirm(1);
    });
    expect(ok).toBe(true);
    expect(vi.mocked(fake.putReview).mock.calls).toEqual([
      [
        'run-1',
        {
          state: 'confirmed',
          marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
        },
      ],
    ]);
  });
});
