// 실행 기록 model(밴드 AD4R ①): KST 「오늘」·기간 → 날짜 범위(조임)·거르기 → 서버 쿼리(값 있는 칸만, 빈 q·NUL 뺌)·모듈 선택지·표시 글.
import { describe, expect, expectTypeOf, it } from 'vitest';

import { RUN_LOG_TEXT } from '../config/text.ts';
import {
  RUN_MODULES,
  RUN_NO_FILTER,
  RUN_REVIEWS,
  RUN_STATUSES,
  aiSettingText,
  costText,
  durationText,
  flowEdition,
  formatRunTime,
  kstToday,
  moduleOptions,
  periodRange,
  rateText,
  runFigures,
  runQuery,
  tokensShort,
  uploaderText,
  withCommas,
} from './index.ts';
import type {
  RunFilter,
  RunLogRow,
  RunQuery,
  RunReview,
  RunStatus,
} from './index.ts';

const t = RUN_LOG_TEXT;
const at = (iso: string) => new Date(iso);
/** 시계 2026-10-15 12:00 KST. */
const query = (filter: Partial<RunFilter>, now = '2026-10-15T03:00:00Z') =>
  runQuery({ ...RUN_NO_FILTER, ...filter }, at(now));

describe('상태 넷·모듈 여섯', () => {
  it('상태: 계약 enum 과 집합이 같다(타입)·표시 차례 대기·처리 중·완료·실패, 문구 표 키 = 전체 + 넷', () => {
    expectTypeOf<(typeof RUN_STATUSES)[number]>().toEqualTypeOf<RunStatus>();
    expect(RUN_STATUSES).toEqual(['queued', 'processing', 'done', 'failed']);
    expect(Object.keys(t.status.options)).toEqual(['all', ...RUN_STATUSES]);
  });

  it('검토: 계약 enum 과 집합이 같다(타입)·차례 미검토·검토 중·확정, 문구 표 키 = 전체 + 셋', () => {
    expectTypeOf<(typeof RUN_REVIEWS)[number]>().toEqualTypeOf<RunReview>();
    expectTypeOf<RunReview>().toEqualTypeOf<NonNullable<RunLogRow['review']>>();
    expect(RUN_REVIEWS).toEqual(['pending', 'in_review', 'confirmed']);
    expect(Object.keys(t.review.options)).toEqual(['all', ...RUN_REVIEWS]);
    expect(RUN_NO_FILTER.review).toBe('all');
  });

  it('모듈: 고정 여섯(서버 id, 셸 메뉴 차례)과 문구 표 키가 같은 차례', () => {
    expect(RUN_MODULES).toEqual([
      'inventory.scope3',
      'greenwash',
      'materiality',
      'dataverify',
      'translation',
      'drafting',
    ]);
    expect(Object.keys(t.modules)).toEqual([...RUN_MODULES]);
    expect(RUN_MODULES.map((id) => t.modules[id])).toEqual([
      '온실가스 Scope 3',
      '그린워싱',
      '중대성평가 IRO',
      '데이터 검증',
      '영문번역',
      '보고서 작성',
    ]);
  });

  it('선택지: 줄이 없으면 고정 여섯, 표에 없는 id 는 처음 본 차례로 끝에(한 번만)', () => {
    expect(moduleOptions([])).toEqual([...RUN_MODULES]);
    expect(
      moduleOptions([
        'inventory.scope12',
        'greenwash',
        'x.y',
        'inventory.scope12',
      ]),
    ).toEqual([...RUN_MODULES, 'inventory.scope12', 'x.y']);
  });
});

describe('KST 오늘', () => {
  it.each([
    ['2026-10-18T14:59:59Z', '2026-10-18'],
    ['2026-10-18T15:00:00Z', '2026-10-19'],
    ['2026-10-19T00:00:00+09:00', '2026-10-19'],
  ])('%s → %s', (now, today) => {
    expect(kstToday(at(now))).toBe(today);
  });
});

describe('기간 → 날짜 범위(둘 다 포함)', () => {
  it.each([
    ['month', '2026-10-15', '2026-10-01', '2026-10-15'],
    ['month', '2026-10-01', '2026-10-01', '2026-10-01'],
    ['lastMonth', '2026-10-15', '2026-09-01', '2026-09-30'],
    ['lastMonth', '2027-01-05', '2026-12-01', '2026-12-31'], // 해를 넘음
    ['lastMonth', '2028-03-10', '2028-02-01', '2028-02-29'], // 윤년 2월
    ['lastMonth', '2026-03-31', '2026-02-01', '2026-02-28'],
  ] as const)('%s · 오늘 %s → %s ~ %s', (period, today, from, to) => {
    expect(periodRange(period, today)).toEqual({ dateFrom: from, dateTo: to });
  });

  it('전체 → null', () => {
    expect(periodRange('all', '2026-10-15')).toBeNull();
  });

  it('조임: 시계가 범위 밖이어도 두 값이 [2000-01-01, 2999-12-31] 안', () => {
    for (const period of ['month', 'lastMonth'] as const) {
      const early = query({ period }, '1999-12-31T03:00:00Z');
      expect(early.dateFrom! >= '2000-01-01', period).toBe(true);
      expect(early.dateTo! >= '2000-01-01', period).toBe(true);
      const late = query({ period }, '3000-01-02T03:00:00Z');
      expect(late.dateFrom! <= '2999-12-31', period).toBe(true);
      expect(late.dateTo! <= '2999-12-31', period).toBe(true);
    }
    expect(query({}, '1999-12-31T03:00:00Z')).toEqual({
      dateFrom: '2000-01-01',
      dateTo: '2000-01-01',
    });
    // 「오늘」이 2000-01-01 로 조여져 지난달(1999-12)도 2000-01-01 로.
    expect(query({ period: 'lastMonth' }, '1999-12-31T03:00:00Z')).toEqual({
      dateFrom: '2000-01-01',
      dateTo: '2000-01-01',
    });
    // 「오늘」이 먼저 2999-12-31 로 조여져 그달 1일부터.
    expect(query({}, '3000-01-02T03:00:00Z')).toEqual({
      dateFrom: '2999-12-01',
      dateTo: '2999-12-31',
    });
  });
});

describe('거르기 → 서버 쿼리', () => {
  it('처음 거르기(이번 달) → 키가 정확히 dateFrom·dateTo, dateTo 는 오늘(다음 날 아님)', () => {
    expect(query({})).toEqual({ dateFrom: '2026-10-01', dateTo: '2026-10-15' });
  });

  it('KST 로 센다: UTC 로는 아직 9월 30일이어도 KST 10월 1일이면 이번 달은 10월', () => {
    expect(query({}, '2026-09-30T15:00:00Z')).toEqual({
      dateFrom: '2026-10-01',
      dateTo: '2026-10-01',
    });
    expect(query({}, '2026-09-30T14:59:59Z')).toEqual({
      dateFrom: '2026-09-01',
      dateTo: '2026-09-30',
    });
  });

  it('지난달·전체', () => {
    expect(query({ period: 'lastMonth' })).toEqual({
      dateFrom: '2026-09-01',
      dateTo: '2026-09-30',
    });
    expect(query({ period: 'all' })).toEqual({});
  });

  it('빈·공백 q 는 키째 빼고, 앞뒤 빈칸은 걷는다', () => {
    expect('q' in query({ query: '' })).toBe(false);
    expect('q' in query({ query: '   ' })).toBe(false);
    expect('q' in query({ query: '\t\n ' })).toBe(false);
    expect(query({ query: ' 보고서 ' }).q).toBe('보고서');
  });

  it('NUL 은 지운다(NUL 만이면 q 없음 — MARC-ISSUE-209)', () => {
    expect(query({ query: 'a\u0000b' }).q).toBe('ab');
    expect('q' in query({ query: '\u0000' })).toBe(false);
    expect('q' in query({ query: ' \u0000 ' })).toBe(false);
  });

  it('q 는 코드 포인트 150자에서 자른다(서로게이트 쌍을 가르지 않는다)', () => {
    expect([...query({ query: '가'.repeat(151) }).q!]).toHaveLength(150);
    const sent = query({ query: '😀'.repeat(151) }).q!;
    expect(sent).toBe('😀'.repeat(150));
  });

  it("모듈·상태 'all' → 키 없음, 고르면 그 값. companyId 는 늘 없음", () => {
    expect(query({ module: 'all', status: 'all', period: 'all' })).toEqual({});
    expect(
      query({ module: 'dataverify', status: 'queued', period: 'all' }),
    ).toEqual({ module: 'dataverify', status: 'queued' });
    for (const filter of [
      {},
      { module: 'greenwash' },
      { period: 'all' as const },
    ])
      expect('companyId' in query(filter)).toBe(false);
    // 검토: 'all' → 키 없음, 고르면 그 값(서버가 거른다)
    expect(query({ review: 'all', period: 'all' })).toEqual({});
    expect(query({ review: 'in_review', period: 'all' })).toEqual({
      review: 'in_review',
    });
    expect(
      query({ review: 'confirmed', status: 'done', period: 'all' }),
    ).toEqual({ status: 'done', review: 'confirmed' });
    // 쿼리 타입에 쪽·회사 칸이 없다
    expectTypeOf<keyof RunQuery>().toEqualTypeOf<
      'module' | 'status' | 'dateFrom' | 'dateTo' | 'q' | 'review'
    >();
  });
});

describe('표시 글', () => {
  it('흐름: flowId 의 @ 뒤 판 글자, @ 가 없으면 그대로', () => {
    expect(flowEdition('greenwash.colab@E0')).toBe('E0');
    expect(flowEdition('a@b@C1')).toBe('C1');
    expect(flowEdition('plain')).toBe('plain');
  });

  it('처리 시간·쉼표·시각', () => {
    expect(durationText(485)).toBe('8분 05초');
    expect(durationText(45)).toBe('0분 45초');
    expect(durationText(null)).toBeNull();
    expect(withCommas(108100)).toBe('108,100');
    expect(withCommas(0)).toBe('0');
    expect(formatRunTime('2026-10-15T15:10:00+09:00')).toBe('2026-10-15 15:10');
  });

  it.each([
    [0, '$0.00'],
    [0.004, '<$0.01'],
    [0.0049, '<$0.01'],
    [0.005, '$0.01'],
    [0.58, '$0.58'],
    [12.345, '$12.35'],
  ])('비용 %s → %s', (usd, text) => {
    expect(costText(usd, t.costBelow)).toBe(text);
  });

  it.each([
    [0, '0'],
    [999_999, '999,999'],
    [1_000_000, '1.0M'],
    [3_150_000, '3.1M'],
    [3_199_999, '3.1M'], // 버림
  ])('지표 토큰 %s → %s', (tokens, text) => {
    expect(tokensShort(tokens)).toBe(text);
  });

  it.each([
    [null, null],
    [0, '0.0'],
    [0.048, '4.8'],
    [0.0485, '4.9'], // 반올림
    [1, '100.0'],
  ])('실패율 %s → %s', (rate, text) => {
    expect(rateText(rate)).toBe(text);
  });

  it('줄 숫자 칸: 「대기」는 처리 시간·토큰·비용 모두 「–」, 그 밖은 값(처리 중 0 토큰은 「0」·「$0.00」)', () => {
    const row = { durationSec: null, tokens: 0, costUsd: 0 };
    expect(runFigures({ ...row, status: 'queued' }, t)).toEqual({
      duration: '–',
      tokens: '–',
      cost: '–',
    });
    expect(runFigures({ ...row, status: 'processing' }, t)).toEqual({
      duration: '–',
      tokens: '0',
      cost: '$0.00',
    });
    expect(
      runFigures(
        { status: 'done', durationSec: 485, tokens: 108_100, costUsd: 0.004 },
        t,
      ),
    ).toEqual({ duration: '8분 05초', tokens: '108,100', cost: '<$0.01' });
    expect(
      runFigures(
        { status: 'failed', durationSec: 30, tokens: 1_234, costUsd: 0.58 },
        t,
      ),
    ).toEqual({ duration: '0분 30초', tokens: '1,234', cost: '$0.58' });
  });

  it('올린 사람: 이름 → 아이디 → 「알 수 없는 사람」(missing)', () => {
    const unknown = t.unknownUploader;
    expect(
      uploaderText(
        { createdByName: '담당자 가', createdByUsername: 'user11' },
        unknown,
      ),
    ).toEqual({ text: '담당자 가', missing: false });
    expect(
      uploaderText(
        { createdByName: null, createdByUsername: 'user11' },
        unknown,
      ),
    ).toEqual({ text: 'user11', missing: false });
    expect(
      uploaderText({ createdByName: null, createdByUsername: null }, unknown),
    ).toEqual({ text: '알 수 없는 사람', missing: true });
  });

  it('AI 설정: 없음 → 「–」(missing), 기본 판(id null) → 「기본 설정」, 그 밖 → 판 이름', () => {
    expect(aiSettingText(null, t)).toEqual({ text: '–', missing: true });
    expect(aiSettingText({ id: null, name: 'colab-2026-01-15-v1' }, t)).toEqual(
      { text: '기본 설정', missing: false },
    );
    expect(aiSettingText({ id: 3, name: 'v3' }, t)).toEqual({
      text: 'v3',
      missing: false,
    });
  });
});
