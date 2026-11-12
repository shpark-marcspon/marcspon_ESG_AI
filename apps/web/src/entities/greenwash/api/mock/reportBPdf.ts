// 실호출 씨앗(run-106) 문서 「B.pdf」의 지은 PDF(밴드 GVS1). 원본 보고서가 아니다 — 결과의 문장 상자 자리에 지어낸 글(MMMM…)만 둔다.
// 목 저장소가 처음 열 때만 지은다(mockStore.ts 의 openDocumentPdf 가 import() 로 부른다). 디스크에 .pdf 를 두지 않는다.
// src 는 src 밖(tools/pdf-writer.ts)을 가져오지 못해([M2], app/guards/layers.test.ts) 여기에 몇 줄로 따로 쓴다: 글자(Helvetica)만.
// 쪽 크기는 842×595(가로 A4 — 상자의 오른끝이 801 까지 간다. 원본 쪽 크기는 결과에 없어 짐작한 값).
import type { ScanResult } from '../../model/index.ts';

const WIDTH = 842;
const HEIGHT = 595;
/** Helvetica 「M」의 폭(글자 크기 1000 기준, Adobe Helvetica AFM). */
const M_WIDTH = 833;

const num = (value: number) => String(Math.round(value * 100) / 100);

/** 쪽마다의 글 조각: 상자마다 그 높이 크기로 상자 폭을 채우는 MMMM…(왼쪽 위 원점 → PDF 왼쪽 아래 원점). */
function pageContents(result: ScanResult, pageCount: number): string[] {
  const ops: string[][] = Array.from({ length: pageCount }, (_, i) => [
    `BT /F1 10 Tf 36 ${num(HEIGHT - 28)} Td (Page ${i + 1}) Tj ET`,
  ]);
  for (const item of result.items) {
    const position = item.position;
    if (position === null) continue;
    const page = ops[position.page - 1];
    if (page === undefined) continue;
    for (const [left, top, right, bottom] of position.boxes) {
      const size = Math.max(bottom - top, 4);
      const count = Math.max(
        1,
        Math.floor((right - left) / ((size * M_WIDTH) / 1000)),
      );
      page.push(
        `BT /F1 ${num(size)} Tf ${num(left)} ${num(HEIGHT - top - size * 0.8)} Td (${'M'.repeat(count)}) Tj ET`,
      );
    }
  }
  return ops.map((page) => page.join('\n'));
}

/** run-106 결과로 쪽 pageCount 개짜리 PDF 파일을 짓는다. */
export function reportBPdf(
  result: ScanResult,
  fileName: string,
  pageCount: number,
): File {
  // 객체 번호: 1 = 목차, 2 = 쪽 목록, 3 = 글꼴, 그 뒤로 쪽마다 둘(쪽, 내용).
  const contents = pageContents(result, pageCount);
  const pageIds = contents.map((_, index) => 4 + index * 2);
  const objects: string[] = [];
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pageCount} >>`;
  objects[3] =
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>';
  contents.forEach((content, index) => {
    const id = pageIds[index]!;
    objects[id] =
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${WIDTH} ${HEIGHT}] ` +
      `/Resources << /Font << /F1 3 0 R >> >> /Contents ${id + 1} 0 R >>`;
    objects[id + 1] =
      `<< /Length ${content.length} >>\nstream\n${content}\nendstream`;
  });
  // 끝의 목록(xref)은 객체마다 시작 바이트 자리. 전부 ASCII 라 글자 수 = 바이트 수다.
  let out = '%PDF-1.4\n';
  const offsets: number[] = [];
  for (let id = 1; id < objects.length; id++) {
    offsets[id] = out.length;
    out += `${id} 0 obj\n${objects[id]}\nendobj\n`;
  }
  const xrefAt = out.length;
  out += `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
  for (let id = 1; id < objects.length; id++)
    out += `${String(offsets[id]).padStart(10, '0')} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`;
  return new File([new TextEncoder().encode(out)], fileName, {
    type: 'application/pdf',
  });
}
