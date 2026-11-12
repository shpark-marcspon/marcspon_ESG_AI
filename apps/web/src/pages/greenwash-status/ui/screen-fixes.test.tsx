// @vitest-environment jsdom
// 밴드 FW2 ⓪: FW1b 디자인 대조의 고칠 것과 sid:MARC-ISSUE-99 화면 고침. 글자는 문구 표(GW_TEXT) 값으로 단언한다.
// 실제 크기·색·스크롤은 e2e/greenwash.spec.ts 가 잰다(jsdom 에는 CSS 가 없다).
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { RunSnapshot } from '../../../entities/greenwash/api/index.ts';
import { snapshotStore } from '../../../entities/greenwash/api/mock/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { RunProgress } from '../../../entities/greenwash/model/index.ts';
import { StatusScreen } from './StatusScreen.tsx';

afterEach(cleanup);

beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

/** PDF 를 열지 않는 openPdf(썸네일은 이 시험에서 그리지 않는다). */

const status = GW_TEXT.status;

const run = (progress: RunProgress): RunSnapshot => ({
  runId: 'run-1',
  documentId: 'doc-1',
  startedAt: '2026-10-16T09:00:00+09:00',
  pageCount: 139,
  checkedPages: 44,
  progress,
  rerunOf: null,
  errorCode: null,
  finishedAt: null,
});

/** 실행 하나만 아는 가짜 저장소(구독은 조금 뒤에 그 실행을, 없으면 onMissing). */
const runStore = (snapshot?: RunSnapshot) =>
  snapshotStore(snapshot, {
    createDocument: vi.fn(async () => ({
      documentId: 'doc-1',
      pageCount: 60,
      hasText: true,
    })),
    createRun: vi.fn(async () => ({ runId: 'run-9' })),
    rerun: vi.fn(async () => ({ runId: 'run-2' })),
  });

describe('GW-03 처리 상태', () => {
  it('불러오는 중은 제목 막대 자리(밴드 GL1), 없는 실행은 화면 이름 제목 줄 + 회색 「점검을 찾을 수 없어요」 + [목록으로] 하나(밴드 LE1)', async () => {
    const store = runStore();
    const onBack = vi.fn();
    render(
      <StatusScreen
        store={store}
        runId="run-x"
        onBack={onBack}
        onRerun={() => {}}
      />,
    );
    expect(
      screen.getByRole('heading', { name: GW_TEXT.load.titlePending }),
    ).toBeTruthy();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBe(status.missing + GW_TEXT.load.toList);
    expect(
      screen.getByRole('heading', { name: status.screenTitle }),
    ).toBeTruthy();
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      GW_TEXT.load.toList,
    ]);
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.toList }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('실패: meta 에 「계속돼요」 없음, 안내 한 문장과 작은 글, [다시 실행]은 store.rerun 으로 새 실행', async () => {
    const store = runStore(
      run({ state: 'failed', stage: 'judge', judge: { done: 28, total: 44 } }),
    );
    const onRerun = vi.fn();
    render(
      <StatusScreen
        store={store}
        runId="run-1"
        onBack={() => {}}
        onRerun={onRerun}
      />,
    );
    const title = await screen.findByRole('heading', {
      name: status.title.failed,
    });
    const root = title.closest('[data-screen="status"]') as HTMLElement;
    expect(root.textContent).toContain(
      status.meta('2026-10-16 09:00', 44, false),
    );
    expect(root.textContent).not.toContain('이 창을 닫아도');
    expect(screen.getByTestId('failure-info').textContent).toBe(status.failure);
    // 덧글(failureNote)은 없다(v115 GW-03 r3 · 디자인 답 D4 — 밴드 GW2R ②)
    expect(screen.queryByTestId('failure-note')).toBeNull();
    expect(root.textContent).not.toContain('28 / 44쪽에서');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: status.rerun }));
    });
    expect(store.rerun).toHaveBeenCalledWith(
      'run-1',
      expect.stringMatching(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      ),
    );
    expect(onRerun).toHaveBeenCalledWith('run-2');
  });

  it('텍스트 추출 줄: 끝난 단계만 「정리했어요」, 진행 중은 「정리해요」. 진행 막대 바탕·대기 점은 background-tertiary', async () => {
    const store = runStore(
      run({
        state: 'running',
        stage: 'extract',
        judge: { done: 0, total: 44 },
      }),
    );
    render(
      <StatusScreen
        store={store}
        runId="run-1"
        onBack={() => {}}
        onRerun={() => {}}
      />,
    );
    await screen.findByRole('heading', { name: status.title.running });
    const extract = document.querySelector('li[data-stage="extract"]')!;
    expect(extract.textContent).toContain(
      status.stages.extract.bodyPending(139),
    );
    expect(extract.textContent).not.toContain(status.stages.extract.body(139));
    expect(screen.getByRole('progressbar').className.split(/\s+/)).toContain(
      'bg-background-tertiary',
    );
    const todoDot = document.querySelector(
      'li[data-stage="summarize"] > span[aria-hidden]',
    )!;
    expect(todoDot.className.split(/\s+/)).toContain('bg-background-tertiary');
    expect(
      document.querySelector('li[data-stage="summarize"]')!.textContent,
    ).toContain(status.stages.summarize.body);
  });
});
