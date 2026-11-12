// translation.result@1 의 zod 거울(밴드 TRW1a ①). 정본: apps/api-py/esgapi/translation/tests/data/flow-shapes/translation.result@1.schema.json
// (contracts/shapes.py). 칸은 스키마의 칸 전부다 — 맨 위 객체 둘(done·rejected)은 모르는 키를 버리고(strip), 안쪽은 거절(strict).
// 판별 칸 status. 지난 값은 화면이 읽는 꼴(model/batch.ts TranslationResult)로 줄여 돌려준다(긴 번역 글은 버린다).
import { z } from 'zod';

import type { TranslationResult } from '../../model/index.ts';
import {
  count,
  obj,
  page,
  rejectionKind,
  serverPart,
  severityCounts,
  variantLabel,
} from './batch.ts';

const strings = z.array(z.string());

const settings = obj({
  part: serverPart,
  variants: z.array(variantLabel),
  routes: obj({ translate: z.string(), review: z.string() }),
  promptIds: strings,
  engine: z.literal('colab_158'),
  constants: obj({
    editorialQaMinScore: z.int(),
    tableBatchSize: z.int(),
    polishMinChars: z.int(),
    polishMaxChars: z.int(),
    koreanRepairRounds: z.int(),
    autofixKoreanRepairRounds: z.int(),
  }),
  retry: obj({
    fromRunId: z.int().min(1),
    pages: z.array(page),
    skippedPages: z.array(page),
  }).nullable(),
});

const documentInfo = obj({
  pageNumbers: z.array(page),
  duplicatePages: z.record(z.string(), z.int().min(2)),
  sourceSha256: z.string().regex(/^[0-9a-f]{64}$/),
});

const editorialQa = obj({
  ran: z.boolean(),
  reason: z.enum([
    'skipped_table_or_short_text',
    'skipped_too_long',
    'json_parse_failed',
    'no_revised_text',
    'score_and_issues_acceptable',
    'structure_tag_changed',
    'korean_leftover_increased',
    'revised_text_applied',
  ]),
  qualityScore: z.int().nullable(),
  scoreDefaulted: z.boolean(),
  hasCriticalIssue: z.boolean().nullable(),
  applied: z.boolean(),
  issues: z.unknown(),
});

const fragment = obj({
  pageNum: page,
  status: z.enum(['translated', 'error']),
  error: z.string().nullable(),
  editorialQa: editorialQa.nullable(),
  remainingKorean: strings,
});

const issue = obj({
  issueType: z.string(),
  severity: z.string(),
  originalSpan: z.string(),
  suggestion: z.string(),
  reason: z.string(),
  source: z.enum(['model', 'glossary_rule']),
});

const review = z.discriminatedUnion('status', [
  obj({
    status: z.enum(['reviewed', 'parse_failed']),
    issues: z.array(issue),
    counts: severityCounts,
    message: z.null(),
  }),
  obj({
    status: z.enum(['call_failed', 'not_run']),
    issues: z.array(issue).max(0),
    counts: severityCounts,
    message: z.string().nullable(),
  }),
]);

const resultPage = obj({
  pageNum: page,
  translated: z.string(),
  bilingual: z.string(),
  review,
});

const glossaryMiss = obj({
  pageNum: page,
  termKo: z.string(),
  termEn: z.string(),
  sourceCount: count,
});

const autofixPage = obj({
  pageNum: page,
  changed: z.boolean(),
  reason: z.enum([
    'llm_repair_applied',
    'no_change_needed',
    'table_pipe_signature_changed_safe_current_used',
  ]),
  issueCount: count,
  spanReplacements: z.array(
    obj({
      issueType: z.string(),
      originalSpan: z.string(),
      suggestion: z.string(),
    }),
  ),
  koreanRepairRounds: z.array(
    obj({
      changed: z.boolean(),
      remainingKorean: strings,
      reason: z
        .literal('table_pipe_signature_changed_safe_current_used')
        .nullable(),
    }),
  ),
  remainingKoreanAfter: strings,
});

const autofix = z.discriminatedUnion('status', [
  obj({
    status: z.literal('done'),
    pages: z.array(autofixPage),
    translatedText: z.string(),
    bilingualText: z.string(),
    stop: z.null(),
    notRunReason: z.null(),
  }),
  obj({
    status: z.literal('stopped'),
    pages: z.array(autofixPage).max(0),
    translatedText: z.null(),
    bilingualText: z.null(),
    stop: obj({
      kind: z.enum(['remaining_korean', 'call_failed']),
      pageNum: page,
      remainingKorean: strings,
      message: z.string(),
    }),
    notRunReason: z.null(),
  }),
  obj({
    status: z.literal('not_run'),
    pages: z.array(autofixPage).max(0),
    translatedText: z.null(),
    bilingualText: z.null(),
    stop: z.null(),
    notRunReason: z.enum([
      'disabled',
      'review_stopped',
      'earlier_variant_stopped',
    ]),
  }),
]);

const variant = obj({
  label: variantLabel,
  translatedText: z.string(),
  bilingualText: z.string(),
  fragments: z.array(fragment),
  pages: z.array(resultPage),
  glossaryCheck: z.array(glossaryMiss),
  autofix,
});

const warning = obj({
  code: z.string(),
  message: z.string(),
  pageNum: page.nullable(),
  variant: variantLabel.nullable(),
});

const common = {
  schemaVersion: z.literal('translation.result@1'),
  settings,
  document: documentInfo,
  warnings: z.array(warning),
};

const done = z.object({
  ...common,
  status: z.literal('done'),
  rejection: z.null(),
  variants: z.array(variant).min(1),
});

const rejected = z.object({
  ...common,
  status: z.literal('rejected'),
  rejection: obj({
    kind: rejectionKind,
    message: z.string(),
    pageCount: count.nullable(),
    limit: count.nullable(),
  }),
  variants: z.array(variant).max(0),
});

/** 결과 거울 — 지나면 화면 꼴로 줄인다(서버 message 는 싣지 않는다). */
export const resultSchema: z.ZodType<TranslationResult, unknown> = z
  .discriminatedUnion('status', [done, rejected])
  .transform((value): TranslationResult => {
    const warnings = value.warnings.map(({ code, pageNum, variant: v }) => ({
      code,
      pageNum,
      variant: v,
    }));
    if (value.status === 'rejected')
      return {
        status: 'rejected',
        part: value.settings.part,
        rejection: {
          kind: value.rejection.kind,
          pageCount: value.rejection.pageCount,
          limit: value.rejection.limit,
        },
        warnings,
      };
    return {
      status: 'done',
      part: value.settings.part,
      pageNumbers: value.document.pageNumbers,
      variants: value.variants.map((v) => ({
        label: v.label,
        fragments: v.fragments.map(
          ({ pageNum, status, error, remainingKorean }) => ({
            pageNum,
            status,
            error,
            remainingKorean,
          }),
        ),
        pages: v.pages,
        glossaryCheck: v.glossaryCheck,
        autofix: {
          status: v.autofix.status,
          pages: v.autofix.pages.map(({ pageNum, changed }) => ({
            pageNum,
            changed,
          })),
          notRunReason: v.autofix.notRunReason,
        },
      })),
      warnings,
    };
  });
