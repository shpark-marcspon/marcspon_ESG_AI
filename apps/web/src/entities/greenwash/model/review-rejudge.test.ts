// 밴드 GRJ1 ③: 기준 판단 고르기·보이는 값·[재판단] 켜짐(서버 review.nothing_to_rejudge 와 같은 규칙)·근거 PUT 본문.
// 값은 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import type {
  GreenwashReview,
  Rejudged,
  ResultItem,
  ReviewRejudge,
} from './index.ts';
import {
  aiChangedSince,
  basisOf,
  evidenceUpdate,
  filterReviewRows,
  joinReview,
  nothingToRejudge,
  shownValues,
} from './index.ts';

const ITEM: ResultItem = {
  page: 3,
  parts: ['CEO 메시지'],
  sentence: '지어낸 문장이다.',
  level: 'Mid',
  riskTags: ['지어낸 유형'],
  confirmedInEvidence: ['지어낸 사실 가', '지어낸 사실 나'],
  missingFields: [],
  reasonBullets: ['첫 판단 사유.'],
  fixParagraph: '첫 판단 수정 방향.',
  evidencePages: [5],
  evidenceInternal: '',
  position: null,
  exampleSentence: null,
};

const judged = (over: Partial<Rejudged> = {}): Rejudged => ({
  runId: 9001,
  judgedAt: '2026-11-09T14:32:00+09:00',
  judgedBy: { id: 7, name: '담당자 가' },
  outcome: 'judged',
  level: 'High',
  riskTags: [],
  confirmedInEvidence: ['다시 본 사실'],
  missingFields: [],
  reasonBullets: ['다시 본 사유.'],
  fixParagraph: '다시 본 수정 방향.',
  evidencePages: [],
  added: [{ text: '지어낸 조각', page: 2 }],
  ...over,
});

const line = (
  current: Rejudged | null,
  status: ReviewRejudge['status'] = 'done',
): ReviewRejudge => ({
  itemIndex: 0,
  status,
  count: current === null ? 0 : 1,
  current,
});

describe('기준 판단(basisOf)', () => {
  it('재판단이 없거나 끝난 것이 없으면 첫 판단(더한 조각 0)', () => {
    expect(basisOf(ITEM, null)).toMatchObject({
      level: 'Mid',
      nonrisk: false,
      confirmedInEvidence: ITEM.confirmedInEvidence,
      added: [],
      rejudged: null,
    });
    expect(basisOf(ITEM, line(null, 'running')).level).toBe('Mid');
  });

  it('current 가 있으면 그것 — 도는 중·실패여도 앞 done 이 기준', () => {
    for (const status of ['done', 'running', 'failed'] as const) {
      const basis = basisOf(ITEM, line(judged(), status));
      expect(basis.level).toBe('High');
      expect(basis.confirmedInEvidence).toEqual(['다시 본 사실']);
      expect(basis.rejudged).toEqual({
        runId: 9001,
        judgedAt: '2026-11-09T14:32:00+09:00',
        judgedBy: '담당자 가',
      });
    }
  });

  it('리스크 아님이면 등급 null — 등급 탭 High·Mid·Low 에 걸리지 않고 「전체」에만(덧붙임 4)', () => {
    const basis = basisOf(
      ITEM,
      line(judged({ outcome: 'nonrisk', level: null })),
    );
    expect([basis.level, basis.nonrisk]).toEqual([null, true]);
    const rows = joinReview(
      [ITEM],
      [],
      [],
      [],
      [line(judged({ outcome: 'nonrisk', level: null }))],
    );
    expect(rows[0]!.shownLevel).toBeNull();
    for (const tab of ['High', 'Mid', 'Low'] as const)
      expect(filterReviewRows(rows, { part: null, tab })).toEqual([]);
    expect(filterReviewRows(rows, { part: null, tab: 'all' })).toHaveLength(1);
  });
});

describe('[재판단] 켜짐(nothingToRejudge — 서버 R4)', () => {
  const first = basisOf(ITEM, null);
  const again = basisOf(ITEM, line(judged()));
  it('지운 칩 0·더한 조각이 기준 판단에 보낸 것과 같으면 다시 판단할 것 없음', () => {
    expect(nothingToRejudge([], [], first)).toBe(true);
    expect(
      nothingToRejudge([], [{ text: '지어낸 조각', page: 2 }], again),
    ).toBe(true);
  });
  it('지운 칩이 있거나·더한 조각이 다르면(글·페이지·수·차례) 켜짐', () => {
    expect(nothingToRejudge([0], [], first)).toBe(false);
    expect(
      nothingToRejudge([], [{ text: '지어낸 조각', page: null }], first),
    ).toBe(false);
    expect(
      nothingToRejudge([], [{ text: '지어낸 조각', page: 3 }], again),
    ).toBe(false);
    expect(nothingToRejudge([], [], again)).toBe(false);
    expect(
      nothingToRejudge(
        [],
        [
          { text: '지어낸 조각', page: 2 },
          { text: '둘', page: null },
        ],
        again,
      ),
    ).toBe(false);
  });
});

describe('보이는 값(shownValues — 물음 ③ 한 곳)', () => {
  it('고침 ?? 기준 판단 ?? 첫 판단', () => {
    const basis = basisOf(ITEM, line(judged()));
    expect(shownValues(null, basis)).toEqual({
      level: 'High',
      reasons: ['다시 본 사유.'],
      fix: '다시 본 수정 방향.',
    });
    const by = { id: 7, name: '담당자 가' };
    const at = '2026-11-09T10:00:00+09:00';
    expect(
      shownValues(
        {
          itemIndex: 0,
          level: { value: 'Low', editedAt: at, editedBy: by },
          reasonBullets: null,
          fixParagraph: null,
        },
        basis,
      ).level,
    ).toBe('Low');
  });

  it('「AI 판단이 바뀌었어요」는 고친 때가 기준 판단(재판단)보다 앞일 때만', () => {
    const basis = basisOf(ITEM, line(judged()));
    expect(aiChangedSince('2026-11-09T14:00:00+09:00', basis)).toBe(true);
    expect(aiChangedSince('2026-11-09T15:00:00+09:00', basis)).toBe(false);
    expect(
      aiChangedSince('2026-11-09T14:00:00+09:00', basisOf(ITEM, null)),
    ).toBe(false);
  });
});

describe('근거 PUT 본문(evidenceUpdate)', () => {
  const review: GreenwashReview = {
    schemaVersion: 'greenwash.review@3',
    runId: 1,
    state: 'in_review',
    confirmedAt: null,
    confirmedBy: null,
    marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
    edits: [],
    evidence: [
      {
        itemIndex: 2,
        removed: [1],
        added: [],
        editedAt: '2026-11-09T10:00:00+09:00',
        editedBy: { id: 7, name: '담당자 가' },
      },
    ],
    rejudges: [],
  };
  it('marks 그대로 + 근거 고침 전부 갈아 넣기(오름, 지운 칩 정렬·겹침 없음), edits 는 싣지 않는다', () => {
    expect(
      evidenceUpdate(review, { itemIndex: 0, removed: [1, 0, 1], added: [] }),
    ).toEqual({
      marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
      evidence: [
        { itemIndex: 0, removed: [0, 1], added: [] },
        { itemIndex: 2, removed: [1], added: [] },
      ],
    });
  });
  it('둘 다 비면 그 문장은 빠진다', () => {
    expect(
      evidenceUpdate(review, { itemIndex: 2, removed: [], added: [] }).evidence,
    ).toEqual([]);
  });
});
