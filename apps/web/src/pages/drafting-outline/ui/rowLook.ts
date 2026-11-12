// RP-03 목차 줄 꼴 — 트리 줄(OutlineTree)과 붙여넣기 미리보기 줄(PasteDialog)이 같은 값을 쓴다(밴드 RPW9 C7).

/** 줄 들여쓰기(px) — 판 `.rp-node` padding-left. */
export const indentOf = (depth: number) => 16 + 16 * (depth - 1);
