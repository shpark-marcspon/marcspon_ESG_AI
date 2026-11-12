// 검수 이슈 거르기·셈(밴드 TRW0b, 발주서 §3-10).
import { describe, expect, it } from 'vitest';

import { SAMPLE_ISSUES } from '../../../entities/translation/model/testing.ts';
import { filterIssues, severityCounts } from './issues.ts';

describe('issues', () => {
  it('심각도 수 넷 = 전체 11 · High 1 · Mid 4 · Low 6', () => {
    expect(severityCounts(SAMPLE_ISSUES)).toEqual({
      all: 11,
      high: 1,
      mid: 4,
      low: 6,
    });
    expect(severityCounts([])).toEqual({ all: 0, high: 0, mid: 0, low: 0 });
  });

  it('거르기: 없는 칸은 거르지 않고, 둘은 겹친다(차례 그대로)', () => {
    expect(filterIssues(SAMPLE_ISSUES, {})).toHaveLength(11);
    expect(
      filterIssues(SAMPLE_ISSUES, { severity: 'high' }).map((i) => i.page),
    ).toEqual([12]);
    expect(
      filterIssues(SAMPLE_ISSUES, { type: 'grammar' }).map((i) => i.page),
    ).toEqual([33, 34]);
    expect(
      filterIssues(SAMPLE_ISSUES, { type: 'unnatural', severity: 'low' }).map(
        (i) => i.page,
      ),
    ).toEqual([35]);
    expect(
      filterIssues(SAMPLE_ISSUES, { type: 'grammar', severity: 'high' }),
    ).toEqual([]);
  });
});
