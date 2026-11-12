// AD-05 감사 기록 읽기(밴드 AD2 ①, 실서버 AD5R ②). 거르기는 서버가 한다 — 화면이 만든 쿼리(auditQuery)를 받는다.
//   - 처음·[다시 시도]: 줄 첫 쪽(offset 0)과 행위자 목록을 함께 부른다. 어느 하나라도 실패면 실패 상자 하나(MARC-ENT-260 「둘로만」).
//   - 쿼리가 바뀌면 줄만 첫 쪽부터 다시(행위자 목록은 지킨다). 300ms 뒤 스켈레톤은 화면이 정한다.
//   - more(): 지금 줄 수를 offset 으로 다음 쪽을 이어 붙인다. 실패하면 줄을 지키고 more 칸만 'failed'(다시 누를 수 있다).
//   - 늦게 온 답은 세대 셈이 버린다(거르기를 빨리 바꿔도 앞 요청의 답이 뒤 화면을 덮지 않는다 — 더 보기의 답도).
import { useCallback, useEffect, useRef, useState } from 'react';

import type { AuditServerPort } from '../../../entities/audit-log/api/index.ts';
import type {
  AuditActorRow,
  AuditEventRow,
  AuditQuery,
} from '../../../entities/audit-log/model/index.ts';

export type AuditLogState =
  | { phase: 'loading' }
  | { phase: 'failed' }
  | {
      phase: 'ready';
      rows: AuditEventRow[];
      /** 조건에 맞는 전부의 수(서버 count). */
      count: number;
      isNext: boolean;
      /** 더 보기의 상태. */
      more: 'idle' | 'loading' | 'failed';
      actors: AuditActorRow[];
    };

export function useAuditLog(port: AuditServerPort, query: AuditQuery) {
  const [state, setState] = useState<AuditLogState>({ phase: 'loading' });
  const generation = useRef(0);
  /** 받은 행위자 목록(쿼리가 바뀌어도 다시 부르지 않는다). port 가 바뀌면 비운다. */
  const actorsRef = useRef<AuditActorRow[] | null>(null);
  const moreBusy = useRef(false);
  // 쿼리 객체는 그릴 때마다 새로 만들어지므로 글자로 견준다.
  const queryKey = JSON.stringify(query);

  const load = useCallback(
    (withActors: boolean) => {
      const mine = ++generation.current;
      moreBusy.current = false;
      setState({ phase: 'loading' });
      const known = withActors ? null : actorsRef.current;
      Promise.all([
        port.list(JSON.parse(queryKey) as AuditQuery, 0),
        known ? { kind: 'ok' as const, actors: known } : port.actors(),
      ]).then(
        ([page, who]) => {
          if (mine !== generation.current) return;
          if (page.kind !== 'ok' || who.kind !== 'ok') {
            setState({ phase: 'failed' });
            return;
          }
          actorsRef.current = who.actors;
          setState({
            phase: 'ready',
            rows: page.rows,
            count: page.count,
            isNext: page.isNext,
            more: 'idle',
            actors: who.actors,
          });
        },
        () => {
          if (mine === generation.current) setState({ phase: 'failed' });
        },
      );
    },
    [port, queryKey],
  );

  useEffect(() => {
    actorsRef.current = null;
  }, [port]);

  useEffect(() => {
    load(false);
    const counter = generation;
    return () => {
      counter.current++;
    };
  }, [load]);

  const more = useCallback(() => {
    if (state.phase !== 'ready' || !state.isNext || moreBusy.current) return;
    moreBusy.current = true;
    const mine = generation.current;
    const offset = state.rows.length;
    setState({ ...state, more: 'loading' });
    const done = (
      next: (
        current: Extract<AuditLogState, { phase: 'ready' }>,
      ) => AuditLogState,
    ) => {
      if (mine !== generation.current) return;
      moreBusy.current = false;
      setState((current) =>
        current.phase === 'ready' ? next(current) : current,
      );
    };
    port.list(JSON.parse(queryKey) as AuditQuery, offset).then(
      (page) =>
        done((current) =>
          page.kind === 'ok' ?
            {
              ...current,
              rows: [...current.rows, ...page.rows],
              count: page.count,
              isNext: page.isNext,
              more: 'idle',
            }
          : { ...current, more: 'failed' },
        ),
      () => done((current) => ({ ...current, more: 'failed' })),
    );
  }, [port, queryKey, state]);

  const retry = useCallback(() => load(true), [load]);

  return { state, retry, more };
}
