// 행의 상태를 들고, 업무 로직(domain)을 돌려 바꾼다. 화면 안 상태다. 새로 고치면 사라진다.
//
// 밖에서 받는 것 둘:
//   calculate  배출량 계산. 서버의 일이라 이 부품은 계산을 모른다. 수정이 일어나면 불러서 결과를 행에 넣는다
//              계산이 실패하면(거부, 예외) 행에 「계산하지 못했다」를 남기고(domain 의 applyRecalcFailed), retry 로 다시 부른다
//   onChange   바뀐 행들을 알린다. ★ 서버를 붙일 자리다(저장 요청). 지금은 아무도 안 받아도 된다
// 누가·언제 바꿨는지의 기록(이력)은 여기 없다. onChange 를 받는 쪽이 남길 수 있다.
import { useCallback, useMemo, useRef, useState } from 'react';

import {
  applyAction,
  applyBulk,
  applyRecalcFailed,
  applyRecalculated,
  currentCandidate,
  currentCategory,
  isRecalcFailed,
  retryRecalc,
  summarize,
} from '../model/index.ts';
import type {
  ActionResult,
  BulkResult,
  Candidate,
  ReviewAction,
  ReviewRow,
  Summary,
} from '../model/index.ts';

export interface CalculateRequest {
  row: ReviewRow;
  /** 고친 뒤의 카테고리와 후보. */
  category: string | null;
  candidate: Candidate | null;
}

/**
 * 배출량(tCO2eq)을 돌려준다. 바로 답해도 되고 Promise 로 답해도 된다.
 *   null            계산해 보니 값이 없다(단위가 안 맞는 등). 행은 「배출량 없음」이 된다
 *   거부하거나 예외   계산이 실패했다(서버 오류 등). 행에 「계산하지 못했다」가 남고 retry 로 다시 부를 수 있다
 */
export type Calculate = (
  request: CalculateRequest,
) => number | null | Promise<number | null>;

export interface ReviewRowsOptions {
  /** 처음 행들. 나중에 바꿔 넣어도 다시 읽지 않는다(자료가 바뀌면 key 로 부품을 새로 만든다). */
  initialRows: readonly ReviewRow[];
  calculate: Calculate;
  onChange?: (changed: readonly ReviewRow[]) => void;
}

export interface ReviewRows {
  /** 전체 행. 처음 받은 순서 그대로다. 바뀌지 않은 행은 같은 객체로 남는다. */
  rows: readonly ReviewRow[];
  summary: Summary;
  act(rowId: string, action: ReviewAction): ActionResult;
  bulk(rowIds: Iterable<string>, action: ReviewAction): BulkResult;
  /** 재계산이 실패한 행의 계산을 다시 부른다. 실패한 행이 아니면 아무것도 하지 않고 false. */
  retry(rowId: string): boolean;
}

export function useReviewRows({
  initialRows,
  calculate,
  onChange,
}: ReviewRowsOptions): ReviewRows {
  const [rows, setRows] = useState<readonly ReviewRow[]>(initialRows);
  // act 를 연달아 불러도 방금 바뀐 값을 읽게, 가장 새 값을 ref 에도 둔다. 덕분에 act 와 bulk 가 다시 만들어지지 않는다.
  const latest = useRef(rows);
  const options = useRef({ calculate, onChange });
  options.current = { calculate, onChange };
  // 행의 순서는 바뀌지 않으므로 id → 자리를 처음 받은 행으로 한 번만 만든다(나중에 다른 배열을 넘겨도 상태와 어긋나지 않게).
  const [indexOf] = useState(
    () => new Map(initialRows.map((row, index) => [row.id, index])),
  );

  /** 바뀐 행들을 제자리에 넣는다. */
  const commit = useCallback(
    (changed: readonly ReviewRow[]) => {
      if (changed.length === 0) return;
      const next = [...latest.current];
      for (const row of changed) next[indexOf.get(row.id)!] = row;
      latest.current = next;
      setRows(next);
      options.current.onChange?.(changed);
    },
    [indexOf],
  );

  /** 재계산을 기다리는 행마다 계산을 부른다. 바로 답이 온 것은 그 자리에서 넣어 돌려주고, 늦게 오는 것은 올 때 넣는다. */
  const recalculate = useCallback(
    (changed: readonly ReviewRow[]): ReviewRow[] =>
      changed.map((row) => {
        if (!row.edit?.recalcPending) return row;
        let answer: ReturnType<Calculate>;
        try {
          answer = options.current.calculate({
            row,
            category: currentCategory(row),
            candidate: currentCandidate(row),
          });
        } catch {
          // 바로 던진 예외도 실패다. 「값이 없다」(null)로 뭉개지 않는다.
          return applyRecalcFailed(row);
        }
        if (!(answer instanceof Promise)) return applyRecalculated(row, answer);
        const askedFor = row.edit;
        const settle = (finish: (now: ReviewRow) => ReviewRow) => {
          const now = latest.current[indexOf.get(row.id)!]!;
          // 기다리는 동안 다시 고쳤거나 되돌렸으면 이 답은 버린다.
          if (now.edit === askedFor) commit([finish(now)]);
        };
        answer.then(
          (emission) => settle((now) => applyRecalculated(now, emission)),
          () => settle(applyRecalcFailed),
        );
        return row;
      }),
    [commit, indexOf],
  );

  const act = useCallback(
    (rowId: string, action: ReviewAction): ActionResult => {
      const index = indexOf.get(rowId);
      if (index === undefined) return { ok: false, error: 'not_allowed' };
      const result = applyAction(latest.current[index]!, action);
      if (!result.ok) return result;
      const [row] = recalculate([result.row]);
      commit([row!]);
      return { ok: true, row: row! };
    },
    [commit, indexOf, recalculate],
  );

  const bulk = useCallback(
    (rowIds: Iterable<string>, action: ReviewAction): BulkResult => {
      const result = applyBulk(latest.current, rowIds, action);
      const changed = recalculate(result.changed);
      commit(changed);
      return { ...result, rows: [...latest.current], changed };
    },
    [commit, recalculate],
  );

  const retry = useCallback(
    (rowId: string): boolean => {
      const index = indexOf.get(rowId);
      const row = index === undefined ? undefined : latest.current[index];
      if (!row || !isRecalcFailed(row)) return false;
      commit(recalculate([retryRecalc(row)]));
      return true;
    },
    [commit, indexOf, recalculate],
  );

  const summary = useMemo(() => summarize(rows), [rows]);
  return { rows, summary, act, bulk, retry };
}
