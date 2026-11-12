// 실행 기록의 꼴과 순수 함수(밴드 AD2 ③, 실서버 AD4R ①). React·DOM·통신을 모른다.
// 계약 타입(RunLogOut·RunMetricsOut·GET /run-logs 의 쿼리)은 shared/api 가 다시 내보낸 것을 타입으로만 가져온다.
//   - runQuery: 화면의 거르기 → 서버 쿼리. 값이 있는 칸만 담는다(빈·공백 q 는 뺀다 — 서버 q 는 1자 이상, NUL 은 지운다 — MARC-ISSUE-209).
//     기간은 KST 「오늘」(now + 9시간의 UTC 날짜)에서 센다. dateTo 는 끝 날 그대로 — 서버가 「KST 그날 끝까지(포함)」다.
//     두 날짜는 서버가 받는 [2000-01-01, 2999-12-31] 안으로 조인다(시계가 틀려도 422 가 나지 않게).
//     같은 날짜 셈이 entities/audit-log/model 에도 있다 — entities 끼리는 가져오지 않아 따로 둔다(감독 판단 Q3 (가)).
//   - 모듈은 고정 목록 RUN_MODULES(셸 메뉴 차례) + 불러온 줄에서 처음 본 다른 id(moduleOptions).
//   - 검토는 서버 review 셋(RUN_REVIEWS) 그대로 거른다 — 화면은 받은 줄을 다시 거르지 않는다(AD4X ①).
//   - 표시 글(올린 사람·AI 설정·비용·토큰 줄임·실패율)은 글자를 넣어 받는다(model 은 문구 표를 모른다 — 화면이 RUN_LOG_TEXT 를 넣는다).
import type { Schemas, paths } from '../../../shared/api/index.ts';

/** GET /run-logs 의 줄 하나. */
export type RunLogRow = Schemas['RunLogOut'];
/** GET /run-logs/metrics 의 지표(이번 달 — 서버 시계, 거르기와 따로). */
export type RunMetricsRow = Schemas['RunMetricsOut'];
/** 실행 상태(서버 status 값 그대로 — 접지 않는다, 감독 판단 Q5 (가)). */
export type RunStatus = RunLogRow['status'];
/** 검토 상태(서버 review 값 — null 은 검토가 보이지 않는 실행). */
export type RunReview = NonNullable<RunLogRow['review']>;

/** 상태 넷(표시 차례 — 디자인: 대기·처리 중·완료·실패). 계약 enum 과 집합이 같다(model 시험). */
export const RUN_STATUSES = [
  'queued',
  'processing',
  'done',
  'failed',
] as const satisfies readonly RunStatus[];

/** 검토 셋(표시 차례 — 미검토·검토 중·확정). 계약 enum 과 집합이 같다(model 시험). */
export const RUN_REVIEWS = [
  'pending',
  'in_review',
  'confirmed',
] as const satisfies readonly RunReview[];

/**
 * 모듈 거르기의 고정 목록(셸 메뉴 차례 — 온실가스 Scope 3 · 그린워싱 · 중대성평가 IRO · 데이터 검증 · 영문번역 · 보고서 작성, AD6).
 * 값은 서버 module id. 라벨은 문구 표(RUN_LOG_TEXT.modules)가 같은 키로 갖는다.
 */
export const RUN_MODULES = [
  'inventory.scope3',
  'greenwash',
  'materiality',
  'dataverify',
  'translation',
  'drafting',
] as const;

export const RUN_PERIODS = ['month', 'lastMonth', 'all'] as const;
export type RunPeriod = (typeof RUN_PERIODS)[number];

/** 화면의 거르기(서버 쿼리로 옮긴다 — runQuery). */
export interface RunFilter {
  query: string;
  /** 'all' 또는 서버 module id. */
  module: string;
  period: RunPeriod;
  status: RunStatus | 'all';
  review: RunReview | 'all';
}

/** 처음 거르기(「모듈: 전체 · 기간: 이번 달 · 상태: 전체 · 검토: 전체」). */
export const RUN_NO_FILTER: RunFilter = {
  query: '',
  module: 'all',
  period: 'month',
  status: 'all',
  review: 'all',
};

/** GET /run-logs 의 쿼리 중 화면이 정하는 칸(쪽·회사는 어댑터가 — companyId 는 보내지 않는다). */
export type RunQuery = Omit<
  NonNullable<paths['/run-logs']['get']['parameters']['query']>,
  'limit' | 'offset' | 'companyId'
>;

/** 검색 글의 상한(서버 q 의 maxLength — 코드 포인트). */
export const RUN_QUERY_MAX = 150;

const DAY = 86_400_000;
const KST = 9 * 3_600_000;
const MIN_DAY = Date.UTC(2000, 0, 1);
const MAX_DAY = Date.UTC(2999, 11, 31);

/** UTC 자정 밀리초 → 'YYYY-MM-DD'(조인 범위 안에서만 부른다). */
const dateOf = (day: number) => new Date(day).toISOString().slice(0, 10);
/** 'YYYY-MM-DD' → UTC 자정 밀리초. */
function dayOf(date: string): number {
  const [y, m, d] = date.slice(0, 10).split('-').map(Number);
  return Date.UTC(y!, m! - 1, d!);
}
const clampDay = (day: number) => Math.min(MAX_DAY, Math.max(MIN_DAY, day));

/** KST 「오늘」의 날짜(now + 9시간의 UTC 날짜). 조이지 않은 날 그대로의 UTC 자정 밀리초. */
function kstDay(now: Date): number {
  const shifted = now.getTime() + KST;
  return shifted - (((shifted % DAY) + DAY) % DAY);
}

/** KST 「오늘」('YYYY-MM-DD'). 서버가 받는 범위 밖이면 그 끝으로 조인다. */
export const kstToday = (now: Date): string => dateOf(clampDay(kstDay(now)));

/**
 * 기간 → 날짜 범위(둘 다 포함). 이번 달 = 그달 1일 ~ 오늘, 지난달 = 앞 달 1일 ~ 앞 달 말일, 전체 = null.
 * 두 값은 [2000-01-01, 2999-12-31] 안으로 조인다.
 */
export function periodRange(
  period: RunPeriod,
  today: string,
): { dateFrom: string; dateTo: string } | null {
  if (period === 'all') return null;
  const end = new Date(dayOf(today));
  const year = end.getUTCFullYear();
  const month = end.getUTCMonth();
  const [start, last] =
    period === 'month' ?
      [Date.UTC(year, month, 1), end.getTime()]
    : [Date.UTC(year, month - 1, 1), Date.UTC(year, month, 1) - DAY];
  return {
    dateFrom: dateOf(clampDay(start)),
    dateTo: dateOf(clampDay(last)),
  };
}

/** 검색 글: NUL 을 지우고 앞뒤 빈칸을 걷고 코드 포인트 150자에서 자른다. 비면 null(보내지 않는다). */
export function searchText(query: string): string | null {
  const text = [...query.replaceAll('\u0000', '').trim()]
    .slice(0, RUN_QUERY_MAX)
    .join('');
  return text === '' ? null : text;
}

/** 거르기 → 서버 쿼리. 값이 있는 칸만(빈 q·'all'·전체 기간의 키는 만들지 않는다). */
export function runQuery(filter: RunFilter, now: Date): RunQuery {
  const query: RunQuery = {};
  const range = periodRange(filter.period, kstToday(now));
  if (range) {
    query.dateFrom = range.dateFrom;
    query.dateTo = range.dateTo;
  }
  const q = searchText(filter.query);
  if (q !== null) query.q = q;
  if (filter.module !== 'all') query.module = filter.module;
  if (filter.status !== 'all') query.status = filter.status;
  if (filter.review !== 'all') query.review = filter.review;
  return query;
}

/** 모듈 거르기의 선택지(id): 고정 여섯 + 불러온 줄에서 처음 본 다른 id(본 차례). */
export function moduleOptions(seen: readonly string[]): string[] {
  const options: string[] = [...RUN_MODULES];
  for (const module of seen)
    if (!options.includes(module)) options.push(module);
  return options;
}

/** 흐름 칸: flowId(`id@판`)의 판 글자(「greenwash.colab@E0」 → 「E0」). @ 가 없으면 그대로. */
export function flowEdition(flowId: string): string {
  const at = flowId.lastIndexOf('@');
  return at < 0 ? flowId : flowId.slice(at + 1);
}

/** 처리 시간 글(「8분 05초」). null 이면 null. */
export function durationText(seconds: number | null): string | null {
  if (seconds === null) return null;
  const minutes = Math.floor(seconds / 60);
  const rest = String(seconds % 60).padStart(2, '0');
  return `${minutes}분 ${rest}초`;
}

/** 천 단위 쉼표. */
export const withCommas = (value: number) =>
  String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

/** 올린 사람 글: 이름 → 아이디 → 넣어 준 대체 글(missing — 화면이 회색으로). */
export function uploaderText(
  row: Pick<RunLogRow, 'createdByName' | 'createdByUsername'>,
  unknown: string,
): { text: string; missing: boolean } {
  const name = row.createdByName ?? row.createdByUsername;
  return name === null ?
      { text: unknown, missing: true }
    : { text: name, missing: false };
}

/**
 * AI 설정 칸 글: 없음(null) → 넣어 준 빈 글(missing — 화면이 회색으로), 기본 판(id null) → 「기본 설정」, 그 밖 → 판 이름(「v3」).
 * 「v<n> · 이름」은 서버가 판 title 을 실은 뒤(MARC-ISSUE-286).
 */
export function aiSettingText(
  setting: RunLogRow['aiSetting'],
  words: { empty: string; defaultSetting: string },
): { text: string; missing: boolean } {
  if (setting === null) return { text: words.empty, missing: true };
  if (setting.id === null)
    return { text: words.defaultSetting, missing: false };
  return { text: setting.name, missing: false };
}

/** 비용 글(USD): 0 → 「$0.00」, 0 < x < 0.005 → 넣어 준 글(「<$0.01」), 그 밖 「$x.xx」. */
export const costText = (usd: number, below: string) =>
  usd > 0 && usd < 0.005 ? below : `$${usd.toFixed(2)}`;

/**
 * 줄의 숫자 칸 셋(처리 시간·토큰·비용). 「대기」(queued) 줄은 아직 돌지 않아 셋 다 빈 값 — 「0」·「$0.00」은 틀린 값처럼 읽힌다(디자인 대조 B2).
 * 그 밖은 처리 시간(없으면 빈 값)·토큰 쉼표·비용 글.
 */
export function runFigures(
  row: Pick<RunLogRow, 'status' | 'durationSec' | 'tokens' | 'costUsd'>,
  words: { empty: string; costBelow: string },
): { duration: string; tokens: string; cost: string } {
  if (row.status === 'queued')
    return { duration: words.empty, tokens: words.empty, cost: words.empty };
  return {
    duration: durationText(row.durationSec) ?? words.empty,
    tokens: withCommas(row.tokens),
    cost: costText(row.costUsd, words.costBelow),
  };
}

/** 지표 카드의 토큰 합: 1,000,000 이상은 「3.1M」(소수 한 자리 버림), 아래는 쉼표. */
export const tokensShort = (tokens: number) =>
  tokens >= 1_000_000 ?
    `${(Math.floor(tokens / 100_000) / 10).toFixed(1)}M`
  : withCommas(tokens);

/** 실패율 글(×100, 소수 한 자리 반올림 — 「%」는 화면이 붙인다). null 이면 null. */
export const rateText = (rate: number | null) =>
  rate === null ? null : (Math.round(rate * 1000) / 10).toFixed(1);

/** 화면의 시각 글(「2026-10-15 15:10」 — 서버 createdAt 은 +09:00 글자). */
export const formatRunTime = (at: string) =>
  `${at.slice(0, 10)} ${at.slice(11, 16)}`;
