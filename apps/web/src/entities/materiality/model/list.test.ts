// 평가 목록의 거르기·다음 할 일(밴드 IRW1 ③ — 판 IR-01). 단계 → 판 줄(목록 「처리 중 · <줄 이름>」).
import { describe, expect, it } from 'vitest';

import { LIST_TABS, nextOf, rowTargetOf, statusesOf } from './list.ts';
import { lineOfStep } from './steps.ts';

describe('목록', () => {
  it('탭 넷 → status 인자(「대기·처리 중」은 둘)', () => {
    expect(LIST_TABS.map(statusesOf)).toEqual([
      undefined,
      ['queued', 'processing'],
      ['done'],
      ['failed'],
    ]);
  });

  it('다음 할 일과 줄 누름: failed 는 [다시 실행]이지만 누름은 처리 상태', () => {
    expect(nextOf('done')).toBe('result');
    expect(nextOf('queued')).toBe('progress');
    expect(nextOf('processing')).toBe('progress');
    expect(nextOf('failed')).toBe('rerun');
    expect(rowTargetOf('failed')).toBe('status');
    expect(rowTargetOf('done')).toBe('result');
  });

  it('단계 이름 → 판 줄(report 는 줄 2, 모르는 이름 null)', () => {
    expect(lineOfStep('report')).toBe('controversy');
    expect(lineOfStep('report_iro')).toBe('report');
    expect(lineOfStep('impact')).toBe('impact');
    expect(lineOfStep('later_step')).toBeNull();
  });
});
