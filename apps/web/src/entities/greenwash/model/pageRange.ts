// 쪽 범위 글자 ↔ 쪽 집합(밴드 FW1b ①, 시안 GW-02_r1 의 글자 칸 꼴).
//
// 글자 꼴: 「4~5」「25~37, 55~74, 150」「7」. 구간은 물결 `~` 또는 하이픈 `-` 로, 떨어진 구간은 쉼표로 잇는다.
//   한국어 입력에 흔한 전각 물결 `～`(U+FF5E)·물결 대시 `〜`(U+301C)도 `~` 와 같이 받는다(sid:MARC-ISSUE-309).
//   쉼표·구간 기호 앞뒤의 공백은 받는다. 빈 글자는 「쪽 없음」(빈 집합)이다.
// 빈 토막(꼬리 쉼표 「4~5,」, 겹친 쉼표 「4~5,,7」)은 무시한다: 치는 도중 오류가 번쩍이지 않게.
// 오류는 사유 코드로만 낸다(문구는 ui 의 문구 표). 첫 오류 하나를 낸다(왼쪽부터).
// 위쪽 한도: 문서 쪽 수를 알면 그 수, 모르면(올리기 전) 1차 입력 한도 MAX_PAGE_COUNT(300). 구간 끝을 펼치기 전에 검사한다
//   (한도가 없으면 「1~20000000」 이 Set 을 터뜨린다. 밴드 FW1b ① 검증 B1).
// 쪽 번호는 PDF 쪽 기준이다(인계 3절). pageCount 를 넘는 쪽은 서버도 422 로 막는다(인계 4절).
// 집합 → 글자는 늘 오름차순 구간 압축이다(「4~5, 7」. 구간 기호는 `~`, 쉼표 뒤 공백 하나).

/** 1차 입력 한도(시안 GW-02 「300쪽, 50MB 까지」). 문서 쪽 수를 모를 때 쪽 범위의 위쪽 한도로도 쓴다. */
export const MAX_PAGE_COUNT = 300;

/** 올릴 수 있는 파일 크기 한도(MB — 드롭존이 고를 때 막고, 안내 글도 이 수를 쓴다). 서버 MAX_UPLOAD_BYTES 를 넘으면 413 UPLOAD_TOO_LARGE. */
export const MAX_UPLOAD_MB = 50;

export const PAGE_RANGE_ERRORS = [
  'not_number',
  'negative',
  'zero',
  'reversed',
  'over_page_count',
] as const;
export type PageRangeErrorCode = (typeof PAGE_RANGE_ERRORS)[number];

export type PageRangeError =
  | { code: 'not_number'; token: string }
  | { code: 'negative'; token: string }
  | { code: 'zero'; token: string }
  | { code: 'reversed'; token: string; from: number; to: number }
  | {
      code: 'over_page_count';
      token: string;
      /** 첫 오류 토막의 끝(구간이면 끝 쪽. 「150, 70」 → 150, 「70, 150」/139 → 150, 「70, 150」/60 → 70). */
      page: number;
      /** 넘은 한도. documentKnown 이 false 면 MAX_PAGE_COUNT. */
      pageCount: number;
      /** 한도가 문서 쪽 수인가(false 면 문서를 아직 몰라 1차 한도로 막았다). */
      documentKnown: boolean;
    };

export type PageRangeResult =
  { ok: true; pages: readonly number[] } | { ok: false; error: PageRangeError };

// 숫자 하나 또는 「숫자 구간기호 숫자」. 숫자 앞의 마이너스는 음수로 읽는다(「-3」, 「3~-5」).
const TOKEN = /^(-?\d+)(?:\s*[~\uFF5E\u301C-]\s*(-?\d+))?$/;

/**
 * 쪽 범위 글자를 쪽 집합(오름차순, 겹침 없음)으로 바꾼다.
 * pageCount 를 주면 그 수를 넘는 쪽은 오류다. 주지 않으면(문서를 아직 모름) MAX_PAGE_COUNT 를 넘는 쪽이 오류다.
 */
export function parsePageRange(
  text: string,
  pageCount?: number,
): PageRangeResult {
  if (text.trim() === '') return { ok: true, pages: [] };
  const pages = new Set<number>();
  const limit = pageCount ?? MAX_PAGE_COUNT;
  for (const raw of text.split(',')) {
    const token = raw.trim();
    if (token === '') continue;
    const match = TOKEN.exec(token);
    if (!match) return { ok: false, error: { code: 'not_number', token } };
    const from = Number(match[1]);
    const to = match[2] === undefined ? from : Number(match[2]);
    if (!Number.isSafeInteger(from) || !Number.isSafeInteger(to))
      return { ok: false, error: { code: 'not_number', token } };
    if (from < 0 || to < 0)
      return { ok: false, error: { code: 'negative', token } };
    if (from === 0 || to === 0)
      return { ok: false, error: { code: 'zero', token } };
    if (from > to)
      return { ok: false, error: { code: 'reversed', token, from, to } };
    if (to > limit)
      return {
        ok: false,
        error: {
          code: 'over_page_count',
          token,
          page: to,
          pageCount: limit,
          documentKnown: pageCount !== undefined,
        },
      };
    for (let page = from; page <= to; page++) pages.add(page);
  }
  return { ok: true, pages: sortPages(pages) };
}

/** 쪽 집합을 오름차순 구간 압축 글자로(「4~5, 7」). 빈 집합은 빈 글자. */
export function formatPageRange(pages: Iterable<number>): string {
  const sorted = sortPages(pages);
  const parts: string[] = [];
  let start: number | undefined;
  let prev: number | undefined;
  for (const page of sorted) {
    if (start === undefined || prev === undefined) {
      start = page;
    } else if (page !== prev + 1) {
      parts.push(start === prev ? `${start}` : `${start}~${prev}`);
      start = page;
    }
    prev = page;
  }
  if (start !== undefined && prev !== undefined)
    parts.push(start === prev ? `${start}` : `${start}~${prev}`);
  return parts.join(', ');
}

/** 겹침을 지우고 오름차순으로. */
export function sortPages(pages: Iterable<number>): number[] {
  return [...new Set(pages)].sort((a, b) => a - b);
}
