// @vitest-environment jsdom
// 밴드 LE1 ②: GW-03 처리 상태의 불러오기 꼴(sid:MARC-ENT-260 ①). 구독이 첫 값을 보내기 전에는 제목 줄(화면 이름 + [목록으로])·STEP 2 를 두고
// 299ms 에는 스켈레톤 없음, 300ms 에는 스켈레톤(숨긴 글 「점검을 불러오는 중이에요」). 첫 값이 오면 진행 화면.
// aria-busy 는 스켈레톤 카드가 아니라 바깥 [data-screen] 이 읽는 동안 내내 단다(밴드 LA1 ①).
// 가짜 시계는 setTimeout·clearTimeout 만 바꾼다.
import { act, cleanup, render, screen } from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RunSnapshot } from '../../../entities/greenwash/api/index.ts';
import { fakeStore } from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import { StatusScreen } from './StatusScreen.tsx';

const status = GW_TEXT.status;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const RUN: RunSnapshot = {
  runId: 'run-1',
  documentId: 'doc-1',
  startedAt: '2026-10-16T09:00:00+09:00',
  pageCount: 139,
  checkedPages: 44,
  progress: { state: 'running', stage: 'judge', judge: { done: 3, total: 44 } },
  rerunOf: null,
  errorCode: null,
  finishedAt: null,
};

describe('GW-03 불러오기 꼴(밴드 LE1)', () => {
  it('바깥 [data-screen] 은 0ms·299ms 에도 aria-busy(스켈레톤은 없음), 300ms 에는 스켈레톤(카드엔 aria-busy 없음). 틀(제목 줄·[목록으로]·STEP 2)은 처음부터, 첫 값이 오면 진행 화면이고 [aria-busy] 0', async () => {
    let send: ((run: RunSnapshot) => void) | null = null;
    const store = fakeStore({
      subscribeRun: vi.fn((_runId: string, listener) => {
        send = listener;
        return () => {};
      }),
    });
    const view = render(
      <StatusScreen
        store={store}
        runId="run-1"
        onBack={() => {}}
        onRerun={() => {}}
      />,
    );
    const outer = () => view.container.querySelector('[data-screen]')!;
    expect(outer().getAttribute('aria-busy')).toBe('true');
    expect(screen.queryByTestId('status-skeleton')).toBeNull();
    // 제목(상태마다 다름)·설명은 실행을 받아야 안다 — 막대 자리, 「처리 상태」 글 0(밴드 GL1)
    expect(
      screen.getByRole('heading', { name: GW_TEXT.load.titlePending }),
    ).toBeTruthy();
    expect(screen.queryByText(status.screenTitle)).toBeNull();
    expect(screen.getByTestId('title-pending')).toBeTruthy();
    expect(screen.getByTestId('description-pending')).toBeTruthy();
    expect(screen.getByRole('button', { name: status.back })).toBeTruthy();
    const steps = screen.getByRole('list', { name: GW_TEXT.stepFlow.label });
    expect(steps.querySelector('[aria-current="step"]')?.textContent).toContain(
      GW_TEXT.stepFlow.steps[1],
    );
    act(() => vi.advanceTimersByTime(299));
    expect(outer().getAttribute('aria-busy')).toBe('true');
    expect(screen.queryByTestId('status-skeleton')).toBeNull();
    act(() => vi.advanceTimersByTime(1));
    const skeleton = screen.getByTestId('status-skeleton');
    expect(skeleton.getAttribute('aria-busy')).toBeNull();
    expect(outer().getAttribute('aria-busy')).toBe('true');
    expect(skeleton.textContent).toBe(status.title.loading);
    // 화면 꼴 스켈레톤(밴드 GL2): 낭독 글은 role="status" 하나 · 공용 카드 0
    expect(skeleton.getAttribute('role')).toBe('status');
    expect(skeleton.getAttribute('aria-label')).toBe(status.title.loading);
    expect(screen.getAllByRole('status')).toHaveLength(1);
    expect(screen.queryByTestId('load-skeleton')).toBeNull();
    act(() => send!(RUN));
    expect(screen.queryByTestId('status-skeleton')).toBeNull();
    expect(
      screen.getByRole('heading', { name: status.title.running }),
    ).toBeTruthy();
    expect(screen.queryByTestId('title-pending')).toBeNull();
    expect(screen.queryByTestId('description-pending')).toBeNull();
    expect(view.container.querySelector('[aria-busy]')).toBeNull();
  });

  it('없는 실행에는 단계 표시를 두지 않는다', async () => {
    const store = fakeStore({
      subscribeRun: vi.fn((_runId: string, _listener, onMissing) => {
        void Promise.resolve().then(() => onMissing?.());
        return () => {};
      }),
    });
    render(
      <StatusScreen
        store={store}
        runId="run-x"
        onBack={() => {}}
        onRerun={() => {}}
      />,
    );
    await act(async () => {});
    expect(screen.getByRole('alert').getAttribute('data-kind')).toBe('missing');
    expect(
      screen.queryByRole('list', { name: GW_TEXT.stepFlow.label }),
    ).toBeNull();
    expect(screen.queryByTestId('status-skeleton')).toBeNull();
    // loading 과 같은 바깥 마디를 되쓰므로 busy 가 풀려야 한다
    expect(document.querySelector('[aria-busy]')).toBeNull();
  });
});
