// 짝 칸 글의 밑줄·번호 순수 셈(밴드 TRW7 ① W1, 6c v182 TR-P05 .tp-u·.tp-ug·.tp-mk). DOM 0, 글 0.
// 붙이기(pdfAttach.attachToPairs — 어느 짝인가)는 그대로 두고, 붙은 짝 안에서 「어느 글자인가」만 따로 찾는다.
// 규칙(시험으로 못 박음):
//   - 정규화는 normalizeText 와 같다(앞뒤 공백 · 공백 덩어리 → 빈칸 하나 · 대소문자 무시). 원래 글자 자리로 되돌려 자른다.
//   - 찾기는 글 줄(문단 member·번역 줄) 하나 안에서만 — 줄을 넘는 구간은 못 찾음(밑줄 0, 목록 줄은 그대로).
//   - 찾는 말이 여럿이면 앞의 것부터(자동 수정 문체: 제안 글 → 고칠 부분). 빈 말은 건넌다.
//   - 겹치면 먼저 놓인 번호가 이긴다: 뒤 번호는 겹치지 않는 다음 자리를 찾고, 없으면 밑줄 0.
//   - 한 번호는 한 자리에만(처음 맞은 줄의 처음 자리).
import { normalizeText } from './pdfAttach.ts';

export type MarkKind = 'issue' | 'term';

export interface MarkTag {
  kind: MarkKind;
  /** 목록 줄 번호(1부터). */
  n: number;
}

export interface MarkWant {
  /** 찾는 말(앞의 것부터). */
  needles: readonly string[];
  mark: MarkTag;
}

/** 글 줄 하나의 조각. mark 가 있으면 밑줄 + 번호. */
export interface MarkPiece {
  text: string;
  mark?: MarkTag;
}

export interface Marked {
  /** 줄마다 조각(이어 붙이면 원래 줄). */
  lines: MarkPiece[][];
  /** want 마다 맞은 말의 자리(needles 의 몇째) — null = 못 찾음. */
  hits: (number | null)[];
}

/** 정규화한 글과 그 글자마다의 원래 자리. */
function normalizedWithMap(text: string): { norm: string; at: number[] } {
  let norm = '';
  const at: number[] = [];
  let space = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i]!;
    if (/\s/.test(ch)) {
      space = norm.length > 0;
      continue;
    }
    if (space) {
      norm += ' ';
      at.push(i - 1);
      space = false;
    }
    const lower = ch.toLowerCase();
    norm += lower.length === 1 ? lower : ch;
    at.push(i);
  }
  return { norm, at };
}

interface Span {
  line: number;
  start: number;
  end: number;
  mark: MarkTag;
}

export function marksOf(
  lines: readonly string[],
  wants: readonly MarkWant[],
): Marked {
  const maps = lines.map(normalizedWithMap);
  const spans: Span[] = [];
  const free = (line: number, start: number, end: number) =>
    spans.every(
      (span) => span.line !== line || end <= span.start || start >= span.end,
    );
  const hits = wants.map((want) => {
    for (let k = 0; k < want.needles.length; k += 1) {
      const wanted = normalizeText(want.needles[k]!);
      if (wanted === '') continue;
      for (let line = 0; line < maps.length; line += 1) {
        const { norm, at } = maps[line]!;
        let from = norm.indexOf(wanted);
        while (from >= 0) {
          const start = at[from]!;
          const end = at[from + wanted.length - 1]! + 1;
          if (free(line, start, end)) {
            spans.push({ line, start, end, mark: want.mark });
            return k;
          }
          from = norm.indexOf(wanted, from + 1);
        }
      }
    }
    return null;
  });
  const pieces = lines.map((text, line) => {
    const mine = spans
      .filter((span) => span.line === line)
      .sort((a, b) => a.start - b.start);
    const out: MarkPiece[] = [];
    let cursor = 0;
    for (const span of mine) {
      if (span.start > cursor)
        out.push({ text: text.slice(cursor, span.start) });
      out.push({ text: text.slice(span.start, span.end), mark: span.mark });
      cursor = span.end;
    }
    if (cursor < text.length || out.length === 0)
      out.push({ text: text.slice(cursor) });
    return out;
  });
  return { lines: pieces, hits };
}

/**
 * 고른 짝의 이슈·용어 → 번역 글·원문 글의 밑줄(W1·W2). 번호 = 이슈 1..k, 이어서 용어 k+1..
 * 자동 수정 문체면 이슈는 제안 글을 먼저 찾고 없으면 고칠 부분. fixed[i] = 자동 수정 문체이고 제안 글이 번역에서 찾아짐(「자동 수정에서 고쳤어요」).
 */
export function pairMarksOf(
  pair: { source: readonly string[]; translation: readonly string[] | null },
  issues: readonly { span: string; suggestion: string }[],
  terms: readonly { ko: string }[],
  stage: 'autofix' | 'translated' | null,
): {
  source: MarkPiece[][];
  translation: MarkPiece[][] | null;
  fixed: boolean[];
} {
  const autofix = stage === 'autofix';
  const translation =
    pair.translation === null ?
      null
    : marksOf(
        pair.translation,
        issues.map((issue, i) => ({
          needles: autofix ? [issue.suggestion, issue.span] : [issue.span],
          mark: { kind: 'issue' as const, n: i + 1 },
        })),
      );
  const source = marksOf(
    pair.source,
    terms.map((term, i) => ({
      needles: [term.ko],
      mark: { kind: 'term' as const, n: issues.length + i + 1 },
    })),
  );
  return {
    source: source.lines,
    translation: translation?.lines ?? null,
    fixed: issues.map(
      (_, i) =>
        autofix &&
        translation !== null &&
        translation.hits[i] === 0 &&
        normalizeText(issues[i]!.suggestion) !== '',
    ),
  };
}
