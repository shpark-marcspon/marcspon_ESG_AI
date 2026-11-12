// 원고작성 거울 시험(밴드 RPW1 ① — 발주서 §2-1 S1): 거울 칸 == openapi(결과는 버리는 맨 위 칸 둘만 빼고) · 결과 거울 == 고정 파일
//   drafting.bullets@3 · 옵션 거울 == 고정 파일 options/drafting.options@2(모르는 키 거절) · 안쪽은 strict(모르는 칸이면 꼴 틀림 — mapping 만 strip, failedBatches 외 칸을 걷는다).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import {
  MIRRORED,
  OPTIONS_MIRRORED,
  parseProjectPage,
  parseResult,
  parseRunCreated,
  parseRunOptions,
} from './index.ts';

type Schema = {
  properties?: Record<string, unknown>;
  required?: string[];
  additionalProperties?: boolean;
  $defs?: Record<string, Schema>;
};

const here = dirname(fileURLToPath(import.meta.url));
const api = resolve(here, '../../../../../../api-py');
const readJson = (path: string) =>
  JSON.parse(readFileSync(resolve(api, path), 'utf8')) as {
    components: { schemas: Record<string, Schema> };
  } & Schema;
const openapi = readJson('generated/openapi.json');
const schemas = openapi.components.schemas;
const SHAPES = 'esgapi/drafting/tests/data/flow-shapes';
/** 결과 맨 위에서 거울이 버리는 칸(화면이 쓰지 않는다 — strip). */
const RESULT_DROPPED = ['basis', 'settings'];

const keys = (schema: Schema | undefined) =>
  Object.keys(schema?.properties ?? {}).sort();

describe('거울 == openapi', () => {
  it('꼴마다 칸 이름이 같다(결과 맨 위는 버리는 둘만 다르다)', () => {
    for (const [name, fields] of Object.entries(MIRRORED)) {
      const want =
        name === 'DraftingResult' ?
          keys(schemas[name]).filter((k) => !RESULT_DROPPED.includes(k))
        : keys(schemas[name]);
      expect([...fields].sort(), name).toEqual(want);
    }
  });

  it('결과 거울 == 고정 파일 drafting.bullets@3(openapi 의 DraftingResult 와 칸이 같고 schemaVersion 은 @3 하나)', () => {
    const fixed = readJson(`${SHAPES}/drafting.bullets@3.schema.json`);
    const root =
      fixed.properties ? fixed : (
        Object.values(fixed.$defs ?? {}).find(
          (d) => d.properties?.schemaVersion,
        )
      );
    expect(keys(root)).toEqual(keys(schemas.DraftingResult));
    expect((root!.properties!.schemaVersion as { const?: string }).const).toBe(
      'drafting.bullets@3',
    );
  });

  it('옵션 거울 == 고정 파일 options/drafting.options@2(맨 위·base 둘 다 모르는 키 거절)', () => {
    const fixed = readJson(`${SHAPES}/options/drafting.options@2.schema.json`);
    expect(keys(fixed)).toEqual([...OPTIONS_MIRRORED.top].sort());
    expect(fixed.additionalProperties).toBe(false);
    const base = fixed.$defs!.DraftingOptionsBase!;
    expect(keys(base)).toEqual([...OPTIONS_MIRRORED.base].sort());
    expect(base.additionalProperties).toBe(false);
    expect(parseRunOptions({ projectId: 1 })).toEqual({ projectId: 1 });
    expect(
      parseRunOptions({ projectId: 1, base: { runId: 2, rebuild: ['n2'] } }),
    ).toEqual({ projectId: 1, base: { runId: 2, rebuild: ['n2'] } });
    expect(parseRunOptions({ projectId: 1, companyId: 0 })).toBeNull();
    expect(
      parseRunOptions({ projectId: 1, base: { runId: 2, rebuild: [], x: 1 } }),
    ).toBeNull();
    expect(
      parseRunOptions({ projectId: 1, base: { runId: 2, rebuild: ['A'] } }),
    ).toBeNull();
  });
});

describe('실행 만들기 답', () => {
  it('POST /runs 201 은 RunCreatedOut — openapi 가 그 꼴을 가리키고 id·status 만으로 지난다', () => {
    const created = (
      openapi as unknown as {
        paths: Record<
          string,
          {
            post: {
              responses: Record<
                string,
                { content: Record<string, { schema: { $ref: string } }> }
              >;
            };
          }
        >;
      }
    ).paths['/runs']!.post.responses['201']!.content['application/json']!.schema
      .$ref;
    expect(created).toBe('#/components/schemas/RunCreatedOut');
    expect(parseRunCreated({ id: 3, status: 'queued' })).toEqual({
      id: 3,
      status: 'queued',
    });
  });
});

describe('RunCreatedOut.status(502 ⓓ)', () => {
  it('넷 == openapi enum · 그 밖 값은 꼴 틀림', () => {
    const status = schemas.RunCreatedOut!.properties!.status as {
      enum: string[];
    };
    expect([...status.enum].sort()).toEqual([
      'done',
      'failed',
      'processing',
      'queued',
    ]);
    for (const value of status.enum)
      expect(parseRunCreated({ id: 3, status: value })).not.toBeNull();
    expect(parseRunCreated({ id: 3, status: '지어낸' })).toBeNull();
  });
});

describe('결과 거울', () => {
  const result = {
    schemaVersion: 'drafting.bullets@3',
    projectId: 1,
    outlineId: 2,
    outlineSha256: 'a'.repeat(64),
    base: null,
    basis: null,
    mapping: { batches: 0, failedBatches: [] },
    settings: {
      promptIds: { map: 'a', draft: 'b' },
      routes: { map: 'a', draft: 'b' },
    },
    status: { status: 'done' },
    document: {
      documentId: 3,
      fileName: '지어낸.pdf',
      pageCount: 1,
      textPages: 1,
      pages: [{ page: 1, width: 600, height: 800 }],
    },
    leaves: [],
    warnings: [],
  };

  it('@3 은 지나고 맨 위 버리는 칸은 걷힌다', () => {
    const parsed = parseResult(result);
    expect(parsed).not.toBeNull();
    expect(Object.keys(parsed!)).not.toContain('basis');
    // 서버 칸 document 는 model 칸 pdf 로(model 은 DOM 낱말을 쓰지 않는다).
    expect(Object.keys(parsed!)).not.toContain('document');
    expect(parsed!.pdf).toEqual(result.document);
  });

  it('@2 꼴은 꼴 틀림(null)', () => {
    expect(
      parseResult({ ...result, schemaVersion: 'drafting.bullets@2' }),
    ).toBeNull();
  });

  it('안쪽 모르는 칸은 꼴 틀림(strict) · 맨 위 모르는 칸은 지난다(strip)', () => {
    expect(
      parseResult({ ...result, document: { ...result.document, extra: 1 } }),
    ).toBeNull();
    expect(parseResult({ ...result, extra: 1 })).not.toBeNull();
    expect(
      parseProjectPage({ count: 0, isNext: false, results: [], extra: 1 }),
    ).not.toBeNull();
  });
});
