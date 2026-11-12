// 파일명 거르기(밴드 TRP2 TE2, 발주서 §3): 대소문자 무시 · 앞뒤 빈칸 무시 · 빈 검색어는 그대로 · 없으면 0.
import { describe, expect, it } from 'vitest';

import { filterByFileName } from './filter.ts';

const ROWS = [
  { fileName: 'Annual_KO_extract.docx' },
  { fileName: '연차보고서_추출본.txt' },
  { fileName: 'appendix_ko_extract.docx' },
];

describe('filterByFileName', () => {
  it('대소문자 무시', () => {
    expect(filterByFileName(ROWS, 'ANNUAL').map((r) => r.fileName)).toEqual([
      'Annual_KO_extract.docx',
    ]);
    expect(filterByFileName(ROWS, 'ko_extract')).toHaveLength(2);
  });

  it('한국어 · 앞뒤 빈칸 무시', () => {
    expect(filterByFileName(ROWS, '  연차 ').map((r) => r.fileName)).toEqual([
      '연차보고서_추출본.txt',
    ]);
  });

  it('빈 검색어는 그대로, 맞는 것이 없으면 0', () => {
    expect(filterByFileName(ROWS, '   ')).toHaveLength(3);
    expect(filterByFileName(ROWS, 'none')).toEqual([]);
  });
});
