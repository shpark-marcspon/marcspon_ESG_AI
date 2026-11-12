// materiality.input@1 의 zod 거울(밴드 IRW1 ①). 정본: apps/api-py/esgapi/materiality/tests/data/flow-shapes/materiality.input@1.schema.json
// (contracts/shapes.py:94-118). 실행(GET /runs/{id})의 options.input 을 대 본다 — 못 지나면 화면은 머리 칸(기업명·토픽 수)을 「–」로 둔다.
// 객체는 전부 모르는 키를 거절한다(strict — 계약의 extra="forbid"). 토픽 겹침 거절은 서버 몫이라 보지 않는다.
import { z } from 'zod';

import type { MaterialityInput } from '../../model/index.ts';

const obj = <Shape extends z.ZodRawShape>(shape: Shape) =>
  z.object(shape).strict();

export const company = obj({ name: z.string() });
export const industry = obj({
  standard: z.string(),
  industryName: z.string(),
  description: z.string(),
});
export const topic = obj({ topic: z.string(), description: z.string() });
export const subtopic = obj({ name: z.string(), description: z.string() });
export const valueChainRow = obj({
  business_unit: z.string(),
  business_unit_description: z.string(),
  value_chain_stage: z.string(),
  stakeholder: z.string(),
  business_activity: z.string(),
});
export const sector = z.enum(['financial', 'non_financial']);

export const input = obj({
  schemaVersion: z.literal('materiality.input@1'),
  company,
  industries: z.array(industry).min(1),
  topics: z.array(topic).min(1),
  geoScope: z.string(),
  userLocation: z.string().regex(/^[A-Z]{2}$/),
  mainLanguage: z.string(),
  dateRange: z.string(),
  sector,
  latestEventMode: z.boolean(),
  subtopicsByTopic: z.record(z.string(), z.array(subtopic)).nullable(),
  valueChain: z.array(valueChainRow).nullable(),
});

export const inputSchema: z.ZodType<MaterialityInput, unknown> = input;
