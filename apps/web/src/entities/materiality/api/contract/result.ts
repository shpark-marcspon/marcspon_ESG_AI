// materiality.result@2 의 zod 거울(밴드 IRW1 ①). 정본: apps/api-py/esgapi/materiality/tests/data/flow-shapes/materiality.result@2.schema.json
// (contracts/shapes.py:392-655). 들어가는 객체는 칸 전부를 거울로 두고 모르는 키를 거절한다(strict — 계약의 extra="forbid"), 맨 위는
// 버리고 통과(strip — 데이터 검증 contract/result.ts 꼴). 갈래는 판별 칸 status. 경고 code 는 글자 하나(z.string — 모르는 code 로
// 결과를 거절하지 않는다, 발주서 §2-1). 모델 JSON(parsed)·selfCheck 는 JSON 값이면 지난다.
// 지나면 화면 꼴(model/result.ts)로 줄인다 — 서버 message(failure·warnings·not_run)·모델 원문(raw·parsed·parseError)·설정은 버린다.
import { z } from 'zod';

import type {
  MaterialityResult,
  Outcome,
  ResearchStatus,
} from '../../model/index.ts';
import { company, sector } from './input.ts';

const obj = <Shape extends z.ZodRawShape>(shape: Shape) =>
  z.object(shape).strict();

const count = z.int().min(0);
const cell = z.string().nullable();
const json = z.json();
const jsonObject = z.record(z.string(), json);

const failure = obj({
  kind: z.enum([
    'unparsable',
    'budget_exceeded',
    'truncated',
    'refusal',
    'provider_error',
    'timeout',
    'tool_executor_raised',
    'schema_mismatch',
  ]),
  message: z.string(),
});

const scope = obj({
  topicCount: count,
  sector,
  whitelist: z.enum(['cell71', 'cell73']),
  dateRange: z.string(),
  geoScope: z.string(),
  userLocation: z.string(),
  mainLanguage: z.string(),
  latestEventMode: z.boolean(),
});

const promptIds = obj({
  regulation: cell,
  keywords: cell,
  controversy: cell,
});
const part2PromptIds = obj({ impact: cell, financial: cell, pathway: cell });
const part2Settings = obj({
  model: cell,
  maxOutputTokens: count,
  latestEventMode: z.boolean(),
  promptIds: part2PromptIds,
});
const settings = obj({
  model: cell,
  temperature: cell,
  searchContextSize: cell,
  promptIds,
  part2: part2Settings,
});

const topicKeywords = obj({ topic: z.string(), keywords: z.array(z.string()) });
const keywordsDone = obj({
  status: z.literal('done'),
  byTopic: z.array(topicKeywords),
  raw: z.string(),
});
const keywordsFailed = obj({
  status: z.literal('failed'),
  raw: cell,
  failure,
});
const keywordsNotRun = obj({
  status: z.literal('not_run'),
  message: z.string(),
});
const keywords = z.discriminatedUnion('status', [
  keywordsDone,
  keywordsFailed,
  keywordsNotRun,
]);

const regulationItem = obj({
  title: cell,
  summary: cell,
  jurisdiction: cell,
  authority: cell,
  event_date: cell,
  publish_date: cell,
  status: cell,
  primary_url: cell,
  region: cell,
});
const controversyItem = obj({
  title: cell,
  date: cell,
  summary: cell,
  severity: cell,
  status: cell,
  url: cell,
  region: z.null(),
});
const regulationDone = obj({
  status: z.literal('done'),
  parsed: jsonObject,
  items: z.array(regulationItem),
  selfCheck: jsonObject.nullable(),
  topicNameMismatch: z.literal(false),
});
const controversyDone = obj({
  status: z.literal('done'),
  parsed: jsonObject,
  items: z.array(controversyItem),
  selfCheck: jsonObject.nullable(),
  topicNameMismatch: z.boolean(),
});
const outcomeFailed = obj({
  status: z.literal('failed'),
  raw: cell,
  parseError: cell,
  failure,
});
const outcomeNotRun = obj({
  status: z.literal('not_run'),
  message: z.string(),
});
const regulation = z.discriminatedUnion('status', [
  regulationDone,
  outcomeFailed,
  outcomeNotRun,
]);
const controversy = z.discriminatedUnion('status', [
  controversyDone,
  outcomeFailed,
  outcomeNotRun,
]);
const topicResult = obj({
  topic: z.string(),
  description: z.string(),
  keywordStr: cell,
  regulation,
  controversy,
});
const part1 = obj({ keywords, topics: z.array(topicResult) });

const contextItem = obj({ title: cell, summary: cell, url: cell });
const context = obj({
  regulations: z.array(contextItem),
  controversies: z.array(contextItem),
});
const impactRow = obj({
  impactDefinition: cell,
  impactType: cell,
  valueChainActivities: z.array(z.string()),
  context,
});
const financialRow = obj({
  impactDefinition: cell,
  impactType: cell,
  riskType: cell,
  valueChainActivities: z.array(z.string()),
  context,
});
const pathwayRow = obj({
  i: z.int().nullable(),
  impactDefinition: cell,
  impactDriver: cell,
  businessImpact: cell,
  financialImpact: cell,
  impactType: cell,
  riskType: cell,
  context,
});
const part2Failed = obj({
  status: z.literal('failed'),
  raw: cell,
  parseError: cell,
  failure,
});
const done = <Row extends z.ZodType>(row: Row) =>
  obj({ status: z.literal('done'), parsed: jsonObject, rows: z.array(row) });
const impactDone = done(impactRow);
const financialDone = done(financialRow);
const pathwayDone = done(pathwayRow);
const impact = z.discriminatedUnion('status', [
  impactDone,
  part2Failed,
  outcomeNotRun,
]);
const financial = z.discriminatedUnion('status', [
  financialDone,
  part2Failed,
  outcomeNotRun,
]);
const pathway = z.discriminatedUnion('status', [
  pathwayDone,
  part2Failed,
  outcomeNotRun,
]);
const subtopicResult = obj({
  name: z.string(),
  description: z.string(),
  autofilled: z.boolean(),
  impact,
  financial,
  pathway,
});
const part2TopicResult = obj({
  topic: z.string(),
  description: z.string(),
  subtopics: z.array(subtopicResult),
});
const part2Input = obj({ source: z.enum(['result', 'shortlist']) });
const part2Done = obj({
  status: z.literal('done'),
  input: part2Input,
  topics: z.array(part2TopicResult),
});
const part2NotRun = obj({ status: z.literal('not_run'), message: z.string() });
const part2 = z.discriminatedUnion('status', [part2NotRun, part2Done]);

const warning = obj({
  code: z.string(),
  message: z.string(),
  topic: cell,
  phase: z
    .enum([
      'regulation',
      'keywords',
      'controversy',
      'impact',
      'financial',
      'pathway',
      'report',
    ])
    .nullable(),
  subtopic: cell,
});

const top = z.object({
  schemaVersion: z.literal('materiality.result@2'),
  company,
  scope,
  settings,
  part1,
  part2,
  warnings: z.array(warning),
});

/** 고정 스키마의 $defs 이름 → 거울이 둔 칸(계약 시험이 견준다). */
export const MIRRORED_DEFS: Readonly<Record<string, readonly string[]>> =
  Object.fromEntries(
    Object.entries({
      MaterialityCompany: company,
      MaterialityContext: context,
      MaterialityContextItem: contextItem,
      MaterialityControversyDone: controversyDone,
      MaterialityControversyItem: controversyItem,
      MaterialityFailure: failure,
      MaterialityFinancialDone: financialDone,
      MaterialityFinancialRow: financialRow,
      MaterialityImpactDone: impactDone,
      MaterialityImpactRow: impactRow,
      MaterialityKeywordsDone: keywordsDone,
      MaterialityKeywordsFailed: keywordsFailed,
      MaterialityKeywordsNotRun: keywordsNotRun,
      MaterialityOutcomeFailed: outcomeFailed,
      MaterialityOutcomeNotRun: outcomeNotRun,
      MaterialityPart1: part1,
      MaterialityPart2Done: part2Done,
      MaterialityPart2Failed: part2Failed,
      MaterialityPart2Input: part2Input,
      MaterialityPart2NotRun: part2NotRun,
      MaterialityPart2PromptIds: part2PromptIds,
      MaterialityPart2Settings: part2Settings,
      MaterialityPart2TopicResult: part2TopicResult,
      MaterialityPathwayDone: pathwayDone,
      MaterialityPathwayRow: pathwayRow,
      MaterialityPromptIds: promptIds,
      MaterialityRegulationDone: regulationDone,
      MaterialityRegulationItem: regulationItem,
      MaterialityResult2: top,
      MaterialityScope: scope,
      MaterialitySettings2: settings,
      MaterialitySubtopicResult: subtopicResult,
      MaterialityTopicKeywords: topicKeywords,
      MaterialityTopicResult: topicResult,
      MaterialityWarning2: warning,
    }).map(([name, schema]) => [name, Object.keys(schema.shape)]),
  );

const research = (value: { status: ResearchStatus }): ResearchStatus =>
  value.status;
const outcome = <Row, Out>(
  value: { status: 'done'; rows: Row[] } | { status: 'failed' | 'not_run' },
  rowOf: (row: Row) => Out,
): Outcome<Out> =>
  value.status === 'done' ?
    { status: 'done', rows: value.rows.map(rowOf) }
  : { status: value.status };

type RawContext = z.infer<typeof context>;
const contextOf = (value: RawContext) => ({
  regulations: value.regulations.map((item) => ({ ...item })),
  controversies: value.controversies.map((item) => ({ ...item })),
});

/** 결과 거울 — 지나면 화면 꼴로 줄인다. */
export const resultSchema: z.ZodType<MaterialityResult, unknown> =
  top.transform((value): MaterialityResult => ({
    companyName: value.company.name,
    scope: {
      topicCount: value.scope.topicCount,
      sector: value.scope.sector,
      dateRange: value.scope.dateRange,
    },
    part1: value.part1.topics.map((t) => ({
      topic: t.topic,
      regulation: research(t.regulation),
      controversy: research(t.controversy),
    })),
    part2:
      value.part2.status === 'not_run' ?
        { status: 'not_run' }
      : {
          status: 'done',
          topics: value.part2.topics.map((t) => ({
            topic: t.topic,
            subtopics: t.subtopics.map((sub) => ({
              name: sub.name,
              autofilled: sub.autofilled,
              impact: outcome(sub.impact, (row) => ({
                impactDefinition: row.impactDefinition,
                impactType: row.impactType,
                valueChainActivities: [...row.valueChainActivities],
                context: contextOf(row.context),
              })),
              financial: outcome(sub.financial, (row) => ({
                impactDefinition: row.impactDefinition,
                impactType: row.impactType,
                riskType: row.riskType,
                valueChainActivities: [...row.valueChainActivities],
                context: contextOf(row.context),
              })),
              pathway: outcome(sub.pathway, (row) => ({
                i: row.i,
                impactDefinition: row.impactDefinition,
                impactDriver: row.impactDriver,
                businessImpact: row.businessImpact,
                financialImpact: row.financialImpact,
                impactType: row.impactType,
                riskType: row.riskType,
                context: contextOf(row.context),
              })),
            })),
          })),
        },
    warnings: value.warnings.map((w) => ({ code: w.code, topic: w.topic })),
  }));
