// 밴드 G1b-3 ③: 검토 고침의 순수 셈 — 보이는 값(고친 값 ?? AI)·tally 고친 문장·등급 탭은 보이는 등급·editUpdate(marks 그대로 + 고침 전부
// 평평한 값)·markUpdate·confirmUpdate 는 edits 를 싣지 않음·판정 사유 글 칸 ↔ 항목. 값은 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import type { GreenwashReview, ResultItem, ReviewEdit } from './result.ts';
import {
  confirmUpdate,
  editUpdate,
  filterReviewRows,
  joinReview,
  markUpdate,
  reasonsFromText,
  reasonsText,
  reviewTally,
} from './review.ts';

const item = (
  page: number,
  level: ResultItem['level'],
  parts: string[] = ['가 파트'],
): ResultItem => ({
  page,
  parts,
  sentence: `지어낸 문장 ${page}`,
  level,
  riskTags: [],
  confirmedInEvidence: [],
  missingFields: [],
  reasonBullets: [`AI 사유 ${page}`],
  fixParagraph: `AI 수정 방향 ${page}`,
  evidencePages: [],
  evidenceInternal: '',
  position: null,
  exampleSentence: null,
});

const items = [item(1, 'High'), item(2, 'Mid'), item(3, 'Low')];
const by = { id: 7, name: '가상 고친이' };
const at = '2026-10-22T14:28:00+09:00';

/** 0: 등급만 High → Low · 2: 사유·수정 방향만. 1 은 고침 없음. */
const edits: ReviewEdit[] = [
  {
    itemIndex: 0,
    level: { value: 'Low', editedAt: at, editedBy: by },
    reasonBullets: null,
    fixParagraph: null,
  },
  {
    itemIndex: 2,
    level: null,
    reasonBullets: {
      value: ['고친 사유 하나', '고친 사유 둘'],
      editedAt: at,
      editedBy: by,
    },
    fixParagraph: { value: '고친 수정 방향', editedAt: at, editedBy: by },
  },
];

const review = (over: Partial<GreenwashReview> = {}): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  evidence: [],
  rejudges: [],
  runId: 1,
  state: 'in_review',
  confirmedAt: null,
  confirmedBy: null,
  marks: [{ itemIndex: 1, decision: 'excluded', excludeReason: '기타: 가' }],
  edits,
  ...over,
});

describe('보이는 값 = 고친 값 ?? AI (칸마다)', () => {
  it('고친 칸은 고친 값, 안 고친 칸은 AI 값. AI 원본(item)은 그대로', () => {
    const rows = joinReview(items, [], edits);
    expect(rows.map((r) => r.shownLevel)).toEqual(['Low', 'Mid', 'Low']);
    expect(rows.map((r) => r.shownReasons)).toEqual([
      ['AI 사유 1'],
      ['AI 사유 2'],
      ['고친 사유 하나', '고친 사유 둘'],
    ]);
    expect(rows.map((r) => r.shownFix)).toEqual([
      'AI 수정 방향 1',
      'AI 수정 방향 2',
      '고친 수정 방향',
    ]);
    expect(rows.map((r) => r.edit?.itemIndex ?? null)).toEqual([0, null, 2]);
    // AI 원본은 결과 그대로
    expect(rows[0]!.item.level).toBe('High');
    expect(items[0]!.level).toBe('High');
  });

  it('edits 를 안 주면(옛 부름) 보이는 값 = AI', () => {
    const rows = joinReview(items, []);
    expect(rows.map((r) => r.shownLevel)).toEqual(['High', 'Mid', 'Low']);
    expect(rows.every((r) => r.edit === null)).toBe(true);
  });

  it('tally.edited = 칸 하나 이상 고친 문장 수', () => {
    expect(reviewTally(joinReview(items, [], edits)).edited).toBe(2);
    expect(reviewTally(joinReview(items, [], [])).edited).toBe(0);
  });

  it('등급 탭은 보이는 등급으로 거른다(High → Low 로 고친 문장은 Low 탭에)', () => {
    const rows = joinReview(items, [], edits);
    const tab = (t: 'High' | 'Mid' | 'Low') =>
      filterReviewRows(rows, { part: null, tab: t }).map((r) => r.index);
    expect(tab('High')).toEqual([]);
    expect(tab('Mid')).toEqual([1]);
    expect(tab('Low')).toEqual([0, 2]);
  });
});

describe('PUT 본문', () => {
  it('editUpdate: marks 는 그대로 + 그 실행의 고침 전부(평평한 값, 오름차순)에 바꾼 칸만 얹는다. state 없음', () => {
    const body = editUpdate(review(), {
      itemIndex: 2,
      column: 'fixParagraph',
      value: '다시 고친 수정 방향',
    });
    expect(body).toEqual({
      marks: [
        { itemIndex: 1, decision: 'excluded', excludeReason: '기타: 가' },
      ],
      edits: [
        { itemIndex: 0, level: 'Low', reasonBullets: null, fixParagraph: null },
        {
          itemIndex: 2,
          level: null,
          reasonBullets: ['고친 사유 하나', '고친 사유 둘'],
          fixParagraph: '다시 고친 수정 방향',
        },
      ],
    });
    expect('state' in body).toBe(false);
  });

  it('editUpdate: 고침 없던 문장은 그 칸 하나만 값인 줄로 더하고, 차례는 itemIndex 오름', () => {
    expect(
      editUpdate(review(), { itemIndex: 1, column: 'level', value: 'High' })
        .edits,
    ).toEqual([
      { itemIndex: 0, level: 'Low', reasonBullets: null, fixParagraph: null },
      { itemIndex: 1, level: 'High', reasonBullets: null, fixParagraph: null },
      {
        itemIndex: 2,
        level: null,
        reasonBullets: ['고친 사유 하나', '고친 사유 둘'],
        fixParagraph: '고친 수정 방향',
      },
    ]);
  });

  it('editUpdate: 바꿈 여럿은 차례대로 얹는다(같은 칸은 마지막 값)', () => {
    const body = editUpdate(
      review({ edits: [] }),
      { itemIndex: 0, column: 'level', value: 'Mid' },
      { itemIndex: 0, column: 'reasonBullets', value: ['가'] },
      { itemIndex: 0, column: 'level', value: 'Low' },
    );
    expect(body.edits).toEqual([
      { itemIndex: 0, level: 'Low', reasonBullets: ['가'], fixParagraph: null },
    ]);
  });

  it('markUpdate·confirmUpdate 는 edits 칸을 싣지 않는다(생략 = 서버의 고침 그대로)', () => {
    const marked = markUpdate(review(), { itemIndex: 0, decision: 'adopted' });
    expect(Object.keys(marked)).toEqual(['marks']);
    const confirmed = confirmUpdate(review(), 3);
    expect(Object.keys(confirmed).sort()).toEqual(['marks', 'state']);
  });
});

describe('판정 사유 글 칸', () => {
  it('항목 → 한 줄씩, 목록 표지 없이(표지 앞에 친 글이 섞이지 않게 — sid:MARC-ISSUE-315)', () => {
    expect(reasonsText(['가', '나'])).toBe('가\n나');
    // 칸 글을 그대로 되읽으면 같은 항목(고치지 않으면 저장 없음)
    expect(reasonsFromText(reasonsText(['가', '나 - 다']))).toEqual([
      '가',
      '나 - 다',
    ]);
  });
  it('한 줄 = 한 항목, 앞뒤 공백과 앞 「- 」를 떼고 빈 줄은 버린다(가운데 「-」는 그대로)', () => {
    expect(
      reasonsFromText('- 첫 줄\n\n  -   둘째 줄  \r\n셋째-줄\n   \n-넷째'),
    ).toEqual(['첫 줄', '둘째 줄', '셋째-줄', '-넷째']);
    expect(reasonsFromText('\n  \n')).toEqual([]);
    // 「-」만 남은 줄도 빈 줄
    expect(reasonsFromText('-  \n-\n- 가')).toEqual(['가']);
  });
  it('지금 보이는 항목과 같은 줄은 그대로 — 「- 」로 시작하는 AI 항목도 떼지 않는다(밴드 GP1 검증 R2)', () => {
    const shown = ['- 지어낸 항목', '나'];
    expect(reasonsFromText(reasonsText(shown), shown)).toEqual(shown);
    // 다른 줄을 고쳐도 그 줄은 그대로, 새로 친 줄의 「- 」는 뗀다
    expect(reasonsFromText('- 지어낸 항목\n나 고침\n- 새 줄', shown)).toEqual([
      '- 지어낸 항목',
      '나 고침',
      '새 줄',
    ]);
  });
});
