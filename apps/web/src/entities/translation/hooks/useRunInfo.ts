// 실행 정보 훅(밴드 TRW6 ①): GET /runs/{id} — PDF 결과 판별(resultShapes 의 layout@1)·흐름·파트. runId 가 null 이면 읽지 않고 loading.
//   loading → ready | not_found(없음·꼴 밖 id) | failed(그 밖).
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import { storeErrorKind } from '../api/index.ts';
import type { RunInfo, TranslationStore } from '../api/index.ts';

export type RunInfoState =
  | { state: 'loading' }
  | { state: 'ready'; info: RunInfo }
  | { state: 'not_found' }
  | { state: 'failed' };

export interface RunInfoHandle {
  status: RunInfoState;
  retry(): void;
}

export function useRunInfo(
  store: TranslationStore,
  runId: string | null,
): RunInfoHandle {
  const { status, retry } = useLoad(
    runId === null ? null : [store, 'run', runId],
    () => store.getRunInfo(runId!),
  );
  const out = useMemo<RunInfoState>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed')
      return storeErrorKind(status.error) === 'not_found' ?
          { state: 'not_found' }
        : { state: 'failed' };
    return { state: 'ready', info: status.data };
  }, [status]);
  return { status: out, retry };
}
