// @vitest-environment jsdom
// 작은 훅 셋을 화면 없이 본다: useReviewDraft(적고 있는 사유, 거부된 까닭), useReviews, usePdf. 전이 규칙 자체는 model/review.test.ts 가 본다.
import { act, renderHook } from '@testing-library/react';

import { describe, expect, it } from 'vitest';

import { transition } from '../model/index.ts';
import type { ReviewAction, ReviewState } from '../model/index.ts';
import { makeTwoDocInput } from '../model/testing.ts';
import type { PdfHandle } from './pdfBackend.ts';
import { usePdf } from './usePdf.ts';
import { useReviewDraft } from './useReviewDraft.ts';
import { useReviews } from './useReviews.ts';

function setup(start: ReviewState = { status: 'pending' }) {
  let state = start;
  const seen: ReviewAction[] = [];
  const hook = renderHook(() =>
    useReviewDraft((action) => {
      seen.push(action);
      const result = transition(state, action);
      if (result.ok) state = result.state;
      return result;
    }),
  );
  return { draft: () => hook.result.current, state: () => state, seen };
}

describe('useReviewDraft', () => {
  it('사유 없이 반려하면 거부되고 까닭이 남는다. 사유를 적어 반려하면 받아들여지고 입력이 비워진다', () => {
    const { draft, state } = setup();
    act(() => draft().reject());
    expect(draft().error).toBe('reason_required');
    expect(state().status).toBe('pending');

    act(() => draft().setReason('단위가 다르다'));
    act(() => draft().reject());
    expect(state()).toEqual({ status: 'rejected', reason: '단위가 다르다' });
    expect(draft().error).toBeNull();
    expect(draft().reason).toBe('');
  });

  it('거부되면 적던 사유는 남는다', () => {
    const { draft } = setup({ status: 'confirmed' });
    act(() => draft().setReason('적던 것'));
    act(() => draft().confirm());
    expect(draft().error).toBe('not_pending');
    expect(draft().reason).toBe('적던 것');
  });

  it('확정·되돌리기는 그 조작을 그대로 넘긴다', () => {
    const { draft, state, seen } = setup();
    act(() => draft().confirm());
    expect(state().status).toBe('confirmed');
    act(() => draft().reopen());
    expect(state().status).toBe('pending');
    act(() => draft().reopen());
    expect(draft().error).toBe('already_pending');
    expect(seen.map((action) => action.type)).toEqual([
      'confirm',
      'reopen',
      'reopen',
    ]);
  });
});

describe('useReviews', () => {
  it('항목마다 따로 들고, 거부된 조작은 상태를 바꾸지 않는다', () => {
    const hook = renderHook(() => useReviews(makeTwoDocInput().items));
    act(() => void hook.result.current.apply('1', { type: 'confirm' }));
    let rejected;
    act(
      () =>
        void (rejected = hook.result.current.apply('1', {
          type: 'reject',
          reason: '사유',
        })),
    );
    expect(rejected).toEqual({ ok: false, error: 'not_pending' });
    expect(
      [...hook.result.current.states].map(
        ([id, state]) => `${id}:${state.status}`,
      ),
    ).toEqual(['1:confirmed', '2:pending', '3:pending']);
  });
});

describe('usePdf', () => {
  const handle = (log: string[], name: string): PdfHandle => ({
    renderPage: () => ({ done: Promise.resolve(), cancel: () => undefined }),
    close: () => void log.push(`close ${name}`),
  });

  it('여는 동안은 loading, 열리면 ready. 부품이 사라지면 닫는다', async () => {
    const log: string[] = [];
    const open = async (url: string) => handle(log, url);
    const hook = renderHook(() => usePdf('a.pdf', open));
    expect(hook.result.current.state).toBe('loading');
    await act(async () => undefined);
    expect(hook.result.current.state).toBe('ready');
    hook.unmount();
    expect(log).toEqual(['close a.pdf']);
  });

  it('열지 못하면 error 와 그 까닭', async () => {
    // (여는 함수가 그릴 때마다 새 함수여도 된다. 아래의 넷째 테스트가 본다.)
    const open = async () => Promise.reject(new Error('없는 파일'));
    const hook = renderHook(() => usePdf('a.pdf', open));
    await act(async () => undefined);
    expect(hook.result.current).toEqual({
      state: 'error',
      message: '없는 파일',
    });
  });

  it('주소가 바뀌면 앞의 것을 닫고 새로 연다. 늦게 열린 옛 것은 열리자마자 닫는다', async () => {
    const log: string[] = [];
    const waiting = new Map<string, (pdf: PdfHandle) => void>();
    const open = (url: string) =>
      new Promise<PdfHandle>((resolve) => waiting.set(url, resolve));
    const hook = renderHook(({ url }) => usePdf(url, open), {
      initialProps: { url: 'a.pdf' },
    });
    hook.rerender({ url: 'b.pdf' });
    // a 가 뒤늦게 열렸다. 이미 b 를 보고 있으므로 바로 닫는다.
    await act(async () => waiting.get('a.pdf')!(handle(log, 'a')));
    expect(log).toEqual(['close a']);
    expect(hook.result.current.state).toBe('loading');
    await act(async () => waiting.get('b.pdf')!(handle(log, 'b')));
    expect(hook.result.current.state).toBe('ready');
  });

  it('열려 있던 문서의 주소가 바뀌면, 새 것이 열릴 때까지 loading 으로 돌아간다(이미 닫은 옛 문서를 내주지 않는다)', async () => {
    const log: string[] = [];
    const waiting = new Map<string, (pdf: PdfHandle) => void>();
    const open = (url: string) =>
      new Promise<PdfHandle>((resolve) => waiting.set(url, resolve));
    const hook = renderHook(({ url }) => usePdf(url, open), {
      initialProps: { url: 'a.pdf' },
    });
    await act(async () => waiting.get('a.pdf')!(handle(log, 'a')));
    expect(hook.result.current.state).toBe('ready');
    hook.rerender({ url: 'b.pdf' });
    // a 는 닫혔고 b 는 아직 열리는 중이다.
    expect(log).toEqual(['close a']);
    expect(hook.result.current).toEqual({ state: 'loading' });
    await act(async () => waiting.get('b.pdf')!(handle(log, 'b')));
    expect(hook.result.current.state).toBe('ready');
  });

  it('주소를 바꾼 뒤에 옛 것이 뒤늦게 열기에 실패해도, 지금 문서의 상태를 건드리지 않는다', async () => {
    const log: string[] = [];
    const waiting = new Map<
      string,
      { resolve(pdf: PdfHandle): void; reject(error: Error): void }
    >();
    const open = (url: string) =>
      new Promise<PdfHandle>((resolve, reject) =>
        waiting.set(url, { resolve, reject }),
      );
    const hook = renderHook(({ url }) => usePdf(url, open), {
      initialProps: { url: 'a.pdf' },
    });
    hook.rerender({ url: 'b.pdf' });
    await act(async () => waiting.get('b.pdf')!.resolve(handle(log, 'b')));
    expect(hook.result.current.state).toBe('ready');
    await act(async () =>
      waiting.get('a.pdf')!.reject(new Error('옛 문서를 열지 못했다')),
    );
    expect(hook.result.current.state).toBe('ready');
  });

  it('여는 함수가 그릴 때마다 새 함수여도 주소가 같으면 다시 열지 않는다. 주소가 바뀌면 그때의 함수로 다시 연다', async () => {
    const log: string[] = [];
    // 쓰는 쪽이 인라인 함수를 넘기는 경우: 그릴 때마다 새 함수다.
    let renders = 0;
    const hook = renderHook(
      ({ url, tag }) => {
        // 안전판: 고치기 전에는 「새 함수 → 다시 열기 → 상태 바뀜 → 다시 그리기 → 새 함수」가 끝없이 돌아 테스트 프로세스의 메모리가 터진다.
        // 그 대신 여기서 던져, 빨갛게 떨어지게 한다.
        if (++renders > 50)
          throw new Error('끝없이 다시 그린다(PDF 를 계속 다시 연다)');
        return usePdf(url, async (asked) => {
          log.push(`open ${asked} (${tag})`);
          return handle(log, asked);
        });
      },
      { initialProps: { url: 'a.pdf', tag: '첫째' } },
    );
    await act(async () => undefined);
    for (const tag of ['둘째', '셋째', '넷째']) {
      hook.rerender({ url: 'a.pdf', tag });
      await act(async () => undefined);
    }
    expect(log).toEqual(['open a.pdf (첫째)']);
    expect(hook.result.current.state).toBe('ready');

    hook.rerender({ url: 'b.pdf', tag: '다섯째' });
    await act(async () => undefined);
    // 다시 열 때는 그 순간에 받은 함수를 쓴다(처음 받은 함수를 쥐고 있지 않는다).
    expect(log).toEqual([
      'open a.pdf (첫째)',
      'close a.pdf',
      'open b.pdf (다섯째)',
    ]);
    hook.unmount();
    expect(log).toEqual([
      'open a.pdf (첫째)',
      'close a.pdf',
      'open b.pdf (다섯째)',
      'close b.pdf',
    ]);
  });
});
