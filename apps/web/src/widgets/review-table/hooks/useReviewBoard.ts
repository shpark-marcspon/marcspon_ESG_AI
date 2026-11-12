// 검토 표의 헤드리스 훅 셋을 하나로 묶은 훅. 화면은 이 훅 하나를 부르고, 행들은 <RowStack> 에 맡긴다.
//
//   useReviewRows    행의 상태와 동작(반영, 수정, 확정 …), 요약
//   useReviewTable   정렬, 걸러 보기, 행 고르기              (TanStack Table)
//   useRowWindow     보이는 행만 그리기, 지금 행, 펼침, 키보드   (TanStack Virtual)
//
// 화면을 다른 UI 라이브러리로 바꿀 때 이 층은 그대로 둔다. 따로 쓰고 싶으면 세 훅을 직접 불러도 된다.
import { useCallback, useState } from 'react';

import type {
  ActionResult,
  BulkResult,
  ReviewAction,
  ReviewRow,
  Summary,
} from '../model/index.ts';
import { useReviewRows } from './useReviewRows.ts';
import type { Calculate } from './useReviewRows.ts';
import { useReviewTable } from './useReviewTable.ts';
import type { BulkScope, ReviewColumn, ReviewTable } from './useReviewTable.ts';
import { useRowWindow } from './useRowWindow.ts';
import type { RowWindow } from './useRowWindow.ts';

export interface ReviewBoardOptions {
  rows: readonly ReviewRow[];
  columns: readonly ReviewColumn[];
  calculate: Calculate;
  onChange?: (changed: readonly ReviewRow[]) => void;
  estimateRowHeight: number;
  overscan?: number;
}

/** 마지막 일괄 동작의 결과. 화면이 「적용 몇 개, 건너뜀 몇 개(까닭별)」를 보여 준다. */
export interface BulkOutcome extends Pick<BulkResult, 'skipped' | 'missing'> {
  action: ReviewAction['type'];
  scope: BulkScope;
  targeted: number;
  applied: number;
}

export interface ReviewBoard {
  /** 전체 행의 수(걸러 보기 전). */
  totalRows: number;
  summary: Summary;
  table: ReviewTable;
  window: RowWindow;
  act(rowId: string, action: ReviewAction): ActionResult;
  /** 대상(고른 행들 또는 걸러 본 결과 전체)에 일괄로 적용한다. 화면에 그려지지 않은 행도 대상이다. */
  bulk(scope: BulkScope, action: ReviewAction): BulkOutcome;
  lastBulk: BulkOutcome | null;
  /** 재계산이 실패한 행의 계산을 다시 부른다. 실패한 행이 아니면 false. */
  retry(rowId: string): boolean;
}

export function useReviewBoard(options: ReviewBoardOptions): ReviewBoard {
  const data = useReviewRows({
    initialRows: options.rows,
    calculate: options.calculate,
    onChange: options.onChange,
  });
  const table = useReviewTable(data.rows, options.columns);
  const window = useRowWindow(table.rows, {
    estimateRowHeight: options.estimateRowHeight,
    overscan: options.overscan,
    onToggleSelected: table.toggleSelected,
  });
  const [lastBulk, setLastBulk] = useState<BulkOutcome | null>(null);

  const { targetIds } = table;
  const { bulk: bulkRows } = data;
  const bulk = useCallback(
    (scope: BulkScope, action: ReviewAction): BulkOutcome => {
      const ids = targetIds(scope);
      const result = bulkRows(ids, action);
      const outcome: BulkOutcome = {
        action: action.type,
        scope,
        targeted: ids.length,
        applied: result.changed.length,
        skipped: result.skipped,
        missing: result.missing,
      };
      setLastBulk(outcome);
      return outcome;
    },
    [targetIds, bulkRows],
  );

  return {
    totalRows: data.rows.length,
    summary: data.summary,
    table,
    window,
    act: data.act,
    bulk,
    lastBulk,
    retry: data.retry,
  };
}
