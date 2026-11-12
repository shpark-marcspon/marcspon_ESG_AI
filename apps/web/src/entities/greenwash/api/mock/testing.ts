// 시험 전용 가짜 저장소(밴드 CW1 ②, sid:MARC-ISSUE-114 (1)). 그린워싱 화면(pages/greenwash-*)의 시험이 같이 쓴다.
// 제품 코드(app·pages 의 시험 아닌 파일)는 가져오지 않는다(layers.test.ts 의 DOORS — 시험만 이 문을 쓴다).
// 바탕은 「부르지 않을 메서드는 거절」이다. 시험마다 쓰는 메서드만 overrides 로 갈아 끼운다.
import { vi } from 'vitest';

import { StoreError } from '../store.ts';
import type { GreenwashStore, RunSnapshot } from '../store.ts';

/** 부르지 않을 메서드: 부르면 StoreError('rejected') 로 거절한다. */
export const unusedMethod = (message = '쓰지 않음') =>
  vi.fn(async () => {
    throw new StoreError('rejected', message);
  });

/**
 * 가짜 저장소. 바탕: 구독은 아무것도 보내지 않고, 문서 목록·기본 단어는 빈 목록, PDF 는 null, 그 밖은 거절.
 * overrides 의 메서드가 바탕을 덮는다.
 */
export function fakeStore(
  overrides: Partial<GreenwashStore> = {},
): GreenwashStore {
  return {
    createDocument: unusedMethod(),
    createRun: unusedMethod(),
    getRun: unusedMethod(),
    subscribeRun: vi.fn(() => () => {}),
    rerun: unusedMethod(),
    listDocuments: vi.fn(async () => []),
    listDefaultTerms: vi.fn(async () => []),
    getDocument: unusedMethod(),
    listCheckRows: unusedMethod(),
    getResult: unusedMethod(),
    getReview: unusedMethod(),
    putReview: unusedMethod(),
    rejudge: unusedMethod(),
    openDocumentPdf: vi.fn(async () => null),
    getReport: unusedMethod(),
    ...overrides,
  };
}

/**
 * 구독을 실제처럼 하는 가짜 저장소. 저장소 계약대로 구독하면 현재값(first(runId))을 먼저 한 번 보낸다 —
 * 조금 뒤(마이크로태스크)에, 그 사이 해제했으면 보내지 않는다. emit 으로 구독자 모두에게 새 상태를 보낸다.
 */
export function liveRunStore(
  first: (runId: string) => RunSnapshot,
  overrides: Partial<GreenwashStore> = {},
) {
  const listeners = new Set<(run: RunSnapshot) => void>();
  const store = fakeStore({
    subscribeRun: vi.fn((runId: string, listener) => {
      listeners.add(listener);
      void Promise.resolve().then(() => {
        if (listeners.has(listener)) listener(first(runId));
      });
      return () => listeners.delete(listener);
    }),
    ...overrides,
  });
  return {
    store,
    emit: (run: RunSnapshot) => listeners.forEach((l) => l(run)),
    listeners,
  };
}

/**
 * 실행 하나(snapshot)만 아는 가짜 저장소. getRun·구독이 그 실행을 낸다(구독은 마이크로태스크 뒤 — 불러오는 중을 먼저 볼 수 있게).
 * snapshot 이 없으면 getRun 은 거절, 구독은 onMissing.
 */
export function snapshotStore(
  snapshot: RunSnapshot | undefined,
  overrides: Partial<GreenwashStore> = {},
): GreenwashStore {
  return fakeStore({
    getRun: vi.fn(async () => {
      if (!snapshot) throw new Error('없음');
      return snapshot;
    }),
    subscribeRun: vi.fn(
      (
        _runId: string,
        listener: (run: RunSnapshot) => void,
        onMissing?: () => void,
      ) => {
        void Promise.resolve().then(() => {
          if (snapshot) listener(snapshot);
          else onMissing?.();
        });
        return () => {};
      },
    ),
    ...overrides,
  });
}

/**
 * 부를 때마다 밖에서 끝내는 약속을 하나씩 내는 메서드(밴드 LE1 — 불러오기 꼴 시험: 미룬 동안 스켈레톤, 거절하면 실패 꼴).
 * calls[n] 이 n 번째 부름의 resolve·reject 다.
 */
export function deferredCalls<T>() {
  const calls: { resolve(value: T): void; reject(error: unknown): void }[] = [];
  const fn = vi.fn(
    () =>
      new Promise<T>((resolve, reject) => {
        calls.push({ resolve, reject });
      }),
  );
  return { fn, calls };
}
