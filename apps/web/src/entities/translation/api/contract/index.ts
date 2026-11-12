// 영문번역 계약 거울의 공개 표면(밴드 TRW1a ①). api 칸 안에서 zod 를 가져오는 자리는 이 폴더뿐이다(app/guards/layers.test.ts).
// 실어댑터(server.ts)가 답을 이 거울로 지키고, 꼴이 어긋나면 거절(rejected)이다 — 목으로 메우지 않는다.
import type { z } from 'zod';

import type {
  TranslationBatchDetail,
  TranslationBatchPage,
  TranslationLayout,
  TranslationResult,
} from '../../model/index.ts';
import { batchDetailSchema, batchPageSchema } from './batch.ts';
import { glossaryReadSchema } from './glossary.ts';
import type { GlossaryRead } from './glossary.ts';
import { layoutSchema } from './layout.ts';
import { resultSchema } from './result.ts';

export { GLOSSARY_REJECTION_KINDS } from './glossary.ts';
export type {
  GlossaryPair,
  GlossaryRead,
  GlossaryRejectionKind,
} from './glossary.ts';

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

export const parseBatchPage = (value: unknown): Parsed<TranslationBatchPage> =>
  parseWith(batchPageSchema, value);
export const parseBatchDetail = (
  value: unknown,
): Parsed<TranslationBatchDetail> => parseWith(batchDetailSchema, value);
export const parseResult = (value: unknown): Parsed<TranslationResult> =>
  parseWith(resultSchema, value);
export const parseGlossaryRead = (value: unknown): Parsed<GlossaryRead> =>
  parseWith(glossaryReadSchema, value);
// translation.layout@1(밴드 TRW6 ① — GET /translation/runs/{id}/layout).
export const parseLayout = (value: unknown): Parsed<TranslationLayout> =>
  parseWith(layoutSchema, value);
