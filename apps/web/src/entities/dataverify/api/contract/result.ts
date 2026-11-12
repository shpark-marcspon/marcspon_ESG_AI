// dataverify.result@2 의 zod 거울(밴드 DV2a ①). 정본: apps/api-py/esgapi/dataverify/tests/data/flow-shapes/dataverify.result@2.schema.json
// (contracts/shapes.py). 들어가는 객체는 칸 전부를 거울로 두고 모르는 키를 거절한다(strict — 계약의 extra="forbid"), 맨 위는 버리고
// 통과(strip — 영문번역 contract/result.ts:2 꼴: 서버가 맨 위에 칸을 더해도 화면이 멈추지 않게). 갈래는 판별 칸(status·kind).
// 지나면 화면 꼴(model/result.ts)로 줄인다 — 서버 message(failure·warnings·error 기록)·모델 원문(plan.raw)·설정의 모델 이름은 버린다.
import { z } from 'zod';

import { FAILURE_KINDS, k } from '../../model/index.ts';
import type {
  Check,
  DataverifyResult,
  FailureKind,
  InsightStage,
  PlanStage,
  ReviewStage,
} from '../../model/index.ts';
import { company } from './input.ts';

/** 모르는 키를 거절하는 객체(안쪽 객체). */
const obj = <Shape extends z.ZodRawShape>(shape: Shape) =>
  z.object(shape).strict();

const count = z.int().min(0);
const seq = z.int().min(1);
const json = z.json();

const failure = obj({
  kind: z.enum(FAILURE_KINDS as [FailureKind, ...FailureKind[]]),
  budgetSource: z.enum(['guard', 'loop']).nullable(),
  message: z.string(),
});

const scope = obj({
  themes: z.array(z.string()),
  itemCount: count,
  keyItemCount: count,
  years: z.array(z.string()),
});

const nullableInt = z.int().nullable();
const nullableText = z.string().nullable();
const settings = obj({
  model: nullableText,
  tolerance: z.string(),
  temperature: nullableText,
  maxSteps: obj({
    plan: nullableInt,
    review: nullableInt,
    insight: nullableInt,
  }),
  promptIds: obj({
    plan: nullableText,
    review: nullableText,
    insight: nullableText,
  }),
});

const empty = <T extends z.ZodType>(item: T) => z.array(item).max(0);

const planDone = obj({
  status: z.literal('done'),
  partial: z.boolean(),
  formulas: z.array(z.string()),
  raw: z.string(),
  failure: z.null(),
});
const planFailed = obj({
  status: z.literal('failed'),
  partial: z.null(),
  formulas: empty(z.string()),
  raw: nullableText,
  failure,
});
const planNotRun = obj({
  status: z.literal('not_run'),
  partial: z.null(),
  formulas: empty(z.string()),
  raw: z.null(),
  failure: z.null(),
});
const plan = z.discriminatedUnion('status', [planDone, planFailed, planNotRun]);

const byNameItems = obj({
  total: json.optional(),
  a: json.optional(),
  b: json.optional(),
  addends: json.optional(),
  target: json.optional(),
  numerator: json.optional(),
  denominator: json.optional(),
  expected: json.optional(),
});
const rawItems = obj({
  a: json.optional(),
  b: json.optional(),
  c: json.optional(),
  d: json.optional(),
  e: json.optional(),
  f: json.optional(),
  addends: json.optional(),
  target: json.optional(),
});
const checkItems = obj({
  byName: byNameItems.nullable(),
  raw: rawItems.nullable(),
});

const yearResult = obj({
  year: json,
  ok: z.boolean(),
  status: z.enum(['OK', 'FAIL']),
  diff: nullableText,
  note: z.enum(['non-numeric', 'division by zero']).nullable(),
  explanation: z.string(),
});

const valueCheck = obj({
  seq,
  tool: z.string(),
  kind: z.literal('value'),
  item: z.array(json).length(4),
  year: json,
  value: nullableText,
  na: z.boolean(),
});
const ruleCheck = obj({
  seq,
  tool: z.string(),
  kind: z.literal('check'),
  rule: z.enum(['sum', 'sum_n', 'ratio']),
  items: checkItems,
  tolerance: nullableText,
  years: z.array(yearResult),
});
const searchFilter = obj({
  [k(0xb300, 0xbd84, 0xb958)]: json.optional(), // 대분류
  [k(0xc911, 0xbd84, 0xb958)]: json.optional(), // 중분류
  [`${k(0xc18c, 0xbd84, 0xb958)}_contains`]: json.optional(), // 소분류_contains
});
const searchCheck = obj({
  seq,
  tool: z.string(),
  kind: z.literal('search'),
  filter: searchFilter,
  total: count,
  limit: json,
  offset: json,
  returned: count,
});
const errorCheck = obj({
  seq,
  tool: z.string(),
  kind: z.literal('error'),
  message: z.string(),
  args: json,
});
const check = z.discriminatedUnion('kind', [
  valueCheck,
  ruleCheck,
  searchCheck,
  errorCheck,
]);

const reviewDone = obj({
  status: z.literal('done'),
  partial: z.boolean(),
  report: z.string(),
  checks: z.array(check),
  failure: z.null(),
});
const reviewFailed = obj({
  status: z.literal('failed'),
  partial: z.null(),
  report: z.null(),
  checks: z.array(check),
  failure,
});
const reviewNotRun = obj({
  status: z.literal('not_run'),
  partial: z.null(),
  report: z.null(),
  checks: empty(check),
  failure: z.null(),
});
const review = z.discriminatedUnion('status', [
  reviewDone,
  reviewFailed,
  reviewNotRun,
]);

const insightRow = obj({
  area: z.string(),
  indicator: z.string(),
  observation: z.string(),
  risk: z.string(),
  interpretation: z.string(),
});
const webSource = obj({ title: nullableText, url: z.string() });

const insightDone = obj({
  status: z.literal('done'),
  partial: z.boolean(),
  report: z.string(),
  rows: z.array(insightRow),
  rowsParsed: z.enum(['parsed', 'unparsed', 'none']),
  sources: z.array(webSource),
  failure: z.null(),
});
const insightFailed = obj({
  status: z.literal('failed'),
  partial: z.null(),
  report: z.null(),
  rows: empty(insightRow),
  rowsParsed: z.literal('none'),
  sources: empty(webSource),
  failure,
  partialText: nullableText,
});
const insightNotRun = obj({
  status: z.literal('not_run'),
  partial: z.null(),
  report: z.null(),
  rows: empty(insightRow),
  rowsParsed: z.literal('none'),
  sources: empty(webSource),
  failure: z.null(),
});
const insight = z.discriminatedUnion('status', [
  insightDone,
  insightFailed,
  insightNotRun,
]);

const warning = obj({ code: z.string(), message: z.string() });

const top = z.object({
  schemaVersion: z.literal('dataverify.result@2'),
  company,
  scope,
  settings,
  plan,
  review,
  insight,
  warnings: z.array(warning),
});

/** 고정 스키마의 $defs 이름 → 거울이 둔 칸(계약 시험이 견준다). */
export const MIRRORED_DEFS: Readonly<Record<string, readonly string[]>> =
  Object.fromEntries(
    Object.entries({
      Company: company,
      Scope: scope,
      DataverifySettings: settings,
      MaxSteps: settings.shape.maxSteps,
      PromptIds: settings.shape.promptIds,
      Failure: failure,
      PlanDone: planDone,
      PlanFailed: planFailed,
      PlanNotRun: planNotRun,
      ByNameItems: byNameItems,
      RawItems: rawItems,
      CheckItems: checkItems,
      YearResult: yearResult,
      ValueCheck: valueCheck,
      RuleCheck: ruleCheck,
      SearchFilter: searchFilter,
      SearchCheck: searchCheck,
      ErrorCheck: errorCheck,
      DataverifyReviewDone: reviewDone,
      ReviewFailed: reviewFailed,
      ReviewNotRun: reviewNotRun,
      InsightRow: insightRow,
      WebSource: webSource,
      InsightDone: insightDone,
      InsightFailed: insightFailed,
      InsightNotRun: insightNotRun,
      DataverifyWarning: warning,
      DataverifyResult: top,
    }).map(([name, schema]) => [name, Object.keys(schema.shape)]),
  );

type RawCheck = z.infer<typeof check>;
const checkOf = (value: RawCheck): Check => {
  if (value.kind === 'check')
    return {
      kind: 'check',
      seq: value.seq,
      tool: value.tool,
      rule: value.rule,
      items: { byName: value.items.byName, raw: value.items.raw },
      tolerance: value.tolerance,
      years: value.years.map((y) => ({ ...y })),
    };
  return { kind: value.kind, seq: value.seq, tool: value.tool };
};

/** 결과 거울 — 지나면 화면 꼴로 줄인다. */
export const resultSchema: z.ZodType<DataverifyResult, unknown> = top.transform(
  (value): DataverifyResult => {
    const p = value.plan;
    const planOut: PlanStage =
      p.status === 'done' ?
        { status: 'done', partial: p.partial, formulas: p.formulas }
      : p.status === 'failed' ?
        { status: 'failed', failure: { kind: p.failure.kind } }
      : { status: 'not_run' };
    const r = value.review;
    const reviewOut: ReviewStage =
      r.status === 'done' ?
        {
          status: 'done',
          partial: r.partial,
          report: r.report,
          checks: r.checks.map(checkOf),
        }
      : r.status === 'failed' ?
        {
          status: 'failed',
          checks: r.checks.map(checkOf),
          failure: { kind: r.failure.kind },
        }
      : { status: 'not_run', checks: [] };
    const i = value.insight;
    const insightOut: InsightStage =
      i.status === 'done' ?
        {
          status: 'done',
          partial: i.partial,
          report: i.report,
          rows: i.rows,
          rowsParsed: i.rowsParsed,
          sources: i.sources,
        }
      : i.status === 'failed' ?
        {
          status: 'failed',
          failure: { kind: i.failure.kind },
          partialText: i.partialText,
        }
      : { status: 'not_run' };
    return {
      company: value.company,
      scope: value.scope,
      tolerance: value.settings.tolerance,
      plan: planOut,
      review: reviewOut,
      insight: insightOut,
      warnings: value.warnings.map((w) => w.code),
    };
  },
);
