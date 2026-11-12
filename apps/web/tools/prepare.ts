// 띄우거나 빌드하기 전에 한 번 도는 준비. 만든 것은 전부 .gitignore 되어 있다.   사용: node tools/prepare.ts
//   1) 예시 PDF 둘을 만들어 public/sample/ 에 쓴다(저장소에는 PDF 를 넣지 않는다)
//   2) pdf.js 가 실행 중에 내려받는 부속 파일을 node_modules 에서 public/pdfjs/ 로 복사한다
//      (cmaps: 한글 등 CJK 글꼴의 문자 대응표, standard_fonts: 기본 글꼴, wasm: JPEG 2000 등 그림 해독기, iccs: 색 공간)
import { cpSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { writePdf } from './pdf-writer.ts';
import { SAMPLE_FILES } from './sample-layout.ts';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

mkdirSync(join(root, 'public/sample'), { recursive: true });
for (const [name, pages] of Object.entries(SAMPLE_FILES)) {
  writeFileSync(join(root, 'public/sample', name), writePdf(pages));
}

const pdfjsDir = dirname(
  fileURLToPath(import.meta.resolve('pdfjs-dist/package.json')),
);
for (const folder of ['cmaps', 'standard_fonts', 'wasm', 'iccs']) {
  cpSync(join(pdfjsDir, folder), join(root, 'public/pdfjs', folder), {
    recursive: true,
  });
}

console.log('prepare: public/sample/*.pdf 와 public/pdfjs/ 를 준비했다');
