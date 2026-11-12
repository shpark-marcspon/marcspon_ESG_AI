// translation.layout@1 의 zod 거울(밴드 TRW6 ①). 정본: apps/api-py/esgapi/translation/tests/data/flow-shapes/translation.layout@1.schema.json
// (TRS3 §1-2 — `$defs` 이름은 G8 의 TranslationLayout… 접두). 칸은 스키마의 칸 전부다 — 맨 위 객체는 모르는 키를 버리고(strip),
// 안쪽은 거절(strict). 지난 값은 화면 꼴(model/layout.ts)로 줄인다(sha·파서 판은 버린다).
import { z } from 'zod';

import type { TranslationLayout } from '../../model/index.ts';
import { count, obj, page, variantLabel } from './batch.ts';

const box = z.tuple([z.number(), z.number(), z.number(), z.number()]);
const tag = z
  .string()
  .regex(/^(BLOCK|VISUAL|TABLE) [1-9][0-9]*$/)
  .nullable();

const parser = obj({
  name: z.string(),
  version: z.string(),
  layout: z.literal(2),
});
const source = obj({
  pdfSha256: z.string(),
  pageCount: count.nullable(),
  parser: parser.nullable(),
  adapter: z.string(),
});
const layoutPage = obj({
  page,
  width: z.number().min(0),
  height: z.number().min(0),
  textLayer: z.enum(['present', 'none']),
});
const member = obj({
  id: z.string(),
  key: z.string().nullable(),
  kind: z.enum(['heading', 'paragraph', 'table']),
  bbox: box,
  source: z.string(),
});
const cell = obj({
  row: count,
  col: count,
  id: z.string(),
  bbox: box.nullable(),
  source: z.string(),
});
const unit = obj({
  tag,
  page,
  kind: z.enum(['block', 'visual', 'table', 'header', 'footer']),
  members: z.array(member),
  cells: z.array(cell).optional(),
  rows: z.array(count).optional(),
});
const placedCell = obj({ row: count, col: count, text: z.string() });
const placedUnit = obj({
  tag,
  page,
  level: z.enum(['block', 'group', 'cell', 'table', 'source_only', 'missing']),
  translations: z.array(z.string()).nullable(),
  cells: z.array(placedCell).optional(),
});
const unplaced = obj({ page, text: z.string() });
const variant = obj({
  label: variantLabel,
  stage: z.enum(['autofix', 'translated']),
  units: z.array(placedUnit),
  unplaced: z.array(unplaced),
});
const skipped = obj({
  emptyTables: z.array(z.string()),
  imageOnlyPages: z.array(page),
});
const warning = obj({
  code: z.enum([
    'image_only_page',
    'tag_missing',
    'tag_extra',
    'tag_shift',
    'page_missing',
    'length_ratio',
  ]),
  page: page.nullable(),
  tag: z.string().nullable(),
  variant: variantLabel.nullable(),
});

/** 거울의 칸 묶음 — 시험이 고정 파일의 `$defs` 칸 이름과 견준다(이름은 G8 뒤 TranslationLayout… — TRS3 병합, 밴드 TRW6 ④). */
export const LAYOUT_DEFS = {
  TranslationLayout: null,
  TranslationLayoutSource: source,
  TranslationLayoutParser: parser,
  TranslationLayoutPage: layoutPage,
  TranslationLayoutMember: member,
  TranslationLayoutCell: cell,
  TranslationLayoutUnit: unit,
  TranslationLayoutPlacedCell: placedCell,
  TranslationLayoutPlacedUnit: placedUnit,
  TranslationLayoutUnplaced: unplaced,
  TranslationLayoutVariant: variant,
  TranslationLayoutSkipped: skipped,
  TranslationLayoutWarning: warning,
} as const;

const root = z.object({
  schemaVersion: z.literal('translation.layout@1'),
  status: z.enum(['done', 'rejected']),
  sourceSha256: z.string(),
  source,
  pages: z.array(layoutPage),
  units: z.array(unit),
  variants: z.array(variant),
  skipped,
  warnings: z.array(warning),
});

/** 맨 위 칸 이름(시험이 고정 파일의 TranslationLayout 칸과 견준다). */
export const LAYOUT_ROOT_KEYS = Object.keys(root.shape);

export const layoutSchema: z.ZodType<TranslationLayout, unknown> =
  root.transform(
    ({
      status,
      pages,
      units,
      variants,
      skipped,
      warnings,
    }): TranslationLayout => ({
      status,
      pages,
      units,
      variants,
      skipped,
      warnings,
    }),
  );
