// AD-04a 실행 상세 읽기(밴드 AD4W). 모달을 열 때마다 GET /run-logs/{run_id} 를 한 번 부른다(캐시 없음 — 처리 중 실행은 바뀐다, 감독 처분 Q2 (가)).
//   - opened 는 화면이 여는 차례마다 새 seq 를 준다(같은 줄을 다시 열어도 다시 부른다). null 이면 idle.
//   - 늦게 온 답은 세대 셈이 버린다(A 를 열고 닫고 B 를 열면 A 의 답이 B 를 덮지 않는다).
//   - retry(): 같은 id 로 한 번 더. 300ms 뒤 스켈레톤은 화면이 정한다.
import { useCallback, useEffect, useRef, useState } from 'react';

import type { RunLogServerPort } from '../../../entities/run-log/api/index.ts';
import type { RunLogDetail } from '../../../entities/run-log/model/index.ts';

export type RunDetailState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'failed' }
  | { phase: 'notFound' }
  | { phase: 'ready'; detail: RunLogDetail };

/** 화면이 연 차례 하나(seq 는 열 때마다 새 값). */
export interface RunDetailOpened {
  runId: number;
  seq: number;
}

export function useRunDetail(
  port: RunLogServerPort,
  opened: RunDetailOpened | null,
) {
  // 받은 상태에 그 상태를 낸 여는 번호를 붙여 둔다 — 다시 연 첫 그리기에 앞 실행의 글이 비치지 않게(번호가 다르면 loading).
  const [stored, setStored] = useState<{
    seq: number;
    state: RunDetailState;
  } | null>(null);
  const generation = useRef(0);
  const runId = opened?.runId ?? null;
  const seq = opened?.seq ?? null;

  const load = useCallback(
    (id: number, at: number) => {
      const mine = ++generation.current;
      setStored({ seq: at, state: { phase: 'loading' } });
      port.detail(id).then(
        (outcome) => {
          if (mine !== generation.current) return;
          setStored({
            seq: at,
            state:
              outcome.kind === 'ok' ?
                { phase: 'ready', detail: outcome.detail }
              : { phase: outcome.kind },
          });
        },
        () => {
          if (mine === generation.current)
            setStored({ seq: at, state: { phase: 'failed' } });
        },
      );
    },
    [port],
  );

  useEffect(() => {
    if (runId === null || seq === null) return;
    load(runId, seq);
    const counter = generation;
    return () => {
      counter.current++;
    };
  }, [load, runId, seq]);

  const retry = useCallback(() => {
    if (runId !== null && seq !== null) load(runId, seq);
  }, [load, runId, seq]);

  const state: RunDetailState =
    seq === null ? { phase: 'idle' }
    : stored?.seq === seq ? stored.state
    : { phase: 'loading' };
  return { state, retry };
}
