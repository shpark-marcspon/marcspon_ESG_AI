// [다시 실행] 훅(밴드 FW2 ①, sid:MARC-ISSUE-99 1. 합침 밴드 WC1 ③). 실패한 실행과 같은 문서·같은 입력으로 새 실행을 만든다(store.rerun).
// 목록(GW-01, useCheckList — 줄마다 다른 실행)과 처리 상태(GW-03, useRerun — 실행 하나)가 같은 일을 해서 핵심 useRerunAction 하나로 합쳤다:
//   - 도는 동안(rerunning = 그 실행 id) 두 번째 누름은 store 를 부르지 않고 null(ref 로 막는다 — 상태는 다음 그리기에야 바뀌어
//     같은 그리기 안의 두 번째 누름을 놓친다. 밴드 FW2 ⑤ M1: 빨리 두 번 누르면 새 실행 둘이 생겼다). GW-03 도 이제 같이 막힌다.
//   - 거절되면 rerunError 에 그 실행 id 와 사유를 두고 null 을 돌려준다(화면은 role="alert" 안내). 다음 누름에서 지운다.
// useRerun 은 실행 하나로 좁힌 꼴이다: 다른 실행으로 바뀌면 앞 실행의 거절은 보이지 않는다.
// 열쇠(Idempotency-Key, 밴드 GR2 · sid:MARC-ISSUE-225): 실행마다 제 열쇠를 쥔다(runId → 열쇠). 누를 때 쥔 열쇠가 없으면 새로 짓는다.
//   끊김(unreachable — 새 실행이 만들어졌는지 모른다)이면 열쇠를 쥔 채 거절 표시를 두고, 다음 누름은 같은 열쇠로 다시 보낸다
//   (서버가 앞 실행을 돌려줘 실행은 하나 — 소리 없이 버리는 누름이 없다. 밴드 GR1 의 lost 막음을 걷었다, GR1 검증 R2).
//   성공·다른 거절이면 그 실행의 열쇠를 버린다(다음 누름은 새 열쇠). 훅이 내려가면(화면을 떠나면) 열쇠도 같이 버려진다.
import { useCallback, useRef, useState } from 'react';

import { newIdempotencyKey, storeErrorKind } from '../api/index.ts';
import type {
  GreenwashStore,
  NewIdempotencyKey,
  StoreErrorKind as StartError,
  StoreErrorKind,
} from '../api/index.ts';

export interface RerunAction {
  rerun(runId: string): Promise<string | null>;
  /** 도는 실행 id. 없으면 null. */
  rerunning: string | null;
  rerunError: { runId: string; error: StoreErrorKind } | null;
}

export function useRerunAction(
  store: GreenwashStore,
  newKey: NewIdempotencyKey = newIdempotencyKey,
): RerunAction {
  const [rerunning, setRerunning] = useState<string | null>(null);
  const [rerunError, setRerunError] = useState<RerunAction['rerunError']>(null);
  const busy = useRef(false);
  /** 실행마다 쥔 열쇠(runId → 열쇠). 보내는 동안과 끊긴 뒤에만 있다 — 끊겼으면 다음 누름이 같은 열쇠로 다시 보낸다. */
  const keys = useRef(new Map<string, string>());
  const rerun = useCallback(
    async (runId: string) => {
      if (busy.current) return null;
      busy.current = true;
      setRerunning(runId);
      setRerunError(null);
      const key = keys.current.get(runId) ?? newKey();
      keys.current.set(runId, key);
      try {
        const { runId: next } = await store.rerun(runId, key);
        keys.current.delete(runId);
        return next;
      } catch (error) {
        const kind = storeErrorKind(error);
        if (kind !== 'unreachable') keys.current.delete(runId);
        setRerunError({ runId, error: kind });
        return null;
      } finally {
        busy.current = false;
        setRerunning(null);
      }
    },
    [store, newKey],
  );
  return { rerun, rerunning, rerunError };
}

export interface Rerun {
  rerun(): Promise<string | null>;
  rerunning: boolean;
  startError: StartError | null;
}

export function useRerun(
  store: GreenwashStore,
  runId: string,
  newKey?: NewIdempotencyKey,
): Rerun {
  const action = useRerunAction(store, newKey);
  const { rerun: rerunRun } = action;
  const rerun = useCallback(() => rerunRun(runId), [rerunRun, runId]);
  return {
    rerun,
    // 어느 실행이든 도는 중이면 참이다: 도는 중 runId 가 바뀌어도 단추가 켜져 보이며 누름이 조용히 null 이 되는 틈이 없게(밴드 WC1 리뷰).
    rerunning: action.rerunning !== null,
    startError:
      action.rerunError !== null && action.rerunError.runId === runId ?
        action.rerunError.error
      : null,
  };
}
