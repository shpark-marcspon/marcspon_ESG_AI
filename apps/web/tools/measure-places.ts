// 강조의 좁은 상자를 글자 자리에서 얼마나 얻었는지 센다. tools/convert.ts 가 남긴 places-report.json 을 읽는다.
//   사용: pnpm --filter @esg/web measure:places          (VIEWER_DATA_DIR 를 convert 때와 같게)
//
// 여기서 세는 것은 「상자를 얻었는가」와 「상자가 몇 개인가(줄 수)」다. 상자가 화면의 글자를 덮는지는 이 스크립트가 알 수 없다
// (그것은 PDF 의 글자를 따로 읽거나 화면을 봐야 안다. apps/web/docs/doc-viewer.md 의 「글자 자리」에 잰 값과 재는 법이 있다).
//
// 어긋남 검사(선택): VIEWER_FACTS=<폴더> 를 주면 그 아래 <문서 이름>/fact-places.json 을 읽어, 대조 쪽(esg-lab)이 값 후보마다 낸
// 글자 범위·상자와 이쪽의 사본(tools/lab/refs.ts 의 숫자 정규식, tools/lab/places.ts 의 spanBoxes)이 내는 것을 값 후보 전부에서 견준다.
// 하나라도 다르면 종료 코드 1 이다. 사본이 원본과 어긋났다는 뜻이다. convert 때와 같은 환경 변수(tools/lab/load.ts)가 필요하다.
// fact-places.json 은 그쪽 저장소에서 낸다: tsx src/compare/places-cli.ts fact-places --doc … --places … --out <폴더>/<문서 이름>
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { LabInputError, loadSide } from './lab/load.ts';
import { placeOf, resolveTarget } from './lab/reconcile.ts';
import type { PlaceRecord } from './lab/reconcile.ts';

const dir = resolve(process.env.VIEWER_DATA_DIR ?? '.local-data');
const records = JSON.parse(
  readFileSync(join(dir, 'places-report.json'), 'utf8'),
) as PlaceRecord[];

const rows = new Map<
  string,
  {
    total: number;
    one: number;
    many: number;
    partial: number;
    missing: Map<string, number>;
  }
>();
for (const record of records) {
  for (const key of [record.form, '전체']) {
    const row = rows.get(key) ?? {
      total: 0,
      one: 0,
      many: 0,
      partial: 0,
      missing: new Map(),
    };
    rows.set(key, row);
    row.total += 1;
    const result = record.result;
    if (!result.found)
      row.missing.set(result.reason, (row.missing.get(result.reason) ?? 0) + 1);
    else {
      if (result.boxes.length === 1) row.one += 1;
      else row.many += 1;
      if (result.length !== null && result.covered !== result.length)
        row.partial += 1;
    }
  }
}

console.log(
  '자리 표기의 꼴 | 강조 수 | 상자를 얻음(하나) | 상자를 얻음(둘 이상) | 그중 범위에 좌표 없는 글자가 낀 것 | 못 얻음(까닭별)',
);
for (const [form, row] of rows) {
  const missing =
    [...row.missing]
      .map(([reason, count]) => `${reason} ${count}`)
      .join(', ') || '0';
  console.log(
    [form, row.total, row.one, row.many, row.partial, missing].join(' | '),
  );
}
const failed = records.filter((record) => !record.result.found);
if (failed.length > 0) {
  console.log('\n못 얻은 것:');
  for (const record of failed)
    console.log(
      `  ${record.side} ${record.ref} ${JSON.stringify(record.result)}`,
    );
}

// ── 어긋남 검사 ──
const factsDir = process.env.VIEWER_FACTS;
if (factsDir) {
  interface FactRow {
    id: string | null;
    container: string | null;
    start: number | null;
    end: number | null;
    raw: string;
    found: boolean;
    boxes: number[][];
  }
  let differs = 0;
  try {
    for (const id of ['a', 'b'] as const) {
      const side = loadSide(id);
      const facts = (
        JSON.parse(
          readFileSync(
            join(resolve(factsDir), side.name, 'fact-places.json'),
            'utf8',
          ),
        ) as { facts: FactRow[] }
      ).facts.filter((fact) => fact.id !== null);
      let same = 0;
      const examples: string[] = [];
      for (const fact of facts) {
        const resolved = resolveTarget(side, fact.id!);
        const mine = resolved.ok ? placeOf(resolved.target, side.places) : null;
        const sameSpan =
          resolved.ok &&
          (resolved.target.span?.start ?? null) === fact.start &&
          (resolved.target.span?.end ?? null) === fact.end;
        const sameBoxes =
          mine !== null &&
          mine.found === fact.found &&
          JSON.stringify(mine.found ? mine.boxes : []) ===
            JSON.stringify(fact.boxes);
        if (sameSpan && sameBoxes) same += 1;
        else if (examples.length < 10)
          examples.push(
            `${fact.id} (${JSON.stringify(fact.raw)}): 그쪽 ${fact.start}~${fact.end} ${JSON.stringify(fact.boxes)} / 이쪽 ${resolved.ok ? `${resolved.target.span?.start ?? null}~${resolved.target.span?.end ?? null} ${JSON.stringify(mine?.found ? mine.boxes : mine)}` : resolved.error}`,
          );
      }
      differs += facts.length - same;
      console.log(
        `\n어긋남 검사 ${id.toUpperCase()} (${side.name}): 값 후보 ${facts.length}개 가운데 글자 범위와 상자가 같은 것 ${same}, 다른 것 ${facts.length - same}`,
      );
      for (const example of examples) console.log(`  ${example}`);
    }
  } catch (error) {
    if (!(error instanceof LabInputError)) throw error;
    console.error(error.message);
    process.exit(1);
  }
  if (differs > 0) {
    console.error(
      '\n사본이 원본과 어긋났다. tools/lab/refs.ts 의 정규식과 tools/lab/places.ts 의 spanBoxes 를 원본과 견준다.',
    );
    process.exit(1);
  }
}
