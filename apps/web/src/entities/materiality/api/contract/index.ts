// 중대성평가 계약 거울의 공개 표면(밴드 IRW1 ①). api 칸 안에서 zod 를 가져오는 자리는 이 폴더뿐이다(app/guards/layers.test.ts).
// 실어댑터(server.ts)가 답을 이 거울로 지키고, 꼴이 어긋나면 거절(rejected)이다 — 목으로 메우지 않는다.
import type { z } from 'zod';

import type { MaterialityInput, MaterialityResult } from '../../model/index.ts';
import { resultEditsSchema } from './edits.ts';
import type { ResultEditsView } from './edits.ts';
import { inputSchema } from './input.ts';
import { resultSchema } from './result.ts';
import { runPageSchema } from './runs.ts';
import type { MaterialityRunPage } from './runs.ts';
import { valueChainReadSchema } from './valueChain.ts';
import type { MaterialityValueChainRead } from './valueChain.ts';

export type { MaterialityRunPage, MaterialityRunRow } from './runs.ts';
export type { ResultEditsView } from './edits.ts';
export type {
  MaterialityValueChainRead,
  MaterialityValueChainReadRow,
} from './valueChain.ts';

export type Parsed<T> = { ok: true; value: T } | { ok: false; issues: string };

function parseWith<T>(
  schema: z.ZodType<T, unknown>,
  value: unknown,
): Parsed<T> {
  const parsed = schema.safeParse(value);
  return parsed.success ?
      { ok: true, value: parsed.data }
    : {
        ok: false,
        issues: parsed.error.issues
          .map(
            (issue) =>
              `${issue.path.map(String).join('.') || '(root)'}: ${issue.message}`,
          )
          .join('; '),
      };
}

export const parseResult = (value: unknown): Parsed<MaterialityResult> =>
  parseWith(resultSchema, value);
export const parseInput = (value: unknown): Parsed<MaterialityInput> =>
  parseWith(inputSchema, value);
export const parseRunPage = (value: unknown): Parsed<MaterialityRunPage> =>
  parseWith(runPageSchema, value);
export const parseValueChainRead = (
  value: unknown,
): Parsed<MaterialityValueChainRead> => parseWith(valueChainReadSchema, value);
export const parseResultEdits = (value: unknown): Parsed<ResultEditsView> =>
  parseWith(resultEditsSchema, value);
