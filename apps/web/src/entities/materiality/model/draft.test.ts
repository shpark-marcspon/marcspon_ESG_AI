// [평가 시작] 검사(밴드 IRW2 ② — 발주서 §3 시험 3, 부록 A4). 칸마다 · 화면 차례 · 처음 꼴(A6-⑪). 넣은 값은 고치지 않는다.
import { describe, expect, it } from 'vitest';

import {
  blankTopic,
  draftProblems,
  initialDraft,
  isCalendarDay,
  seoulDay,
} from './draft.ts';
import { fakeDraft } from './testing.ts';
import { blankValueChainRow } from './valueChain.ts';

/** 서울 2026-10-28 09:00. */
const NOW = new Date('2026-10-28T00:00:00Z');

describe('initialDraft', () => {
  it('처음 꼴: 칸 빔 · 토픽 카드 하나(서브토픽 줄 하나) · KR · 한국어 · 2024-01-01 · 비금융(최신 이슈 칸 없음 — IRW15 ③)', () => {
    const draft = initialDraft('가상 지역', blankTopic(1, 2));
    expect(draft).toMatchObject({
      company: '',
      valueChain: [],
      geoScope: '가상 지역',
      userLocation: 'KR',
      mainLanguage: '한국어',
      startDate: '2024-01-01',
      sector: 'non_financial',
    });
    expect('latestEventMode' in draft).toBe(false);
    expect(draft.topics).toEqual([
      {
        key: 1,
        topic: '',
        description: '',
        subtopics: [{ key: 2, name: '', description: '' }],
      },
    ]);
  });
});

describe('draftProblems', () => {
  it('다 채우면 없다 · 넣은 값은 그대로', () => {
    const draft = fakeDraft();
    const before = JSON.stringify(draft);
    expect(draftProblems(draft, NOW)).toEqual([]);
    expect(JSON.stringify(draft)).toBe(before);
  });

  it('빈 처음 꼴 — 화면 차례로', () => {
    expect(
      draftProblems(initialDraft('가상 지역', blankTopic(1, 2)), NOW),
    ).toEqual([
      { field: 'company' },
      { field: 'industry', standard: 'SASB', code: 'required' },
      { field: 'topic', index: 0, code: 'required' },
      { field: 'subtopics', index: 0 },
    ]);
  });

  it('기업명·검색 지역은 trim 뒤 빔', () => {
    expect(
      draftProblems(fakeDraft({ company: '  ', geoScope: ' ' }), NOW),
    ).toEqual([{ field: 'company' }, { field: 'geoScope' }]);
  });

  it('SASB 이름 빔 · GICS·KSIC 설명만 있음(A6-⑩)', () => {
    const draft = fakeDraft({
      industries: {
        SASB: { name: '', description: '설명' },
        GICS: { name: ' ', description: '설명만' },
        KSIC: { name: '', description: '' },
      },
    });
    expect(draftProblems(draft, NOW)).toEqual([
      { field: 'industry', standard: 'SASB', code: 'required' },
      { field: 'industry', standard: 'GICS', code: 'description_only' },
    ]);
  });

  it('시작일: 서울 오늘 이상은 「앞선 날」, 빔·달력에 없는 날은 「넣어 주세요」', () => {
    const at = (startDate: string) =>
      draftProblems(fakeDraft({ startDate }), NOW);
    expect(at('2026-10-27')).toEqual([]);
    expect(at('2026-10-28')).toEqual([
      { field: 'startDate', code: 'not_before_today' },
    ]);
    expect(at('2027-01-01')).toEqual([
      { field: 'startDate', code: 'not_before_today' },
    ]);
    for (const text of [
      '',
      '2024-02-30',
      '2024-13-01',
      '24-01-01',
      '2024/01/01',
    ])
      expect(at(text), text).toEqual([
        { field: 'startDate', code: 'required' },
      ]);
    // 서울 자정 앞뒤(UTC 15:00)
    expect(seoulDay(new Date('2026-10-27T14:59:59Z'))).toBe('2026-10-27');
    expect(seoulDay(new Date('2026-10-27T15:00:00Z'))).toBe('2026-10-28');
    expect(isCalendarDay('2024-02-29')).toBe(true);
    expect(isCalendarDay('2023-02-29')).toBe(false);
  });

  it('토픽 0개 · 이름 빔 · 겹침(trim 뒤 같음 — 뒤의 것)', () => {
    expect(draftProblems(fakeDraft({ topics: [] }), NOW)).toEqual([
      { field: 'topics' },
    ]);
    const base = fakeDraft();
    const [a, b] = base.topics as [
      (typeof base.topics)[0],
      (typeof base.topics)[0],
    ];
    expect(
      draftProblems(
        fakeDraft({ topics: [a, { ...b, topic: ' 가상토픽 A ' }] }),
        NOW,
      ),
    ).toEqual([{ field: 'topic', index: 1, code: 'duplicate' }]);
    expect(
      draftProblems(fakeDraft({ topics: [a, { ...b, topic: '' }] }), NOW),
    ).toEqual([{ field: 'topic', index: 1, code: 'required' }]);
  });

  it('서브토픽 0개(두 칸 다 빈 줄은 뺀 뒤) · 설명만 찬 줄은 이름 빔', () => {
    const base = fakeDraft();
    const [a, b] = base.topics as [
      (typeof base.topics)[0],
      (typeof base.topics)[0],
    ];
    const noSubs = {
      ...b,
      subtopics: [{ key: 9, name: ' ', description: '' }],
    };
    expect(draftProblems(fakeDraft({ topics: [a, noSubs] }), NOW)).toEqual([
      { field: 'subtopics', index: 1 },
    ]);
    const nameless = {
      ...a,
      subtopics: [...a.subtopics, { key: 10, name: '', description: '설명만' }],
    };
    expect(draftProblems(fakeDraft({ topics: [nameless, b] }), NOW)).toEqual([
      { field: 'subtopic', index: 0, sub: 2 },
    ]);
  });

  it('밸류체인 빈 행(번호 차례)', () => {
    const row = (stage: '' | 'upstream') => ({
      business_unit: '가',
      business_unit_description: '',
      value_chain_stage: stage,
      stakeholder: '',
      business_activity: '',
    });
    expect(
      draftProblems(
        fakeDraft({ valueChain: [row('upstream'), row(''), row('')] }),
        NOW,
      ),
    ).toEqual([{ field: 'stage', rows: [2, 3] }]);
  });

  it('다섯 칸 다 빈 행뿐이면 밸류체인 문제 0 · 섞이면 빈 행만 빼고 번호는 표 그대로(IRW3 Q2)', () => {
    const blank = blankValueChainRow();
    expect(
      draftProblems(fakeDraft({ valueChain: [blank, blank] }), NOW),
    ).toEqual([]);
    const half = { ...blankValueChainRow(), business_unit: '가' };
    expect(
      draftProblems(fakeDraft({ valueChain: [blank, half] }), NOW),
    ).toEqual([{ field: 'stage', rows: [2] }]);
  });

  it('options 바이트가 262,144 를 넘으면 size(맨 끝)', () => {
    const base = fakeDraft();
    const [a, b] = base.topics as [
      (typeof base.topics)[0],
      (typeof base.topics)[0],
    ];
    const long = { ...a, description: '가'.repeat(90_000) };
    expect(draftProblems(fakeDraft({ topics: [long, b] }), NOW)).toEqual([
      { field: 'size' },
    ]);
  });
});
