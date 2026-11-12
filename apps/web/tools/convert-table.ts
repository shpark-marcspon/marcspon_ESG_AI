// 실제 자료(git 밖)를 검토 표의 입력으로 바꿔 VIEWER_DATA_DIR 에 쓴다. 저장소에는 아무것도 남기지 않는다.
//
// 사용:
//   ESG_LAB_OUT=<실측 산출물 폴더> ESG_LAB_DATA=<실측 저장소의 data 폴더> pnpm --filter @esg/web convert:table
// (상대 경로는 apps/web 을 기준으로 읽는다. 절대 경로를 주는 편이 헷갈리지 않는다.)
//
//   ESG_LAB_OUT      <TABLE_RUN>/rows.json 과 (있으면) <TABLE_RUN>/calls.jsonl 이 있는 폴더
//   ESG_LAB_DATA     factors/factors.jsonl 과 (있으면) scope3-examples/rows.synthetic.jsonl 이 있는 폴더
//   TABLE_RUN        (선택) 실행의 폴더. 기본 measure-openai/scope3-s100
//   VIEWER_DATA_DIR  (선택) 결과를 쓸 폴더. 기본은 apps/web/.local-data (.gitignore 되어 있다)
//
// 쓰는 것: review-table.json 하나. 화면에서는 ?view=table&data=local 로 연다.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { z } from 'zod';

import { parseTableInput } from '../src/widgets/review-table/model/index.ts';
import {
  buildTableInput,
  labCallSchema,
  labFactorSchema,
  labRowSchema,
  labSourceRowSchema,
} from './lab/scope3.ts';

function env(name: string): string {
  const value = process.env[name];
  if (!value) {
    console.error(
      `환경 변수 ${name} 가 필요하다. 사용법은 이 파일(tools/convert-table.ts) 머리말에 있다.`,
    );
    process.exit(2);
  }
  return value;
}
/** 한 줄에 JSON 하나인 파일. 없으면 빈 목록. */
function readLines<T>(path: string, schema: z.ZodType<T>): T[] {
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map((line) => schema.parse(JSON.parse(line)));
}

const run = join(
  resolve(env('ESG_LAB_OUT')),
  process.env.TABLE_RUN ?? 'measure-openai/scope3-s100',
);
const data = resolve(env('ESG_LAB_DATA'));
const outDir = resolve(process.env.VIEWER_DATA_DIR ?? '.local-data');

const rows = z
  .array(labRowSchema)
  .parse(JSON.parse(readFileSync(join(run, 'rows.json'), 'utf8')));
// 계수 표는 만 줄이 넘는다. 행이 고른 계수만 남긴다.
const wanted = new Set(rows.flatMap((row) => row.picks));
const factors = new Map(
  readFileSync(join(data, 'factors/factors.jsonl'), 'utf8')
    .split('\n')
    .filter((line) => line.trim() !== '')
    .map((line) => JSON.parse(line) as { id: string })
    .filter((factor) => wanted.has(factor.id))
    .map((factor) => [factor.id, labFactorSchema.parse(factor)]),
);
const calls = readLines(join(run, 'calls.jsonl'), labCallSchema);
const sourceRows = readLines(
  join(data, 'scope3-examples/rows.synthetic.jsonl'),
  labSourceRowSchema,
);

const { input, counts } = buildTableInput(rows, factors, calls, sourceRows);
// 화면이 받는 것과 같은 검증을 여기서도 돌린다(뷰어의 변환 tools/convert.ts 와 같다). 통과하지 못하는 자료는 쓰지 않는다.
// 검증은 보기만 한다: 쓰는 것은 검증이 돌려준 값이 아니라 위에서 만든 input 그대로다.
const checked = parseTableInput(input);
if (!checked.ok) {
  console.error(
    'convert:table: 만든 자료가 검토 표의 입력 계약에 맞지 않는다. 아무것도 쓰지 않았다\n' +
      checked.errors.slice(0, 20).join('\n'),
  );
  process.exit(1);
}
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, 'review-table.json'), JSON.stringify(input));

console.log(`convert:table: ${join(outDir, 'review-table.json')} 에 썼다`);
console.log(
  `  행 ${counts.rows} (수량이 있는 행 ${counts.rowsWithQuantity}), 후보 ${counts.candidates}`,
);
console.log(
  `  매핑 이유가 붙은 후보 ${counts.withReason}/${counts.candidates}, 배출량(대역)이 계산된 후보 ${counts.withEmission}/${counts.candidates}`,
);
if (counts.unknownFactors > 0)
  console.log(`  계수 표에 없는 계수 id ${counts.unknownFactors}개는 뺐다`);
if (calls.length === 0)
  console.log('  호출 기록(calls.jsonl)이 없어 매핑 이유·신뢰도가 비었다');
if (sourceRows.length === 0)
  console.log(
    '  넣었던 내역(rows.synthetic.jsonl)이 없어 수량과 배출량이 비었다',
  );
