// 일괄 동작. 대상 행들에 같은 동작을 적용하고, 못 한 행은 건너뛰며 「몇 개가 왜」를 돌려준다.
// 대상(targetIds)을 정하는 것은 이 함수의 일이 아니다. 화면에 그려졌는지와 무관하게, 받은 id 전부가 대상이다.
import type { ReviewRow, ReviewStatus } from './row.ts';
import { STATUS_LABEL } from './row.ts';
import { ACTION_ERROR_MESSAGE, applyAction } from './transitions.ts';
import type { ActionError, ReviewAction } from './transitions.ts';

export interface BulkSkip {
  error: ActionError;
  /** 건너뛴 행의 그때 상태. */
  status: ReviewStatus;
  count: number;
}

export interface BulkResult {
  /** 바뀐 뒤의 전체 행. 순서는 그대로다. 바뀌지 않은 행은 같은 객체다. */
  rows: ReviewRow[];
  /** 실제로 바뀐 행들(바뀐 뒤의 모습). */
  changed: ReviewRow[];
  skipped: BulkSkip[];
  /** 대상으로 받았지만 그런 id 의 행이 없던 개수. */
  missing: number;
}

export function applyBulk(
  rows: readonly ReviewRow[],
  targetIds: Iterable<string>,
  action: ReviewAction,
): BulkResult {
  const targets = new Set(targetIds);
  const changed: ReviewRow[] = [];
  const skips = new Map<string, BulkSkip>();
  let found = 0;

  const next = rows.map((row) => {
    if (!targets.has(row.id)) return row;
    found += 1;
    const result = applyAction(row, action);
    if (result.ok) {
      changed.push(result.row);
      return result.row;
    }
    const key = `${result.error}:${row.status}`;
    const skip = skips.get(key) ?? {
      error: result.error,
      status: row.status,
      count: 0,
    };
    skip.count += 1;
    skips.set(key, skip);
    return row;
  });

  return {
    rows: next,
    changed,
    skipped: [...skips.values()],
    missing: targets.size - found,
  };
}

export function skippedCount(result: Pick<BulkResult, 'skipped'>): number {
  return result.skipped.reduce((sum, skip) => sum + skip.count, 0);
}

/** 건너뛴 까닭을 사람이 읽을 한 줄로. 예: 「검토대기 12개: 지금 상태에서는 할 수 없는 동작이다.」 */
export function describeSkip(skip: BulkSkip): string {
  return `${STATUS_LABEL[skip.status]} ${skip.count}개: ${ACTION_ERROR_MESSAGE[skip.error]}`;
}
