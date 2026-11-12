// greenwash.result@1 의 zod 거울(밴드 FW2 ① [N8]). 정본: apps/api-py/esgapi/greenwash/tests/data/flow-shapes/greenwash.result@1.schema.json
// (contracts/shapes.py, main ee18aaa). 칸은 스키마 파일의 칸 전부다. 맨 위 객체(scanResult·dryRunResult)만 모르는 키를 버리고 통과시키고
// (zod 4 의 z.object 기본 strip — 결함 D10: 서버가 맨 위에 칸을 더해도 화면이 「꼴 오류」로 멈추지 않게. 밴드 WC1 ①),
// 안쪽 객체는 모두 모르는 키를 거절한다(계약의 extra="forbid" — 아래 obj). 필수 칸이 없거나 타입이 틀리면 맨 위도 거절이다.
// 두 갈래(ScanResult·DryRunResult)는 dryRun 이 null 이냐로 가른다. 꼴은 model/result.ts 와 z.ZodType<…> 로 맞춘다.
// 거울은 스키마만 옮긴다: 설명 글의 규칙(Low 이면 riskTags = ["선언적 문장"], counts 가 items 를 다시 센 것 등)은 검사하지 않는다.
import { z } from 'zod';

import { LEVELS, RESULT_SHAPE } from '../../model/index.ts';
import type {
  Box,
  GreenwashResult,
  ResultItem,
  Tally,
} from '../../model/index.ts';

/** 모르는 키를 거절하는 객체(이 파일과 review.ts 의 안쪽 객체와 PUT 본문이 이것을 지난다. 맨 위 응답 객체는 z.object). */
export const obj = <Shape extends z.ZodRawShape>(shape: Shape) =>
  z.object(shape).strict();

const page = z.int().min(1);
const count = z.int().min(0);
const strings = z.array(z.string());

const box: z.ZodType<Box> = z.tuple([
  z.number(),
  z.number(),
  z.number(),
  z.number(),
]);

const position = obj({ page, boxes: z.array(box).min(1) });

const source = obj({
  fileName: z.string(),
  sha256: z.string().regex(/^[0-9a-f]{64}$/),
  pageCount: count,
});

const config = obj({
  checker: obj({
    maxCandidatesPerPage: z.int(),
    maxCharsPageText: z.int(),
    evidenceK: z.int(),
    maxCharsPerChunk: z.int(),
    useEvidenceFailopen: z.boolean(),
    maxCharsEvidenceTotal: z.int(),
    reportLevels: strings,
    debug: z.boolean(),
    debugPages: z.int(),
    batchEval: z.boolean(),
    promptVersion: z.string(),
  }),
  chunking: obj({
    chunkSize: z.int(),
    chunkOverlap: z.int(),
    separators: strings,
    normalize: z.boolean(),
    embeddingBatchSize: z.int(),
  }),
  chat: obj({ temperature: z.number(), maxTokens: z.int() }),
});

const models = obj({ chat: z.string(), embedding: z.string() });

const part = obj({ name: z.string(), pages: z.array(page) });

export const resultItemSchema: z.ZodType<ResultItem> = obj({
  page,
  parts: strings,
  sentence: z.string(),
  level: z.enum(LEVELS),
  riskTags: strings,
  confirmedInEvidence: strings,
  missingFields: strings,
  reasonBullets: strings,
  fixParagraph: z.string(),
  evidencePages: z.array(page),
  evidenceInternal: z.string(),
  position: position.nullable(),
  exampleSentence: z.string().nullable(),
});

const candidateStats = obj({
  raw: count,
  hardDropped: count,
  nonEnvDropped: count,
  promoDropped: count,
  tableDropped: count,
  kept: count,
  failedPages: z.array(obj({ page, error: z.string() })),
});

const levelCounts = obj({ High: count, Mid: count, Low: count });

const counts = obj({
  total: count,
  byLevel: levelCounts,
  byPart: z.record(z.string(), levelCounts),
});

const termCount = obj({ term: z.string(), count: z.int().min(1) });

const wordCounts = obj({
  total: z.array(termCount),
  pages: z.array(obj({ page, counts: z.array(termCount) })),
});

const tokens = z.discriminatedUnion('status', [
  obj({
    status: z.literal('measured'),
    encoding: z.string(),
    value: count,
  }),
  obj({
    status: z.literal('unmeasured'),
    encoding: z.string(),
    reason: z.string(),
  }),
]);

const tally: z.ZodType<Tally> = obj({
  requests: count,
  inputChars: count,
  inputTokens: tokens,
});

const byKind = obj({
  detect: tally,
  eval: tally,
  lowOnly: tally,
  repair: tally,
});

const dryRun = obj({
  pagesChecked: count,
  pagesWithText: count,
  pagesTruncated: count,
  chunks: count,
  embeddingIndex: tally,
  ruleCandidates: count,
  lower: obj({
    chat: tally,
    chatByKind: byKind,
    embeddingQueries: tally,
    judged: count,
  }),
  upper: obj({
    chat: tally,
    chatByKind: byKind,
    embeddingQueries: tally,
    outputTokensMax: count,
    evidenceChars: count,
    evidenceCapReached: z.boolean(),
  }),
  perPage: z.array(
    obj({
      page,
      textChars: count,
      truncated: z.boolean(),
      ruleCandidates: count,
      lowerJudged: count,
    }),
  ),
});

const common = {
  schemaVersion: z.literal(RESULT_SHAPE),
  source,
  config,
  models,
  promptVersion: z.string(),
  parts: z.array(part),
  pages: z.array(page),
  extraTerms: z.array(z.string().min(1).max(30)).max(30),
  terms: z.array(z.string().min(1).max(30)).max(1030).optional(),
  wordCounts: wordCounts,
};

const scanResult = z.object({
  ...common,
  items: z.array(resultItemSchema),
  candidateStats: candidateStats,
  counts,
  dryRun: z.null(),
  report: obj({ file: z.literal('greenwash-report.xlsx') }),
});

const dryRunResult = z.object({
  ...common,
  items: z.tuple([]),
  candidateStats: z.null(),
  counts: z.null(),
  dryRun: dryRun,
  report: z.null(),
});

/** greenwash.result@1 거울. */
export const resultSchema: z.ZodType<GreenwashResult> = z.union([
  scanResult,
  dryRunResult,
]);

/**
 * 실패 글을 지을 가지(sid:MARC-ISSUE-133). z.union 은 가지 오류를 「(맨 위): Invalid input」 하나로 접는다.
 * dryRun 이 null 이면 점검 결과, 객체면 시험 실행의 가지로 다시 읽어 틀린 칸을 드러낸다. 그 밖(칸 없음 등)은 null — union 의 글 그대로.
 * 받아들이는 값은 resultSchema 하나가 정한다(이 함수는 글만 짓는다).
 */
export function resultBranchOf(value: unknown): z.ZodType | null {
  if (typeof value !== 'object' || value === null || !('dryRun' in value))
    return null;
  const { dryRun: flag } = value;
  return (
    flag === null ? scanResult
    : typeof flag === 'object' ? dryRunResult
    : null
  );
}
