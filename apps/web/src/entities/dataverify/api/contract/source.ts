// options.source 의 zod 거울(밴드 DV2b). 정본: apps/api-py/esgapi/dataverify/contracts/options_shapes.py:41·56·65
// (고정 tests/data/flow-shapes/options/dataverify.options@1.schema.json — kind 로 가르고 모르는 열쇠는 거절). 이름 규칙은 model/source.ts.
import { z } from 'zod';

import { isSourceName } from '../../model/index.ts';
import type { InputSource } from '../../model/index.ts';

export const sourceSchema: z.ZodType<InputSource, unknown> = z.union([
  z
    .object({ kind: z.literal('file'), name: z.string().refine(isSourceName) })
    .strict(),
  z.object({ kind: z.literal('paste') }).strict(),
]);
