// 검증 결과 표·요약 셈·계산 식·상태 갈래(밴드 DV2a ① — 발주서 §3-1-6, 디자인 2e ①②③⑥).
import { describe, expect, it } from 'vitest';

import { parseResult } from '../api/contract/index.ts';
import {
  checkLines,
  onlyProblems,
  resultCounts,
  ruleOfTool,
  summarize,
} from './checks.ts';
import type { CheckLine } from './checks.ts';
import { decimalSum, explain } from './explain.ts';
import type { DataverifyResult, YearResult } from './result.ts';
import {
  currentStep,
  failureReason,
  hasNoTarget,
  notices,
  someStageFailed,
  stageState,
  stepViews,
} from './status.ts';
import {
  fakeResult,
  insightDone,
  insightFailed,
  noTargetResult,
  planDone,
  planFailed,
  reviewDone,
  reviewFailed,
} from './testing.ts';

const read = (value: unknown): DataverifyResult => {
  const parsed = parseResult(value);
  if (!parsed.ok) throw new Error(parsed.issues);
  return parsed.value;
};

describe('checkLines · summarize', () => {
  it('판 DV-04 수: 줄 5 · 검산 6곳(맞음 1 + 어긋남 1 + 계산 못 함 4) · 어긋남 1 · 계산 못 함 4(수가 아님 1 · 0 나눔 1 · 도구 2) · 리스크 2', () => {
    const { lines, summary, risks } = resultCounts(read(fakeResult()));
    expect(lines.map((line) => [line.no, line.kind, line.rule])).toEqual([
      [1, 'check', 'sum'],
      [2, 'check', 'sum_n'],
      [3, 'check', 'ratio'],
      [4, 'error', 'sum'],
      [5, 'error', null],
    ]);
    expect(summary).toEqual({
      checks: 5,
      places: 6,
      okYears: 1,
      mismatches: 1,
      uncomputable: 4,
      nonNumeric: 1,
      divisionByZero: 1,
      toolErrors: 2,
      years: 4,
    });
    expect(risks).toBe(2);
  });

  it('검산 곳 = 맞음 + 어긋남 + 계산 못 함 = 연도 칸 + 도구 오류 줄(줄 수와 다름 — 밴드 DV7)', () => {
    const year = (
      verdict: 'ok' | 'mismatch' | 'uncomputable',
      note: 'non-numeric' | 'division by zero' | null = null,
    ) => ({
      year: '2023',
      verdict,
      diff: null,
      note,
      explanation: { kind: 'raw', text: '' } as const,
    });
    const items = {
      rule: 'sum',
      byName: false,
      addends: [],
      target: { kind: 'missing' },
      unit: null,
    } as const;
    const lines: CheckLine[] = [
      {
        no: 1,
        kind: 'check',
        rule: 'sum',
        items,
        years: [year('ok'), year('ok'), year('mismatch')],
      },
      {
        no: 2,
        kind: 'check',
        rule: 'ratio',
        items,
        years: [
          year('uncomputable', 'non-numeric'),
          year('uncomputable', 'division by zero'),
          year('ok'),
        ],
      },
      { no: 3, kind: 'error', rule: 'sum' },
      { no: 4, kind: 'error', rule: null },
      { no: 5, kind: 'check', rule: 'sum_n', items, years: [] },
    ];
    const summary = summarize(lines);
    expect(summary.checks).toBe(5);
    expect(summary.okYears).toBe(3);
    expect(summary.mismatches).toBe(1);
    expect(summary.uncomputable).toBe(4);
    expect(summary.places).toBe(8);
    expect(summary.places).toBe(
      summary.okYears + summary.mismatches + summary.uncomputable,
    );
    expect(summary.places).toBe(summary.years + summary.toolErrors);
    expect(summarize([]).places).toBe(0);
  });

  it('줄의 해: 판정·차이(null 은 그대로)·메모', () => {
    const [sum, sumN, ratio] = checkLines(read(fakeResult()).review);
    expect(sum!.kind === 'check' && sum!.years).toMatchObject([
      { year: '2023', verdict: 'ok', diff: '0.0', note: null },
      { year: '2024', verdict: 'mismatch', diff: '5.0', note: null },
    ]);
    expect(sumN!.kind === 'check' && sumN!.years).toMatchObject([
      { year: null, verdict: 'uncomputable', diff: null, note: 'non-numeric' },
    ]);
    expect(ratio!.kind === 'check' && ratio!.years).toMatchObject([
      { verdict: 'uncomputable', diff: null, note: 'division by zero' },
    ]);
  });

  it('항목: 이름형은 「 | 」로 잇고, 단건은 수·「N/A」(na)', () => {
    const [sum, sumN] = checkLines(read(fakeResult()).review);
    expect(sum!.kind === 'check' && sum!.items).toEqual({
      rule: 'sum',
      byName: true,
      addends: [
        {
          kind: 'text',
          text: '온실가스 배출량 | 직접 배출량 | Scope 1 | tCO2eq',
        },
        {
          kind: 'text',
          text: '온실가스 배출량 | 간접 배출량 | Scope 2 | tCO2eq',
        },
      ],
      target: {
        kind: 'text',
        text: '온실가스 배출량 | 총 배출량 | Scope 1+2 | tCO2eq',
      },
      unit: 'tCO2eq',
    });
    expect(sumN!.kind === 'check' && sumN!.items).toEqual({
      rule: 'sum',
      byName: false,
      addends: [{ kind: 'text', text: '1200.5' }, { kind: 'na' }],
      target: { kind: 'text', text: '1500' },
      unit: null,
    });
  });

  it('대상 단위(밴드 DV10): 이름형 대상의 넷째 칸 · 빈 칸·없음·글 아님 → null', () => {
    const unitOf = (target: unknown) => {
      const [line] = checkLines(
        read(
          fakeResult({
            review: reviewDone(false, [
              {
                seq: 1,
                tool: 'sum_n_check_by_names',
                kind: 'check',
                rule: 'sum_n',
                items: {
                  byName: { addends: [['가', '나', '다', 'kWh']], target },
                  raw: null,
                },
                tolerance: '0.01',
                years: [],
              },
            ]),
          }),
        ).review,
      );
      return line!.kind === 'check' && line!.items.rule === 'sum' ?
          line!.items.unit
        : 'not-sum';
    };
    expect(unitOf(['가', '나', '합', ' kWh '])).toBe('kWh');
    expect(unitOf(['가', '나', '합', ''])).toBeNull();
    expect(unitOf(['가', '나', '합'])).toBeNull();
    expect(unitOf(['가', '나', '합', 3])).toBeNull();
    expect(unitOf('합')).toBeNull();
  });

  it('순번은 보이는 줄의 1..n(seq 아님) — 걸러도 다시 매긴다', () => {
    const lines = checkLines(read(fakeResult()).review);
    const problems = onlyProblems(lines);
    expect(problems.map((line) => line.no)).toEqual([1, 2, 3, 4, 5]);
    expect(problems[0]!.kind === 'check' && problems[0]!.years).toHaveLength(1);
    const allOk = onlyProblems(lines.slice(0, 1));
    expect(allOk).toHaveLength(1);
    const okOnly = read(
      fakeResult({
        review: reviewDone(false, [
          {
            seq: 9,
            tool: 'sum_check',
            kind: 'check',
            rule: 'sum',
            items: { byName: null, raw: { a: 1, b: 2, c: 3 } },
            tolerance: '1.1',
            years: [
              {
                year: null,
                ok: true,
                status: 'OK',
                diff: '0.0',
                note: null,
                explanation:
                  'Sum(1.0 + 2.0) - Target(3.0) = 0.000000 → within tolerance (1.1).',
              },
            ],
          },
        ]),
      }),
    );
    expect(onlyProblems(checkLines(okOnly.review))).toEqual([]);
  });

  it('도구 오류의 규칙은 tool 이름 대응(2e ⑥)', () => {
    expect(ruleOfTool('sum_check')).toBe('sum');
    expect(ruleOfTool('sum_n_check_by_names')).toBe('sum_n');
    expect(ruleOfTool('ratio_check_by_name')).toBe('ratio');
    expect(ruleOfTool('value_of')).toBeNull();
    expect(ruleOfTool('toString')).toBeNull();
  });

  it('리스크: unparsed·실패·돌지 않음은 null(「–」)', () => {
    expect(
      resultCounts(
        read(
          fakeResult({
            insight: insightDone({ rowsParsed: 'unparsed', rows: [] }),
          }),
        ),
      ).risks,
    ).toBeNull();
    expect(
      resultCounts(read(fakeResult({ insight: insightFailed() }))).risks,
    ).toBeNull();
    expect(resultCounts(read(noTargetResult())).risks).toBeNull();
  });
});

const year = (
  explanation: string,
  extra: Partial<YearResult> = {},
): YearResult => ({
  year: '2024',
  ok: false,
  status: 'FAIL',
  diff: '5.0',
  note: null,
  explanation,
  ...extra,
});

describe('explain — 도구 설명 꼴 다섯(tools.py)', () => {
  it('합계', () => {
    expect(
      explain(
        'sum',
        year(
          'Sum(1300.0 + 310.0) - Target(1605.0) = 5.000000 → exceeds tolerance (1.1).',
        ),
      ),
    ).toEqual({
      kind: 'sum',
      addends: ['1300.0', '310.0'],
      target: '1605.0',
      diff: '5.0',
      within: false,
      tolerance: '1.1',
    });
  });

  it('부분합(목록)', () => {
    expect(
      explain(
        'sum_n',
        year(
          'Sum([1.0, 2.5, 1e-05]) - Target(3.5) = 0.000010 → within tolerance (1.1).',
          {
            diff: '1e-05',
          },
        ),
      ),
    ).toEqual({
      kind: 'sum',
      addends: ['1.0', '2.5', '1e-05'],
      target: '3.5',
      diff: '1e-05',
      within: true,
      tolerance: '1.1',
    });
  });

  it('비율', () => {
    expect(
      explain(
        'ratio',
        year(
          'Ratio = 30.0/120.0 × 100 = 25.0000%, Expected ≈ 24.0000%, Diff = 1.0000 → within tolerance (1.1 p.p.).',
          { diff: '1.0' },
        ),
      ),
    ).toEqual({
      kind: 'ratio',
      numerator: '30.0',
      denominator: '120.0',
      percent: '25.0000',
      expected: '24.0000',
      diff: '1.0',
      within: true,
      tolerance: '1.1',
    });
  });

  it('note 둘', () => {
    expect(
      explain(
        'sum_n',
        year('Input values are not numeric.', {
          diff: null,
          note: 'non-numeric',
        }),
      ),
    ).toEqual({ kind: 'non_numeric' });
    expect(
      explain(
        'ratio',
        year('Cannot divide by zero.', {
          diff: null,
          note: 'division by zero',
        }),
      ),
    ).toEqual({ kind: 'division_by_zero' });
  });

  it('꼴 밖은 원문 그대로', () => {
    const odd = 'Something else entirely.';
    expect(explain('sum', year(odd))).toEqual({ kind: 'raw', text: odd });
    expect(
      explain(
        'ratio',
        year(
          'Sum(1.0 + 2.0) - Target(3.0) = 0.000000 → within tolerance (1.1).',
        ),
      ),
    ).toMatchObject({ kind: 'raw' });
    expect(
      explain(
        'sum',
        year('Input values are not numeric.', {
          note: 'non-numeric',
          diff: null,
        }),
      ),
    ).toEqual({ kind: 'non_numeric' });
    expect(
      explain('sum', year('changed text', { note: 'non-numeric', diff: null })),
    ).toMatchObject({ kind: 'raw' });
  });
});

describe('status', () => {
  it('단계 다섯: 서버가 주지 않은 단계는 대기 · n번째', () => {
    const views = stepViews([
      { step: 'load', status: 'done' },
      { step: 'plan', status: 'done' },
      { step: 'review', status: 'running' },
    ]);
    expect(views.map((v) => v.status)).toEqual([
      'done',
      'done',
      'running',
      'pending',
      'pending',
    ]);
    expect(currentStep(views)).toBe(3);
    expect(currentStep(stepViews([]))).toBe(1);
    expect(
      currentStep(
        stepViews(
          ['load', 'plan', 'review', 'insight', 'report'].map((step) => ({
            step,
            status: 'done' as const,
          })),
        ),
      ),
    ).toBe(5);
  });

  it('결과 단계 상태 · 일부 못 함 · 띠 갈래(Plan → 검토 → 인사이트 차례)', () => {
    const base = read(fakeResult());
    expect(stageState(base, 'review')).toBe('partial');
    expect(someStageFailed(base)).toBe(false);
    expect(notices(base)).toEqual(['review_partial']);

    const failed = read(
      fakeResult({
        plan: planFailed('unparsable'),
        review: {
          status: 'not_run',
          partial: null,
          report: null,
          checks: [],
          failure: null,
        },
        insight: insightDone({ partial: true }),
      }),
    );
    expect(stageState(failed, 'plan')).toBe('failed');
    expect(stageState(failed, 'review')).toBe('not_run');
    expect(someStageFailed(failed)).toBe(true);
    expect(notices(failed)).toEqual(['plan_unreadable', 'insight_partial']);

    const call = read(
      fakeResult({
        plan: planDone(true),
        review: reviewFailed('timeout'),
        insight: insightFailed('truncated', '지어낸 부분 원문'),
      }),
    );
    expect(notices(call)).toEqual([
      'plan_partial',
      'review_failed',
      'insight_failed',
    ]);
    expect(
      notices(read(fakeResult({ plan: planFailed('budget_exceeded') })))[0],
    ).toBe('plan_failed');
  });

  it('실패 까닭은 둘(unparsable · 그 밖 일곱)', () => {
    expect(failureReason('unparsable')).toBe('unreadable');
    for (const kind of [
      'budget_exceeded',
      'truncated',
      'refusal',
      'provider_error',
      'timeout',
      'tool_executor_raised',
      'schema_mismatch',
    ] as const)
      expect(failureReason(kind)).toBe('call');
  });

  it('no_target_theme 경고만 「검증할 항목이 없어요」', () => {
    expect(hasNoTarget(read(noTargetResult()))).toBe(true);
    expect(hasNoTarget(read(fakeResult()))).toBe(false);
  });
});

describe('decimalSum — 실제값(더한 값의 합)은 글자 그대로 10진 덧셈(밴드 DV6 ①)', () => {
  it('0.1 + 0.2 = 0.3 정확히(Number 덧셈의 0.30000000000000004 아님)', () => {
    expect(0.1 + 0.2).not.toBe(0.3);
    expect(decimalSum(['0.1', '0.2'])).toBe('0.3');
    expect(decimalSum(['1300.0', '310.0'])).toBe('1610.0');
    expect(decimalSum(['1.0', '2.5', '1e-05'])).toBe('3.50001');
  });

  it('큰 수 · 음수 · 정수 · 빈 목록', () => {
    expect(decimalSum(['9007199254740993.5', '0.5'])).toBe(
      '9007199254740994.0',
    );
    expect(decimalSum(['1e+20', '1.5'])).toBe('100000000000000000001.5');
    expect(decimalSum(['-1.5', '0.25'])).toBe('-1.25');
    expect(decimalSum(['-0.1', '-0.2'])).toBe('-0.3');
    expect(decimalSum(['1', '2'])).toBe('3');
    expect(decimalSum([])).toBe('0');
  });

  it('수가 아닌 글(inf·nan)이 있으면 null', () => {
    expect(decimalSum(['inf', '1.0'])).toBeNull();
    expect(decimalSum(['nan'])).toBeNull();
  });
});
