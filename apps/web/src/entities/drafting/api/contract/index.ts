// 원고작성 계약 거울(밴드 RPW1 ① — 발주서 §1-4 ②). 꼴은 apps/api-py/generated/openapi.json 의 Drafting*·DocumentStatusOut·RunOut 과
//   고정 파일 둘(drafting.bullets@3 · options/drafting.options@2 — openapi 밖)이다. api 칸 안에서 zod 를 가져오는 자리는 이 폴더뿐이다.
// 안쪽 객체는 strict(모르는 칸이면 꼴 틀림), 맨 위는 strip(모르는 칸은 버리고 지난다). 옵션 거울은 나가는 본문이라 맨 위도 strict
//   (서버가 모르는 키를 거절한다 — 고정 파일 additionalProperties false). contract.test.ts 가 칸 이름을 openapi·고정 파일과 견준다.
import { z } from 'zod';

import type {
  DraftingResult,
  OutlineChanges,
  Project,
  ProjectPage,
  RunItem,
  RunOptions,
  RunPage,
} from '../../model/index.ts';

const int = z.number().int();
const id = int.min(1);
const count = int.min(0);
const time = z.string();
const KEY = /^[a-z0-9][a-z0-9-]{0,39}$/;
const key = z.string().regex(KEY);

const runProgress = z
  .object({ step: z.string(), done: count.nullable(), total: count.nullable() })
  .strict();
const runLeaves = z
  .object({
    total: count,
    drafted: count,
    noMaterial: count,
    failed: count,
    notRun: count,
  })
  .strict();
const runItemInner = z
  .object({
    id,
    status: z.enum(['queued', 'processing', 'done', 'failed']),
    createdAt: time,
    finishedAt: time.nullable(),
    outlineId: id.nullable(),
    baseRunId: id.nullable(),
    rebuild: z.array(z.string()),
    progress: runProgress.nullable(),
    rejected: z.boolean().nullable(),
    leaves: runLeaves.nullable(),
  })
  .strict();

const projectRow = z
  .object({
    id,
    name: z.string(),
    year: int,
    createdAt: time,
    hasDocument: z.boolean(),
    documentName: z.string().nullable(),
    outlineId: id.nullable(),
    outlineRevision: int.nullable(),
    latestRun: runItemInner.nullable(),
  })
  .strict();

const outlineNode = z
  .object({
    key: z.string(),
    parentKey: z.string().nullable(),
    depth: int,
    title: z.string(),
    requirement: z.string(),
  })
  .strict();

const projectObject = z.object({
  id,
  name: z.string(),
  year: int,
  createdAt: time,
  createdByUserId: int,
  document: z
    .object({
      documentId: id,
      kind: z.string(),
      attachedAt: time,
      attachedByUserId: int,
    })
    .strict()
    .nullable(),
  outline: z
    .object({
      outlineId: id,
      revision: int,
      sha256: z.string(),
      outline: z.object({ nodes: z.array(outlineNode) }).strict(),
    })
    .strict()
    .nullable(),
  latestRun: runItemInner.nullable(),
});
/** 서버 칸 `document` 를 model 칸 `pdf` 로(model 은 DOM 낱말을 쓰지 않는다). */
const projectSchema: z.ZodType<Project, unknown> = projectObject.transform(
  ({ document, ...rest }) => ({ ...rest, pdf: document }),
);

const projectPageSchema: z.ZodType<ProjectPage, unknown> = z.object({
  count,
  isNext: z.boolean(),
  results: z.array(projectRow),
});

const runPageSchema: z.ZodType<RunPage, unknown> = z.object({
  count,
  isNext: z.boolean(),
  results: z.array(runItemInner),
});

const runItemSchema: z.ZodType<RunItem, unknown> = runItemInner;

/** confirm 답(DocumentStatusOut)에서 쓰는 칸만 — 문서 꼴은 공용이라 strip. */
const documentStatusSchema = z.object({
  document: z.object({
    id,
    fileName: z.string(),
    pageCount: count.nullable(),
    hasText: z.boolean().nullable(),
  }),
});

/** POST /documents 답(DocumentCreatedOut)에서 쓰는 칸만. */
const documentCreatedSchema = z.object({
  document: z.object({ id }),
  upload: z.object({ url: z.string(), method: z.string() }),
});

const outlinePutSchema = z.object({
  outlineId: id,
  revision: int,
  sha256: z.string(),
});

/** POST /runs 답(RunCreatedOut — 새 실행·다시 보냄 둘 다 201). 공용 꼴이라 strip. */
const runCreatedSchema = z.object({
  id,
  status: z.enum(['queued', 'processing', 'done', 'failed']),
});

/** GET /runs/{id} 답(RunOut)에서 쓰는 칸만 — 공용 꼴이라 strip. */
const runOutSchema = z.object({
  id,
  module: z.string(),
  status: z.enum(['queued', 'processing', 'done', 'failed']),
  options: z.record(z.string(), z.unknown()),
  steps: z.array(
    z.object({
      step: z.string(),
      status: z.enum(['pending', 'running', 'done', 'failed']),
      done: count.nullable(),
      total: count.nullable(),
    }),
  ),
  errorCode: z.string().nullable(),
  createdAt: time,
  finishedAt: time.nullable(),
});
export type RunOutRead = z.infer<typeof runOutSchema>;

/** 나가는 옵션(drafting.options@2) — 맨 위까지 strict(모르는 키 거절). */
const runOptionsSchema: z.ZodType<RunOptions, unknown> = z
  .object({
    projectId: id,
    base: z
      .object({ runId: id, rebuild: z.array(key).max(150) })
      .strict()
      .optional(),
  })
  .strict();

const box = z.tuple([z.number(), z.number(), z.number(), z.number()]);
const source = z
  .object({
    documentId: id,
    blockId: z.string(),
    page: id,
    blockBox: box,
    sentence: z
      .object({ index: count, boxes: z.array(box).min(1) })
      .strict()
      .nullable(),
  })
  .strict();
const bullet = z
  .object({
    text: z.string(),
    unsupported: z.boolean(),
    sources: z.array(source),
  })
  .strict();
const failure = z.object({ kind: z.string(), message: z.string() }).strict();
const leaf = z
  .object({
    key: z.string(),
    titlePath: z.array(z.string()),
    pages: z.array(id),
    reusedFrom: z.object({ runId: id, outlineId: id }).strict().nullable(),
    outcome: z.discriminatedUnion('status', [
      z
        .object({ status: z.literal('done'), bullets: z.array(bullet) })
        .strict(),
      z.object({ status: z.literal('no_material') }).strict(),
      z.object({ status: z.literal('failed'), failure }).strict(),
      z.object({ status: z.literal('not_run'), reason: z.string() }).strict(),
    ]),
  })
  .strict();

const resultObject = z.object({
  schemaVersion: z.literal('drafting.bullets@3'),
  projectId: id,
  outlineId: id,
  outlineSha256: z.string(),
  base: z
    .object({
      runId: id,
      outlineId: id,
      matched: z.boolean(),
      reason: z
        .enum(['document', 'versions', 'settings', 'base_rejected'])
        .nullable(),
    })
    .strict()
    .nullable(),
  status: z.discriminatedUnion('status', [
    z.object({ status: z.literal('done') }).strict(),
    z
      .object({
        status: z.literal('rejected'),
        code: z.enum(['over_budget', 'too_large']),
        stage: z.enum(['before_map', 'before_draft']),
        message: z.string(),
      })
      .strict(),
  ]),
  document: z
    .object({
      documentId: id,
      fileName: z.string(),
      pageCount: count,
      textPages: count,
      pages: z.array(
        z.object({ page: id, width: z.number(), height: z.number() }).strict(),
      ),
    })
    .strict(),
  leaves: z.array(leaf),
  /** 앞 결과의 지도가 깨졌으면 서버는 잎 전부를 다시 짓는다(다시 짓는 잎 표시에 쓴다 — RPW2). 그 밖 칸은 쓰지 않아 걷는다. */
  mapping: z.object({ failedBatches: z.array(z.unknown()) }),
  warnings: z.array(
    z
      .object({
        code: z.string(),
        key: z.string().nullable(),
        page: int.nullable(),
        message: z.string(),
      })
      .strict(),
  ),
});
const resultSchema: z.ZodType<DraftingResult, unknown> = resultObject.transform(
  ({ document, ...rest }) => ({ ...rest, pdf: document }),
);

const changesObject = z.object({
  baseRunId: id,
  baseOutlineId: id,
  outlineId: id,
  document: z.enum(['same', 'changed']),
  leaves: z.array(
    z
      .object({ key: z.string(), change: z.enum(['same', 'changed', 'added']) })
      .strict(),
  ),
  removed: z.array(z.string()),
});
const changesSchema: z.ZodType<OutlineChanges, unknown> =
  changesObject.transform(({ document, ...rest }) => ({
    ...rest,
    pdf: document,
  }));

/** 꼴이 맞으면 그 값, 아니면 null(실어댑터가 failed 로 받는다). */
const parseWith =
  <T>(schema: z.ZodType<T, unknown>) =>
  (value: unknown): T | null => {
    const parsed = schema.safeParse(value);
    return parsed.success ? parsed.data : null;
  };

export const parseProjectPage = parseWith(projectPageSchema);
export const parseProject = parseWith(projectSchema);
export const parseRunPage = parseWith(runPageSchema);
export const parseRunItem = parseWith(runItemSchema);
export const parseDocumentStatus = parseWith(documentStatusSchema);
export const parseDocumentCreated = parseWith(documentCreatedSchema);
export const parseOutlinePut = parseWith(outlinePutSchema);
export const parseRunCreated = parseWith(runCreatedSchema);
export const parseRunOut = parseWith(runOutSchema);
export const parseRunOptions = parseWith(runOptionsSchema);
export const parseResult = parseWith(resultSchema);
export const parseChanges = parseWith(changesSchema);

/** 시험이 칸 이름을 openapi 와 견주는 거울 표(꼴 이름 → 칸 이름). 결과는 쓰는 칸만이 아니라 꼴 통째(strict 라 칸이 같아야 지난다). */
/** 옵션 거울의 칸(고정 파일 options/drafting.options@2 와 견준다). */
export const OPTIONS_MIRRORED = {
  top: ['projectId', 'base'],
  base: ['runId', 'rebuild'],
} as const;

export const MIRRORED: Readonly<Record<string, readonly string[]>> = {
  DraftingProjectPage: ['count', 'isNext', 'results'],
  DraftingProjectListItem: Object.keys(projectRow.shape),
  DraftingRunItem: Object.keys(runItemInner.shape),
  DraftingRunProgress: Object.keys(runProgress.shape),
  DraftingRunLeaves: Object.keys(runLeaves.shape),
  DraftingOutlineNode: Object.keys(outlineNode.shape),
  DraftingSource: Object.keys(source.shape),
  DraftingBullet: Object.keys(bullet.shape),
  DraftingLeaf: Object.keys(leaf.shape),
  DraftingProject: Object.keys(projectObject.shape),
  DraftingResult: Object.keys(resultObject.shape),
  DraftingOutlineChanges: Object.keys(changesObject.shape),
  DraftingOutlineLeafChange: ['key', 'change'],
  DraftingDocument: Object.keys(resultObject.shape.document.shape),
  DraftingBase: ['runId', 'outlineId', 'matched', 'reason'],
  DraftingSentence: ['index', 'boxes'],
  RunCreatedOut: Object.keys(runCreatedSchema.shape),
};
