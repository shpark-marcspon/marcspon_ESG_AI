// 실측 산출물이 쓰는 자리 표기를 읽는다. 뷰어 부품은 이 표기를 모른다(변환 스크립트만 안다).
//
//   p59-t1:r3c1      59쪽 첫 표의 칸. r·c 는 0부터 세고 tables[].cells[r][c] 그대로다(머리 행 포함)
//   p59-t1:r3c1#n2   그 칸 안의 두 번째 숫자(1부터 센다)
//   p2-b6#n1         2쪽 여섯째 블록(문단)의 첫 번째 숫자(1부터 센다. 연도·번호 같은 것도 다 센다)

export type Ref =
  | {
      kind: 'cell';
      page: number;
      tableId: string;
      row: number;
      col: number;
      nth: number | null;
    }
  | { kind: 'block'; page: number; blockId: string; nth: number };

export type RefResult = { ok: true; ref: Ref } | { ok: false; error: string };

const CELL = /^(p(\d+)-t\d+):r(\d+)c(\d+)(?:#n(\d+))?$/;
const BLOCK = /^(p(\d+)-b\d+)#n(\d+)$/;

export function parseRef(text: string): RefResult {
  const cell = CELL.exec(text);
  if (cell) {
    const nth = cell[5] === undefined ? null : Number(cell[5]);
    if (nth === 0) return { ok: false, error: `"${text}": #n 은 1부터 센다` };
    return {
      ok: true,
      ref: {
        kind: 'cell',
        page: Number(cell[2]),
        tableId: cell[1]!,
        row: Number(cell[3]),
        col: Number(cell[4]),
        nth,
      },
    };
  }
  const block = BLOCK.exec(text);
  if (block) {
    const nth = Number(block[3]);
    if (nth === 0) return { ok: false, error: `"${text}": #n 은 1부터 센다` };
    return {
      ok: true,
      ref: { kind: 'block', page: Number(block[2]), blockId: block[1]!, nth },
    };
  }
  return {
    ok: false,
    error: `"${text}": 아는 자리 표기가 아니다(p<쪽>-t<n>:r<행>c<열>[#n<m>] 또는 p<쪽>-b<n>#n<m>)`,
  };
}

// ── 글 안의 숫자 세기 ─────────────────────────────────────────────────────────
// 「#n2」가 가리키는 것을 알려면 실측 코드와 똑같이 세어야 한다. 아래 정규식은 그쪽의 것을 옮겨 적은 것이다
// (esg-lab 의 ts/reconcile/src/domain/notation.ts, NUMBER_BODY 와 TOKEN. 커밋 1c6c194). 그쪽이 바뀌면 여기도 바꿔야 한다.
// 여기서 얻은 [start, end) 가 그쪽 값 후보의 글자 범위(where.span)와 같아야 글자 자리에서 같은 상자가 나온다.
// 어긋났는지는 measure:places 가 실제 자료로 본다(tools/lab/places.ts 머리말).
// 제품에서는 대조 결과가 자리마다 글자 범위를 같이 내주는 편이 옳다(이렇게 두 곳에서 세지 않게).
const NUMBER_BODY = String.raw`\d{1,3}(?:,\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?`;
const TOKEN = new RegExp(String.raw`(?<!\d)(${NUMBER_BODY})(%p|%)?`, 'gu');

export interface NumberToken {
  /** 숫자 부분만(뒤의 % 는 뺀다). */
  body: string;
  /** 글 안에서 시작하는 자리. */
  start: number;
  /** 끝나는 자리(그 글자는 들지 않는다). 숫자 바로 뒤의 % · %p 까지다. */
  end: number;
}

export function scanNumbers(text: string): NumberToken[] {
  return [...text.matchAll(TOKEN)].map((match) => ({
    body: match[1]!,
    start: match.index,
    end: match.index + match[0].length,
  }));
}
