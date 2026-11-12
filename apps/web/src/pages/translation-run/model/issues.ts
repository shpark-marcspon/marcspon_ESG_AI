// 번역 검수 이슈 거르기·셈(밴드 TRW0b, 시안 TR-04 「유형 전체 · 전체 11 High 1 Mid 4 Low 6」). 순수 함수.
// 심각도 상자 탭의 수는 이 파트의 이슈 전체로 센다(유형 거르기와 상관없이 — 시안 「거르기 숫자는 이 파트의 이슈 전체예요」).
import type {
  IssueTypeKey,
  Severity,
} from '../../../entities/translation/model/index.ts';

export interface QaIssue {
  page: number;
  type: IssueTypeKey;
  severity: Severity;
  span: string;
  suggestion: string;
  reason: string;
}

export interface IssueFilter {
  type?: IssueTypeKey;
  severity?: Severity;
}

/** 유형·심각도 둘 다 맞는 이슈(없는 칸은 거르지 않는다). 차례는 그대로. */
export function filterIssues(
  issues: readonly QaIssue[],
  filter: IssueFilter,
): QaIssue[] {
  return issues.filter(
    (issue) =>
      (filter.type === undefined || issue.type === filter.type) &&
      (filter.severity === undefined || issue.severity === filter.severity),
  );
}

/** 심각도 상자 탭의 수(전체 · High · Mid · Low). */
export function severityCounts(issues: readonly QaIssue[]): {
  all: number;
  high: number;
  mid: number;
  low: number;
} {
  const count = (severity: Severity) =>
    issues.filter((issue) => issue.severity === severity).length;
  return {
    all: issues.length,
    high: count('high'),
    mid: count('mid'),
    low: count('low'),
  };
}
