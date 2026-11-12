// S3 상세 표 꼴 하나(밴드 W12-1c ② #1·#2 — 판 S12-03 `.f12b-th`·`.f12b-td`·`.f12b-td--sum`). 블록·총합·히스토리·계수 표가 같이 쓴다.
//   머리 44 · 바탕 support-grey-subtle · 14px/500 tertiary · 위아래 1px border-tertiary · 안쪽 8·16.
//   칸 최소 56(표 칸의 height 는 최소 높이로 동작) · 아래 1px border-quaternary · 세로 가운데 · 안쪽 8·16.
//   표는 border-separate + spacing 0 — 오른쪽 고정 열(sticky)의 선이 스크롤과 같이 간다.

/** 표 자체. */
export const TABLE = 'border-separate border-spacing-0';

/** 머리 칸. */
export const HEAD_CELL =
  'box-border h-11 whitespace-nowrap border-x-0 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 py-2 text-left align-middle text-style-pre-body-05 text-text-tertiary';

/** 본문 칸. */
export const CELL =
  'box-border h-14 border-x-0 border-b border-t-0 border-solid border-border-quaternary px-4 py-2 align-middle text-style-pre-body-06 text-text-secondary';

/** 총합 줄 칸(CELL 뒤에 덧붙임). */
export const SUM_CELL = 'bg-support-grey-subtle text-style-pre-body-04';
