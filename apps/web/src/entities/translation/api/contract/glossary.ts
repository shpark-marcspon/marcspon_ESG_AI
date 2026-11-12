// 용어집 엑셀 읽기 답의 zod 거울(밴드 TRW1a ①). 정본: apps/api-py/esgapi/translation/contracts/glossary_shapes.py
// (generated/api.d.ts TranslationGlossaryReadOk | TranslationGlossaryReadRejected — 둘 다 200, 판별 칸 ok).
// 맨 위 객체 둘은 strip, 짝은 strict. 거절의 message(서버 글)는 버린다 — 화면 글은 kind·row 로 config/text.ts 가 짓는다.
import { z } from 'zod';

import { count, obj } from './batch.ts';

export const GLOSSARY_REJECTION_KINDS = [
  'too_large',
  'not_xlsx',
  'unsafe_xlsx',
  'bad_header',
  'empty_cell',
  'not_text',
  'too_long',
  'duplicate_ko',
  'too_many_rows',
  'no_rows',
] as const;
export type GlossaryRejectionKind = (typeof GLOSSARY_REJECTION_KINDS)[number];

export interface GlossaryPair {
  ko: string;
  en: string;
}
export type GlossaryRead =
  | { ok: true; pairs: GlossaryPair[]; rowCount: number }
  | { ok: false; kind: GlossaryRejectionKind; row: number | null };

export const glossaryReadSchema: z.ZodType<GlossaryRead, unknown> = z
  .discriminatedUnion('ok', [
    z.object({
      ok: z.literal(true),
      pairs: z
        .array(obj({ ko: z.string().min(1), en: z.string().min(1) }))
        .min(1)
        .max(500),
      rowCount: count,
    }),
    z.object({
      ok: z.literal(false),
      kind: z.enum(GLOSSARY_REJECTION_KINDS),
      row: z.int().min(1).nullable(),
      message: z.string(),
    }),
  ])
  .transform((value): GlossaryRead =>
    value.ok ?
      { ok: true, pairs: value.pairs, rowCount: value.rowCount }
    : { ok: false, kind: value.kind, row: value.row },
  );
