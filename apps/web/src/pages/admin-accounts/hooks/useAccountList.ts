// AD-01 목록 읽기(밴드 AD1 ②, 실서버 거르기 UA1W ②). 거르기는 서버가 한다 — 화면이 만든 쿼리(accountQuery)를 받는다.
//   - 처음·[다시 시도]: loading 을 거쳐 목록(list)과 전체 수(total)를 함께 부른다. 어느 하나라도 실패면 실패 상자 하나(MARC-ENT-260 「둘로만」).
//   - 쿼리가 바뀌면 loading 을 거쳐 목록만 다시(전체 수는 거르기와 따로라 지킨다 — 받은 적이 없으면 같이 부른다. AD4R useRunLog 꼴).
//   - 쓰기 뒤 다시 받기(refresh)는 지금 줄을 둔 채 목록과 전체 수를 함께 받는다(만들기로 전체 수가 바뀐다).
//   300ms 뒤 스켈레톤은 화면이 정한다. 늦게 온 답은 세대 셈이 버린다(거르기를 빨리 바꿔도 마지막 것만 그린다).
import { useCallback, useEffect, useRef, useState } from 'react';

import type { AccountsPort } from '../../../entities/account/api/index.ts';
import type {
  Account,
  AccountQuery,
} from '../../../entities/account/model/index.ts';

export type AccountListState =
  | { phase: 'loading' }
  | { phase: 'failed' }
  | {
      phase: 'ready';
      /** 거르지 않은 전체 수(설명 줄의 개수). */
      total: number;
      /** 조건에 맞는 전부의 수(서버 count). */
      count: number;
      accounts: Account[];
    };

export interface AccountList {
  state: AccountListState;
  /** [다시 시도]: loading 을 거쳐 다시 받는다. */
  retry(): void;
  /** 쓰기 뒤: 지금 줄을 둔 채 다시 받는다. */
  refresh(): void;
}

export function useAccountList(
  port: AccountsPort,
  query: AccountQuery,
): AccountList {
  const [state, setState] = useState<AccountListState>({ phase: 'loading' });
  const generation = useRef(0);
  /** 받은 전체 수(쿼리가 바뀌어도 다시 부르지 않는다). port 가 바뀌면 비운다. */
  const totalRef = useRef<number | null>(null);
  // 쿼리 객체는 그릴 때마다 새로 만들어지므로 글자로 견준다.
  const queryKey = JSON.stringify(query);

  const load = useCallback(
    ({ quiet, withTotal }: { quiet: boolean; withTotal: boolean }) => {
      const mine = ++generation.current;
      if (!quiet) setState({ phase: 'loading' });
      const known = withTotal ? null : totalRef.current;
      Promise.all([
        port.list(JSON.parse(queryKey) as AccountQuery),
        known === null ? port.total() : { kind: 'ok' as const, total: known },
      ]).then(
        ([page, all]) => {
          if (mine !== generation.current) return;
          if (page.kind !== 'ok' || all.kind !== 'ok') {
            setState({ phase: 'failed' });
            return;
          }
          totalRef.current = all.total;
          setState({
            phase: 'ready',
            total: all.total,
            count: page.count,
            accounts: page.accounts,
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
    totalRef.current = null;
  }, [port]);

  useEffect(() => {
    load({ quiet: false, withTotal: false });
    // 마운트가 풀리면(또는 port·쿼리가 바뀌면) 늦게 온 답을 버린다.
    const counter = generation;
    return () => {
      counter.current++;
    };
  }, [load]);

  return {
    state,
    retry: useCallback(() => load({ quiet: false, withTotal: true }), [load]),
    refresh: useCallback(() => load({ quiet: true, withTotal: true }), [load]),
  };
}
