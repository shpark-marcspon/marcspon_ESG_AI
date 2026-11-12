// 결과 읽기 훅(밴드 IRW1 ①, IR-03 끝남·IR-04 — 데이터 검증 useResult 꼴). 끝난(done) 실행만 읽는다(runId 가 null 이면 읽지 않고 loading).
//   loading → ready(결과 — 거울을 지난 화면 꼴) | not_done(409 — 아직 끝나지 않음) | missing(없음) | failed(그 밖 — 꼴 틀림 포함).
//   retry 는 loading 부터.
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import { storeErrorKind } from '../api/index.ts';
import type { MaterialityStore } from '../api/index.ts';
import type { MaterialityResult } from '../model/index.ts';

export type ResultState =
  | { state: 'loading' }
  | { state: 'ready'; result: MaterialityResult }
  | { state: 'not_done' }
  | { state: 'missing' }
  | { state: 'failed' };

export interface ResultHandle {
  status: ResultState;
  retry(): void;
}

export function useResult(
  store: MaterialityStore,
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
      return (
        kind === 'not_done' ? { state: 'not_done' }
        : kind === 'not_found' ? { state: 'missing' }
        : { state: 'failed' }
      );
    }
    return { state: 'ready', result: status.data };
  }, [status]);
  return { status: out, retry };
}
