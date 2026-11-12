// 배출량 단위의 파수(sid:MARC-ENT-264 위험 ①). 칸 이름 emission 에는 단위가 없어서, 1000배 착오는 입력 맨 위의
// 판(version)과 단위(unit) 글자로 막는다. 그 글자가 백엔드 Scope 3 결과의 단위 칸과 같은지 백엔드 스키마를 읽어 본다
// (그린워싱 거울 시험이 apps/api-py 의 시험 자료를 읽는 것과 같은 꼴. 읽기만 한다).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { EMISSION_UNIT } from './format.ts';
import { parseTableInput, tableInputSchema } from './input.ts';

// ★ 파일 이름에 판(@2)이 박혀 있다. 백엔드가 결과 꼴의 판을 올리면 이 파일을 못 찾아 빨강이다 — 의도한 것이다.
//   그때 새 판의 단위를 보고, 바뀌었으면 웹 입력의 판·단위도 같이 올린다.
const SCHEMA = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../api-py/esgapi/inventory/tests/data/flow-shapes/scope3.llm-first.result@2.schema.json',
);

describe('배출량 단위', () => {
  it('웹 입력의 단위 글자(EMISSION_UNIT 과 입력 스키마의 unit 리터럴)는 백엔드 Scope 3 결과의 단위 칸(ComputedCalc.unit 의 const)과 같다', () => {
    // 파일이 없으면 readFileSync 가 던진다: 조용히 건너뛰지 않는다.
    const schema = JSON.parse(readFileSync(SCHEMA, 'utf8')) as {
      $defs: { ComputedCalc: { properties: { unit: { const: string } } } };
    };
    const backend = schema.$defs.ComputedCalc.properties.unit.const;
    expect(backend).toBe(EMISSION_UNIT);
    expect(tableInputSchema.shape.unit.value).toBe(backend);
  });

  const valid = {
    version: 2,
    unit: 'tCO2eq',
    categories: ['가'],
    rows: [],
  };

  it('판 2·tCO2eq 자료는 받는다', () => {
    expect(parseTableInput(valid).ok).toBe(true);
  });

  // 옛 kg 자료(판 1, git 밖 .local-data 에 남은 변환 결과 포함)가 1000배 큰 값으로 조용히 읽히지 않는다.
  it.each([
    ['판 1(옛 kgCO2e 자료)', { ...valid, version: 1 }, 'version'],
    ['단위 없음', { version: 2, categories: ['가'], rows: [] }, 'unit'],
    ['단위 kgCO2e', { ...valid, unit: 'kgCO2e' }, 'unit'],
    ['판 1 + 단위 kgCO2e', { ...valid, version: 1, unit: 'kgCO2e' }, 'version'],
  ])('%s 는 거부한다', (_name, raw, field) => {
    const result = parseTableInput(raw);
    expect(result.ok).toBe(false);
    expect(!result.ok && result.errors.join('\n')).toContain(field);
  });
});
