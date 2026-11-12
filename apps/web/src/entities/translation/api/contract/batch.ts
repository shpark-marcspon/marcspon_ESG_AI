// translation.batch@1 · translation.digest@1 의 zod 거울(밴드 TRW1a ①). 정본: apps/api-py/esgapi/translation/tests/data/api-shapes/
// translation.batch@1.schema.json · flow-shapes/translation.digest@1.schema.json(contracts/batch_shapes.py·digest_shapes.py).
// 칸은 스키마의 칸 전부다. 맨 위 객체(묶음·쪽·묶음 하나)는 모르는 키를 버리고 통과시키고(z.object 기본 strip — 그린워싱 D10 꼴:
// 서버가 맨 위에 칸을 더해도 화면이 멈추지 않게), 안쪽 객체는 모르는 키를 거절한다(계약의 extra="forbid").
// 꼴은 model/batch.ts 와 z.ZodType<…> 로 맞춘다. 설명 글의 규칙(round = earlier + 1 등)은 검사하지 않는다.
import { z } from 'zod';

import { SERVER_PARTS, SERVER_REJECTION_KINDS } from '../../model/index.ts';
import type {
  BatchRun,
  ServerBatchPart,
  TranslationBatch,
  TranslationBatchDetail,
  TranslationBatchPage,
  TranslationDigest,
} from '../../model/index.ts';
import { BATCH_KEY_PATTERN } from '../ids.ts';

/** 모르는 키를 거절하는 객체(안쪽 객체). */
export const obj = <Shape extends z.ZodRawShape>(shape: Shape) =>
  z.object(shape).strict();

export const count = z.int().min(0);
export const page = z.int().min(0);
const runId = z.int().min(1);
const time = z.string();
const runStatus = z.enum(['queued', 'processing', 'done', 'failed']);
export const outcome = z.enum(['done', 'partial', 'rejected']);
export const variantLabel = z.enum(['single', 'A', 'B']);
export const serverPart = z.enum(SERVER_PARTS);
export const rejectionKind = z.enum(SERVER_REJECTION_KINDS);
export const severityCounts = obj({ high: count, medium: count, low: count });

const person = obj({ userId: z.int().min(0), name: z.string() });
const fileName = z.string().min(1).nullable();

const digestFiles = obj({
  bilingual: fileName,
  qa: fileName,
  autofix: fileName,
});

const digestVariant = obj({
  label: variantLabel,
  reviewStatus: z.enum(['reviewed', 'call_failed', 'not_run']),
  reviewStoppedAt: page.nullable(),
  parseFailedPages: count,
  issueCount: count,
  issueCounts: severityCounts,
  glossaryMisses: count,
  autofixStatus: z.enum(['done', 'stopped', 'not_run']),
  autofixChangedPages: count,
  files: digestFiles,
});

const digest = obj({
  schemaVersion: z.literal('translation.digest@1'),
  status: z.enum(['done', 'rejected']),
  rejectionKind: rejectionKind.nullable(),
  outcome,
  pageCount: count,
  failedPages: z.array(page),
  variants: z.array(digestVariant),
  warningCount: count,
});
export const digestSchema: z.ZodType<TranslationDigest> = digest;

const pages = obj({ start: z.int().nullable(), end: z.int().nullable() });
const style = obj({ compareAb: z.boolean(), single: z.enum(['A', 'B']) });
const glossaryCounts = obj({ base: count, final: count });
const step = obj({
  step: z.string(),
  status: z.enum(['pending', 'running', 'done', 'failed']),
  done: z.int().nullable(),
  total: z.int().nullable(),
});
const earlier = obj({
  runId,
  status: runStatus,
  createdAt: time,
  finishedAt: time.nullable(),
  outcome: outcome.nullable(),
});

const run = obj({
  runId,
  flowId: z.string(),
  status: runStatus,
  pages: pages.nullable(),
  style: style.nullable(),
  glossaryCounts,
  createdAt: time,
  startedAt: time.nullable(),
  finishedAt: time.nullable(),
  failedStep: z.string().nullable(),
  errorCode: z.string().nullable(),
  steps: z.array(step),
  digest: digestSchema.nullable(),
});
const typedRun: z.ZodType<BatchRun> = run;

const part = obj({
  part: serverPart,
  latest: typedRun,
  earlier: z.array(earlier),
  round: z.int().min(1),
});
const typedPart: z.ZodType<ServerBatchPart> = part;
const batchDocument = obj({
  id: z.int().min(1),
  fileName: z.string(),
  uploadedAt: time.nullable(),
  uploadedBy: person,
});

const batchShape = {
  batchKey: z.string().regex(BATCH_KEY_PATTERN),
  inputKind: z.enum(['word', 'pdf']),
  document: batchDocument,
  createdBy: person,
  parts: z.array(typedPart),
  state: z.enum(['active', 'done', 'failed']),
  doneParts: count,
  partCount: z.int().min(1),
};

/** 서버 칸 document → model 칸 file(model 은 DOM 낱말을 쓰지 않는다 — model/batch.ts). */
const withFile = <T extends { document: TranslationBatch['file'] }>({
  document: file,
  ...rest
}: T) => ({ ...rest, file });

/** 목록 쪽 안의 묶음 하나(안쪽 객체 — 모르는 키 거절). */
const listedBatch = obj(batchShape);
const typedListedBatch: z.ZodType<TranslationBatch, unknown> =
  listedBatch.transform(withFile);

/** 묶음 하나 보기(맨 위 — strip). */
export const batchDetailSchema: z.ZodType<TranslationBatchDetail, unknown> = z
  .object({ ...batchShape, truncated: z.boolean() })
  .transform(withFile);

/** 묶음 목록 한 쪽(맨 위 — strip). */
export const batchPageSchema: z.ZodType<TranslationBatchPage, unknown> =
  z.object({
    companyName: z.string(),
    count,
    isNext: z.boolean(),
    truncated: z.boolean(),
    results: z.array(typedListedBatch),
  });

/** 고정 스키마 파일의 $defs 이름 → 거울 객체(contract.test.ts 가 칸 이름을 견준다 — 공개 표면이 아니다). */
export const MIRRORED_DEFS = {
  DigestFiles: digestFiles,
  DigestVariant: digestVariant,
  SeverityCounts: severityCounts,
  TranslationBatch: listedBatch,
  TranslationBatchDocument: batchDocument,
  TranslationBatchEarlier: earlier,
  TranslationBatchGlossaryCounts: glossaryCounts,
  TranslationBatchPages: pages,
  TranslationBatchPart: part,
  TranslationBatchPerson: person,
  TranslationBatchRun: run,
  TranslationBatchStep: step,
  TranslationBatchStyle: style,
  TranslationDigest: digest,
} as const;
