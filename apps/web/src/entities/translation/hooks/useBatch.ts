// 묶음 하나 폴링 훅(밴드 TRW1a ①, TR-03·04). 저장소의 subscribeBatch(그린워싱 subscribeRun 규칙 — 멈춤은 state !== 'active')를 잇는다.
//   loading → ready(묶음 — 폴링마다 새 값) | missing(404·꼴 밖 열쇠) | failed(처음 읽기 실패·연속 3번 실패).
//   열쇠가 바뀌면 앞 구독을 끊고 loading 부터. 내려가면 끊는다(해제 뒤 온 답은 저장소가 버린다). retry 는 다시 구독.
//   restart 는 [이 파트만 다시] 뒤 멈춘 폴링을 다시 붙인다 — 받은 값(ready)을 들고 있다가 새 값으로 바꾼다(loading 으로 떨어지지 않음,
//   sid:MARC-ENT-443 ① — 스켈레톤 번쩍 0. 밴드 TRW1b).
import { useEffect, useState } from 'react';

import type { TranslationStore } from '../api/index.ts';
import type { TranslationBatchDetail } from '../model/index.ts';

export type BatchWatch =
  | { state: 'loading' }
  | { state: 'ready'; batch: TranslationBatchDetail }
  | { state: 'missing' }
  | { state: 'failed' };

export interface BatchHandle {
  status: BatchWatch;
  retry(): void;
  /** 다시 구독하되 받은 값을 들고 있는다(새 값이 오면 바꿈). */
  restart(): void;
}

export function useBatch(
  store: TranslationStore,
  documentId: string,
  batchKey: string,
): BatchHandle {
  const [{ round, hold }, setRound] = useState({ round: 0, hold: false });
  const [read, setRead] = useState<{ key: string; status: BatchWatch }>({
    key: '',
    status: { state: 'loading' },
  });
  const prefix = `${documentId}/${batchKey}/`;
  const key = `${prefix}${round}`;
  useEffect(() => {
    const put = (status: BatchWatch) => setRead({ key, status });
    return store.subscribeBatch(
      documentId,
      batchKey,
      (batch) => put({ state: 'ready', batch }),
      () => put({ state: 'missing' }),
      () => put({ state: 'failed' }),
    );
  }, [store, documentId, batchKey, key]);
  // restart 뒤 새 답을 받기 전: 같은 묶음의 앞 회차 값이 ready 면 그대로.
  const held =
    hold && read.key.startsWith(prefix) && read.status.state === 'ready';
  return {
    status: read.key === key || held ? read.status : { state: 'loading' },
    retry: () => setRound((now) => ({ round: now.round + 1, hold: false })),
    restart: () => setRound((now) => ({ round: now.round + 1, hold: true })),
  };
}
