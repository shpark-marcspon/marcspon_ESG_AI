// PDF 보기 항목 칸: 문체(A·B)를 바꿔도 고른 항목에 머문다(밴드 TRW8 ④ — 디자인 74 처방). 순수 셈 — 붙이기·밑줄·짝 셈은 건드리지 않는다.
// A·B level 이 다를 수 있다(블록 ↔ 묶음 · 표 칸 ↔ 표 전체). 찾는 차례: ⓐ 같은 unit·같은 member ⓑ 같은 unit 의 첫 항목 ⓒ 없으면 null(목록으로).
// 표 칸(cell)은 새 항목에 격자가 있고 그 행·열 칸이 있을 때만 남긴다.
import type { PdfCellAt, PdfPageView, PdfPair } from './pdfView.ts';

export function samePairIn(
  view: PdfPageView,
  pair: PdfPair,
  cell: PdfCellAt | null,
): { pair: number; cell: PdfCellAt | null } | null {
  const sameUnit = view.pairs.flatMap((each, index) =>
    each.unit === pair.unit ? [index] : [],
  );
  if (sameUnit.length === 0) return null;
  const sameMember =
    pair.member === undefined ?
      undefined
    : sameUnit.find((index) => view.pairs[index]!.member === pair.member);
  const found = sameMember ?? sameUnit[0]!;
  const grid = view.pairs[found]!.grid;
  const keep =
    cell !== null &&
    grid !== undefined &&
    grid.cells.some((each) => each.row === cell.row && each.col === cell.col);
  return { pair: found, cell: keep ? cell : null };
}
