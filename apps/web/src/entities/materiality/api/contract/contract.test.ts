// 중대성평가 계약 거울(밴드 IRW1 ① — 발주서 §3-1). 백엔드 고정 파일을 읽기만 한다(옮기지 않는다):
//   apps/api-py/esgapi/materiality/tests/data/examples/result2-sample.json — 결과 예시가 거울을 지나는가(★E).
//   apps/api-py/esgapi/materiality/tests/data/flow-shapes/materiality.result@2.schema.json — $defs 마다 칸이 거울과 같은가.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import {
  impactLines,
  pathwayLines,
  shortlistLines,
  undecidedSubtopics,
} from '../../model/index.ts';
import { fakeInput, fakeResult, warning } from '../../model/testing.ts';
import { MIRRORED_EDITS } from './edits.ts';
import { parseInput, parseResult, parseResultEdits } from './index.ts';
import { MIRRORED_DEFS } from './result.ts';

const data = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../../api-py/esgapi/materiality/tests/data',
);
const read = (name: string): Record<string, unknown> =>
  JSON.parse(readFileSync(resolve(data, name), 'utf8')) as Record<
    string,
    unknown
  >;

/** ★E: 예시의 2-1·2-2 줄 수와 1-1 토픽 하나의 규제·컨트로버시 항목 수(final_xlsx 로 잼 — 보고 ★E). */
const SAMPLE = { impact: 1, pathway: 2, shortlist: [2, 2], undecided: 1 };

describe('result@2 거울', () => {
  it('백엔드 예시가 지난다(★E — 줄 수)', () => {
    const parsed = parseResult(read('examples/result2-sample.json'));
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(impactLines(parsed.value)).toHaveLength(SAMPLE.impact);
    expect(pathwayLines(parsed.value)).toHaveLength(SAMPLE.pathway);
    const [first] = shortlistLines(parsed.value);
    expect([
      first!.regulation.items.length,
      first!.controversy.items.length,
    ]).toEqual(SAMPLE.shortlist);
    expect(undecidedSubtopics(parsed.value)).toHaveLength(SAMPLE.undecided);
  });

  it('고정 스키마의 $defs 마다 칸 이름이 거울과 같다(JsonValue 밖 전부)', () => {
    const schema = read('flow-shapes/materiality.result@2.schema.json');
    const defs = schema.$defs as Record<
      string,
      { properties?: Record<string, unknown> }
    >;
    const objects = Object.entries(defs).filter(
      ([, def]) => def.properties !== undefined,
    );
    expect(objects.map(([name]) => name).sort()).toEqual(
      Object.keys(MIRRORED_DEFS).sort(),
    );
    for (const [name, def] of objects)
      expect([...MIRRORED_DEFS[name]!].sort(), name).toEqual(
        Object.keys(def.properties!).sort(),
      );
  });

  it('안쪽 모르는 칸은 거절, 맨 위 모르는 칸은 버리고 지난다', () => {
    const inner = fakeResult();
    (inner.scope as Record<string, unknown>).extra = 1;
    expect(parseResult(inner).ok).toBe(false);
    const deep = read('examples/result2-sample.json');
    const topics = (deep.part2 as { topics: { subtopics: unknown[] }[] })
      .topics;
    const sub = topics[0]!.subtopics[0] as {
      impact: { rows: Record<string, unknown>[] };
    };
    sub.impact.rows[0]!.extra = true;
    expect(parseResult(deep).ok).toBe(false);
    expect(parseResult({ ...fakeResult(), later: 'x' }).ok).toBe(true);
  });

  it('판별 칸 밖 값·빠진 칸은 거절, 모르는 경고 code 는 지난다', () => {
    expect(
      parseResult({ ...fakeResult(), schemaVersion: 'materiality.result@1' })
        .ok,
    ).toBe(false);
    const missing = fakeResult();
    delete missing.warnings;
    expect(parseResult(missing).ok).toBe(false);
    expect(
      parseResult(fakeResult({ part2: { status: 'later', topics: [] } })).ok,
    ).toBe(false);
    expect(
      parseResult(fakeResult({ warnings: [warning('code_from_later')] })).ok,
    ).toBe(true);
  });

  it('서버 message 는 화면 꼴에 싣지 않는다', () => {
    const parsed = parseResult(
      fakeResult({ warnings: [warning('answer_truncated', '가상토픽 A')] }),
    );
    expect(parsed.ok).toBe(true);
    expect(JSON.stringify(parsed)).not.toContain('지어낸 서버 글');
    const sample = JSON.stringify(
      parseResult(read('examples/result2-sample.json')),
    );
    expect(sample).not.toContain('provider_error');
    expect(sample).not.toContain('message');
  });
});

describe('input@1 거울', () => {
  it('지어낸 입력이 지나고 모르는 칸·위치 꼴 틀림·빈 토픽은 거절', () => {
    expect(parseInput(fakeInput()).ok).toBe(true);
    expect(parseInput(read('examples/input-sample.json')).ok).toBe(true);
    expect(parseInput({ ...fakeInput(), today: '2026-10-19' }).ok).toBe(false);
    expect(parseInput(fakeInput({ userLocation: 'kr' })).ok).toBe(false);
    expect(parseInput(fakeInput({ topics: [] })).ok).toBe(false);
  });
});

describe('result-edits@1 거울(밴드 IRW11)', () => {
  it('거울 칸 이름이 generated openapi.json 의 스키마 칸과 같다', () => {
    const openapi = JSON.parse(
      readFileSync(
        resolve(
          dirname(fileURLToPath(import.meta.url)),
          '../../../../../../api-py/generated/openapi.json',
        ),
        'utf8',
      ),
    ) as {
      components: {
        schemas: Record<string, { properties: Record<string, unknown> }>;
      };
    };
    for (const [name, fields] of Object.entries(MIRRORED_EDITS))
      expect([...fields].sort(), name).toEqual(
        Object.keys(openapi.components.schemas[name]!.properties).sort(),
      );
  });

  it('꼴: 지나면 revision·edits · 모르는 칸·판 밖·음수 revision·빈 이름은 거절', () => {
    const good = {
      schemaVersion: 'materiality.result-edits@1',
      revision: 2,
      edits: [
        {
          pointer: '/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition',
          value: null,
          original: '가상 원문',
          editedAt: '2026-11-03T14:28:05+09:00',
          editedBy: { name: '담당자 A' },
        },
      ],
    };
    const parsed = parseResultEdits(good);
    expect(parsed.ok && parsed.value.revision).toBe(2);
    expect(parseResultEdits({ ...good, extra: 1 }).ok).toBe(false);
    expect(
      parseResultEdits({ ...good, schemaVersion: 'materiality.result-edits@2' })
        .ok,
    ).toBe(false);
    expect(parseResultEdits({ ...good, revision: -1 }).ok).toBe(false);
    const nameless = structuredClone(good);
    nameless.edits[0]!.editedBy.name = '';
    expect(parseResultEdits(nameless).ok).toBe(false);
  });
});
