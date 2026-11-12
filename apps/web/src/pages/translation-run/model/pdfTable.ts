// 표 짝 글의 pipe 꼴 → 행·열 순수 셈(밴드 TRW7 ① W3, 6c v182 TR-P05 .tp-mtbl). DOM 0.
// pipe 꼴 = 빈 줄을 뺀 줄이 모두 「|」로 시작·끝나고, 둘째 줄이 나눔 줄(| --- | :-: | …). 첫 줄이 머리, 나눔 줄 다음이 몸.
// 아니면 null — 화면은 지금처럼 문단으로 그린다. 칸 글은 앞뒤 공백을 뗀다(「\|」 같은 이스케이프는 다루지 않는다).
export interface PipeTable {
  head: string[];
  rows: string[][];
  /** 열 수(머리·몸 줄 중 가장 많은 칸). */
  cols: number;
}

const DIVIDER = /^\|(\s*:?-{3,}:?\s*\|)+$/;

const cellsOf = (line: string) =>
  line
    .slice(1, -1)
    .split('|')
    .map((cell) => cell.trim());

export function pipeTableOf(text: string): PipeTable | null {
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line !== '');
  if (lines.length < 2) return null;
  if (
    !lines.every(
      (line) => line.length > 1 && line.startsWith('|') && line.endsWith('|'),
    )
  )
    return null;
  if (!DIVIDER.test(lines[1]!.replace(/\s+/g, ' '))) return null;
  if (lines.slice(2).some((line) => DIVIDER.test(line))) return null;
  const head = cellsOf(lines[0]!);
  const rows = lines.slice(2).map(cellsOf);
  const cols = Math.max(head.length, ...rows.map((row) => row.length));
  return { head, rows, cols };
}
