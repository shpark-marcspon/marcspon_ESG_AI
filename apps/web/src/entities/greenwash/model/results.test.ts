// 결과·검토 domain(밴드 FW2 ① §3): 요약 셈, 「추가」, 검토 잇기·거르기, PUT 본문, 확정 본문, 제외 사유 글, 서버 단계 맞춤,
// 바깥 상자, 목록 줄, 시각 꾸미기. 표 꼴. 심은 파손 (나)는 confirmUpdate 의 시험이 잡는다((가) 의 riskTagCounts 는 밴드 GW2R ① 에서 걷었다).
import { describe, expect, it } from 'vitest';

import {
  formatKst,
  formatKstMonthDay,
  toKstIso,
} from '../../../shared/lib/time.ts';
import { buildCheckRows, filterCheckRows, runOrdinal } from './checkRows.ts';
import type {
  CheckRowsSource,
  ListedDocument,
  ListedRun,
} from './checkRows.ts';
import type { RunProgress } from './progress.ts';
import type { GreenwashReview, Level, ResultItem } from './result.ts';
import {
  confirmUpdate,
  excludeReasonText,
  filterReviewRows,
  joinReview,
  markUpdate,
  reviewTally,
} from './review.ts';
import { progressFromServer } from './serverRun.ts';
import type { ServerStep } from './serverRun.ts';

const review = (
  state: GreenwashReview['state'],
  marks: GreenwashReview['marks'] = [],
): GreenwashReview => ({
  schemaVersion: 'greenwash.review@3',
  evidence: [],
  rejudges: [],
  runId: 7,
  state,
  confirmedAt: null,
  confirmedBy: null,
  marks,
  edits: [],
});

/** 결과 문장 하나(검토 잇기·거르기에 쓰는 칸만 뜻이 있다). */
const item = (
  page: number,
  parts: string[],
  level: Level,
  tags: string[] = [],
): ResultItem => ({
  page,
  parts,
  sentence: `문장 ${page}`,
  level,
  riskTags: level === 'Low' ? ['선언적 문장'] : tags,
  confirmedInEvidence: [],
  missingFields: [],
  reasonBullets: [],
  fixParagraph: '고칠 방향',
  evidencePages: [],
  evidenceInternal: '',
  position: null,
  exampleSentence: null,
});

describe('검토 잇기·셈·거르기', () => {
  const items = [
    item(2, ['CEO'], 'High', ['미래 약속', '목표 근거 부족']),
    item(4, ['회사', '기후'], 'Mid', ['미래 약속']),
    item(5, ['기후'], 'Low'),
  ];
  const marks = [
    { itemIndex: 0, decision: 'adopted' as const, excludeReason: null },
    { itemIndex: 2, decision: 'excluded' as const, excludeReason: '기타: x' },
    { itemIndex: 9, decision: 'adopted' as const, excludeReason: null },
  ];

  it('(실행, itemIndex) 로 잇는다. items 밖 표시는 버린다', () => {
    const rows = joinReview(items, marks);
    expect(rows.map((r) => [r.index, r.mark?.decision ?? null])).toEqual([
      [0, 'adopted'],
      [1, null],
      [2, 'excluded'],
    ]);
    expect(reviewTally(rows)).toEqual({
      total: 3,
      reviewed: 2,
      adopted: 1,
      excluded: 1,
      pending: 1,
      edited: 0,
    });
  });

  it('거르기: 파트 × 탭', () => {
    const rows = joinReview(items, marks);
    const pick = (
      part: string | null,
      tab: Parameters<typeof filterReviewRows>[1]['tab'],
    ) => filterReviewRows(rows, { part, tab }).map((r) => r.index);
    expect(pick(null, 'all')).toEqual([0, 1, 2]);
    expect(pick(null, 'High')).toEqual([0]);
    expect(pick(null, 'pending')).toEqual([1]);
    expect(pick(null, 'excluded')).toEqual([2]);
    expect(pick('기후', 'all')).toEqual([1, 2]);
    expect(pick('기후', 'Low')).toEqual([2]);
    expect(pick('CEO', 'pending')).toEqual([]);
  });
});

describe('PUT 본문 [B3]', () => {
  it('첫 표시(pending)여도 state 를 싣지 않는다 — pending → in_review 는 서버가 옮긴다(결함 D1)', () => {
    const body = markUpdate(review('pending'), {
      itemIndex: 1,
      decision: 'adopted',
    });
    expect(body).toEqual({
      marks: [{ itemIndex: 1, decision: 'adopted', excludeReason: null }],
    });
    expect('state' in body).toBe(false);
  });

  it('두 번째 표시 뒤의 본문에 첫 표시가 남는다(marks 전부, 오름차순). in_review 면 state 를 보내지 않는다', () => {
    const first = review('in_review', [
      { itemIndex: 3, decision: 'adopted', excludeReason: null },
    ]);
    const body = markUpdate(first, {
      itemIndex: 1,
      decision: 'excluded',
      reason: '등급이 맞지 않음',
    });
    expect(body).toEqual({
      marks: [
        {
          itemIndex: 1,
          decision: 'excluded',
          excludeReason: '등급이 맞지 않음',
        },
        { itemIndex: 3, decision: 'adopted', excludeReason: null },
      ],
    });
    expect('state' in body).toBe(false);
  });

  it('같은 문장을 다시 표시하면 갈아 끼운다(겹침 없음), 채택이면 사유는 null', () => {
    const marked = review('in_review', [
      { itemIndex: 0, decision: 'excluded', excludeReason: '기타: x' },
    ]);
    expect(
      markUpdate(marked, { itemIndex: 0, decision: 'adopted' }).marks,
    ).toEqual([{ itemIndex: 0, decision: 'adopted', excludeReason: null }]);
  });
});

describe('확정 본문', () => {
  it('미검토를 모두 adopted 로 채운 marks 전부 + state: confirmed. 제외는 그대로', () => {
    const current = review('in_review', [
      { itemIndex: 1, decision: 'excluded', excludeReason: '기타: x' },
    ]);
    expect(confirmUpdate(current, 3)).toEqual({
      state: 'confirmed',
      marks: [
        { itemIndex: 0, decision: 'adopted', excludeReason: null },
        { itemIndex: 1, decision: 'excluded', excludeReason: '기타: x' },
        { itemIndex: 2, decision: 'adopted', excludeReason: null },
      ],
    });
  });

  it('pending 에서 곧바로 확정해도 전부 채택', () => {
    const body = confirmUpdate(review('pending'), 2);
    expect(body.marks.map((m) => m.decision)).toEqual(['adopted', 'adopted']);
    expect(confirmUpdate(review('pending'), 0)).toEqual({
      state: 'confirmed',
      marks: [],
    });
  });
});

describe('제외 사유 글 [R6]', () => {
  it.each([
    ['환경 주장 문장이 아님', '', false, '환경 주장 문장이 아님'],
    [
      '환경 주장 문장이 아님',
      '  부록에 있어요 ',
      false,
      '환경 주장 문장이 아님: 부록에 있어요',
    ],
    ['기타', '직접 적은 까닭', true, '기타: 직접 적은 까닭'],
  ])('%s + 「%s」 → 「%s」', (label, note, requiresNote, text) => {
    expect(excludeReasonText({ label, note, requiresNote })).toEqual({
      ok: true,
      text,
    });
  });

  it('기타 + 빈 설명(공백만 포함)은 오류', () => {
    for (const note of ['', '   '])
      expect(
        excludeReasonText({ label: '기타', note, requiresNote: true }),
      ).toEqual({ ok: false, code: 'note_required' });
  });
});

describe('서버 단계 맞춤(sid:MARC-ISSUE-99 3)', () => {
  const names = ['extract', 'index', 'judge', 'wordcount', 'locate', 'report'];
  /** at 앞 단계는 done, at 은 status, 뒤는 pending. */
  const steps = (
    at: number,
    status: ServerStep['status'],
    judge: [number, number] | null = null,
  ): ServerStep[] =>
    names.map((step, i) => ({
      step,
      status:
        i < at ? 'done'
        : i === at ? status
        : 'pending',
      done: step === 'judge' && judge ? judge[0] : null,
      total: step === 'judge' && judge ? judge[1] : null,
    }));

  it.each([
    // [단계 차례, 서버 단계 상태, 실행 상태, 화면 단계, 화면 상태]
    [0, 'running', 'processing', 'extract', 'running'],
    [1, 'running', 'processing', 'judge', 'running'],
    [2, 'running', 'processing', 'judge', 'running'],
    [3, 'running', 'processing', 'summarize', 'running'],
    [4, 'running', 'processing', 'summarize', 'running'],
    [5, 'running', 'processing', 'summarize', 'running'],
    [0, 'failed', 'failed', 'extract', 'failed'],
    [1, 'failed', 'failed', 'judge', 'failed'],
    [2, 'failed', 'failed', 'judge', 'failed'],
    [3, 'failed', 'failed', 'summarize', 'failed'],
    [4, 'failed', 'failed', 'summarize', 'failed'],
    [5, 'failed', 'failed', 'summarize', 'failed'],
  ] as const)(
    '%i번 단계 %s · 실행 %s → %s / %s',
    (at, stepStatus, runStatus, stage, state) => {
      const progress = progressFromServer(runStatus, steps(at, stepStatus), 10);
      expect(progress.stage).toBe(stage);
      expect(progress.state).toBe(state);
    },
  );

  it('queued: 모두 pending 이면 추출 단계, 판정 0 / 점검할 쪽', () => {
    expect(progressFromServer('queued', steps(0, 'pending'), 12)).toEqual({
      state: 'running',
      stage: 'extract',
      judge: { done: 0, total: 12 },
    });
  });

  it('판정 쪽 진행은 judge 단계의 done/total, 판정을 지나면 done = total, 끝나면 정리·done', () => {
    expect(
      progressFromServer('processing', steps(2, 'running', [7, 44]), 44).judge,
    ).toEqual({ done: 7, total: 44 });
    expect(
      progressFromServer('processing', steps(3, 'running', [44, 44]), 44).judge,
    ).toEqual({ done: 44, total: 44 });
    expect(progressFromServer('done', steps(6, 'done', [44, 44]), 44)).toEqual({
      state: 'done',
      stage: 'summarize',
      judge: { done: 44, total: 44 },
    });
    // 판정 중 실패면 멈춘 쪽 진행을 남긴다
    expect(
      progressFromServer('failed', steps(2, 'failed', [28, 44]), 44),
    ).toEqual({
      state: 'failed',
      stage: 'judge',
      judge: { done: 28, total: 44 },
    });
  });

  it('모르는 단계는 건너뛴다', () => {
    const withUnknown: ServerStep[] = [
      { step: 'warmup', status: 'running', done: null, total: null },
      ...steps(0, 'running'),
    ];
    expect(progressFromServer('processing', withUnknown, 3).stage).toBe(
      'extract',
    );
  });
});

describe('목록 줄 [R11]', () => {
  const me = { userId: 'u1', name: '나' };
  const other = { userId: 'u2', name: '남' };
  const doc = (
    documentId: string,
    previousDocumentId: string | null = null,
    extra: Partial<ListedDocument> = {},
  ): ListedDocument => ({
    documentId,
    fileName: `${documentId}.pdf`,
    reportYear: 2026,
    previousDocumentId,
    pageCount: 10,
    uploadedAt: '2026-10-01T09:00:00+09:00',
    uploadedBy: me,
    ...extra,
  });
  const done = {
    state: 'done' as const,
    stage: 'summarize' as const,
    judge: { done: 4, total: 4 },
  };
  const run = (
    runId: string,
    documentId: string,
    createdAt: string,
    extra: Partial<ListedRun> = {},
  ): ListedRun => ({
    runId,
    documentId,
    createdAt,
    progress: done,
    levelCounts: { High: 1, Mid: 1, Low: 0 },
    review: {
      state: 'pending',
      reviewed: 0,
      total: 2,
      confirmedAt: null,
      confirmedBy: null,
    },
    ...extra,
  });
  const source: CheckRowsSource = {
    currentUserId: 'u1',
    companyName: '고객사',
    documents: [
      doc('v1'),
      doc('v2', 'v1'),
      doc('v3', 'v2', { reportYear: 2025, uploadedBy: other }),
      doc('a'),
      doc('b', null, { fileName: '기후공시.pdf' }),
      doc('c'),
      doc('d'),
    ],
    runs: [
      run('r1', 'v3', '2026-10-05T09:00:00+09:00', {
        review: {
          state: 'in_review',
          reviewed: 1,
          total: 2,
          confirmedAt: null,
          confirmedBy: null,
        },
      }),
      run('r0', 'v3', '2026-10-04T09:00:00+09:00'),
      run('r2', 'a', '2026-10-06T09:00:00+09:00', {
        progress: {
          state: 'running',
          stage: 'judge',
          judge: { done: 2, total: 4 },
        },
        levelCounts: null,
        review: null,
      }),
      run('r3', 'b', '2026-10-03T09:00:00+09:00', {
        progress: {
          state: 'failed',
          stage: 'judge',
          judge: { done: 1, total: 4 },
        },
        levelCounts: null,
        review: null,
      }),
      run('r4', 'c', '2026-10-02T09:00:00+09:00', {
        review: {
          state: 'confirmed',
          reviewed: 2,
          total: 2,
          confirmedAt: '2026-10-02T15:00:00+09:00',
          confirmedBy: '남',
        },
      }),
      run('r5', 'd', '2026-10-01T10:00:00+09:00'),
    ],
  };

  it('판 사슬의 마지막 문서만 한 줄, 앞 판 수 = 사슬 길이 − 1, 늦은 차례', () => {
    const rows = buildCheckRows(source);
    expect(rows.map((r) => r.doc.documentId)).toEqual([
      'a',
      'v3',
      'b',
      'c',
      'd',
    ]);
    const v3 = rows.find((r) => r.doc.documentId === 'v3')!;
    expect([v3.version, v3.previousVersionCount]).toEqual([3, 2]);
    expect(
      rows.find((r) => r.doc.documentId === 'a')!.previousVersionCount,
    ).toBe(0);
  });

  it('상태와 다음 할 일, AI 점검 중의 진행률, 회차', () => {
    const rows = buildCheckRows(source);
    const by = (id: string) => rows.find((r) => r.doc.documentId === id)!;
    expect(
      ['a', 'b', 'd', 'v3', 'c'].map((id) => [by(id).status, by(id).next]),
    ).toEqual([
      ['running', 'view_progress'],
      ['failed', 'rerun'],
      ['pending', 'review'],
      ['in_review', 'continue_review'],
      ['confirmed', 'view_result'],
    ]);
    expect(by('a').percent).toBe(50);
    expect(by('v3').percent).toBeNull();
    // v3 의 마지막 실행은 r1(늦게 만든 것), 2회차
    expect(by('v3').lastRun?.runId).toBe('r1');
    expect(by('v3').runOrdinal).toBe(2);
    expect(runOrdinal(source.runs, 'r0')).toBe(1);
    expect(runOrdinal(source.runs, 'r1')).toBe(2);
    expect(runOrdinal(source.runs, 'zz')).toBe(0);
  });

  it('실행이 없는 문서는 상태·다음 할 일이 null, 앞 판 고리는 한 바퀴에서 멈춘다', () => {
    const rows = buildCheckRows({
      ...source,
      documents: [doc('x'), doc('p', 'q'), doc('q', 'p')],
      runs: [],
    });
    expect(rows.find((r) => r.doc.documentId === 'x')).toMatchObject({
      status: null,
      next: null,
      runOrdinal: 0,
    });
    // p ↔ q 고리: 둘 다 다른 것의 앞 판이라 줄이 없다(무한 반복 없이 끝난다)
    expect(rows.map((r) => r.doc.documentId)).toEqual(['x']);
  });

  it('거르기: 검색 · 보고연도 · 상태 탭 여섯 · 내가 올린 것만', () => {
    const rows = buildCheckRows(source);
    const pick = (filter: Partial<Parameters<typeof filterCheckRows>[1]>) =>
      filterCheckRows(
        rows,
        { query: '', reportYear: null, tab: 'all', mineOnly: false, ...filter },
        source.currentUserId,
      ).map((r) => r.doc.documentId);
    expect(pick({})).toHaveLength(5);
    expect(pick({ query: '  기후 ' })).toEqual(['b']);
    expect(pick({ query: 'V3' })).toEqual(['v3']);
    expect(pick({ reportYear: 2025 })).toEqual(['v3']);
    expect(pick({ tab: 'pending' })).toEqual(['d']);
    expect(pick({ tab: 'in_review' })).toEqual(['v3']);
    expect(pick({ tab: 'confirmed' })).toEqual(['c']);
    // 옛 한 탭 「점검 중·멈춤」을 둘로 나눔(시안 댓글 — sid:MARC-ENT-603): AI 점검 중 = a 하나, 멈춤 = b 하나
    expect(pick({ tab: 'running' })).toEqual(['a']);
    expect(pick({ tab: 'failed' })).toEqual(['b']);
    expect(pick({ mineOnly: true })).toEqual(['a', 'b', 'c', 'd']);
  });
});

describe('시각(한국 시각)', () => {
  it('ISO → 「YYYY-MM-DD HH:mm」, 오프셋이 달라도 같은 순간', () => {
    expect(formatKst('2026-10-15T14:20:00+09:00')).toBe('2026-10-15 14:20');
    expect(formatKst('2026-10-15T05:20:00Z')).toBe('2026-10-15 14:20');
    expect(formatKst('2026-10-15T23:30:00Z')).toBe('2026-10-16 08:30');
    expect(formatKstMonthDay('2026-10-03T15:30:00+09:00')).toBe('10-03');
    expect(formatKst('아님')).toBe('아님');
  });

  it('Date → +09:00 ISO', () => {
    expect(toKstIso(new Date(Date.UTC(2026, 9, 15, 5, 20, 7)))).toBe(
      '2026-10-15T14:20:07+09:00',
    );
  });
});

describe('목록 차례·회차는 시각을 순간끼리 견준다(오프셋이 달라도)', () => {
  const doc = (documentId: string, uploadedAt: string): ListedDocument => ({
    documentId,
    fileName: `${documentId}.pdf`,
    reportYear: null,
    previousDocumentId: null,
    pageCount: 1,
    uploadedAt,
    uploadedBy: { userId: 'u', name: '가' },
  });
  const listed = (
    runId: string,
    documentId: string,
    createdAt: string,
  ): ListedRun => ({
    runId,
    documentId,
    createdAt,
    progress: { state: 'done' } as RunProgress,
    levelCounts: null,
    review: null,
  });
  // x 의 실행은 UTC 01:00(= KST 10:00), y 의 실행은 KST 09:30. 글자로 견주면 「2026-10-01T09:30+09:00」 이 「…T01:00Z」 보다 늦다.
  const source: CheckRowsSource = {
    currentUserId: 'u',
    companyName: '가',
    documents: [
      doc('x', '2026-09-30T00:00:00Z'),
      doc('y', '2026-09-30T00:00:00Z'),
    ],
    runs: [
      listed('x1', 'x', '2026-10-01T01:00:00Z'),
      listed('y1', 'y', '2026-10-01T09:30:00+09:00'),
      listed('x0', 'x', '2026-10-01T09:50:00+09:00'),
    ],
  };

  it('늦은 마지막 실행이 위: x(KST 10:00) → y(KST 09:30)', () => {
    expect(buildCheckRows(source).map((row) => row.doc.documentId)).toEqual([
      'x',
      'y',
    ]);
  });

  it('회차: x0(KST 09:50)가 1회차, x1(KST 10:00)이 2회차', () => {
    expect(runOrdinal(source.runs, 'x0')).toBe(1);
    expect(runOrdinal(source.runs, 'x1')).toBe(2);
  });
});
