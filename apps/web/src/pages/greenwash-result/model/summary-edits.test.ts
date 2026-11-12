// 밴드 G1b-3 ③: GW-04 요약의 효력 등급(고친 등급 ?? AI — 디자인 80 회신 Q8). 등급 합과 파트 × 등급 둘 다, 결과(items)는 그대로,
// countsAgree 는 서버 counts(AI 셈)와 견주므로 고침과 상관없다. 값은 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import type {
  Level,
  Rejudged,
  ResultItem,
  ReviewEdit,
  ReviewRejudge,
  ScanResult,
} from '../../../entities/greenwash/model/index.ts';
import { countsAgree, levelCountsOf, partSummaries } from './summary.ts';

const item = (page: number, parts: string[], level: Level): ResultItem => ({
  page,
  parts,
  sentence: `지어낸 문장 ${page}`,
  level,
  riskTags: [],
  confirmedInEvidence: [],
  missingFields: [],
  reasonBullets: [],
  fixParagraph: '고칠 방향',
  evidencePages: [],
  evidenceInternal: '',
  position: null,
  exampleSentence: null,
});

const by = { id: 1, name: '가상 고친이' };
const at = '2026-10-22T09:00:00+09:00';
const level = (itemIndex: number, value: Level): ReviewEdit => ({
  itemIndex,
  level: { value, editedAt: at, editedBy: by },
  reasonBullets: null,
  fixParagraph: null,
});
/** 등급은 안 고치고 수정 방향만 고친 문장 — 셈에 들지 않는다. */
const fixOnly = (itemIndex: number): ReviewEdit => ({
  itemIndex,
  level: null,
  reasonBullets: null,
  fixParagraph: { value: '고친 방향', editedAt: at, editedBy: by },
});

const items = [
  item(2, ['가'], 'High'),
  item(4, ['가', '나'], 'High'), // 두 파트에 든 문장
  item(5, ['나'], 'Mid'),
  item(6, ['나'], 'Low'),
];
const result = {
  parts: [
    { name: '가', pages: [2, 4] },
    { name: '나', pages: [4, 5, 6] },
    { name: '다', pages: [9] },
  ],
  items,
  counts: {
    total: 4,
    byLevel: { High: 2, Mid: 1, Low: 1 },
    byPart: {},
  },
} as unknown as ScanResult;

describe('GW-04 효력 등급', () => {
  it('등급 합: 고친 등급으로(High → Low 하나면 High −1·Low +1), 등급을 안 고친 고침은 셈 그대로', () => {
    expect(levelCountsOf(items)).toEqual({ High: 2, Mid: 1, Low: 1 });
    expect(levelCountsOf(items, [level(1, 'Low'), fixOnly(2)])).toEqual({
      High: 1,
      Mid: 1,
      Low: 2,
    });
  });

  it('파트 × 등급도 고친 등급으로 — 두 파트에 든 문장은 두 파트 다 옮기고, 빈 파트는 0', () => {
    const parts = partSummaries(result, [level(1, 'Low'), level(2, 'High')]);
    expect(parts.map((p) => [p.name, p.counts, p.total])).toEqual([
      ['가', { High: 1, Mid: 0, Low: 1 }, 2],
      ['나', { High: 1, Mid: 0, Low: 2 }, 3],
      ['다', { High: 0, Mid: 0, Low: 0 }, 0],
    ]);
    // edits 없으면 AI 셈(지금 그대로)
    expect(partSummaries(result).map((p) => p.counts)).toEqual([
      { High: 2, Mid: 0, Low: 0 },
      { High: 1, Mid: 1, Low: 1 },
      { High: 0, Mid: 0, Low: 0 },
    ]);
  });

  it('결과 items 는 그대로(사본에서 센다), countsAgree 는 고침과 상관없이 AI 셈과 견준다', () => {
    const before = structuredClone(items);
    levelCountsOf(items, [level(0, 'Low')]);
    partSummaries(result, [level(0, 'Low')]);
    expect(items).toEqual(before);
    expect(countsAgree(result)).toBe(true);
  });
});

// 밴드 GRJ1 ③ 검증 3 B1: 재판단 기준 판단도 효력 등급에 든다(고친 등급 ?? 기준 판단 ?? 첫 판단, 리스크 아님은 세 등급 밖) —
// 서버 목록 levelCounts·확정 엑셀과 같은 셈.
describe('GW-04 효력 등급 — 재판단 기준 판단(GRJ1)', () => {
  const judged = (
    itemIndex: number,
    over: Partial<Rejudged>,
    status: ReviewRejudge['status'] = 'done',
  ): ReviewRejudge => ({
    itemIndex,
    status,
    count: 1,
    current: {
      runId: 9001 + itemIndex,
      judgedAt: '2026-11-09T14:32:00+09:00',
      judgedBy: by,
      outcome: 'judged',
      level: 'High',
      riskTags: [],
      confirmedInEvidence: [],
      missingFields: [],
      reasonBullets: ['다시 본 사유.'],
      fixParagraph: '다시 본 방향.',
      evidencePages: [],
      added: [],
      ...over,
    },
  });
  // 문장 2(Mid) → 재판단 High · 문장 3(Low) → 리스크 아님 · 문장 0(High) → 재판단 Mid 이지만 사람이 Low 로 고침
  const rejudges = [
    judged(0, { level: 'Mid' }),
    judged(2, { level: 'High' }),
    judged(3, { outcome: 'nonrisk', level: null }),
  ];

  it('등급 합: 재판단 Mid→High 를 옮기고 리스크 아님은 빼며, 고친 등급이 기준 판단보다 앞선다', () => {
    expect(levelCountsOf(items, [], rejudges)).toEqual({
      High: 2,
      Mid: 1,
      Low: 0,
    });
    expect(levelCountsOf(items, [level(0, 'Low')], rejudges)).toEqual({
      High: 2,
      Mid: 0,
      Low: 1,
    });
    // 도는 중인 줄은 current 가 앞 done — 줄이 있어도 current 가 없으면 첫 판단
    expect(
      levelCountsOf(items, [], [{ ...judged(2, {}), current: null }]),
    ).toEqual({ High: 2, Mid: 1, Low: 1 });
  });

  it('파트 × 등급도 같은 셈 — 리스크 아님은 그 파트에서 빠진다', () => {
    const parts = partSummaries(result, [level(0, 'Low')], rejudges);
    expect(parts.map((part) => [part.name, part.counts, part.total])).toEqual([
      ['가', { High: 1, Mid: 0, Low: 1 }, 2],
      ['나', { High: 2, Mid: 0, Low: 0 }, 2],
      ['다', { High: 0, Mid: 0, Low: 0 }, 0],
    ]);
  });
});
