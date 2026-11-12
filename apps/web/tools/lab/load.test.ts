// 변환이 PDF 파일 자체를 본다: 문서 모델(document.json)의 source.sha256 은 분해한 PDF 파일 바이트의 sha256 이다.
// ESG_REPORTS 의 PDF 가 그 파일이 아니면(다른 판이면) 상자가 엉뚱한 자리를 가리키므로, 변환은 멈추고 아무것도 쓰지 않는다.
// 작은 가짜 파일로 본다(PDF 의 속은 읽지 않으므로 아무 바이트나 된다). 실제 자료는 쓰지 않는다.
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
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

import { LabInputError, assertSamePdf } from './load.ts';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const sha256 = (bytes: string) =>
  createHash('sha256').update(bytes).digest('hex');
const PDF_A = '가짜 PDF 의 바이트 A';
const PDF_B = '가짜 PDF 의 바이트 B';
const OTHER = '다른 판의 바이트';

const dirs: string[] = [];
afterEach(() => {
  for (const dir of dirs.splice(0))
    rmSync(dir, { recursive: true, force: true });
});

describe('assertSamePdf', () => {
  function pdfFile(bytes: string | null) {
    const root = mkdtempSync(join(tmpdir(), 'web-load-test-'));
    dirs.push(root);
    const pdfPath = join(root, 'doc.pdf');
    if (bytes !== null) writeFileSync(pdfPath, bytes);
    return pdfPath;
  }
  const side = (pdfPath: string, hash: string) => ({
    name: 'doc',
    pdfPath,
    document: { source: { sha256: hash } },
  });

  it('PDF 파일의 해시가 문서 모델의 것과 같으면 지나간다', () => {
    expect(() =>
      assertSamePdf(side(pdfFile(PDF_A), sha256(PDF_A))),
    ).not.toThrow();
  });
  it('다르면 멈추고, 어느 파일인지와 두 해시의 앞머리를 말한다', () => {
    const pdfPath = pdfFile(OTHER);
    expect(() => assertSamePdf(side(pdfPath, sha256(PDF_A)))).toThrow(
      LabInputError,
    );
    expect(() => assertSamePdf(side(pdfPath, sha256(PDF_A)))).toThrow(
      new RegExp(
        `doc\\.pdf.*${sha256(OTHER).slice(0, 12)}.*${sha256(PDF_A).slice(0, 12)}`,
        's',
      ),
    );
  });
  it('PDF 파일이 없으면 멈춘다(스택이 아니라 읽을 수 있는 말로)', () => {
    expect(() => assertSamePdf(side(pdfFile(null), sha256(PDF_A)))).toThrow(
      LabInputError,
    );
    expect(() => assertSamePdf(side(pdfFile(null), sha256(PDF_A)))).toThrow(
      /PDF 가 없다/,
    );
  });
});

describe('convert (스크립트를 실제로 돌린다)', () => {
  /** 임시 폴더에 산출물 꼴로 파일을 놓는다. 문서 모델은 늘 PDF_A·PDF_B 의 것이고, 실제로 놓는 PDF 의 바이트를 쪽마다 따로 줄 수 있다. */
  function arrange(pdfB: string, pdfA: string = PDF_A) {
    const root = mkdtempSync(join(tmpdir(), 'web-convert-test-'));
    dirs.push(root);
    const document = (bytes: string) => ({
      source: { sha256: sha256(bytes) },
      pages: [{ page: 1, width: 600, height: 800 }],
      blocks: [
        {
          id: 'p1-b1',
          page: 1,
          kind: 'paragraph',
          bbox: [10, 10, 200, 30],
          text: '지어낸 문장이다. 값은 12이다.',
        },
      ],
      tables: [],
    });
    for (const [name, bytes] of [
      ['one', PDF_A],
      ['two', PDF_B],
    ] as const) {
      mkdirSync(join(root, 'out', `parse-${name}`), { recursive: true });
      writeFileSync(
        join(root, 'out', `parse-${name}`, 'document.json'),
        JSON.stringify(document(bytes)),
      );
    }
    mkdirSync(join(root, 'out', 'run'), { recursive: true });
    writeFileSync(
      join(root, 'out', 'run', 'outcome.json'),
      JSON.stringify({ after: { verdicts: [] }, states: { a: {}, b: {} } }),
    );
    mkdirSync(join(root, 'reports'));
    writeFileSync(join(root, 'reports', 'one.pdf'), pdfA);
    writeFileSync(join(root, 'reports', 'two.pdf'), pdfB);
    const outDir = join(root, 'viewer-data');
    const env = {
      PATH: process.env.PATH ?? '',
      ESG_LAB_OUT: join(root, 'out'),
      ESG_REPORTS: join(root, 'reports'),
      VIEWER_DOC_A: 'one',
      VIEWER_DOC_B: 'two',
      VIEWER_RUN: 'run',
      VIEWER_DATA_DIR: outDir,
    };
    const run = () =>
      spawnSync(process.execPath, ['tools/convert.ts'], {
        cwd: webRoot,
        env,
        encoding: 'utf8',
      });
    return { outDir, run };
  }

  it('두 PDF 가 문서 모델의 그 파일이면 변환하고 PDF 를 복사한다', () => {
    const { outDir, run } = arrange(PDF_B);
    const result = run();
    expect(result.stderr).toBe('');
    expect(result.status).toBe(0);
    expect(readdirSync(outDir).sort()).toEqual([
      'a.pdf',
      'b.pdf',
      'index.json',
      'places-report.json',
      'reconcile.json',
      'sentences.json',
    ]);
    expect(readFileSync(join(outDir, 'b.pdf'), 'utf8')).toBe(PDF_B);
  });

  it('한쪽 PDF 가 다른 판이면 멈추고(종료 코드 1) 아무것도 쓰지 않는다. 결과 폴더도 만들지 않는다', () => {
    const { outDir, run } = arrange(OTHER);
    const result = run();
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/two\.pdf/);
    expect(result.stderr).toMatch(/다른 파일/);
    expect(existsSync(outDir)).toBe(false);
  });

  it('다른 판인 것이 a 쪽 PDF 여도 똑같이 멈춘다(두 문서를 다 본다)', () => {
    const { outDir, run } = arrange(PDF_B, OTHER);
    const result = run();
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/one\.pdf/);
    expect(result.stderr).toMatch(/다른 파일/);
    expect(existsSync(outDir)).toBe(false);
  });
});
