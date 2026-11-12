// 코드로 만든 예시 PDF 를 pdf.js 로 다시 읽어, 글자가 적어 둔 자리에 있는지 본다.
// (PDF 를 쓰는 쪽의 뒤집기와, pdf.js 가 읽는 자리가 서로 맞는지. 브라우저 없이 node 에서 돈다.)
// 글자 층을 읽는 것은 이 테스트뿐이다. 뷰어도 변환도 PDF 의 글자를 읽지 않는다(좁은 상자는 글자 자리 파일에서 온다).
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
// node 에서는 legacy 빌드를 쓴다(pdf.js 의 안내).
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { describe, expect, it } from 'vitest';

import { writePdf } from './pdf-writer.ts';
import { SAMPLE_A, glyphWidth } from './sample-layout.ts';

const pdfjsDir = dirname(
  fileURLToPath(import.meta.resolve('pdfjs-dist/package.json')),
);

interface Piece {
  str: string;
  /** 쪽 좌표(왼쪽 위 원점)에서 글자 토막의 왼쪽 끝, 밑줄의 높이, 폭. */
  x: number;
  baseline: number;
  width: number;
  /** 글자의 위 끝과 아래 끝: 밑줄에서 글꼴의 올림·내림(pdf.js 가 글꼴에서 읽은 값 × 글자 크기)만큼 떨어진 곳. 어림이 아니다. */
  top: number;
  bottom: number;
}

/** 그 쪽의 글자 토막들. pdf.js 가 주는 자리(왼쪽 아래 원점)를 쪽 좌표로 옮긴다. 예시 PDF 의 1·2쪽은 돌아가 있지 않아 y 만 뒤집으면 된다. */
async function readPieces(
  pdf: Uint8Array,
  pageNumber: number,
): Promise<{ pageCount: number; pieces: Piece[] }> {
  const doc = await getDocument({
    data: pdf,
    standardFontDataUrl: join(pdfjsDir, 'standard_fonts/'),
    disableFontFace: true,
    verbosity: 0,
  }).promise;
  try {
    const page = await doc.getPage(pageNumber);
    const height = page.getViewport({ scale: 1 }).height;
    const content = await page.getTextContent();
    const pieces = content.items.flatMap((item) => {
      if (!('str' in item) || item.str === '') return [];
      const baseline = height - (item.transform[5] as number);
      const font = content.styles[item.fontName]!;
      return [
        {
          str: item.str,
          x: item.transform[4] as number,
          baseline,
          width: item.width,
          top: baseline - font.ascent * item.height,
          bottom: baseline - font.descent * item.height,
        },
      ];
    });
    return { pageCount: doc.numPages, pieces };
  } finally {
    await doc.loadingTask.destroy();
  }
}

describe('예시 PDF', () => {
  it('쪽 수가 맞고, 표의 값이 그 칸 안에서 읽힌다', async () => {
    const { pageCount, pieces } = await readPieces(writePdf(SAMPLE_A), 1);
    expect(pageCount).toBe(3);
    const table = SAMPLE_A[0]!.tables[0]!;
    // 글자가 통째로 그 상자 안에 있는가: 가로는 토막의 양 끝, 세로는 글자의 위 끝과 아래 끝(밑줄 한 줄만 보지 않는다).
    const inBox = (piece: Piece, [x0, y0, x1, y1]: readonly number[]) =>
      piece.x >= x0! &&
      piece.x + piece.width <= x1! &&
      piece.top >= y0! &&
      piece.bottom <= y1!;

    // 표 안에서 「1,234」는 r1c2 칸(372~522, 230~260) 하나뿐이다.
    const found = pieces.filter(
      (piece) => piece.str === '1,234' && inBox(piece, table.box),
    );
    expect(found).toHaveLength(1);
    expect(inBox(found[0]!, [372, 230, 522, 260])).toBe(true);

    // 표 밖(문장)의 「1,234」는 표 영역에는 없고, 문장 영역에 하나 있다(pdf.js 는 한 줄에 이어 놓인 토막을 한 토막으로 읽는다).
    const sentence = pieces.filter((piece) =>
      inBox(piece, [72, 114, 523, 136]),
    );
    expect(
      sentence
        .map((piece) => piece.str.split('1,234').length - 1)
        .reduce((sum, n) => sum + n, 0),
    ).toBe(1);
  });

  it('두 줄 문단: pdf.js 가 읽은 줄의 자리와 폭이, 글자 폭 표로 셈한 것과 같다(문장 강조 예시의 상자가 이 셈에서 나온다)', async () => {
    const { pieces } = await readPieces(writePdf(SAMPLE_A), 2);
    const lines = SAMPLE_A[1]!.paragraphs![0]!.lines;
    expect(lines).toHaveLength(2);
    for (const line of lines) {
      const piece = pieces.find((candidate) => candidate.str === line.str);
      expect(piece, line.str).toBeDefined();
      const width = [...line.str].reduce(
        (sum, char) => sum + glyphWidth(char, line.size),
        0,
      );
      expect(piece!.x).toBeCloseTo(line.x, 1);
      expect(piece!.baseline).toBeCloseTo(line.top + line.size * 0.8, 1);
      // 글자 폭 표가 한 글자라도 틀리면 줄의 폭이 달라진다.
      expect(piece!.width).toBeCloseTo(width, 1);
    }
  });
});
