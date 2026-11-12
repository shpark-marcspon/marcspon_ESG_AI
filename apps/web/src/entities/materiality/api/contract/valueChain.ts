// POST /materiality/value-chain/read 의 zod 거울(밴드 IRW2 ② — 정본 apps/api-py/esgapi/materiality/contracts/value_chain_shapes.py,
// generated api.d.ts MaterialityValueChainRead{Ok,Rejected,Row}). 두 갈래 다 모르는 칸을 거절한다(strict — 계약의 extra="forbid").
// 판별 칸은 ok. 거절의 message 는 꼴만 보고 화면에 싣지 않는다(화면은 kind 로 글을 고른다 — 부록 A5).
import { z } from 'zod';

import type { Schemas } from '../../../../shared/api/index.ts';

export type MaterialityValueChainReadRow =
  Schemas['MaterialityValueChainReadRow'];
export type MaterialityValueChainRead =
  | Schemas['MaterialityValueChainReadOk']
  | Schemas['MaterialityValueChainReadRejected'];

const KINDS = [
  'too_large',
  'not_xlsx',
  'unsafe_xlsx',
  'bad_header',
  'not_text',
  'too_long',
  'too_many_rows',
  'too_many_scanned_rows',
  'no_rows',
] as const;

const row = z
  .object({
    business_unit: z.string(),
    business_unit_description: z.string(),
    value_chain_stage: z.string(),
    stakeholder: z.string(),
    business_activity: z.string(),
  })
  .strict();

const ok = z
  .object({
    ok: z.literal(true),
    rows: z.array(row).min(1).max(100),
    rowCount: z.number().int().min(0),
  })
  .strict();

const rejected = z
  .object({
    ok: z.literal(false),
    kind: z.enum(KINDS),
    row: z.number().int().min(1).nullable(),
    column: z.number().int().min(0).max(4).nullable(),
    message: z.string(),
  })
  .strict();

export const valueChainReadSchema: z.ZodType<
  MaterialityValueChainRead,
  unknown
> = z.discriminatedUnion('ok', [ok, rejected]);

/** 거울이 보는 칸 이름(contract.test.ts 가 generated 의 칸과 맞춘다). */
export const MIRRORED_VALUE_CHAIN: Readonly<Record<string, readonly string[]>> =
  {
    MaterialityValueChainReadOk: Object.keys(ok.shape),
    MaterialityValueChainReadRejected: Object.keys(rejected.shape),
    MaterialityValueChainReadRow: Object.keys(row.shape),
  };
