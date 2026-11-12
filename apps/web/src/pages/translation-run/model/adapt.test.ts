// 검수 이슈 차례(밴드 TRP2 TC27, 발주서 §3): 심각도 High → Mid → Low, 같은 심각도 안은 쪽 차례(안정 정렬).
import { describe, expect, it } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import type {
  ResultPage,
  ResultVariant,
  ReviewIssue,
} from '../../../entities/translation/model/index.ts';
import { issuesOf, reviewedRangeOf } from './adapt.ts';

const issue = (severity: string, reason: string): ReviewIssue => ({
  issueType: 'GRAMMAR',
  severity,
  originalSpan: 'span',
  suggestion: 'suggestion',
  reason,
  source: 'model',
});
const page = (pageNum: number, issues: ReviewIssue[]): ResultPage => ({
  pageNum,
  translated: '',
  bilingual: '',
  review: {
    status: 'reviewed',
    issues,
    counts: { high: 0, medium: 0, low: 0 },
    message: null,
  },
});
const variant = (pages: ResultPage[]): ResultVariant => ({
  label: 'single',
  fragments: [],
  pages,
  glossaryCheck: [],
  autofix: { status: 'done', pages: [], notRunReason: null },
});

describe('issuesOf 차례', () => {
  it('High 가 쪽 12 에 있고 Mid·Low 가 앞 쪽에 있어도 High 가 첫째, 같은 심각도는 쪽 차례', () => {
    const { issues } = issuesOf(
      variant([
        page(4, [issue('LOW', 'l4'), issue('MEDIUM', 'm4')]),
        page(7, [issue('MEDIUM', 'm7'), issue('LOW', 'l7')]),
        page(12, [issue('HIGH', 'h12')]),
        page(15, [issue('HIGH', 'h15'), issue('MEDIUM', 'm15')]),
      ]),
    );
    expect(issues.map((one) => `${one.page}:${one.reason}`)).toEqual([
      '12:h12',
      '15:h15',
      '4:m4',
      '7:m7',
      '15:m15',
      '4:l4',
      '7:l7',
    ]);
  });
});

// [TRP2 TC26] 검수가 멈췄을 때 기준 글 「4~29쪽 · 7건 · 자동 수정 전 글 기준」.
describe('reviewedRangeOf · basisStopped', () => {
  it('시작 4 · 30쪽에서 멈춤 → 4~29, 글은 시안 TR-04a 그대로', () => {
    const range = reviewedRangeOf(4, 30)!;
    expect(range).toEqual({ from: 4, to: 29 });
    expect(TR_TEXT.issues.basisStopped(range.from, range.to, 7)).toBe(
      '4~29페이지 · 7건 · 자동 수정 전 글 기준',
    );
  });

  it('멈추지 않음 · 첫 쪽에서 멈춤 · 시작 모름 → null(기본 글)', () => {
    expect(reviewedRangeOf(4, null)).toBeNull();
    expect(reviewedRangeOf(4, 4)).toBeNull();
    expect(reviewedRangeOf(null, 30)).toBeNull();
  });
});
