// 데이터 검증 계약 거울(밴드 DV2a ① — 발주서 §3-1-4). 백엔드 고정 파일을 읽기만 한다(옮기지 않는다):
//   apps/api-py/esgapi/dataverify/tests/data/examples/result-sample.json — 결과 예시가 거울을 지나는가.
//   apps/api-py/esgapi/dataverify/tests/data/flow-shapes/dataverify.result@2.schema.json — 결과 꼴의 맨 위 칸이 거울과 같은가.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { fakeInput, fakeResult, noTargetResult } from '../../model/testing.ts';
import { parseInput, parseResult } from './index.ts';
import { MIRRORED_DEFS } from './result.ts';

const data = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../../api-py/esgapi/dataverify/tests/data',
);
const read = (name: string): Record<string, unknown> =>
  JSON.parse(readFileSync(resolve(data, name), 'utf8')) as Record<
    string,
    unknown
  >;

describe('result@2 거울', () => {
  it('백엔드 예시가 지난다(판 DV-04 수)', () => {
    const parsed = parseResult(read('examples/result-sample.json'));
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.value.tolerance).toBe('0.0'); // 판정 허용 오차 0(밴드 DV16)
    expect(parsed.value.review.checks).toHaveLength(8);
    expect(parsed.value.warnings).toEqual([]);
  });

  it('고정 스키마의 $defs 마다 칸 이름이 거울과 같다(JsonValue 밖 전부)', () => {
    const schema = read('flow-shapes/dataverify.result@2.schema.json');
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

  it('지어낸 결과·「환경」 없음 결과가 지난다', () => {
    expect(parseResult(fakeResult()).ok).toBe(true);
    expect(parseResult(noTargetResult()).ok).toBe(true);
  });

  it('안쪽 모르는 칸은 거절, 맨 위 모르는 칸은 버리고 지난다', () => {
    const inner = fakeResult();
    (inner.scope as Record<string, unknown>).extra = 1;
    expect(parseResult(inner).ok).toBe(false);
    const deep = read('examples/result-sample.json');
    const checks = (deep.review as { checks: Record<string, unknown>[] })
      .checks;
    checks[3]!.extra = true;
    expect(parseResult(deep).ok).toBe(false);
    expect(parseResult({ ...fakeResult(), later: 'x' }).ok).toBe(true);
  });

  it('판별 칸 밖 값·빠진 칸은 거절', () => {
    expect(
      parseResult({ ...fakeResult(), schemaVersion: 'dataverify.result@1' }).ok,
    ).toBe(false);
    const missing = fakeResult();
    delete missing.warnings;
    expect(parseResult(missing).ok).toBe(false);
    expect(
      parseResult(
        fakeResult({
          plan: {
            status: 'failed',
            partial: null,
            formulas: [],
            raw: null,
            failure: { kind: 'call_failed', budgetSource: null, message: 'x' },
          },
        }),
      ).ok,
    ).toBe(false);
  });

  it('서버 message 는 화면 꼴에 싣지 않는다', () => {
    const parsed = parseResult(read('examples/result-sample.json'));
    expect(JSON.stringify(parsed)).not.toContain('runtime error');
    expect(JSON.stringify(parsed)).not.toContain('unknown tool');
  });
});

describe('input@1 거울', () => {
  it('지어낸 입력이 지나고 모르는 칸·연도 꼴 틀림은 거절', () => {
    expect(parseInput(fakeInput()).ok).toBe(true);
    expect(parseInput({ ...fakeInput(), source: 'x' }).ok).toBe(false);
    const year = fakeInput();
    (year.company as Record<string, unknown>).reportingYear = '25';
    expect(parseInput(year).ok).toBe(false);
    expect(parseInput(fakeInput({ 환경: [{ ID: 1 }] })).ok).toBe(false);
  });
});
