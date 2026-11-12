// 실행 상태 훅(밴드 FW1b ①, 시안 GW-03). 저장소를 구독하고 언마운트 때(또는 runId 가 바뀌면) 해제한다.
// 밴드 FW2 ① (sid:MARC-ISSUE-99 2·3):
//   - getRun 으로 따로 읽지 않는다. 저장소 계약은 「subscribe 가 현재값을 먼저 한 번 보낸다」이다(store.ts). 그래서 늦게 온
//     읽기 응답이 구독으로 받은 새 상태를 덮는 길이 없다. 없는 실행은 onMissing 으로 받는다.
//   - 실행 응답에 쪽 수가 없으면(pageCount null) 문서 조회(getDocument)로 채운다 [R5]. 문서 id 마다 한 번 읽고, 못 읽으면 null 그대로.
// 밴드 GW1R ②:
//   - 읽기 실패(저장소의 onFailed — 실어댑터의 처음 읽기 실패·잇단 실패)는 failed. retry 는 loading 부터 다시 구독한다([다시 시도]).
//   - 실패 code 가 no_text_layer 면 파일 이름도 문서 조회로 읽는다(GW-03 의 [새 점검] 카드 파일 줄). 읽기 전·못 읽으면 null.
import { useCallback, useEffect, useState } from 'react';

import type {
  GreenwashStore,
  RunSnapshot,
} from '../../../entities/greenwash/api/index.ts';
import { useLoad } from '../../../shared/lib/useLoad.ts';

export type RunStatusState =
  | { state: 'loading' }
  | {
      state: 'ready';
      run: RunSnapshot;
      /** 문서 파일 이름(문서 조회를 했을 때만 — 쪽 수가 없거나 no_text_layer). 모르면 null. */
      fileName: string | null;
    }
  | { state: 'missing' }
  | { state: 'failed' };

/** 상태와 [다시 시도](loading 부터 다시 구독). */
export type RunStatus = RunStatusState & { retry(): void };

type Raw =
  | { state: 'loading' }
  | { state: 'ready'; run: RunSnapshot }
  | { state: 'missing' }
  | { state: 'failed' };

export function useRunStatus(store: GreenwashStore, runId: string): RunStatus {
  const [attempt, setAttempt] = useState(0);
  const [raw, setRaw] = useState<{
    runId: string;
    attempt: number;
    status: Raw;
  }>({ runId, attempt, status: { state: 'loading' } });
  useEffect(() => {
    let alive = true;
    const unsubscribe = store.subscribeRun(
      runId,
      (run) => {
        if (alive) setRaw({ runId, attempt, status: { state: 'ready', run } });
      },
      () => {
        if (alive) setRaw({ runId, attempt, status: { state: 'missing' } });
      },
      () => {
        if (alive) setRaw({ runId, attempt, status: { state: 'failed' } });
      },
    );
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [store, runId, attempt]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  // runId 가 바뀐 뒤(또는 다시 시도 뒤) 아직 새 값을 받지 못했으면 loading(앞의 값을 보이지 않는다).
  const status: Raw =
    raw.runId === runId && raw.attempt === attempt ?
      raw.status
    : { state: 'loading' };
  const needs =
    (
      status.state === 'ready' &&
      (status.run.pageCount === null ||
        status.run.errorCode === 'no_text_layer')
    ) ?
      status.run.documentId
    : null;
  const doc = useDocumentInfo(store, needs);

  if (status.state !== 'ready') return { ...status, retry };
  return {
    state: 'ready',
    run:
      status.run.pageCount === null ?
        { ...status.run, pageCount: doc?.pageCount ?? null }
      : status.run,
    fileName: doc?.fileName ?? null,
    retry,
  };
}

/** 문서 하나(documentId 가 null 이면 읽지 않는다). 읽기 전·못 읽으면 null. */
function useDocumentInfo(
  store: GreenwashStore,
  documentId: string | null,
): { fileName: string; pageCount: number | null } | null {
  const { status } = useLoad(
    documentId === null ? null : [store, documentId],
    () => store.getDocument(documentId!),
  );
  return status.state === 'ready' ? status.data : null;
}
