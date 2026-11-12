// @vitest-environment jsdom
// (밴드 FS1 ③: start-errors.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ① 의 화면 쪽(sid:MARC-ISSUE-99 1·3): 실행 시작·[다시 실행]이 거절되면 role="alert" 안내, 시작 시각은 ISO 를 꾸며 보인다,
// 쪽 수를 아직 모르면 「문서에서」. 글자는 문구 표(GW_TEXT) 값으로 단언한다.
// 밴드 GR2: [다시 실행] 끊김 뒤 다시 누름은 같은 열쇠 — 목 저장소가 같은 실행을 돌려줘 실행은 하나.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type {
  GreenwashStore,
  RunSnapshot,
} from '../../../entities/greenwash/api/index.ts';
import { createMockStore } from '../../../entities/greenwash/api/mock/index.ts';
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

const status = GW_TEXT.status;

const snapshot = (
  progress: RunProgress,
  extra: Partial<RunSnapshot> = {},
): RunSnapshot => ({
  runId: 'run-1',
  documentId: 'doc-1',
  startedAt: '2026-10-16T00:30:00Z',
  pageCount: 139,
  checkedPages: 44,
  progress,
  rerunOf: null,
  errorCode: null,
  finishedAt: null,
  ...extra,
});

function store(overrides: Partial<GreenwashStore> = {}): GreenwashStore {
  const unused = () =>
    vi.fn(async () => {
      throw new StoreError('rejected', '쓰지 않음');
    });
  return {
    createDocument: vi.fn(async () => ({
      documentId: 'doc-1',
      pageCount: 60,
      hasText: true,
    })),
    createRun: vi.fn(async () => {
      throw new StoreError('rejected', '서버 오류');
    }),
    getRun: unused(),
    subscribeRun: vi.fn(() => () => {}),
    rerun: vi.fn(async () => {
      throw new StoreError('rejected', '서버 오류');
    }),
    listDocuments: vi.fn(async () => []),
    listDefaultTerms: vi.fn(async () => []),
    getDocument: vi.fn(async () => ({
      documentId: 'doc-1',
      fileName: 'a.pdf',
      pageCount: 88,
    })),
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

describe('GW-03', () => {
  it('[다시 실행]이 거절되면 role="alert" 안내, onRerun 은 부르지 않는다', async () => {
    const failed = snapshot({
      state: 'failed',
      stage: 'judge',
      judge: { done: 3, total: 44 },
    });
    const onRerun = vi.fn();
    const fake = store({
      subscribeRun: vi.fn((_id, listener) => {
        listener(failed);
        return () => {};
      }),
    });
    render(
      <StatusScreen
        store={fake}
        runId="run-1"
        onBack={() => {}}
        onRerun={onRerun}
      />,
    );
    expect(screen.queryByTestId('rerun-error')).toBeNull();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: status.rerun }));
    });
    expect(fake.rerun).toHaveBeenCalledWith(
      'run-1',
      expect.stringMatching(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      ),
    );
    expect(onRerun).not.toHaveBeenCalled();
    const alert = screen.getByTestId('rerun-error');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.textContent).toContain(status.rerunRejected);
  });

  it('시작 시각은 ISO 를 한국 시각으로 꾸민다. 쪽 수가 없으면 문서 조회로 채운다', async () => {
    const running = snapshot(
      { state: 'running', stage: 'extract', judge: { done: 0, total: 44 } },
      { pageCount: null },
    );
    render(
      <StatusScreen
        store={store({
          subscribeRun: vi.fn((_id, listener) => {
            listener(running);
            return () => {};
          }),
        })}
        runId="run-1"
        onBack={() => {}}
        onRerun={() => {}}
      />,
    );
    // 2026-10-16T00:30:00Z = 한국 시각 09:30
    expect(screen.getByText(status.meta('2026-10-16 09:30', 44))).toBeTruthy();
    expect(
      await screen.findByText(status.stages.extract.bodyPending(88)),
    ).toBeTruthy();
  });

  it('문구: 시작 전(null)은 「시작 대기」, 쪽 수를 모르면 「문서에서」', () => {
    expect(status.meta(null, 3, false)).toBe('시작 대기 · 점검할 페이지 3개');
    expect(status.stages.extract.body(null)).toBe(
      '문서에서 텍스트를 추출해 근거로 찾을 수 있게 정리했어요',
    );
  });
});

describe('GW-03 [다시 실행] 끊김(밴드 GR1·GR2, sid:MARC-ISSUE-225)', () => {
  it('rerun 이 unreachable 이면 e9 글 + [다시 실행]은 켜진 채, 다시 누르면 같은 열쇠로 보내 목이 같은 실행을 돌려준다(실행 하나), [목록으로]는 onBack', async () => {
    // 목 저장소: 첫 부름은 실행을 만든 뒤 답이 끊긴 꼴(서버는 만들었다), 둘째부터는 그대로
    const mock = createMockStore({ scenario: 'failed' });
    const made: string[] = [];
    const rerunFn = vi.fn<GreenwashStore['rerun']>(async (runId, key) => {
      const { runId: next } = await mock.store.rerun(runId, key);
      made.push(next);
      if (made.length === 1) throw new StoreError('unreachable', '지어낸 끊김');
      return { runId: next };
    });
    const onBack = vi.fn();
    const onRerun = vi.fn();
    render(
      <StatusScreen
        store={{ ...mock.store, rerun: rerunFn }}
        runId={mock.seededRunId!}
        onBack={onBack}
        onRerun={onRerun}
      />,
    );
    const rerun = await screen.findByRole('button', { name: status.rerun });
    await act(async () => {
      fireEvent.click(rerun);
    });
    const alert = screen.getByTestId('rerun-error');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.textContent).toBe(GW_TEXT.runUnreachable.rerun);
    expect(rerun.hasAttribute('disabled')).toBe(false);
    expect(onRerun).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.click(rerun);
    });
    expect(rerunFn).toHaveBeenCalledTimes(2);
    const [first, second] = rerunFn.mock.calls;
    expect(second![1]).toBe(first![1]);
    expect(made).toEqual([made[0], made[0]]);
    expect(onRerun).toHaveBeenCalledTimes(1);
    expect(onRerun).toHaveBeenCalledWith(made[0]);
    // 실패 카드의 [목록으로](제목 줄에도 하나 있다)
    fireEvent.click(
      within(screen.getByTestId('failure')).getByRole('button', {
        name: status.back,
      }),
    );
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
