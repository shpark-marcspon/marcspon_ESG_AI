// layout@1 읽기 훅(밴드 TRW6 ①, TR-P05). runId 가 null 이면 읽지 않고 loading.
//   loading → ready(거울을 지난 화면 꼴) | not_found(404 — 없음·layout 없는 끝난 실행) | not_done(409 — 끝나지 않음) | failed(그 밖 — 꼴 틀림 포함).
//   부재를 빈 결과로 메우지 않는다(발주서 §1-7). retry 는 loading 부터.
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import { storeErrorKind } from '../api/index.ts';
import type { TranslationStore } from '../api/index.ts';
import type { TranslationLayout } from '../model/index.ts';

export type LayoutState =
  | { state: 'loading' }
  | { state: 'ready'; layout: TranslationLayout }
  | { state: 'not_found' }
  | { state: 'not_done' }
  | { state: 'failed' };

export interface LayoutHandle {
  status: LayoutState;
  retry(): void;
}

export function useLayout(
  store: TranslationStore,
  runId: string | null,
): LayoutHandle {
  const { status, retry } = useLoad(
    runId === null ? null : [store, 'layout', runId],
    () => store.getLayout(runId!),
  );
  const out = useMemo<LayoutState>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed') {
      const kind = storeErrorKind(status.error);
      return (
        kind === 'not_found' ? { state: 'not_found' }
        : kind === 'not_done' ? { state: 'not_done' }
        : { state: 'failed' }
      );
    }
    return { state: 'ready', layout: status.data };
  }, [status]);
  return { status: out, retry };
}
