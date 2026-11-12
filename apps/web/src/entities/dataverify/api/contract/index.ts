// 데이터 검증 계약 거울의 공개 표면(밴드 DV2a ①). api 칸 안에서 zod 를 가져오는 자리는 이 폴더뿐이다(app/guards/layers.test.ts).
// 실어댑터(server.ts)가 답을 이 거울로 지키고, 꼴이 어긋나면 거절(rejected)이다 — 목으로 메우지 않는다.
import type { z } from 'zod';

import type {
  DataverifyInput,
  DataverifyResult,
  InputSource,
} from '../../model/index.ts';
import { edkReadSchema } from './edkRead.ts';
import type { DataverifyEdkRead } from './edkRead.ts';
import { inputSchema } from './input.ts';
import { resultSchema } from './result.ts';
import { runPageSchema } from './runs.ts';
import type { DataverifyRunPage } from './runs.ts';
import { sourceSchema } from './source.ts';

export type { DataverifyRunPage, DataverifyRunRow } from './runs.ts';
export {
  EDK_MAX_CELL_CHARS,
  EDK_MAX_ITEMS,
  EDK_READ_KINDS,
  EDK_XLSX_MAX_BYTES,
} from './edkRead.ts';
export type {
  DataverifyEdkRead,
  DataverifyEdkReadOk,
  DataverifyEdkReadRejected,
  EdkReadKind,
} from './edkRead.ts';

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

export const parseResult = (value: unknown): Parsed<DataverifyResult> =>
  parseWith(resultSchema, value);
export const parseInput = (value: unknown): Parsed<DataverifyInput> =>
  parseWith(inputSchema, value);
export const parseSource = (value: unknown): Parsed<InputSource> =>
  parseWith(sourceSchema, value);
export const parseRunPage = (value: unknown): Parsed<DataverifyRunPage> =>
  parseWith(runPageSchema, value);
export const parseEdkRead = (value: unknown): Parsed<DataverifyEdkRead> =>
  parseWith(edkReadSchema, value);
