// 검증 결과 표(판 DV-04)의 줄과 요약 칸 넷의 셈(밴드 DV2a ① · 디자인 2e DV2a-design-text.md ②⑥).
// 표 줄 = review.checks 가운데 kind check(합계·부분합·비율)와 error(도구 오류)뿐, seq 차례. value·search 는 엑셀에만(세지 않는다).
// 순번 = 보이는 줄의 1..n(seq 아님 — 2e ⑥). 해마다: OK → 맞음, FAIL·note 없음 → 어긋남, note 있음 → 계산 못 함.
// 요약: 검산 n곳 = 맞음 + 어긋남 + 계산 못 함(연도 칸 하나·도구 오류 줄 하나가 한 곳 — 시안 v212 DV-03·04·04a r2, 밴드 DV7) ·
//   줄 수(checks)는 셈에만 남긴다 · 맞음 a = OK 인 해 · 어긋남 b = FAIL·note null 인 해 · 계산 못 함 = note 있는 해 + error 줄
//   (갈래 수: 수가 아닌 값·0으로 나눔·도구가 답을 못 냄) · 리스크 = insight.rows 수(unparsed·실패·돌지 않음은 null — 「–」).
// 도구 오류 줄의 규칙은 tool 이름 대응(2e ⑥), 모르는 도구는 null(「–」). 항목은 모델이 준 인자 그대로를 꺼내 글로 잇는다
//   (이름형은 [대분류, 중분류, 소분류, 단위] 를 잇고, 단건은 수·「N/A」 — 「N/A」 는 na 로).
import { explain } from './explain.ts';
import type { Explanation } from './explain.ts';
import { pyNumber } from './options.ts';
import type {
  Check,
  CheckRule,
  DataverifyResult,
  InsightStage,
  ReviewStage,
  YearNote,
} from './result.ts';

export type Verdict = 'ok' | 'mismatch' | 'uncomputable';

/** 항목 칸의 한 조각: 글(이름형은 「 | 」로 이은 것) · na(「N/A」 — 값 없음) · missing(모델이 주지 않음). */
export type Term =
  { kind: 'text'; text: string } | { kind: 'na' } | { kind: 'missing' };

/** 항목 칸: 규칙마다 쓰는 자리(이름형·단건). */
export type ItemsView =
  | {
      rule: 'sum';
      byName: boolean;
      addends: readonly Term[];
      target: Term;
      /** 대상 항목의 단위(이름형 대상 [대분류, 중분류, 소분류, 단위] 의 넷째 칸 — [보기] 차이 뒤, 밴드 DV10). 단건·빈 칸은 null. */
      unit: string | null;
    }
  | {
      rule: 'ratio';
      byName: boolean;
      numerator: Term;
      denominator: Term;
      expected: Term;
    };

export interface YearLine {
  /** 연도 글(모델이 준 인자 — 단건 도구는 null). */
  year: string | null;
  verdict: Verdict;
  diff: string | null;
  note: YearNote | null;
  explanation: Explanation;
}

export type CheckLine =
  | {
      no: number;
      kind: 'check';
      rule: CheckRule;
      items: ItemsView;
      years: readonly YearLine[];
    }
  | { no: number; kind: 'error'; rule: CheckRule | null };

export interface CheckSummary {
  /** 표 줄 수(검사 도구 호출 — 화면 글에는 쓰지 않는다). */
  checks: number;
  /** 검산 n곳 = okYears + mismatches + uncomputable(= years + toolErrors, 밴드 DV7). */
  places: number;
  okYears: number;
  mismatches: number;
  /** 계산 못 함 n회와 갈래. */
  uncomputable: number;
  nonNumeric: number;
  divisionByZero: number;
  toolErrors: number;
  /** 보이는 해의 수(실패 전까지 「연도 m개」). */
  years: number;
}

const TOOL_RULES: Readonly<Record<string, CheckRule>> = {
  sum_check: 'sum',
  sum_check_by_name: 'sum',
  sum_n_check: 'sum_n',
  sum_n_check_by_names: 'sum_n',
  ratio_check: 'ratio',
  ratio_check_by_name: 'ratio',
};

/** 도구 이름 → 규칙(모르면 null). */
export const ruleOfTool = (tool: string): CheckRule | null =>
  Object.hasOwn(TOOL_RULES, tool) ? TOOL_RULES[tool]! : null;

const NA = 'N/A';

/** JSON 값 하나를 글로(글자 그대로·수는 서버가 적는 꼴·그 밖은 JSON). */
function textOf(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return pyNumber(value);
  return JSON.stringify(value) ?? '';
}

/** 이름형 항목([대분류, 중분류, 소분류, 단위]) → 「 | 」로 이은 글. */
function nameTerm(value: unknown): Term {
  if (value === undefined) return { kind: 'missing' };
  if (Array.isArray(value))
    return { kind: 'text', text: value.map(textOf).join(' | ') };
  return { kind: 'text', text: textOf(value) };
}

/** 단건 인자 → 수 글(「N/A」 는 na). */
function rawTerm(value: unknown): Term {
  if (value === undefined) return { kind: 'missing' };
  if (value === NA) return { kind: 'na' };
  return { kind: 'text', text: textOf(value) };
}

/** 이름형 대상 인자의 단위 칸(넷째) — 글이 아니거나 비면 null(밴드 DV10). */
function unitOf(value: unknown): string | null {
  if (!Array.isArray(value)) return null;
  const unit: unknown = value[3];
  if (typeof unit !== 'string') return null;
  const trimmed = unit.trim();
  return trimmed === '' ? null : trimmed;
}

function itemsOf(check: Extract<Check, { kind: 'check' }>): ItemsView {
  const byName = check.items.byName !== null;
  const args = check.items.byName ?? check.items.raw ?? {};
  const term = byName ? nameTerm : rawTerm;
  const list = (value: unknown): Term[] =>
    Array.isArray(value) ? value.map(term) : [term(value)];
  if (check.rule === 'ratio')
    return byName ?
        {
          rule: 'ratio',
          byName,
          numerator: term(args.numerator),
          denominator: term(args.denominator),
          expected: term(args.expected),
        }
      : {
          rule: 'ratio',
          byName,
          numerator: term(args.d),
          denominator: term(args.e),
          expected: term(args.f),
        };
  if (check.rule === 'sum_n')
    return {
      rule: 'sum',
      byName,
      addends: args.addends === undefined ? [] : list(args.addends),
      target: term(args.target),
      unit: byName ? unitOf(args.target) : null,
    };
  return byName ?
      {
        rule: 'sum',
        byName,
        addends: [term(args.a), term(args.b)],
        target: term(args.total),
        unit: unitOf(args.total),
      }
    : {
        rule: 'sum',
        byName,
        addends: [term(args.a), term(args.b)],
        target: term(args.c),
        unit: null,
      };
}

const verdictOf = (status: 'OK' | 'FAIL', note: YearNote | null): Verdict =>
  note !== null ? 'uncomputable'
  : status === 'OK' ? 'ok'
  : 'mismatch';

/** 표 줄(check·error 만, seq 차례, 순번 1..n). */
export function checkLines(review: ReviewStage): CheckLine[] {
  const shown = review.checks
    .filter((check) => check.kind === 'check' || check.kind === 'error')
    .sort((a, b) => a.seq - b.seq);
  return shown.map((check, index): CheckLine => {
    const no = index + 1;
    if (check.kind !== 'check')
      return { no, kind: 'error', rule: ruleOfTool(check.tool) };
    return {
      no,
      kind: 'check',
      rule: check.rule,
      items: itemsOf(check),
      years: check.years.map((year) => ({
        year: year.year === null ? null : textOf(year.year),
        verdict: verdictOf(year.status, year.note),
        diff: year.diff,
        note: year.note,
        explanation: explain(check.rule, year),
      })),
    };
  });
}

/** 요약 칸의 셈(2e ②). */
export function summarize(lines: readonly CheckLine[]): CheckSummary {
  const summary: CheckSummary = {
    checks: lines.length,
    places: 0,
    okYears: 0,
    mismatches: 0,
    uncomputable: 0,
    nonNumeric: 0,
    divisionByZero: 0,
    toolErrors: 0,
    years: 0,
  };
  for (const line of lines) {
    if (line.kind === 'error') {
      summary.toolErrors += 1;
      continue;
    }
    for (const year of line.years) {
      summary.years += 1;
      if (year.verdict === 'ok') summary.okYears += 1;
      else if (year.verdict === 'mismatch') summary.mismatches += 1;
      else if (year.note === 'non-numeric') summary.nonNumeric += 1;
      else summary.divisionByZero += 1;
    }
  }
  summary.uncomputable =
    summary.nonNumeric + summary.divisionByZero + summary.toolErrors;
  summary.places = summary.okYears + summary.mismatches + summary.uncomputable;
  return summary;
}

/** 리스크 n건 — 표로 나눈 인사이트만(unparsed·실패·돌지 않음은 null). */
export const riskCount = (insight: InsightStage): number | null =>
  insight.status === 'done' && insight.rowsParsed !== 'unparsed' ?
    insight.rows.length
  : null;

/** 결과 하나의 셈 묶음(DV-03 끝남 카드·DV-04 요약). */
export function resultCounts(result: DataverifyResult) {
  const lines = checkLines(result.review);
  return { lines, summary: summarize(lines), risks: riskCount(result.insight) };
}

/** 어긋남·계산 못 함만 거른 줄(맞음 해를 빼고, 남은 해가 없는 줄은 뺀다). 순번은 보이는 줄의 1..n 으로 다시 매긴다(2e ⑥). */
export function onlyProblems(lines: readonly CheckLine[]): CheckLine[] {
  return lines
    .flatMap((line): CheckLine[] => {
      if (line.kind === 'error') return [line];
      const years = line.years.filter((year) => year.verdict !== 'ok');
      return years.length === 0 ? [] : [{ ...line, years }];
    })
    .map((line, index) => ({ ...line, no: index + 1 }));
}
