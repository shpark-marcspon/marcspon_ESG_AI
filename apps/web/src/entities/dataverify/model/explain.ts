// 검사 한 해의 「계산 식」 풀이(밴드 DV2a ①, Q7 (가) · 디자인 2e DV2a-design-text.md ①).
// 도구의 explanation 은 꼴이 정해진 영어 한 줄이다(apps/api-py/esgapi/dataverify/engines/colab_156/tools.py — 합계 :46-47, 부분합 :73,
//   비율 :123-127 의 f-string 셋과 note 둘 :40·:105). 그 꼴을 읽어 수만 꺼내고, 글은 문구 표(config/text.ts)가 짓는다.
// 차이는 years[].diff 칸 값을 쓰고(2e ①), 그 밖의 수는 설명 글의 글자 그대로다. 꼴에 맞지 않으면 원문(raw) — 번역하지 않는다.
import type { CheckRule, YearResult } from './result.ts';

export type Explanation =
  | {
      kind: 'sum';
      addends: readonly string[];
      target: string;
      diff: string;
      within: boolean;
      tolerance: string;
    }
  | {
      kind: 'ratio';
      numerator: string;
      denominator: string;
      percent: string;
      expected: string;
      diff: string;
      within: boolean;
      tolerance: string;
    }
  | { kind: 'non_numeric' }
  | { kind: 'division_by_zero' }
  | { kind: 'raw'; text: string };

const NUM = String.raw`-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?|-?inf|nan`;
const SUM = new RegExp(
  String.raw`^Sum\((${NUM}) \+ (${NUM})\) - Target\((${NUM})\) = (${NUM}) → (within|exceeds) tolerance \((.+)\)\.$`,
);
const SUM_N = new RegExp(
  String.raw`^Sum\(\[((?:${NUM})(?:, (?:${NUM}))*)?\]\) - Target\((${NUM})\) = (${NUM}) → (within|exceeds) tolerance \((.+)\)\.$`,
);
const RATIO = new RegExp(
  String.raw`^Ratio = (${NUM})/(${NUM}) × 100 = (${NUM})%, Expected ≈ (${NUM})%, Diff = (${NUM}) → (within|exceeds) tolerance \((.+) p\.p\.\)\.$`,
);
const NON_NUMERIC = 'Input values are not numeric.';
const DIVISION_BY_ZERO = 'Cannot divide by zero.';

/** 검사 한 해의 풀이. 꼴 밖이면 raw(원문). */
export function explain(rule: CheckRule, year: YearResult): Explanation {
  const text = year.explanation;
  const raw = { kind: 'raw', text } as const;
  if (year.note === 'non-numeric')
    return text === NON_NUMERIC ? { kind: 'non_numeric' } : raw;
  if (year.note === 'division by zero')
    return text === DIVISION_BY_ZERO ? { kind: 'division_by_zero' } : raw;
  if (year.diff === null) return raw;
  const diff = year.diff;
  if (rule === 'sum') {
    const m = SUM.exec(text);
    if (!m) return raw;
    return {
      kind: 'sum',
      addends: [m[1]!, m[2]!],
      target: m[3]!,
      diff,
      within: m[5] === 'within',
      tolerance: m[6]!,
    };
  }
  if (rule === 'sum_n') {
    const m = SUM_N.exec(text);
    if (!m) return raw;
    return {
      kind: 'sum',
      addends: m[1] === undefined ? [] : m[1].split(', '),
      target: m[2]!,
      diff,
      within: m[4] === 'within',
      tolerance: m[5]!,
    };
  }
  const m = RATIO.exec(text);
  if (!m) return raw;
  return {
    kind: 'ratio',
    numerator: m[1]!,
    denominator: m[2]!,
    percent: m[3]!,
    expected: m[4]!,
    diff,
    within: m[6] === 'within',
    tolerance: m[7]!,
  };
}

const DECIMAL = /^(-?)(\d*)(?:\.(\d*))?(?:e([+-]?\d+))?$/;

/** 수 글 하나 → (부호 붙은 자릿수, 소수 자리 수). 꼴 밖(inf·nan 등)이면 null. */
function digitsOf(text: string): { digits: bigint; scale: number } | null {
  const m = DECIMAL.exec(text);
  if (!m || (m[2] === '' && (m[3] ?? '') === '')) return null;
  const whole = m[2]!;
  const frac = m[3] ?? '';
  const exp = m[4] === undefined ? 0 : Number(m[4]);
  let scale = frac.length - exp;
  let body = whole + frac;
  if (scale < 0) {
    body += '0'.repeat(-scale);
    scale = 0;
  }
  const digits = BigInt(body === '' ? '0' : body);
  return { digits: m[1] === '-' ? -digits : digits, scale };
}

/**
 * 더한 값들의 합(실제값 — 밴드 DV6 ①). 글자 그대로 10진 덧셈이다(소수 자리를 맞춰 BigInt) —
 * Number 덧셈의 0.1 + 0.2 = 0.30000000000000004 꼴을 화면에 내지 않는다. 소수가 있던 합은 소수 한 자리 이상을 남긴다
 * (1.0 + 2.0 = 3.0 — repr(float) 꼴). 수가 아닌 글(inf·nan)이 하나라도 있으면 null.
 */
export function decimalSum(addends: readonly string[]): string | null {
  const parts = addends.map(digitsOf);
  if (parts.some((part) => part === null)) return null;
  const nums = parts as { digits: bigint; scale: number }[];
  const scale = Math.max(0, ...nums.map((part) => part.scale));
  const total = nums.reduce(
    (sum, part) => sum + part.digits * 10n ** BigInt(scale - part.scale),
    0n,
  );
  const negative = total < 0n;
  const body = (negative ? -total : total).toString().padStart(scale + 1, '0');
  const whole = body.slice(0, body.length - scale);
  const frac = body.slice(body.length - scale).replace(/0+$/, '');
  const decimals = addends.some((text) => /[.e]/.test(text));
  const text =
    frac !== '' ? `${whole}.${frac}`
    : decimals ? `${whole}.0`
    : whole;
  return negative ? `-${text}` : text;
}
