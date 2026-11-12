// 결과 글 칸 고침 GET·POST /materiality/runs/{run_id}/result/edits 의 zod 거울(밴드 IRW11 — 정본 apps/api-py/esgapi/materiality/contracts/
// edit_shapes.py, generated api.d.ts MaterialityResultEdits·MaterialityResultEdit·MaterialityResultEditor). 계약이 extra="forbid" 라 strict.
// 받은 값이 그 꼴인지만 본다 — 꼴이 틀리면 거절(rejected), 목으로 메우지 않는다.
import { z } from 'zod';

import type { Schemas } from '../../../../shared/api/index.ts';
import type { ResultEdit } from '../../model/index.ts';

export type MaterialityResultEdits = Schemas['MaterialityResultEdits'];

const editor = z.strictObject({ name: z.string().min(1) });
const edit = z.strictObject({
  pointer: z.string(),
  value: z.string().nullable(),
  original: z.string().nullable(),
  editedAt: z.string(),
  editedBy: editor,
});
const edits = z.strictObject({
  schemaVersion: z.literal('materiality.result-edits@1'),
  revision: z.number().int().min(0),
  edits: z.array(edit),
});

/** 화면 꼴(revision·edits). */
export interface ResultEditsView {
  revision: number;
  edits: ResultEdit[];
}

export const resultEditsSchema: z.ZodType<ResultEditsView, unknown> =
  edits.transform((value) => ({
    revision: value.revision,
    edits: value.edits.map((item) => ({
      ...item,
      editedBy: { ...item.editedBy },
    })),
  }));

/** 거울이 보는 칸 이름(contract.test.ts 가 generated openapi.json 의 칸과 맞춘다). */
export const MIRRORED_EDITS: Readonly<Record<string, readonly string[]>> = {
  MaterialityResultEdits: Object.keys(edits.shape),
  MaterialityResultEdit: Object.keys(edit.shape),
  MaterialityResultEditor: Object.keys(editor.shape),
};
