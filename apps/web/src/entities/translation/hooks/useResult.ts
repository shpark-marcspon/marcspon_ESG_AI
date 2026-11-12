// 결과 읽기 훅(밴드 TRW1a ①, TR-04). 끝난 파트만 읽는다(runId 가 null 이면 읽지 않고 loading).
//   loading → ready(결과 — 거울을 지난 화면 꼴) | missing(없음·끝나지 않음) | failed(그 밖 — 꼴 틀림 포함). retry 는 loading 부터.
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import { storeErrorKind } from '../api/index.ts';
import type { TranslationStore } from '../api/index.ts';
import type { TranslationResult } from '../model/index.ts';

export type ResultState =
  | { state: 'loading' }
  | { state: 'ready'; result: TranslationResult }
  | { state: 'missing' }
  | { state: 'failed' };

export interface ResultHandle {
  status: ResultState;
  retry(): void;
}

export function useResult(
  store: TranslationStore,
  runId: string | null,
): ResultHandle {
  const { status, retry } = useLoad(
    runId === null ? null : [store, runId],
    () => store.getResult(runId!),
  );
  const out = useMemo<ResultState>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed') {
      const kind = storeErrorKind(status.error);
      return kind === 'not_found' || kind === 'not_done' ?
          { state: 'missing' }
        : { state: 'failed' };
    }
    return { state: 'ready', result: status.data };
  }, [status]);
  return { status: out, retry };
}
