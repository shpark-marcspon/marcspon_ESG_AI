// 검토 표의 변환(convert:table)을 스크립트째 돌려 본다. 작은 가짜 산출물로 본다. 실제 자료는 쓰지 않는다.
// 지키려는 것: 만든 자료가 표의 입력 계약에 맞지 않으면 멈추고 아무것도 쓰지 않는다(화면이 못 읽을 파일을 남기지 않는다).
import { spawnSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';

import { parseTableInput } from '../src/widgets/review-table/model/index.ts';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const dirs: string[] = [];
afterEach(() => {
  for (const dir of dirs.splice(0))
    rmSync(dir, { recursive: true, force: true });
});

const labRow = (rowId: string, itemName: string) => ({
  rowId,
  itemName,
  unit: 'kg',
  status: 'recommended',
  predictedCategory: 1,
  picks: ['f1'],
  basis: { used: 'activity' },
  calcStatus: 'computed',
});
const FACTOR = {
  id: 'f1',
  name: { original: 'factor f1', ko: '수지' },
  value: 1.5,
  unit: 'kg CO2e/kg',
  unit_denominator: 'kg',
  source: { name: '계수표' },
};

describe('convert:table (스크립트를 실제로 돌린다)', () => {
  /** 임시 폴더에 산출물 꼴로 파일을 놓는다: 실행 결과의 행들과 계수 표 한 줄. */
  function arrange(rows: object[]) {
    const root = mkdtempSync(join(tmpdir(), 'web-convert-table-test-'));
    dirs.push(root);
    mkdirSync(join(root, 'out', 'run'), { recursive: true });
    writeFileSync(join(root, 'out', 'run', 'rows.json'), JSON.stringify(rows));
    mkdirSync(join(root, 'data', 'factors'), { recursive: true });
    writeFileSync(
      join(root, 'data', 'factors', 'factors.jsonl'),
      JSON.stringify(FACTOR) + '\n',
    );
    const outDir = join(root, 'viewer-data');
    const env = {
      PATH: process.env.PATH ?? '',
      ESG_LAB_OUT: join(root, 'out'),
      ESG_LAB_DATA: join(root, 'data'),
      TABLE_RUN: 'run',
      VIEWER_DATA_DIR: outDir,
    };
    const run = () =>
      spawnSync(process.execPath, ['tools/convert-table.ts'], {
        cwd: webRoot,
        env,
        encoding: 'utf8',
      });
    return { outDir, run };
  }

  it('행이 계약에 맞으면 review-table.json 하나를 쓰고, 그 파일이 표의 입력 계약을 통과한다', () => {
    const { outDir, run } = arrange([
      labRow('r1', '수지 원료'),
      labRow('r2', '포장재'),
    ]);
    const result = run();
    expect(result.stderr).toBe('');
    expect(result.status).toBe(0);
    expect(readdirSync(outDir)).toEqual(['review-table.json']);
    const written = parseTableInput(
      JSON.parse(readFileSync(join(outDir, 'review-table.json'), 'utf8')),
    );
    expect(written.ok && written.input.rows.map((row) => row.id)).toEqual([
      'r1',
      'r2',
    ]);
  });

  it('행의 id 가 겹치면 멈추고(종료 코드 1) 아무것도 쓰지 않는다. 결과 폴더도 만들지 않는다', () => {
    const { outDir, run } = arrange([
      labRow('r1', '수지 원료'),
      labRow('r1', '포장재'),
    ]);
    const result = run();
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/계약에 맞지 않는다/);
    expect(result.stderr).toMatch(/r1/);
    expect(existsSync(outDir)).toBe(false);
  });
});
