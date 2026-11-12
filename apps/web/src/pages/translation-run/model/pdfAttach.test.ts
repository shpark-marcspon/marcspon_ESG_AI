// 이슈·용어 붙이기(밴드 TRW6 ③ W9, sid:MARC-ENT-481): 이슈는 번역에서, 용어는 원문(표 칸 포함)에서 · 정규화(공백·대소문자) ·
// 첫 단위 · 칸 짝이 테두리보다 먼저 · 못 찾음·빈 구간 → 페이지만 · 번역 없는 짝에는 이슈 0.
import { describe, expect, it } from 'vitest';

import { attachToPairs, normalizeText, placesOf } from './pdfAttach.ts';
import type { PdfPair } from './pdfView.ts';

const pair = (
  unit: number,
  kind: PdfPair['kind'],
  source: string[],
  translation: string[] | null,
): PdfPair => ({
  unit,
  kind,
  unitKind: 'block',
  visual: false,
  source,
  translation,
});

const PAIRS: PdfPair[] = [
  pair(0, 'block', ['기후 대응 전략'], ['Climate  Strategy']),
  pair(1, 'block', ['배출을 줄인다'], ['We cut emissions by 14%']),
  pair(2, 'table', ['| 구분 | 배출량 |'], ['Category', 'Emissions']),
  pair(2, 'cell', ['배출량'], ['Emissions']),
  pair(3, 'missing', ['빠진 배출 문단'], null),
  pair(4, 'block', ['또 배출을 줄인다'], ['We cut emissions by 14% again']),
];

describe('attachToPairs', () => {
  it('정규화: 앞뒤·여러 공백·줄바꿈을 하나로, 대소문자 무시', () => {
    expect(normalizeText('  A\n  b\tC ')).toBe('a b c');
    const got = attachToPairs(PAIRS, {
      issues: ['climate strategy'],
      misses: [],
    });
    expect([...got.byPair]).toEqual([[0, { issues: [0], misses: [] }]]);
  });

  it('이슈는 번역에서 — 원문에만 있는 글은 못 찾음(페이지만)', () => {
    const got = attachToPairs(PAIRS, {
      issues: ['배출을 줄인다'],
      misses: [],
    });
    expect(got.byPair.size).toBe(0);
    expect(got.pageOnly.issues).toEqual([0]);
  });

  it('두 단위에 맞으면 첫 단위 하나에만', () => {
    const got = attachToPairs(PAIRS, {
      issues: ['by 14%'],
      misses: [],
    });
    expect([...got.byPair.keys()]).toEqual([1]);
  });

  it('용어는 원문에서 · 표면 칸 짝이 테두리보다 먼저', () => {
    const got = attachToPairs(PAIRS, { issues: [], misses: ['배출량'] });
    expect([...got.byPair]).toEqual([[3, { issues: [], misses: [0] }]]);
  });

  it('번역 없는 짝(missing)에는 이슈 0, 원문 용어는 붙는다', () => {
    const only = [PAIRS[4]!];
    const got = attachToPairs(only, {
      issues: ['빠진 배출 문단'],
      misses: ['빠진 배출'],
    });
    expect(got.pageOnly.issues).toEqual([0]);
    expect(got.byPair.get(0)).toEqual({ issues: [], misses: [0] });
  });

  it('빈 구간·못 찾은 것은 페이지만(첫 상자에 붙이지 않음)', () => {
    const got = attachToPairs(PAIRS, {
      issues: ['', '   ', 'nowhere'],
      misses: ['없는 용어'],
    });
    expect(got.byPair.size).toBe(0);
    expect(got.pageOnly).toEqual({ issues: [0, 1, 2], misses: [0] });
  });
});

// 요약 표 줄 → PDF 보기 자리(① 표 줄 누름 → ② 의 그 쪽·그 상자, 못 붙은 줄은 그 쪽만).
describe('placesOf', () => {
  const OTHER: PdfPair[] = [pair(7, 'block', ['다른 쪽 글'], ['Other page'])];
  const pairsOf = (page: number) =>
    page === 12 ? PAIRS
    : page === 13 ? OTHER
    : [];

  it('줄 차례 그대로 · 쪽마다 그 쪽 짝에서 찾음 · 못 찾음·layout 에 없는 쪽은 pair null', () => {
    const got = placesOf(pairsOf, {
      issues: [
        { page: 13, span: 'other page' },
        { page: 12, span: 'emissions by 14%' },
        { page: 12, span: '없는 글' },
        { page: 99, span: 'Other page' },
      ],
      misses: [
        { page: 12, ko: '배출량' },
        { page: 13, ko: '배출량' },
      ],
    });
    expect(got.issues).toEqual([
      { page: 13, pair: 0 },
      { page: 12, pair: 1 },
      { page: 12, pair: null },
      { page: 99, pair: null },
    ]);
    // 용어는 원문 — 12 는 칸 짝(자리 3)이 테두리(자리 2)보다 먼저, 13 엔 없음.
    expect(got.misses).toEqual([
      { page: 12, pair: 3 },
      { page: 13, pair: null },
    ]);
  });
});
