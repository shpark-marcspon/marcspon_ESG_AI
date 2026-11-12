// @vitest-environment jsdom
// 모듈 바탕 몫 캐시는 슬롯 key 에 묶인다(밴드 MS1W ② — sid:MARC-ISSUE-325). 같은 key 의 새 슬롯 객체는 다시 읽지 않고 새 객체로 센다,
//   다른 key 면 비우고 다시 읽는다, 늦게 온 답은 옛 key 의 것만 버린다. 지어낸 슬롯: 바탕 몫 = 낱말 둘, count = 차이 수.
import { act, renderHook, waitFor } from '@testing-library/react';

import { describe, expect, it, vi } from 'vitest';

import { fakePromptModel } from '../../../entities/ai-setting/api/testing.ts';
import type { ModuleDraftSlot } from '../../../entities/ai-setting/model/index.ts';
import { useDraft } from './useDraft.ts';

type Words = readonly string[];
type Loaded = Awaited<ReturnType<ModuleDraftSlot['load']>>;

const BASE: Words = ['지어낸 낱말 가', '지어낸 낱말 나'];
const diff = (base: unknown, draft: unknown) => {
  const before = base as Words;
  const after = draft as Words;
  return (
    before.filter((one) => !after.includes(one)).length +
    after.filter((one) => !before.includes(one)).length
  );
};

function fakeSlot(
  key = 'fake-draft',
  load: () => Promise<Loaded> = () =>
    Promise.resolve({ kind: 'ok', base: BASE }),
) {
  const slot: ModuleDraftSlot = {
    key,
    load: vi.fn(load),
    count: vi.fn(diff),
    changed: () => [],
    blocked: () => false,
    sum: () => '',
    refusal: () => null,
    render: () => null,
  };
  return slot;
}

function draw(slot: ModuleDraftSlot) {
  const pm = fakePromptModel('13');
  return renderHook(
    ({ slot: now }: { slot: ModuleDraftSlot }) => useDraft('13', pm, now),
    { initialProps: { slot } },
  );
}

/** 끝나지 않은 답 하나(풀어 줄 때까지). */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => (resolve = done));
  return { promise, resolve };
}

describe('useDraft 모듈 바탕 몫 — 슬롯 key 에 묶임(MS1W)', () => {
  it('T2 같은 key 의 새 슬롯 객체 → load 다시 0 · 셈·dirty·고친 값 그대로 · 셈은 새 객체로', async () => {
    const first = fakeSlot();
    const { result, rerender } = draw(first);
    await waitFor(() => expect(result.current.module?.kind).toBe('ok'));
    act(() => {
      expect(result.current.updateModule([BASE[0]])).toBe(true);
    });
    expect(result.current.changes.module).toBe(1);
    expect(result.current.dirty).toBe(true);

    const second = fakeSlot();
    rerender({ slot: second });
    await act(async () => {
      await new Promise((done) => setTimeout(done, 20));
    });
    expect(first.load).toHaveBeenCalledTimes(1);
    expect(second.load).not.toHaveBeenCalled();
    expect(result.current.module).toEqual({
      kind: 'ok',
      base: BASE,
      draft: [BASE[0]],
    });
    expect(result.current.changes.module).toBe(1);
    expect(result.current.dirty).toBe(true);
    expect(result.current.moduleBody).toEqual([BASE[0]]);
    expect(second.count).toHaveBeenCalled();
  });

  it('T2 다른 key 의 슬롯 → 바탕 몫을 비우고 새 슬롯으로 다시 읽음', async () => {
    const first = fakeSlot();
    const { result, rerender } = draw(first);
    await waitFor(() => expect(result.current.module?.kind).toBe('ok'));

    const held = deferred<Loaded>();
    const other = fakeSlot('other-draft', () => held.promise);
    rerender({ slot: other });
    await waitFor(() =>
      expect(result.current.module).toEqual({ kind: 'loading' }),
    );
    expect(other.load).toHaveBeenCalledTimes(1);
    expect(other.load).toHaveBeenCalledWith('13');
    await act(async () => {
      held.resolve({ kind: 'ok', base: ['지어낸 낱말 다'] });
      await held.promise;
    });
    expect(result.current.module).toEqual({
      kind: 'ok',
      base: ['지어낸 낱말 다'],
      draft: ['지어낸 낱말 다'],
    });
  });

  it('T2 늦게 온 답: 같은 key 의 새 객체로 바뀐 뒤 온 답은 받고, 다른 key 로 바뀐 뒤 온 옛 key 의 답은 버림', async () => {
    const held = deferred<Loaded>();
    const first = fakeSlot('fake-draft', () => held.promise);
    const { result, rerender } = draw(first);
    rerender({ slot: fakeSlot('fake-draft', () => held.promise) });
    await act(async () => {
      held.resolve({ kind: 'ok', base: BASE });
      await held.promise;
    });
    await waitFor(() =>
      expect(result.current.module).toEqual({
        kind: 'ok',
        base: BASE,
        draft: BASE,
      }),
    );

    const late = deferred<Loaded>();
    const second = draw(fakeSlot('fake-draft', () => late.promise));
    const fresh = deferred<Loaded>();
    second.rerender({ slot: fakeSlot('other-draft', () => fresh.promise) });
    await act(async () => {
      late.resolve({ kind: 'ok', base: BASE });
      await late.promise;
    });
    expect(second.result.current.module).toEqual({ kind: 'loading' });
  });
});
