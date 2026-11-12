// 결과 읽기 훅(밴드 FW2 ①, GW-04·GW-05). 저장소의 결과 JSON 을 거울(contract)로 지킨다.
//   loading → ready(꼴을 지난 결과) | missing(없는 실행·끝나지 않은 실행) | invalid(꼴 오류 — issues 는 개발자용 글) | failed(그 밖의 거절).
// retry(밴드 LE1 ①): 화면의 [다시 시도]. 늘 loading 을 거쳐 다시 읽는다(invalid 는 useLoad 에서 ready 라 reload 로는 앞 값이 남는다).
import { useMemo } from 'react';

import { useLoad } from '../../../shared/lib/useLoad.ts';
import { parseResult } from '../api/index.ts';
import { storeErrorKind } from '../api/index.ts';
import type { GreenwashStore } from '../api/index.ts';
import type { GreenwashResult } from '../model/index.ts';

export type ResultState =
  | { state: 'loading' }
  | { state: 'ready'; result: GreenwashResult }
  | { state: 'missing' }
  | { state: 'invalid'; issues: string }
  | { state: 'failed' };

export interface ResultHandle {
  status: ResultState;
  /** 다시 읽는다(loading 부터). */
  retry(): void;
}

export function useResult(
  store: GreenwashStore,
  runId: string,
  /** 거짓이면 읽지 않는다(상태는 loading 그대로 — GW-03 은 끝난 실행만 읽는다, 밴드 GW2R ②). 기본 참. */
  enabled = true,
): ResultHandle {
  const { status, retry } = useLoad(enabled ? [store, runId] : null, async () =>
    parseResult(await store.getResult(runId)),
  );
  const state = useMemo<ResultState>(() => {
    if (status.state === 'loading') return { state: 'loading' };
    if (status.state === 'failed')
      return storeErrorKind(status.error) === 'not_found' ?
          { state: 'missing' }
        : { state: 'failed' };
    const parsed = status.data;
    return parsed.ok ?
        { state: 'ready', result: parsed.value }
      : { state: 'invalid', issues: parsed.issues };
  }, [status]);
  return { status: state, retry };
}
