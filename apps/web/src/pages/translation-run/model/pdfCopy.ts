// PDF 보기 상세 「번역 복사」 글(밴드 TRW14 ③ — TR-P05 c3 스펙). 순수 셈, DOM 0.
//   - 글 줄: translation[] 을 문단 사이 빈 줄(\n\n)로 잇는다. 글 안의 줄바꿈은 그대로.
//   - 칸을 맞춘 표(grid): 행마다 칸 글을 탭으로, 행은 \n 으로. 없는 칸은 빈 글. 칸 하나를 골라도 표 전체(감독 Q10 — 「보이는 글」).
//   - pipe 꼴 표 글(못 맞춘 표): 화면이 그리는 머리 + 몸 행을 같은 탭·줄 꼴로(나눔 줄은 뺀다).
//   - 번역이 없으면(source_only · translation null) null — 화면은 복사 단추를 그리지 않는다(감독 Q8).
import { pipeTableOf } from './pdfTable.ts';
import type { PdfGrid, PdfPair } from './pdfView.ts';

const rowsText = (rows: readonly (readonly string[])[]) =>
  rows.map((row) => row.join('\t')).join('\n');

function gridText(grid: PdfGrid): string {
  const at = new Map(
    grid.cells.map((cell) => [`${cell.row}:${cell.col}`, cell.translation]),
  );
  return rowsText(
    Array.from({ length: grid.rows }, (_, row) =>
      Array.from(
        { length: grid.cols },
        (_, col) => at.get(`${row}:${col}`) ?? '',
      ),
    ),
  );
}

function lineText(text: string): string {
  const table = pipeTableOf(text);
  return table === null ? text : rowsText([table.head, ...table.rows]);
}

export function copyTextOf(pair: PdfPair): string | null {
  if (pair.kind === 'source_only') return null;
  if (pair.grid !== undefined) return gridText(pair.grid);
  if (pair.translation === null) return null;
  return pair.translation.map(lineText).join('\n\n');
}
