// 영문번역 계약 거울(밴드 TRW1a ① — ★G). 백엔드 고정 파일을 읽기만 한다(옮기지 않는다):
//   apps/api-py/esgapi/translation/tests/data/api-shapes/translation.batch@1.schema.json — $defs 마다 칸 이름이 거울과 같은가.
//   apps/api-py/esgapi/translation/tests/data/examples/result-sample.json — 결과 예시가 거울을 지나는가(묶음·요약 예시 JSON 은 없다 — ★G).
// 안쪽 객체는 모르는 키를 거절하고(strict), 맨 위 객체는 버리고 통과한다(strip — 그린워싱 D10 꼴).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { MIRRORED_DEFS } from './batch.ts';
import { parseBatchDetail, parseBatchPage, parseResult } from './index.ts';

const data = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../../api-py/esgapi/translation/tests/data',
);
const read = (name: string): unknown =>
  JSON.parse(readFileSync(resolve(data, name), 'utf8'));

type Json = Record<string, unknown>;

describe('batch@1 · digest@1 고정 스키마 → 거울 칸', () => {
  const schema = read('api-shapes/translation.batch@1.schema.json') as {
    $defs: Record<string, { properties: Json; additionalProperties?: boolean }>;
  };
  it('$defs 이름이 거울 표와 같다', () => {
    expect(Object.keys(schema.$defs).sort()).toEqual(
      Object.keys(MIRRORED_DEFS).sort(),
    );
  });
  it.each(Object.keys(MIRRORED_DEFS))('%s 의 칸 이름이 같다', (name) => {
    const mirror = MIRRORED_DEFS[name as keyof typeof MIRRORED_DEFS];
    expect(Object.keys(mirror.shape).sort()).toEqual(
      Object.keys(schema.$defs[name]!.properties).sort(),
    );
  });
});

// 밴드 TRC1 §3-5-10: 목록 쪽 맨 위 companyName(필수 글자 — 감독 답 3). 쪽 꼴은 고정 스키마 밖이라 여기서 따로.
describe('묶음 목록 쪽 → 거울(companyName)', () => {
  const empty = { count: 0, isNext: false, truncated: false, results: [] };

  it('companyName 이 있으면 지나고 값을 넘긴다(빈 글자도)', () => {
    for (const name of ['지어낸 회사', '']) {
      const parsed = parseBatchPage({ companyName: name, ...empty });
      expect(parsed.ok ? parsed.value.companyName : parsed.issues).toBe(name);
    }
  });

  it('없거나 글자가 아니면 거절', () => {
    expect(parseBatchPage(empty).ok).toBe(false);
    expect(parseBatchPage({ companyName: 7, ...empty }).ok).toBe(false);
    expect(parseBatchPage({ companyName: null, ...empty }).ok).toBe(false);
  });
});

// 밴드 TRS3 ①: 묶음 inputKind(word|pdf)·파트 최신 실행 latest.flowId(글자) — 둘 다 필수(안쪽 객체라 빠지면 거절).
describe('묶음 inputKind · latest.flowId → 거울', () => {
  const latest = {
    runId: 345,
    flowId: 'translation.pdf@158',
    status: 'processing',
    pages: { start: 1, end: null },
    style: { compareAb: false, single: 'B' },
    glossaryCounts: { base: 0, final: 0 },
    createdAt: '2026-10-28T10:00:00+09:00',
    startedAt: '2026-10-28T10:00:01+09:00',
    finishedAt: null,
    failedStep: null,
    errorCode: null,
    steps: [{ step: 'prepare', status: 'running', done: null, total: null }],
    digest: null,
  };
  const batch = {
    batchKey: '00000000-0000-4000-8000-000000000001',
    inputKind: 'pdf',
    document: {
      id: 12,
      fileName: '지어낸 보고서.pdf',
      uploadedAt: null,
      uploadedBy: { userId: 1, name: '지어낸 사람' },
    },
    createdBy: { userId: 1, name: '지어낸 사람' },
    parts: [{ part: 'general', latest, earlier: [], round: 1 }],
    state: 'active',
    doneParts: 0,
    partCount: 1,
  };
  const pageOf = (one: Json) => ({
    companyName: '지어낸 회사',
    count: 1,
    isNext: false,
    truncated: false,
    results: [one],
  });

  it('두 칸을 받아 넘긴다(word·pdf 둘 다)', () => {
    for (const kind of ['word', 'pdf'] as const) {
      const parsed = parseBatchPage(pageOf({ ...batch, inputKind: kind }));
      expect(
        parsed.ok ? parsed.value.results[0]!.inputKind : parsed.issues,
      ).toBe(kind);
    }
    const parsed = parseBatchPage(pageOf(batch));
    expect(
      parsed.ok ?
        parsed.value.results[0]!.parts[0]!.latest.flowId
      : parsed.issues,
    ).toBe('translation.pdf@158');
    expect(parseBatchDetail({ ...batch, truncated: false }).ok).toBe(true);
  });

  it('inputKind 가 빠지거나 둘 밖이면 거절', () => {
    const without: Json = { ...batch };
    delete without.inputKind;
    expect(parseBatchPage(pageOf(without)).ok).toBe(false);
    expect(parseBatchPage(pageOf({ ...batch, inputKind: 'hwp' })).ok).toBe(
      false,
    );
  });

  it('latest.flowId 가 빠지거나 글자가 아니면 거절', () => {
    const noFlow: Json = { ...latest };
    delete noFlow.flowId;
    for (const run of [noFlow, { ...latest, flowId: null }]) {
      const parts = [{ part: 'general', latest: run, earlier: [], round: 1 }];
      expect(parseBatchPage(pageOf({ ...batch, parts })).ok).toBe(false);
    }
  });
});

describe('result@1 예시 → 거울', () => {
  const sample = read('examples/result-sample.json') as Json;

  it('result-sample.json 은 지난다', () => {
    const parsed = parseResult(sample);
    expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
  });

  it('맨 위 모르는 키는 버리고 지난다', () => {
    expect(parseResult({ ...sample, extraTop: 1 }).ok).toBe(true);
  });

  it('안쪽 모르는 키는 거절(variants[0])', () => {
    const variants = structuredClone(sample.variants) as Json[];
    variants[0] = { ...variants[0], extraInner: 1 };
    expect(parseResult({ ...sample, variants }).ok).toBe(false);
  });

  it('status 판별: done 인데 rejection 이 있으면 거절', () => {
    expect(
      parseResult({
        ...sample,
        rejection: {
          kind: 'no_pages',
          message: 'x',
          pageCount: null,
          limit: null,
        },
      }).ok,
    ).toBe(false);
  });
});
