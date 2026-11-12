// 이슈·용어를 PDF 쪽의 짝에 붙이는 순수 셈(밴드 TRW6 ③ W9, 결정 sid:MARC-ENT-481 — 서버 0, 화면이 글자로 찾음). DOM 0.
// 규칙(시험으로 못 박음):
//   - 정규화: 앞뒤 공백을 떼고, 공백 덩어리(줄바꿈 포함)를 빈칸 하나로, 대소문자를 가리지 않는다(toLowerCase).
//   - 검수 이슈 originalSpan 은 그 쪽 짝의 「번역」(고른 문체)에서, 용어집 미반영 termKo 는 짝의 「원문」에서 찾는다.
//   - 짝 차례 = 단위 차례(units i) · 같은 단위 안에서는 표 칸 짝이 표 테두리 짝보다 먼저 · 처음 맞은 짝 하나에만 붙인다.
//   - 빈 구간(정규화 뒤 빈 글)·못 찾은 것은 「페이지만」(표에만 — 상자 표지 0).
//   - 번역이 없는 짝(source_only·missing)에는 이슈가 붙지 않는다(원문 용어는 붙는다).
// 이슈는 자동 수정 전 글 기준이라 자동 수정 문체에서는 못 찾는 수가 늘 수 있다(1차는 페이지만 — 보고에 수).
import type { LayoutVariantLabel } from '../../../entities/translation/model/index.ts';
import type { PdfPair } from './pdfView.ts';

export const normalizeText = (text: string): string =>
  text.trim().replace(/\s+/g, ' ').toLowerCase();

export interface AttachInput {
  /** 그 쪽 검수 이슈의 originalSpan(차례 = 표 차례). */
  issues: readonly string[];
  /** 그 쪽 용어집 미반영의 termKo. */
  misses: readonly string[];
}

export interface Attached {
  /** 짝 자리 → 붙은 이슈·용어(입력 차례 번호). */
  byPair: ReadonlyMap<number, { issues: number[]; misses: number[] }>;
  /** 어느 짝에도 붙지 못한 것(페이지만). */
  pageOnly: { issues: number[]; misses: number[] };
}

/** 찾는 차례: 단위 차례, 같은 단위면 표 칸 짝 → 그 밖. */
function searchOrder(pairs: readonly PdfPair[]): number[] {
  return pairs
    .map((pair, index) => ({ pair, index }))
    .sort(
      (a, b) =>
        a.pair.unit - b.pair.unit ||
        (a.pair.kind === 'cell' ? 0 : 1) - (b.pair.kind === 'cell' ? 0 : 1) ||
        a.index - b.index,
    )
    .map(({ index }) => index);
}

export function attachToPairs(
  pairs: readonly PdfPair[],
  input: AttachInput,
): Attached {
  const order = searchOrder(pairs);
  const byPair = new Map<number, { issues: number[]; misses: number[] }>();
  const pageOnly = { issues: [] as number[], misses: [] as number[] };
  const slot = (index: number) => {
    let found = byPair.get(index);
    if (!found) {
      found = { issues: [], misses: [] };
      byPair.set(index, found);
    }
    return found;
  };
  const place = (
    needle: string,
    textOf: (pair: PdfPair) => readonly string[] | null,
  ): number | null => {
    const wanted = normalizeText(needle);
    if (wanted === '') return null;
    for (const index of order) {
      const texts = textOf(pairs[index]!);
      if (texts === null) continue;
      if (normalizeText(texts.join(' ')).includes(wanted)) return index;
    }
    return null;
  };
  input.issues.forEach((span, n) => {
    const at = place(span, (pair) => pair.translation);
    if (at === null) pageOnly.issues.push(n);
    else slot(at).issues.push(n);
  });
  input.misses.forEach((term, n) => {
    const at = place(term, (pair) => pair.source);
    if (at === null) pageOnly.misses.push(n);
    else slot(at).misses.push(n);
  });
  return { byPair, pageOnly };
}

/** 요약 표 한 줄이 PDF 보기의 어디로 가는가(W9 — 표 줄 누름 → 그 쪽 · 그 짝, 못 붙은 줄은 그 쪽만). */
export interface PdfPlace {
  page: number;
  /** 그 쪽 짝 자리(pairs 의 자리). null = 페이지만. */
  pair: number | null;
}

/**
 * 요약 표 줄에서 PDF 보기로 들고 가는 자리(from = 검수 이슈 줄의 띠 글 재료 — 「12페이지 둘째 문단」·「숫자·단위 오류」).
 * label 은 요약에서 고른 문체 — 짝 자리는 문체마다 다르다(A·B level 이 다를 수 있음). 보기는 그 문체로 연다.
 */
export interface PdfOpenFocus extends PdfPlace {
  label: LayoutVariantLabel;
  from: { where: string; type: string } | null;
  /** 처음 쪽 목록 거르기(밴드 TRW7 ③a — 요약 「확인할 곳」 칸에서 왔을 때 'checks'). 없으면 [페이지 전체]. */
  filter?: 'checks';
}

/**
 * 요약 표의 줄(이슈·용어집 미반영)마다 자리(입력 차례 그대로). 쪽마다 attachToPairs 를 한 번 부른다.
 * pairsOf 는 그 쪽의 짝(고른 문체 — pdfPageOf(...).pairs). layout 에 없는 쪽이면 빈 목록이 와서 페이지만.
 */
export function placesOf(
  pairsOf: (page: number) => readonly PdfPair[],
  rows: {
    issues: readonly { page: number; span: string }[];
    misses: readonly { page: number; ko: string }[];
  },
): { issues: PdfPlace[]; misses: PdfPlace[] } {
  const issues: PdfPlace[] = rows.issues.map(({ page }) => ({
    page,
    pair: null,
  }));
  const misses: PdfPlace[] = rows.misses.map(({ page }) => ({
    page,
    pair: null,
  }));
  const pages = new Set([
    ...rows.issues.map((row) => row.page),
    ...rows.misses.map((row) => row.page),
  ]);
  for (const page of pages) {
    const issueAt = rows.issues.flatMap((row, i) =>
      row.page === page ? [i] : [],
    );
    const missAt = rows.misses.flatMap((row, i) =>
      row.page === page ? [i] : [],
    );
    const { byPair } = attachToPairs(pairsOf(page), {
      issues: issueAt.map((i) => rows.issues[i]!.span),
      misses: missAt.map((i) => rows.misses[i]!.ko),
    });
    for (const [pair, found] of byPair) {
      for (const n of found.issues) issues[issueAt[n]!]!.pair = pair;
      for (const n of found.misses) misses[missAt[n]!]!.pair = pair;
    }
  }
  return { issues, misses };
}
