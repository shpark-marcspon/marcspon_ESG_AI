// 쪽 범위 파서·압축·겹침·합계(밴드 FW1b ①). 표 꼴 시험.
import { describe, expect, it } from 'vitest';

import {
  MAX_PAGE_COUNT,
  PAGE_RANGE_ERRORS,
  formatPageRange,
  parsePageRange,
} from './pageRange.ts';
import type { PageRangeErrorCode } from './pageRange.ts';
import {
  EMPTY_PARTS,
  allPartsEmpty,
  overlapOf,
  overlapPages,
  partsOfPage,
  totalPages,
  unionPages,
} from './parts.ts';

const range = (from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => from + i);

describe('parsePageRange: 맞는 글자', () => {
  const cases: [string, number | undefined, number[]][] = [
    ['4~5', 139, [4, 5]],
    ['7', 139, [7]],
    ['25~37, 55~74, 150', 200, [...range(25, 37), ...range(55, 74), 150]],
    ['4-5', 139, [4, 5]],
    ['4 ~ 5', 139, [4, 5]],
    ['4 - 5', 139, [4, 5]],
    ['  4~5 ,7 ,  9  ', 139, [4, 5, 7, 9]],
    ['7, 4~5', 139, [4, 5, 7]],
    ['4~6, 5~8', 139, range(4, 8)],
    ['3, 3', 139, [3]],
    ['', 139, []],
    ['   ', 139, []],
    ['139', 139, [139]],
    ['1~139', 139, range(1, 139)],
    ['150', undefined, [150]],
    ['300', undefined, [300]],
    ['4~5,', 139, [4, 5]],
    ['4~5,,7', 139, [4, 5, 7]],
    [', 4 , ', 139, [4]],
    [',', 139, []],
    ['5~5', 10, [5]],
  ];
  it.each(cases)('%j (쪽 수 %s) → 쪽 집합', (text, pageCount, pages) => {
    expect(parsePageRange(text, pageCount)).toEqual({ ok: true, pages });
  });
});

describe('parsePageRange: 전각 물결(sid:MARC-ISSUE-309)', () => {
  it.each(['3～7', '3〜7', '3 ～ 7', '3〜 7'])(
    '%j 는 「3-7」 과 같은 결과',
    (text) => {
      expect(parsePageRange(text, 139)).toEqual(parsePageRange('3-7', 139));
      expect(parsePageRange(text, 139)).toEqual({
        ok: true,
        pages: range(3, 7),
      });
    },
  );

  it('오류 갈래도 같다(뒤집힘·음수·초과), 그 밖 물결 꼴 글자(〰 U+3030·∼ U+223C)는 지금처럼 not_number', () => {
    expect(parsePageRange('9～3', 139)).toEqual({
      ok: false,
      error: { code: 'reversed', token: '9～3', from: 9, to: 3 },
    });
    expect(parsePageRange('3〜-5', 139)).toEqual({
      ok: false,
      error: { code: 'negative', token: '3〜-5' },
    });
    expect(parsePageRange('130～150', 139)).toMatchObject({
      ok: false,
      error: { code: 'over_page_count', page: 150 },
    });
    for (const text of ['3〰7', '3∼7', '3～～7'])
      expect(parsePageRange(text, 139)).toEqual({
        ok: false,
        error: { code: 'not_number', token: text },
      });
  });
});

describe('parsePageRange: 오류 사유 코드', () => {
  const cases: [string, number | undefined, PageRangeErrorCode][] = [
    ['9~3', 139, 'reversed'],
    ['4~5, 9-3', 139, 'reversed'],
    ['0', 139, 'zero'],
    ['0~5', 139, 'zero'],
    ['-3', 139, 'negative'],
    ['3~-5', 139, 'negative'],
    ['3--5', 139, 'negative'],
    ['abc', 139, 'not_number'],
    ['4~', 139, 'not_number'],
    ['4.5', 139, 'not_number'],
    ['4~5~6', 139, 'not_number'],
    ['4, x', 139, 'not_number'],
    ['150', 139, 'over_page_count'],
    ['25~37, 55~74, 150', 139, 'over_page_count'],
    ['130~150', 139, 'over_page_count'],
    ['140', 139, 'over_page_count'],
    ['301', undefined, 'over_page_count'],
  ];
  it.each(cases)('%j (쪽 수 %s) → %s', (text, pageCount, code) => {
    const result = parsePageRange(text, pageCount);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.code).toBe(code);
  });

  it('오류 코드 다섯이 위 표에 모두 나온다', () => {
    const seen = new Set(
      cases.map(([text, count]) => {
        const result = parsePageRange(text, count);
        return result.ok ? null : result.error.code;
      }),
    );
    for (const code of PAGE_RANGE_ERRORS)
      expect(seen.has(code), code).toBe(true);
  });

  it('쪽 수 초과는 넘은 쪽과 마지막 쪽을 함께 낸다(문구 「{n}쪽은 … 마지막 쪽({m}쪽)을 넘어요」의 재료)', () => {
    expect(parsePageRange('25~37, 55~74, 150', 139)).toEqual({
      ok: false,
      error: {
        code: 'over_page_count',
        token: '150',
        page: 150,
        pageCount: 139,
        documentKnown: true,
      },
    });
    // 넘은 수 가운데 가장 큰 것(구간이면 끝)
    for (const text of ['70~80', '50~80']) {
      const result = parsePageRange(text, 60);
      expect(
        !result.ok &&
          result.error.code === 'over_page_count' &&
          result.error.page,
        text,
      ).toBe(80);
    }
    const reversed = parsePageRange('9~3', 139);
    expect(reversed).toEqual({
      ok: false,
      error: { code: 'reversed', token: '9~3', from: 9, to: 3 },
    });
  });
});

describe('parsePageRange: over_page_count.page 는 첫 오류 토막의 끝', () => {
  it.each([
    ['150, 70', 139, 150],
    ['70, 150', 139, 150],
    ['70, 150', 60, 70],
    ['50~80', 60, 80],
    ['70~80', 60, 80],
  ] as const)('%j / %s → %s', (text, count, page) => {
    const result = parsePageRange(text, count);
    expect(
      !result.ok &&
        result.error.code === 'over_page_count' &&
        result.error.page,
    ).toBe(page);
  });
});

describe('parsePageRange: 위쪽 한도(검증 B1)', () => {
  it('문서 쪽 수를 몰라도 「1~20000000」 은 펼치지 않고 바로 1차 한도(300) 초과로 끝난다', () => {
    const started = performance.now();
    const result = parsePageRange('1~20000000');
    expect(performance.now() - started).toBeLessThan(50);
    expect(result).toEqual({
      ok: false,
      error: {
        code: 'over_page_count',
        token: '1~20000000',
        page: 20000000,
        pageCount: MAX_PAGE_COUNT,
        documentKnown: false,
      },
    });
    expect(parsePageRange('1~10000000', 139).ok).toBe(false);
  });
});

describe('formatPageRange: 늘 오름차순 구간 압축', () => {
  const cases: [number[], string][] = [
    [[4, 5], '4~5'],
    [[7], '7'],
    [[7, 4, 5], '4~5, 7'],
    [[5, 4, 4, 5], '4~5'],
    [[], ''],
    [[...range(25, 37), ...range(55, 74), 150], '25~37, 55~74, 150'],
    [[1, 3, 5], '1, 3, 5'],
  ];
  it.each(cases)('%j → %j', (pages, text) => {
    expect(formatPageRange(pages)).toBe(text);
  });

  it('글자 → 집합 → 글자 가 정리된 꼴로 돌아온다', () => {
    const parsed = parsePageRange(' 7 , 4-5 ', 139);
    expect(parsed.ok && formatPageRange(parsed.pages)).toBe('4~5, 7');
  });
});

describe('파트: 겹침과 합계', () => {
  // 시안 GW-02_r1: CEO 4~5 · 회사소개 5~14 · 기후·환경 25~37, 55~74 → 점검할 쪽 44
  const parts = {
    ceo: [4, 5],
    company: range(5, 14),
    climate: [...range(25, 37), ...range(55, 74)],
  };

  it('합계는 합집합의 수(겹친 5쪽은 한 번)', () => {
    expect(totalPages(parts)).toBe(44);
    expect(unionPages(parts)).toHaveLength(44);
    expect(parts.ceo.length + parts.company.length).toBe(12);
  });

  it('겹친 쪽과 파트마다의 겹침, 쪽이 든 파트', () => {
    expect(overlapPages(parts)).toEqual([5]);
    expect(overlapOf(parts, 'company')).toEqual([5]);
    expect(overlapOf(parts, 'climate')).toEqual([]);
    expect(partsOfPage(parts, 5)).toEqual(['ceo', 'company']);
    expect(partsOfPage(parts, 1)).toEqual([]);
  });

  it('세 파트가 모두 비었는가', () => {
    expect(allPartsEmpty(EMPTY_PARTS)).toBe(true);
    expect(allPartsEmpty({ ...EMPTY_PARTS, climate: [3] })).toBe(false);
    expect(totalPages(EMPTY_PARTS)).toBe(0);
  });
});
