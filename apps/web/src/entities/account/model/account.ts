// 계정(고객사 사용자)의 꼴과 순수 함수(밴드 AD1 ②). React·DOM·통신을 모른다.
// 계약 타입(CustomerUserOut·UserPageOut)은 shared/api 가 다시 내보낸 것을 타입으로만 가져온다.
//   - statusOf: 상태 칸 하나에 배지 하나. 앞섬 차례 사용 중지 > 잠김 > 초기화 대기 > 사용 중(디자인 원문 2026-10-18 — 잠김을 보인다).
//     isLocked 는 서버의 잠금 판정(5번 틀려 10분)이고, 초기화하면 풀린다. 서버 status 거르기도 같은 앞섬이다(UA1).
//   - accountQuery: 화면의 거르기 → GET /users 의 쿼리(밴드 UA1W). 값이 있는 칸만 담는다 — 빈·공백 q, 'all' 의 키는 만들지 않는다.
//     q 는 NUL 을 지우고 앞뒤 빈칸을 걷고 코드 포인트 150자에서 자른다(searchText). limit·offset 은 어댑터가, companyId 는 보내지 않는다(MARC-ENT-251).
//   - makeTemporaryPassword: 임시 비밀번호는 웹이 만들어 보낸다(서버는 받기만 — 발주서 §1). 난수 함수는 넣어 받는다(app/ 이 crypto 를 넣는다).
//   - usernameProblem·nameLength: AD-01a 의 칸 검사. 아이디는 시안 도움 글대로 ASCII(서버 패턴 `^[A-Za-z0-9_.@+-]+$` 와 같다 — UA1).
import type { Schemas, paths } from '../../../shared/api/index.ts';

/** GET /users 의 줄 하나(고객사 사용자). */
export type Account = Schemas['CustomerUserOut'];
/** GET /users 의 쪽 하나. */
export type AccountPage = Schemas['UserPageOut'];

export const ACCOUNT_STATUSES = [
  'inactive',
  'locked',
  'initial',
  'active',
] as const;
/** 상태 칸의 배지: 사용 중지 · 잠김 · 초기화 대기 · 사용 중. */
export type AccountStatus = (typeof ACCOUNT_STATUSES)[number];

/**
 * 사용 중지 뒤에도 이미 낸 access 가 통하는 분(사용 중지 확인 글 — 디자인 원문 UA1W Q13).
 * 서버 정본은 apps/api-py/esgapi/core/auth/tokens.py 의 ACCESS_TTL_SECONDS(30 * 60). 서버가 이 값을 내주지 않아 웹 상수로 둔다.
 */
export const ACCESS_TTL_MINUTES = 30;

/** 위가 이긴다: 사용 중지 > 잠김 > 초기화 대기(새로 만든 계정도) > 사용 중. */
export function statusOf(
  account: Pick<Account, 'isActive' | 'isLocked' | 'isInitial'>,
): AccountStatus {
  if (!account.isActive) return 'inactive';
  if (account.isLocked) return 'locked';
  if (account.isInitial) return 'initial';
  return 'active';
}

/** GET /users 의 쿼리 중 화면이 정하는 칸(limit·offset 은 어댑터, companyId 는 보내지 않는다). */
export type AccountQuery = Omit<
  NonNullable<paths['/users']['get']['parameters']['query']>,
  'limit' | 'offset' | 'companyId'
>;

/** 상태 고르기: 전체 또는 배지 넷. */
export type StatusFilter = 'all' | AccountStatus;
export const STATUS_FILTERS: readonly StatusFilter[] = [
  'all',
  'active',
  'initial',
  'locked',
  'inactive',
];

/** 화면의 거르기(검색 글은 입력 그대로 — 보낼 때 searchText 로 다듬는다). */
export interface AccountFilter {
  query: string;
  status: StatusFilter;
}

export const NO_FILTER: AccountFilter = { query: '', status: 'all' };

/** 검색 글의 상한(서버 q 의 maxLength — 코드 포인트). */
export const ACCOUNT_QUERY_MAX = 150;

/** 검색 글: NUL 을 지우고 앞뒤 빈칸을 걷고 코드 포인트 150자에서 자른다. 비면 null(보내지 않는다). */
export function searchText(query: string): string | null {
  const text = [...query.replaceAll('\u0000', '').trim()]
    .slice(0, ACCOUNT_QUERY_MAX)
    .join('');
  return text === '' ? null : text;
}

/** 거르기 → 서버 쿼리. 값이 있는 칸만(빈 q·'all' 의 키는 만들지 않는다). */
export function accountQuery(filter: AccountFilter): AccountQuery {
  const query: AccountQuery = {};
  const q = searchText(filter.query);
  if (q !== null) query.q = q;
  if (filter.status !== 'all') query.status = filter.status;
  return query;
}

/** 거른 채인가(빈 목록 글을 가른다 — 보낼 쿼리가 비었으면 거르지 않은 것). */
export const isFiltered = (filter: AccountFilter) =>
  Object.keys(accountQuery(filter)).length > 0;

/** lastLoginAt(+09:00 그대로)를 「YYYY-MM-DD HH:mm」로. 없거나 꼴이 아니면 null(화면은 「—」). */
export function formatLastLogin(at: string | null): string | null {
  const match = at ? /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(at) : null;
  return match ? `${match[1]} ${match[2]}` : null;
}

const KST_MS = 9 * 60 * 60 * 1000;
/** createdAt 을 KST 날짜 「YYYY-MM-DD」로(UA1W 디자인 원문 — 만든 날 열). 꼴이 아니면 null(화면은 「—」). */
export function formatCreatedDate(at: string): string | null {
  const time = Date.parse(at);
  if (!/^\d{4}-\d{2}-\d{2}T/.test(at) || Number.isNaN(time)) return null;
  return new Date(time + KST_MS).toISOString().slice(0, 10);
}

/** 아이디 1~150자(서버 상한), 시안 도움 글의 글자만: 영문·숫자와 . @ + - _ */
export const USERNAME_PATTERN = /^[A-Za-z0-9.@+_-]{1,150}$/;
/** 이름 상한(코드 포인트 — 서버의 파이썬 길이와 같다). */
export const NAME_MAX = 20;

/** 아이디 칸의 문제: 비었음 · 쓸 수 없는 글자(또는 150자 넘음) · 없음. 앞뒤 공백도 쓸 수 없는 글자다(서버는 다듬지 않는다). */
export function usernameProblem(username: string): 'empty' | 'format' | null {
  if (username === '') return 'empty';
  return USERNAME_PATTERN.test(username) ? null : 'format';
}

/** 이름의 길이(코드 포인트 — 이모지·한글 한 글자가 하나). */
export const nameLength = (name: string) => [...name].length;

/** 보낼 이름(앞뒤 공백을 다듬는다). 다듬은 뒤 비었거나 20자를 넘으면 null(보내지 않는다). */
export function nameToSend(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed === '' || nameLength(trimmed) > NAME_MAX) return null;
  return trimmed;
}

/** 난수 함수: 받은 배열을 난수로 채운다(crypto.getRandomValues 의 꼴). */
export type RandomFill = (array: Uint32Array) => Uint32Array;

/** 헷갈리는 글자(0 O o 1 l I)를 뺀 네 갈래. 기호는 URL·셸에서도 덜 헷갈리는 몇. */
export const PASSWORD_GROUPS = [
  'ABCDEFGHJKLMNPQRSTUVWXYZ',
  'abcdefghijkmnpqrstuvwxyz',
  '23456789',
  '#%+=@',
] as const;
export const TEMPORARY_PASSWORD_LENGTH = 12;
const ALL = PASSWORD_GROUPS.join('');
const RANGE = 2 ** 32;

/** 0 이상 n 미만의 고른 정수. 나머지 편향을 피해 거절 표본으로 뽑는다(남는 끝자리 값은 버리고 다시 뽑는다). */
export function uniformIndex(random: RandomFill, n: number): number {
  const limit = RANGE - (RANGE % n);
  const cell = new Uint32Array(1);
  for (;;) {
    const value = random(cell)[0]!;
    if (value < limit) return value % n;
  }
}

/**
 * 임시 비밀번호 12자. 네 갈래(대문자·소문자·숫자·기호)를 하나씩 넣고 나머지는 전체에서 뽑은 뒤 섞는다(Fisher–Yates).
 * 서버 검사기는 8자 미만만 거절한다(UA1 — MARC-ENT-282)라 12자는 늘 지난다. 어댑터의 PASSWORD_REJECTED 한 번 다시는 방어로 남긴다.
 */
export function makeTemporaryPassword(random: RandomFill): string {
  const chars = PASSWORD_GROUPS.map(
    (group) => group[uniformIndex(random, group.length)]!,
  );
  while (chars.length < TEMPORARY_PASSWORD_LENGTH)
    chars.push(ALL[uniformIndex(random, ALL.length)]!);
  for (let i = chars.length - 1; i > 0; i--) {
    const j = uniformIndex(random, i + 1);
    [chars[i], chars[j]] = [chars[j]!, chars[i]!];
  }
  return chars.join('');
}
