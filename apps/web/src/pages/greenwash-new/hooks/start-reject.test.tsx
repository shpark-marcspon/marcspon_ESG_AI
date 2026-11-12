// @vitest-environment jsdom
// (밴드 FS1 ③: results-hooks.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// headless 의 결과·검토 바닥(밴드 FW2 ① §3): 시작·[다시 실행] 거절(sid:MARC-ISSUE-99 1), 구독 차례(같은 이슈 2 — 늦게 온 값이 덮지 않음),
// pageCount 채우기([R5]), 결과 읽기(불러오는 중·없음·꼴 오류), 검토 쓰기(PUT 뒤 반영·실패·409·확정).
// 목 저장소 대신 시험 안의 가짜 저장소를 쓴다(headless 는 mock 을 모른다).
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type {
  GreenwashStore,
  RunSnapshot,
} from '../../../entities/greenwash/api/index.ts';
import type { RunProgress } from '../../../entities/greenwash/model/index.ts';
import { useNewCheckForm } from './useNewCheckForm.ts';

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

describe('시작·[다시 실행] 거절(sid:MARC-ISSUE-99 1)', () => {
  it('createRun 이 거절되면 start 는 null, startError 가 서고, 다시 누르면 지워진다', async () => {
    const createRun = vi
      .fn<GreenwashStore['createRun']>()
      .mockRejectedValueOnce(new Error('서버 오류'))
      .mockResolvedValueOnce({ runId: 'run-5' });
    const store = baseStore({ createRun });
    const hook = renderHook(() => useNewCheckForm({ store }));
    act(() =>
      hook.result.current.onChangeItems([
        {
          id: 'f',
          name: 'a.pdf',
          date: '2026-10-16',
          file: new File([new Uint8Array([1])], 'a.pdf'),
        },
      ]),
    );
    await waitFor(() => expect(hook.result.current.uploading).toBe(false));
    act(() => hook.result.current.setPartText('ceo', '2'));
    let runId: string | null = 'x';
    await act(async () => {
      runId = await hook.result.current.start();
    });
    expect(runId).toBeNull();
    expect(hook.result.current.startError).toBe('rejected');
    expect(hook.result.current.submitting).toBe(false);
    await act(async () => {
      runId = await hook.result.current.start();
    });
    expect(runId).toBe('run-5');
    expect(hook.result.current.startError).toBeNull();
  });
  it('StoreError 의 갈래를 그대로 낸다(없는 문서 → not_found)', async () => {
    const store = baseStore({
      createRun: vi.fn(async () => {
        throw new StoreError('not_found', '없는 문서');
      }),
    });
    const hook = renderHook(() => useNewCheckForm({ store }));
    act(() =>
      hook.result.current.onChangeItems([
        {
          id: 'f',
          name: 'a.pdf',
          date: '2026-10-16',
          file: new File([new Uint8Array([1])], 'a.pdf'),
        },
      ]),
    );
    await waitFor(() => expect(hook.result.current.uploading).toBe(false));
    act(() => hook.result.current.setPartText('ceo', '2'));
    await act(async () => {
      await hook.result.current.start();
    });
    expect(hook.result.current.startError).toBe('not_found');
  });
});

describe('실행 만들기 열쇠(밴드 GR2, sid:MARC-ISSUE-225 · GR1 검증 R1 — 단추를 거치지 않고 start 를 바로 부른다)', () => {
  /** 부를 때마다 key-1, key-2 … 를 낸다. */
  const counter = () => {
    let n = 0;
    return vi.fn(() => `key-${++n}`);
  };

  async function ready(
    createRun: GreenwashStore['createRun'],
    newKey = counter(),
  ) {
    const store = baseStore({ createRun });
    const hook = renderHook(() => useNewCheckForm({ store, newKey }));
    act(() =>
      hook.result.current.onChangeItems([
        {
          id: 'f',
          name: 'a.pdf',
          date: '2026-10-16',
          file: new File([new Uint8Array([1])], 'a.pdf'),
        },
      ]),
    );
    await waitFor(() => expect(hook.result.current.uploading).toBe(false));
    act(() => hook.result.current.setPartText('ceo', '2'));
    const start = async () => {
      let runId: string | null = 'x';
      await act(async () => {
        runId = await hook.result.current.start();
      });
      return runId;
    };
    return { hook, start, newKey };
  }

  const keyOf = (createRun: ReturnType<typeof vi.fn>, call: number) =>
    createRun.mock.calls[call]![2];

  it('끊김(unreachable) 뒤 다시 부르면 같은 열쇠로 보낸다(canStart 는 참), 성공하면 버려 다음은 새 열쇠', async () => {
    const createRun = vi
      .fn<GreenwashStore['createRun']>()
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'))
      .mockResolvedValueOnce({ runId: 'run-5' })
      .mockResolvedValueOnce({ runId: 'run-6' });
    const { hook, start } = await ready(createRun);
    expect(await start()).toBeNull();
    expect(hook.result.current.startError).toBe('unreachable');
    expect(hook.result.current.canStart).toBe(true);
    expect(await start()).toBe('run-5');
    expect(hook.result.current.startError).toBeNull();
    expect(await start()).toBe('run-6');
    expect(createRun).toHaveBeenCalledTimes(3);
    expect(keyOf(createRun, 0)).toBe('key-1');
    expect(keyOf(createRun, 1)).toBe('key-1');
    expect(keyOf(createRun, 2)).toBe('key-2');
  });

  it('끊김이 거듭돼도 같은 열쇠, 서버 거절(rejected·not_found)이면 버려 다음은 새 열쇠', async () => {
    const createRun = vi
      .fn<GreenwashStore['createRun']>()
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'))
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'))
      .mockRejectedValueOnce(new StoreError('rejected', '지어낸 거절'))
      .mockRejectedValueOnce(new StoreError('not_found', '지어낸 없음'))
      .mockResolvedValueOnce({ runId: 'run-5' });
    const { start } = await ready(createRun);
    for (let i = 0; i < 4; i++) expect(await start()).toBeNull();
    expect(await start()).toBe('run-5');
    expect(createRun.mock.calls.map((call) => call[2])).toEqual([
      'key-1',
      'key-1',
      'key-1',
      'key-2',
      'key-3',
    ]);
  });

  it('409 키 재사용(key_reused)이면 열쇠를 쥔 채 — 다시 눌러도 같은 열쇠(새 실행을 짓지 않음, sid:MARC-ISSUE-312), canStart 는 참', async () => {
    const createRun = vi
      .fn<GreenwashStore['createRun']>()
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'))
      .mockRejectedValueOnce(new StoreError('key_reused', '지어낸 409'))
      .mockRejectedValueOnce(new StoreError('key_reused', '지어낸 409'))
      .mockResolvedValueOnce({ runId: 'run-5' })
      .mockResolvedValueOnce({ runId: 'run-6' });
    const { hook, start } = await ready(createRun);
    expect(await start()).toBeNull();
    expect(await start()).toBeNull();
    expect(hook.result.current.startError).toBe('key_reused');
    expect(hook.result.current.canStart).toBe(true);
    expect(await start()).toBeNull();
    expect(hook.result.current.startError).toBe('key_reused');
    expect(await start()).toBe('run-5');
    expect(await start()).toBe('run-6');
    expect(createRun.mock.calls.map((call) => call[2])).toEqual([
      'key-1',
      'key-1',
      'key-1',
      'key-1',
      'key-2',
    ]);
  });

  it('검사에 걸린 누름은 열쇠를 짓지 않는다(보내지 않음)', async () => {
    const createRun = vi.fn<GreenwashStore['createRun']>(async () => ({
      runId: 'run-5',
    }));
    const { hook, start, newKey } = await ready(createRun);
    act(() => hook.result.current.setPartText('ceo', ''));
    expect(await start()).toBeNull();
    expect(newKey).not.toHaveBeenCalled();
    expect(createRun).not.toHaveBeenCalled();
  });

  it('주입하지 않으면 열쇠는 소문자 UUID', async () => {
    const createRun = vi.fn<GreenwashStore['createRun']>(async () => ({
      runId: 'run-5',
    }));
    const store = baseStore({ createRun });
    const hook = renderHook(() => useNewCheckForm({ store }));
    act(() =>
      hook.result.current.onChangeItems([
        {
          id: 'f',
          name: 'a.pdf',
          date: '2026-10-16',
          file: new File([new Uint8Array([1])], 'a.pdf'),
        },
      ]),
    );
    await waitFor(() => expect(hook.result.current.uploading).toBe(false));
    act(() => hook.result.current.setPartText('ceo', '2'));
    await act(async () => {
      await hook.result.current.start();
    });
    expect(keyOf(createRun, 0)).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });
});
