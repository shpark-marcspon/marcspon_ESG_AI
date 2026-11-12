// 아주 작은 PDF 를 글자 그대로 써서 만든다. 라이브러리를 쓰지 않는다.
// 예시 자료와 테스트에만 쓴다: 색칠한 사각형, 선, 영문·숫자 글자(PDF 기본 글꼴 Helvetica)만 그릴 수 있다.
//
// PDF 안의 좌표는 원점이 왼쪽 아래다. 이 파일이 받는 좌표는 뷰어와 같은 왼쪽 위 원점이고,
// 여기서 뒤집어 적는다(toUser). 뷰어의 좌표 변환과는 따로 짠 계산이라, 브라우저 테스트에서 서로를 확인해 준다.
import type { Box } from '../src/widgets/doc-viewer/model/index.ts';
import type { SamplePage } from './sample-layout.ts';

const num = (value: number) => String(Math.round(value * 100) / 100);
const escapeText = (text: string) =>
  text.replace(/[\\()]/g, (char) => `\\${char}`);

/** 화면에 놓인 쪽의 점(왼쪽 위 원점) → PDF 안의 점(왼쪽 아래 원점, 돌리기 전). */
function toUser(page: SamplePage, x: number, y: number): [number, number] {
  // /Rotate 90: PDF 안의 쪽을 시계 방향으로 90도 돌려 보여 준다. 거꾸로 풀면 (x, y) → (y, x) 다.
  if (page.rotate === 90) return [y, x];
  return [x, page.height - y];
}

function rect(page: SamplePage, box: Box): string {
  const [ax, ay] = toUser(page, box[0], box[1]);
  const [bx, by] = toUser(page, box[2], box[3]);
  return `${num(Math.min(ax, bx))} ${num(Math.min(ay, by))} ${num(Math.abs(bx - ax))} ${num(Math.abs(by - ay))} re`;
}

function pageContent(page: SamplePage): string {
  const ops: string[] = [];

  for (const mark of page.marks) {
    ops.push(
      `${mark.color.map((c) => num(c / 255)).join(' ')} rg ${rect(page, mark.box)} f`,
    );
  }

  ops.push('0 0 0 rg 0.4 0.4 0.4 RG 0.5 w');
  const texts = [
    ...page.texts,
    ...(page.paragraphs ?? []).flatMap((paragraph) => paragraph.lines),
  ];
  for (const table of page.tables) {
    const [x0, y0, x1, y1] = table.box;
    const rowHeight = (y1 - y0) / table.rows.length;
    const colWidth = (x1 - x0) / table.rows[0]!.length;
    table.rows.forEach((row, r) => {
      row.forEach((cell, c) => {
        const cellBox: Box = [
          x0 + c * colWidth,
          y0 + r * rowHeight,
          x0 + (c + 1) * colWidth,
          y0 + (r + 1) * rowHeight,
        ];
        ops.push(`${rect(page, cellBox)} S`);
        texts.push({
          x: cellBox[0] + 8,
          top: cellBox[1] + 9,
          size: 12,
          str: cell,
        });
      });
    });
  }

  for (const text of texts) {
    // 글자의 밑줄(baseline)은 윗변에서 글자 크기의 0.8 쯤 내려온 곳이다.
    const [x, y] = toUser(page, text.x, text.top + text.size * 0.8);
    ops.push(
      `BT /F1 ${num(text.size)} Tf ${num(x)} ${num(y)} Td (${escapeText(text.str)}) Tj ET`,
    );
  }
  return ops.join('\n');
}

export function writePdf(pages: readonly SamplePage[]): Uint8Array {
  // 객체 번호: 1 = 목차(Catalog), 2 = 쪽 목록, 3 = 글꼴, 그 뒤로 쪽마다 둘(쪽, 내용).
  const objects: string[] = [];
  const pageIds = pages.map((_, index) => 4 + index * 2);

  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${pages.length} >>`;
  objects[3] =
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>';
  pages.forEach((page, index) => {
    const id = pageIds[index]!;
    const sideways = page.rotate === 90;
    const mediaBox =
      sideways ?
        `0 0 ${page.height} ${page.width}`
      : `0 0 ${page.width} ${page.height}`;
    const content = pageContent(page);
    objects[id] =
      `<< /Type /Page /Parent 2 0 R /MediaBox [${mediaBox}] /Rotate ${page.rotate} ` +
      `/Resources << /Font << /F1 3 0 R >> >> /Contents ${id + 1} 0 R >>`;
    objects[id + 1] =
      `<< /Length ${content.length} >>\nstream\n${content}\nendstream`;
  });

  // 파일 끝의 목록(xref)에는 객체마다 「파일의 몇 번째 바이트에서 시작하는가」를 적는다. 전부 ASCII 라 글자 수 = 바이트 수다.
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
  return new TextEncoder().encode(out);
}
