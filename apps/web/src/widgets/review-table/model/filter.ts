// 걸러 보기의 조건. 상태, 카테고리, 글자 셋을 모두 만족하는 행만 남는다.
import { currentCandidate, currentCategory } from './row.ts';
import type { ReviewRow, ReviewStatus } from './row.ts';

export interface RowFilter {
  /** 비어 있으면 모든 상태. */
  statuses: readonly ReviewStatus[];
  /** null 이면 모든 카테고리. 수정했으면 수정한 카테고리로 견준다. */
  category: string | null;
  /** 원본 데이터의 값, 카테고리, 지금 후보의 계수 이름에서 찾는다. 대소문자를 가리지 않는다. */
  text: string;
}

export const NO_FILTER: RowFilter = { statuses: [], category: null, text: '' };

export function matchesFilter(row: ReviewRow, filter: RowFilter): boolean {
  if (filter.statuses.length > 0 && !filter.statuses.includes(row.status))
    return false;
  if (filter.category !== null && currentCategory(row) !== filter.category)
    return false;
  const needle = filter.text.trim().toLowerCase();
  if (needle === '') return true;
  const haystack = [
    ...Object.values(row.raw),
    currentCategory(row),
    currentCandidate(row)?.factorName,
  ];
  return haystack.some(
    (value) =>
      value !== null &&
      value !== undefined &&
      String(value).toLowerCase().includes(needle),
  );
}
