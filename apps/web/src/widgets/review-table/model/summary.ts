// 요약. 상태별 개수와 합계.
// ★ 최종확정된 행만 결과 합계(finalTotal)에 든다. 반영·수정 상태의 행은 「최종 결과 후보」라 임시 합계(provisionalTotal)에 따로 든다.
import {
  STATUSES,
  currentEmission,
  isRecalcFailed,
  isRecalcPending,
} from './row.ts';
import type { ReviewRow, ReviewStatus } from './row.ts';

export interface Summary {
  total: number;
  byStatus: Record<ReviewStatus, number>;
  /** 최종확정 행의 배출량 합(tCO2eq). 단위는 입력 맨 위의 unit 하나라 같은 입력의 행끼리는 늘 같은 단위다. */
  finalTotal: number;
  /** 반영·수정 상태(아직 확정 전)인 행의 배출량 합. 배출량이 없는 행은 빠진다. */
  provisionalTotal: number;
  /** 재계산을 기다리는 행의 수. */
  recalcPending: number;
  /** 재계산이 실패한 채로 있는 행의 수. 배출량이 없는 행의 수가 아니다. */
  recalcFailed: number;
}

export function summarize(rows: readonly ReviewRow[]): Summary {
  const byStatus = Object.fromEntries(
    STATUSES.map((status) => [status, 0]),
  ) as Record<ReviewStatus, number>;
  let finalTotal = 0;
  let provisionalTotal = 0;
  let recalcPending = 0;
  let recalcFailed = 0;

  for (const row of rows) {
    byStatus[row.status] += 1;
    if (isRecalcPending(row)) recalcPending += 1;
    if (isRecalcFailed(row)) recalcFailed += 1;
    const emission = currentEmission(row);
    if (emission === null) continue;
    if (row.status === 'finalized') finalTotal += emission;
    else if (row.status === 'accepted' || row.status === 'edited')
      provisionalTotal += emission;
  }
  return {
    total: rows.length,
    byStatus,
    finalTotal,
    provisionalTotal,
    recalcPending,
    recalcFailed,
  };
}
