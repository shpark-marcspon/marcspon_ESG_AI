// 묶음 목록 읽기 훅(밴드 TRW1a ①, TR-01). 저장소의 listBatches 를 useLoad 로 — 거른 값(state·mine·offset)이 바뀌면 다시 읽는다.
//   loading → ready(쪽) | failed. retry 는 화면의 [다시 시도](늘 loading 부터).
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import type { BatchQuery, TranslationStore } from '../api/index.ts';
import type { TranslationBatchPage } from '../model/index.ts';

export type BatchesState =
  | { state: 'loading' }
  | { state: 'ready'; page: TranslationBatchPage }
  | { state: 'failed' };

export interface BatchesHandle {
  status: BatchesState;
  retry(): void;
}

export function useBatches(
  store: TranslationStore,
  query: BatchQuery,
): BatchesHandle {
  const { state, mine, offset } = query;
  const { status, retry } = useLoad([store, state, mine, offset], () =>
    store.listBatches({
      ...(state === undefined ? {} : { state }),
      mine,
      offset,
    }),
  );
  const out = useMemo<BatchesState>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed') return { state: 'failed' };
    return { state: 'ready', page: status.data };
  }, [status]);
  return { status: out, retry };
}
