// 파트 하나의 쪽 범위(밴드 TRW0a ②, 결정 sid:MARC-ENT-392 — 파트마다 이어진 한 구간). 순수 함수만.
// 쪽 번호는 추출본의 [PAGE n] 기준, 1부터. 글자 칸(「1~3」)과 쪽 칸 끌기·누르기가 같은 Range 를 고친다.
// 부재는 판별 유니온으로 말한다: 빈 글 = 그 파트를 옮기지 않음(range null), 읽지 못함 = 오류(error). 0 으로 삼키지 않는다.
import { PART_KEYS } from './parts.ts';
import type { PartKey } from './parts.ts';

/** 이어진 한 구간(1부터, from ≤ to). */
export interface Range {
  from: number;
  to: number;
}

/**
 * 글자 칸을 읽지 못한 까닭. 오류 글이 말하는 값을 함께 싣는다: over_last 는 넘은 쪽(구간의 끝)과 마지막 쪽,
 * order 는 친 두 쪽, not_number 는 친 글자(앞뒤 공백 뺌). ceo_over_limit 은 글자 칸이 아니라 CEO 파트의 쪽 수가 낸다(ceoError).
 * 열쇠 이름은 그린워싱 PageRangeError 와 같은 code(감독 판단 — 뒤에 공통화하기 쉽게).
 */
export type RangeError =
  | { code: 'comma' }
  | { code: 'over_last'; page: number; last: number }
  | { code: 'order'; from: number; to: number }
  | { code: 'not_number'; token: string }
  | { code: 'zero' }
  | { code: 'ceo_over_limit'; limit: number };
export type RangeErrorCode = RangeError['code'];

export type RangeRead =
  { ok: true; range: Range | null } | { ok: false; error: RangeError };

/** CEO 메시지를 한 번에 옮기는 쪽 한도(6쪽 고정 — 사용자 10-22 밤, 디자인 e9 전달: 한도 입력 칸 없음). */
export const CEO_PAGE_LIMIT = 6;

/**
 * 「5」 또는 「1~3」·「1-3」·「1～3」·「1〜3」(그린워싱 pageRange 와 같은 넷 — 물결·하이픈·전각 물결 ～(U+FF5E)·〜(U+301C),
 * 그린워싱 GR2 sid:MARC-ISSUE-309 · TRW0b). 앞뒤·둘레 공백은 된다. 보일 때는 늘 물결.
 */
const RANGE_TEXT = /^(\d+)(?:\s*[~\-\uFF5E\u301C]\s*(\d+))?$/;

/** 글자 칸 → 구간. 빈 글은 range null(그 파트는 옮기지 않는다). lastPage 는 추출본의 쪽 수. */
export function parseRange(text: string, lastPage: number): RangeRead {
  const trimmed = text.trim();
  if (trimmed === '') return { ok: true, range: null };
  if (trimmed.includes(',')) return { ok: false, error: { code: 'comma' } };
  const match = RANGE_TEXT.exec(trimmed);
  if (!match)
    return { ok: false, error: { code: 'not_number', token: trimmed } };
  const from = Number(match[1]);
  const to = match[2] === undefined ? from : Number(match[2]);
  if (!Number.isSafeInteger(from) || !Number.isSafeInteger(to))
    return { ok: false, error: { code: 'not_number', token: trimmed } };
  if (from === 0 || to === 0) return { ok: false, error: { code: 'zero' } };
  if (from > to) return { ok: false, error: { code: 'order', from, to } };
  if (to > lastPage)
    return {
      ok: false,
      error: { code: 'over_last', page: to, last: lastPage },
    };
  return { ok: true, range: { from, to } };
}

/** 구간 → 글자 칸(「1~3」, 한 쪽이면 「5」). */
export function formatRange(range: Range): string {
  return range.from === range.to ?
      String(range.from)
    : `${range.from}~${range.to}`;
}

/** 구간의 쪽 수(없으면 0). */
export function pageCountOf(range: Range | null): number {
  return range === null ? 0 : range.to - range.from + 1;
}

/** 두 파트 이상이 가진 쪽(오름차순), 쪽마다 그 파트들(PART_KEYS 차례). */
export function overlapOf(
  ranges: Readonly<Record<PartKey, Range | null>>,
): { page: number; parts: PartKey[] }[] {
  const byPage = new Map<number, PartKey[]>();
  for (const part of PART_KEYS) {
    const range = ranges[part];
    if (range === null) continue;
    for (let page = range.from; page <= range.to; page++)
      byPage.set(page, [...(byPage.get(page) ?? []), part]);
  }
  return [...byPage]
    .filter(([, parts]) => parts.length > 1)
    .sort(([a], [b]) => a - b)
    .map(([page, parts]) => ({ page, parts }));
}

/** CEO 메시지의 쪽 수가 한도(CEO_PAGE_LIMIT)를 넘는가(없으면 넘지 않음). */
export function ceoOverLimit(range: Range | null): boolean {
  return pageCountOf(range) > CEO_PAGE_LIMIT;
}

/** CEO 파트의 쪽 범위 오류(한도를 넘으면). 없으면 null. */
export function ceoError(range: Range | null): RangeError | null {
  return ceoOverLimit(range) ?
      { code: 'ceo_over_limit', limit: CEO_PAGE_LIMIT }
    : null;
}

/** 떨어진 쪽 누름·칠하기: 구간을 거기까지 늘린다. 구간이 없으면 그 한 쪽. 구간 안의 쪽이면 그대로. */
export function extendRange(range: Range | null, page: number): Range {
  if (range === null) return { from: page, to: page };
  return { from: Math.min(range.from, page), to: Math.max(range.to, page) };
}

/** 두 구간이 같이 가진 쪽(없으면 null). 겹침 줄(「7~8쪽은 CEO 메시지와 겹침」)이 쓴다. */
export function intersectRange(a: Range | null, b: Range | null): Range | null {
  if (a === null || b === null) return null;
  const from = Math.max(a.from, b.from);
  const to = Math.min(a.to, b.to);
  return from <= to ? { from, to } : null;
}

/**
 * 구간에서 [lo..hi] 를 뺀다(한 구간을 지킨다 — 결정 sid:MARC-ENT-392). 다 덮으면 null, 한 끝을 덮으면 그 끝이 줄고,
 * 가운데만이면 남는 두 조각 중 작은 쪽을 같이 뺀다(같으면 앞을 남김).
 */
function cutRange(range: Range, lo: number, hi: number): Range | null {
  if (hi < range.from || lo > range.to) return range;
  if (lo <= range.from && hi >= range.to) return null;
  if (lo <= range.from) return { from: hi + 1, to: range.to };
  if (hi >= range.to) return { from: range.from, to: lo - 1 };
  return lo - range.from < range.to - hi ?
      { from: hi + 1, to: range.to }
    : { from: range.from, to: lo - 1 };
}

/**
 * 쪽 누름(그린워싱 togglePage 꼴, 밴드 TRW3): 구간 밖이면 거기까지 늘리고(extendRange), 구간 안이면 그 쪽을 뺀다 —
 * 가운데 쪽이면 가까운 끝까지 같이(같으면 뒤쪽을 자름). 한 쪽만 남은 쪽을 누르면 null(파트 비움).
 */
export function pressRange(range: Range | null, page: number): Range | null {
  if (range === null || page < range.from || page > range.to)
    return extendRange(range, page);
  return cutRange(range, page, page);
}

/**
 * 끌기(그린워싱 paintModeAt·paintRange 꼴, 밴드 TRW3): 시작 쪽(anchor)이 끌기 전 구간(base) 밖이면 칠하기 —
 * base 와 끈 구간을 덮는 한 구간(떨어져 있으면 사이도), 안이면 지우개 — base 에서 끈 구간을 뺀다(cutRange). 차례 무관.
 */
export function paintRange(
  base: Range | null,
  anchor: number,
  page: number,
): Range | null {
  const lo = Math.min(anchor, page);
  const hi = Math.max(anchor, page);
  if (base === null || anchor < base.from || anchor > base.to)
    return extendRange(extendRange(base, lo), hi);
  return cutRange(base, lo, hi);
}
