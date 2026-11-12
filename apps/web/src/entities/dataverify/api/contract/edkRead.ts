// POST /dataverify/edk/read 의 zod 거울(밴드 DVX1 ② — 정본 apps/api-py/esgapi/dataverify/contracts/edk_read_shapes.py,
// generated api.d.ts DataverifyEdkRead{Ok,Rejected,Skipped}). 두 갈래 다 모르는 칸을 거절한다(strict — 계약의 extra="forbid").
// 판별 칸은 ok. data 의 항목 꼴은 여기서 보지 않는다 — 화면이 JSON 글로 바꿔 model/edk.ts 의 readEdk(isEdkData·미리 읽기·256KiB 셈)
//   한 길로 읽는다(발주서 §1-2 「화면 이음」). 거절의 message 는 꼴만 보고 화면에 싣지 않는다(화면은 kind 로 글을 고른다).
import { z } from 'zod';

/** 읽개의 거절 갈래(서버 edk_read_shapes.py 의 Literal 차례). */
export const EDK_READ_KINDS = [
  'too_large',
  'not_xlsx',
  'unsafe_xlsx',
  'bad_header',
  'bad_cell',
  'no_theme',
  'too_many_rows',
  'too_many_scanned_rows',
  'no_rows',
  'no_target_theme',
  'long_cell',
  'converted_too_large',
] as const;
export type EdkReadKind = (typeof EDK_READ_KINDS)[number];

/** 엑셀 본문의 바이트 상한(서버 tools/edk_xlsx.py MAX_BYTES — section4 가 같은지 본다). */
export const EDK_XLSX_MAX_BYTES = 1024 * 1024;
/** 파일 하나의 항목 상한(서버 tools/edk_xlsx.py MAX_ITEMS — section4 가 같은지 본다). */
export const EDK_MAX_ITEMS = 2000;
/** 읽는 칸 하나의 글자 상한(서버 tools/edk_xlsx.py MAX_CELL_CHARS — section4 가 같은지 본다). */
export const EDK_MAX_CELL_CHARS = 2000;

export interface DataverifyEdkReadOk {
  ok: true;
  /** 검증 대상 테마 → 항목(항목 꼴은 readEdk 가 본다). */
  data: { [theme: string]: { [key: string]: unknown }[] };
  itemCount: number;
  skipped: { themes: number; items: number };
  years: string[];
  skippedEmptyRows: number;
  ignoredColumns: number;
}
export interface DataverifyEdkReadRejected {
  ok: false;
  kind: EdkReadKind;
  row: number | null;
  column: number | null;
  message: string;
}
export type DataverifyEdkRead = DataverifyEdkReadOk | DataverifyEdkReadRejected;

const count = z.number().int().min(0);

const skipped = z.object({ themes: count, items: count }).strict();

const ok = z
  .object({
    ok: z.literal(true),
    data: z.record(
      z.string(),
      z.array(z.record(z.string(), z.unknown())).max(EDK_MAX_ITEMS),
    ),
    itemCount: count.max(EDK_MAX_ITEMS),
    skipped,
    years: z.array(z.string().regex(/^[0-9]{4}$/)),
    skippedEmptyRows: count,
    ignoredColumns: count,
  })
  .strict();

const rejected = z
  .object({
    ok: z.literal(false),
    kind: z.enum(EDK_READ_KINDS),
    row: z.number().int().min(1).nullable(),
    column: z.number().int().min(1).nullable(),
    message: z.string(),
  })
  .strict();

export const edkReadSchema: z.ZodType<DataverifyEdkRead, unknown> =
  z.discriminatedUnion('ok', [ok, rejected]);

/** 거울이 보는 칸 이름(server.test.ts 가 openapi.json 의 칸과 맞춘다). */
export const MIRRORED_EDK_READ: Readonly<Record<string, readonly string[]>> = {
  DataverifyEdkReadOk: Object.keys(ok.shape),
  DataverifyEdkReadRejected: Object.keys(rejected.shape),
  DataverifyEdkReadSkipped: Object.keys(skipped.shape),
};
