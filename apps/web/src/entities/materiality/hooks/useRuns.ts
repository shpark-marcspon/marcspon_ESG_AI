// 실행 목록 읽기 훅(밴드 IRW1 ③, IR-01·01a — 데이터 검증 useRuns 꼴). 저장소의 listRuns 를 useLoad 로 — 거르기(상태 묶음·mine·offset)가 바뀌면 다시 읽는다.
// loading → ready(쪽) | failed. retry 는 화면의 [다시 시도](늘 loading 부터).
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import type {
  MaterialityRunPage,
  MaterialityStore,
  RunListQuery,
} from '../api/index.ts';
import type { RunStatus } from '../model/index.ts';

export type RunsState =
  | { state: 'loading' }
  | { state: 'ready'; page: MaterialityRunPage }
  | { state: 'failed' };

export interface RunsHandle {
  status: RunsState;
  retry(): void;
}

export function useRuns(
  store: MaterialityStore,
  query: RunListQuery,
): RunsHandle {
  const { status: statuses, mine = false, offset } = query;
  // 상태 묶음은 글자 하나로 견준다(그리기마다 새 배열이어도 같은 읽기).
  const statusKey = statuses?.join(',') ?? '';
  const { status, retry } = useLoad([store, statusKey, mine, offset], () =>
    store.listRuns({
      ...(statusKey === '' ?
        {}
      : { status: statusKey.split(',') as RunStatus[] }),
      mine,
      offset,
    }),
  );
  const out = useMemo<RunsState>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed') return { state: 'failed' };
    return { state: 'ready', page: status.data };
  }, [status]);
  return { status: out, retry };
}
