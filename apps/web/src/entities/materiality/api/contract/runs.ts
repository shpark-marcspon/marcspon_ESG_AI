// 실행 목록 GET /materiality/runs 의 zod 거울(밴드 IRW1 ③ — IR3c 계약 소비). 꼴은 generated api.d.ts 의 MaterialityRunPage·MaterialityRunRow
// (정본 apps/api-py/esgapi/materiality/contracts/run_list_shapes.py). 타입은 generated 그대로 쓰고 이 파일은 받은 값이 그 꼴인지만 본다.
// 칸을 더하는 것은 같은 판 안이라(run_list_shapes.py 머리) 모르는 칸은 버리고 지난다(데이터 검증 contract/runs.ts 꼴).
import { z } from 'zod';

import type { Schemas } from '../../../../shared/api/index.ts';

export type MaterialityRunRow = Schemas['MaterialityRunRow'];
export type MaterialityRunPage = Schemas['MaterialityRunPage'];

const count = z.number().int().min(0);
const textOrNull = z.string().nullable();

const industry = z.object({ standard: z.string(), industryName: z.string() });

const row = z.object({
  id: z.number().int().min(1),
  status: z.enum(['queued', 'processing', 'done', 'failed']),
  createdAt: z.string(),
  startedAt: textOrNull,
  finishedAt: textOrNull,
  createdBy: z.object({ userId: z.number().int().min(1), name: z.string() }),
  companyName: textOrNull,
  industries: z.array(industry).nullable(),
  topicCount: count.nullable(),
  dateRange: textOrNull,
  latestEventMode: z.boolean().nullable(),
  currentStep: textOrNull,
  failedStep: textOrNull,
  impactRows: count.nullable(),
  pathwayRows: count.nullable(),
});

const page = z.object({ count, isNext: z.boolean(), results: z.array(row) });

export const runPageSchema: z.ZodType<MaterialityRunPage, unknown> = page;

/** 거울이 보는 칸 이름(contract.test.ts 가 generated 의 칸과 맞춘다). */
export const MIRRORED_LIST: Readonly<Record<string, readonly string[]>> = {
  MaterialityRunPage: Object.keys(page.shape),
  MaterialityRunRow: Object.keys(row.shape),
  MaterialityPerson: Object.keys(row.shape.createdBy.shape),
  MaterialityRunIndustry: Object.keys(industry.shape),
};
