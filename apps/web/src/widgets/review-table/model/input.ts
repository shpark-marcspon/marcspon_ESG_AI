// 검토 표의 입력: 꼴과 런타임 검증. 표는 이 꼴의 자료 하나만 받는다. 어디서 왔는지는 모른다.
//
// 검증은 뷰어의 입력 계약(src/widgets/doc-viewer/model/contract.ts)과 같은 두 단계다.
//   1) 꼴(zod)   2) 가리킴(행 id 가 겹치지 않는가, 고른 후보가 그 행에 있는가)
import { z } from 'zod';

import { EMISSION_UNIT } from './format.ts';
import type { ReviewRow, RowEdit } from './row.ts';

const rawValueSchema = z.union([z.string(), z.number(), z.null()]);

const candidateSchema = z.object({
  id: z.string().min(1),
  factorName: z.string().min(1),
  factorValue: z.number().nullable(),
  factorUnit: z.string(),
  source: z.string().optional(),
  reason: z.string().optional(),
  confidence: z.enum(['high', 'medium', 'low']).optional(),
  emission: z.number().nullable(),
});

const editSchema = z.object({
  category: z.string().min(1).optional(),
  candidateId: z.string().min(1).optional(),
  /** 고친 값으로 계산한 배출량. 값이 나오지 않았으면 null. */
  emission: z.number().nullable(),
  /** (선택) 재계산이 실패한 채로 저장된 행. 이때 emission 은 null 이어야 한다. */
  recalcFailed: z.boolean().optional(),
});

const reviewSchema = z.object({
  status: z.enum([
    'pending',
    'accepted',
    'declined',
    'edited',
    'rerequested',
    'rejected',
    'finalized',
  ]),
  rejectReason: z.string().min(1).optional(),
  edit: editSchema.optional(),
});

const rowSchema = z.object({
  id: z.string().min(1),
  /** 원본 데이터. 키의 뜻은 표가 모른다. */
  raw: z.record(z.string(), rawValueSchema),
  processing: z.string().optional(),
  ai: z.object({
    category: z.string().nullable(),
    categoryNote: z.string().optional(),
    /** 첫 번째가 대표 후보. */
    candidates: z.array(candidateSchema),
  }),
  /** 검토 상태의 처음 값. 서버가 생기면 저장된 값이 여기로 온다. */
  review: reviewSchema,
});

export const tableInputSchema = z.object({
  // 판 2: 배출량(후보·수정값의 emission, 합계)이 kgCO2e 에서 tCO2eq 로 바뀌었다(sid:MARC-ENT-264). 입력 하나에 단위 하나다. 칸 이름 emission 에는 단위가 없어서,
  // 옛 kg 자료(판 1)가 1000배 큰 값으로 조용히 읽히지 않게 판과 단위 글자로 막는다.
  version: z.literal(2),
  unit: z.literal(EMISSION_UNIT),
  /** 화면 위에 보일 알림(자료의 한계 등). */
  notice: z.string().optional(),
  /** 카테고리를 고칠 때 고를 수 있는 값들. */
  categories: z.array(z.string().min(1)),
  rows: z.array(rowSchema),
});

export type TableInputJson = z.infer<typeof tableInputSchema>;

export interface TableInput {
  notice?: string;
  categories: string[];
  rows: ReviewRow[];
}

export type ParseResult =
  { ok: true; input: TableInput } | { ok: false; errors: string[] };

/** 저장돼 있던 수정값 → 행의 수정값. 재계산은 끝난 것으로 읽고, 실패 표시는 true 일 때만 남긴다. */
function toRowEdit({
  recalcFailed,
  ...edit
}: z.infer<typeof editSchema>): RowEdit {
  return {
    ...edit,
    recalcPending: false,
    ...(recalcFailed ? { recalcFailed: true as const } : {}),
  };
}

export function parseTableInput(raw: unknown): ParseResult {
  const shape = tableInputSchema.safeParse(raw);
  if (!shape.success) {
    return {
      ok: false,
      errors: shape.error.issues.map(
        (issue) => `${issue.path.join('.')}: ${issue.message}`,
      ),
    };
  }
  const errors: string[] = [];
  const ids = new Set<string>();
  const rows: ReviewRow[] = [];

  for (const row of shape.data.rows) {
    if (ids.has(row.id)) errors.push(`rows: id "${row.id}" 가 둘 이상이다`);
    ids.add(row.id);

    const candidateIds = new Set(
      row.ai.candidates.map((candidate) => candidate.id),
    );
    if (candidateIds.size !== row.ai.candidates.length)
      errors.push(`rows "${row.id}": 후보의 id 가 겹친다`);
    const { status, rejectReason, edit } = row.review;
    if (edit?.candidateId !== undefined && !candidateIds.has(edit.candidateId))
      errors.push(
        `rows "${row.id}": 없는 후보 "${edit.candidateId}" 를 골랐다`,
      );
    if (status === 'rejected' && rejectReason === undefined)
      errors.push(`rows "${row.id}": 반려인데 사유가 없다`);
    if (status === 'edited' && edit === undefined)
      errors.push(`rows "${row.id}": 수정 상태인데 수정값이 없다`);
    // 반영은 「AI 제안 그대로」이고 검토대기는 아직 손대지 않은 것이라, 수정값이 같이 올 수 없다.
    if ((status === 'pending' || status === 'accepted') && edit !== undefined)
      errors.push(`rows "${row.id}": ${status} 상태인데 수정값이 있다`);
    // 최종확정 행은 합계에 든다. 배출량이 없으면 조용히 빠지므로 받지 않는다.
    const emission =
      edit ? edit.emission : (row.ai.candidates[0]?.emission ?? null);
    if (edit?.recalcFailed && edit.emission !== null)
      errors.push(`rows "${row.id}": 계산 실패인데 배출량이 있다`);
    if (status === 'finalized' && emission === null)
      errors.push(`rows "${row.id}": 최종확정인데 배출량이 없다`);

    rows.push({
      id: row.id,
      raw: row.raw,
      ...(row.processing !== undefined ? { processing: row.processing } : {}),
      ai: row.ai,
      edit: edit ? toRowEdit(edit) : null,
      status,
      ...(status === 'rejected' && rejectReason !== undefined ?
        { rejectReason }
      : {}),
    });
  }

  if (errors.length > 0) return { ok: false, errors };
  return {
    ok: true,
    input: {
      ...(shape.data.notice !== undefined ? { notice: shape.data.notice } : {}),
      categories: shape.data.categories,
      rows,
    },
  };
}
