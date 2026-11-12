// 실행 하나 폴링 훅(밴드 DV2a ①, DV-03). 저장소의 subscribeRun(그린워싱 subscribeRun 규칙 — done·failed 에서 멈춤)을 잇는다.
//   loading → ready(실행 — 폴링마다 새 값) | missing(404·꼴 밖 id·데이터 검증 아님) | failed(처음 읽기 실패·연속 3번 실패).
//   id 가 바뀌면 앞 구독을 끊고 loading 부터. 내려가면 끊는다(해제 뒤 온 답은 저장소가 버린다). retry 는 다시 구독.
import { useEffect, useState } from 'react';

import type { DataverifyStore } from '../api/index.ts';
import type { DataverifyRun } from '../model/index.ts';

export type RunWatch =
  | { state: 'loading' }
  | { state: 'ready'; run: DataverifyRun }
  | { state: 'missing' }
  | { state: 'failed' };

export interface RunHandle {
  status: RunWatch;
  retry(): void;
}

export function useRun(store: DataverifyStore, runId: string): RunHandle {
  const [round, setRound] = useState(0);
  const [read, setRead] = useState<{ key: string; status: RunWatch }>({
    key: '',
    status: { state: 'loading' },
  });
  const key = `${runId}/${round}`;
  useEffect(() => {
    const put = (status: RunWatch) => setRead({ key, status });
    return store.subscribeRun(
      runId,
      (run) => put({ state: 'ready', run }),
      () => put({ state: 'missing' }),
      () => put({ state: 'failed' }),
    );
  }, [store, runId, key]);
  return {
    status: read.key === key ? read.status : { state: 'loading' },
    retry: () => setRound((n) => n + 1),
  };
}
