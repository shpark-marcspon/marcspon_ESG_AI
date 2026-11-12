// @vitest-environment jsdom
// 밴드 GR1(sid:MARC-ISSUE-281 1·4): useReview 의 저장 경합 — 저장 중에 온 mark·confirm 은 보내지 않지만 busyRefusals 를 올려
// 화면이 알리게 한다(조용히 버림 0), 확정된 뒤에는 기다린 고침을 보내지 않는다(409 review_locked 빨간 줄 0). 값은 지어낸 것이다.
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../api/index.ts';
import type { GreenwashStore } from '../api/index.ts';
import type { GreenwashReview } from '../model/index.ts';
import { useReview } from './useReview.ts';

afterEach(cleanup);

// hooks 칸의 시험은 api/mock/testing.ts 를 못 가져온다(layers) — review-edit.test.tsx 처럼 여기서 짓는다.
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

/** 부를 때마다 밖에서 끝내는 약속을 하나씩 내는 메서드. calls[n] 이 n 번째 부름의 resolve 다. */
function deferredCalls<T>() {
  const calls: { resolve(value: T): void }[] = [];
  const fn = vi.fn(
    () =>
      new Promise<T>((resolve) => {
        calls.push({ resolve });
      }),
  );
  return { fn, calls };
}

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

const confirmedReview = () =>
  review({
    state: 'confirmed',
    confirmedAt: '2026-10-22T11:00:00+09:00',
    confirmedBy: { id: 3, name: '가상 확정자' },
    marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
  });

const fixEdit = {
  itemIndex: 0,
  column: 'fixParagraph',
  value: '가상으로 고친 수정 방향',
} as const;

async function ready(store: GreenwashStore) {
  const hook = renderHook(({ id }) => useReview(store, id), {
    initialProps: { id: 'run-1' },
  });
  await waitFor(() => expect(hook.result.current.status.state).toBe('ready'));
  return hook;
}

describe('useReview 저장 경합(밴드 GR1)', () => {
  it('고침 저장이 도는 중에 누른 [채택]은 보내지 않지만 busyRefusals 가 오른다(조용히 버림 0). 저장이 끝나면 받는다', async () => {
    const put = deferredCalls<unknown>();
    const fake = fakeStore({
      getReview: vi.fn(async () => review()),
      putReview: put.fn,
    });
    const hook = await ready(fake);
    expect(hook.result.current.busyRefusals).toBe(0);
    let editing!: Promise<boolean>;
    act(() => {
      editing = hook.result.current.edit(fixEdit);
    });
    let marked: boolean | null = null;
    await act(async () => {
      marked = await hook.result.current.mark({
        itemIndex: 0,
        decision: 'adopted',
      });
    });
    expect(marked).toBe(false);
    expect(hook.result.current.busyRefusals).toBe(1);
    expect(put.fn).toHaveBeenCalledTimes(1);
    await act(async () => {
      put.calls[0]!.resolve(review({ state: 'in_review' }));
      await editing;
    });
    // 저장이 끝난 뒤 다시 누르면 보낸다
    const again = hook.result.current.mark({
      itemIndex: 0,
      decision: 'adopted',
    });
    await act(async () => {
      put.calls[1]!.resolve(
        review({
          state: 'in_review',
          marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
        }),
      );
      expect(await again).toBe(true);
    });
    expect(put.fn).toHaveBeenCalledTimes(2);
    expect(hook.result.current.busyRefusals).toBe(1);
  });

  it('고침 저장이 도는 중에 누른 [확정]도 같다 — 다시 읽기·PUT 없이 false, busyRefusals 가 오른다', async () => {
    const put = deferredCalls<unknown>();
    const fake = fakeStore({
      getReview: vi.fn(async () => review()),
      putReview: put.fn,
    });
    const hook = await ready(fake);
    act(() => {
      void hook.result.current.edit(fixEdit);
    });
    let confirmed: boolean | null = null;
    await act(async () => {
      confirmed = await hook.result.current.confirm(1);
    });
    expect(confirmed).toBe(false);
    expect(hook.result.current.busyRefusals).toBe(1);
    // 처음 읽기 한 번뿐(확정 전 다시 읽기를 하지 않았다)
    expect(fake.getReview).toHaveBeenCalledTimes(1);
    expect(put.fn).toHaveBeenCalledTimes(1);
  });

  it('확정 PUT 이 도는 중에 기다린 고침은 확정이 받아들여지면 보내지 않고 false 로 끝난다(review_locked 0)', async () => {
    const put = deferredCalls<unknown>();
    const fake = fakeStore({
      getReview: vi.fn(async () => review()),
      putReview: put.fn,
    });
    const hook = await ready(fake);
    let confirming!: Promise<boolean>;
    await act(async () => {
      confirming = hook.result.current.confirm(1);
      // 확정 전 다시 읽기가 끝나 PUT 이 나갈 때까지
      await waitFor(() => expect(put.fn).toHaveBeenCalledTimes(1));
    });
    let editing!: Promise<boolean>;
    act(() => {
      editing = hook.result.current.edit(fixEdit);
    });
    await act(async () => {
      put.calls[0]!.resolve(confirmedReview());
      expect(await confirming).toBe(true);
      expect(await editing).toBe(false);
    });
    expect(put.fn).toHaveBeenCalledTimes(1);
    expect(hook.result.current.saveError).toBeNull();
    const now = hook.result.current.status;
    expect(now.state === 'ready' && now.review.state).toBe('confirmed');
  });

  it('확정 전 다시 읽기가 이미 확정이면 그동안 기다린 고침을 보내지 않는다 — already_confirmed 회색 그대로', async () => {
    const reread = deferredCalls<unknown>();
    let reads = 0;
    const fake = fakeStore({
      getReview: vi.fn(() => {
        reads += 1;
        return reads === 1 ? Promise.resolve(review()) : reread.fn();
      }),
      putReview: vi.fn(async () => {
        throw new StoreError('review_locked', '확정된 실행');
      }),
    });
    const hook = await ready(fake);
    let confirming!: Promise<boolean>;
    act(() => {
      confirming = hook.result.current.confirm(1);
    });
    let editing!: Promise<boolean>;
    act(() => {
      editing = hook.result.current.edit(fixEdit);
    });
    await act(async () => {
      reread.calls[0]!.resolve(confirmedReview());
      expect(await confirming).toBe(false);
      expect(await editing).toBe(false);
    });
    expect(fake.putReview).not.toHaveBeenCalled();
    expect(hook.result.current.saveError).toBe('already_confirmed');
  });
});
