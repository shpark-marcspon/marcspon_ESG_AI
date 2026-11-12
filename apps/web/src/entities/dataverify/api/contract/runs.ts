// 실행 목록 GET /dataverify/runs 의 zod 거울(밴드 DV2b — DV1g 계약 소비). 꼴은 generated api.d.ts 의 DataverifyRunPage·DataverifyRunRow
// (정본 apps/api-py/esgapi/dataverify/contracts/run_list_shapes.py:35-73 · digest_shapes.py:23-54). 타입은 generated 그대로 쓰고
// 이 파일은 받은 값이 그 꼴인지만 본다. 칸을 더하는 것은 같은 판 안이라(run_list_shapes.py 머리) 모르는 칸은 버리고 지난다.
import { z } from 'zod';

import type { Schemas } from '../../../../shared/api/index.ts';
import { sourceSchema } from './source.ts';

export type DataverifyRunRow = Schemas['DataverifyRunRow'];
export type DataverifyRunPage = Schemas['DataverifyRunPage'];

const count = z.number().int().min(0);
const textOrNull = z.string().nullable();

const stageHead = z.object({
  status: z.enum(['done', 'failed', 'not_run']),
  partial: z.boolean().nullable(),
});

const row = z.object({
  id: z.number().int().min(1),
  status: z.enum(['queued', 'processing', 'done', 'failed']),
  createdAt: z.string(),
  finishedAt: textOrNull,
  createdBy: z.object({ userId: z.number().int().min(1), name: z.string() }),
  source: sourceSchema.nullable(),
  companyName: textOrNull,
  reportingYear: textOrNull,
  itemCount: count.nullable(),
  failedStep: textOrNull,
  currentStep: textOrNull,
  stages: z
    .object({ plan: stageHead, review: stageHead, insight: stageHead })
    .nullable(),
  checks: z
    .object({
      ok: count,
      fail: count,
      notComputed: count,
      naValues: count,
      toolErrors: count,
    })
    .nullable(),
});

const page = z.object({ count, isNext: z.boolean(), results: z.array(row) });

export const runPageSchema: z.ZodType<DataverifyRunPage, unknown> = page;

/** 거울이 보는 칸 이름(contract.test.ts 가 openapi.json 의 칸과 맞춘다). */
export const MIRRORED_LIST: Readonly<Record<string, readonly string[]>> = {
  DataverifyRunPage: Object.keys(page.shape),
  DataverifyRunRow: Object.keys(row.shape),
  DataverifyPerson: Object.keys(row.shape.createdBy.shape),
  DataverifyStageHead: Object.keys(stageHead.shape),
  DataverifyCheckCounts: Object.keys(row.shape.checks.unwrap().shape),
};
