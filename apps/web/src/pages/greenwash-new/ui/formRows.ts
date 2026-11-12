// GW-02·02a 양식 줄의 꼴(시안 .e-formrows — gw-r1.css 87-91, GW3R A5): 묶음 위 선, 줄마다 아래 선·높이 64 이상,
// 160 라벨 칸은 옅은 회색 바탕·오른쪽 선·500 14 회색 글, 값 칸은 위아래 12·좌우 16.

/** 줄 묶음(위 선). */
export const FORM_ROWS_CLASS =
  'flex flex-col border-0 border-t border-solid border-border-tertiary';
/** 줄 하나(아래 선). */
export const FORM_ROW_CLASS =
  'flex min-h-16 items-stretch border-0 border-b border-solid border-border-tertiary';
/** 라벨 칸. */
export const FORM_LABEL_CLASS =
  'box-border flex w-40 shrink-0 items-center gap-1 border-0 border-r border-solid border-border-tertiary bg-support-grey-subtle px-6 text-style-pre-body-05 text-text-tertiary';
/** 값 칸. */
export const FORM_VALUE_CLASS = 'flex min-w-0 flex-1 px-4 py-3';
