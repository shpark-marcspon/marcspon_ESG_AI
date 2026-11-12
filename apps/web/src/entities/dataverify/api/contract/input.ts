// dataverify.input@1 의 zod 거울(밴드 DV2a ①). 정본: apps/api-py/esgapi/dataverify/tests/data/flow-shapes/dataverify.input@1.schema.json
// (contracts/shapes.py:57-78). 실행(GET /runs/{id})의 options.input 을 대 본다 — 못 지나면 화면은 입력 칸(기업명 등)을 「–」로 둔다.
// 바깥 둘(입력·company)은 모르는 키를 거절(strict), data 의 꼴은 model/edk.ts 의 isEdkData(항목은 모르는 키를 받는다)를 그대로 쓴다.
import { z } from 'zod';

import { INPUT_SHAPE, isEdkData } from '../../model/index.ts';
import type { DataverifyInput, EdkData } from '../../model/index.ts';

export const company = z
  .object({
    name: z.string(),
    sasbIndustry: z.string(),
    materialTopics: z.array(z.string()),
    reportingYear: z.string().regex(/^[0-9]{4}$/),
  })
  .strict();

const data = z.custom<EdkData>(isEdkData);

export const inputSchema: z.ZodType<DataverifyInput, unknown> = z
  .object({ schemaVersion: z.literal(INPUT_SHAPE), company, data })
  .strict();
