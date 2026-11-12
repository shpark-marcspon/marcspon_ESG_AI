// 묶음 표(BatchTable)의 머리 칸·몸 칸 클래스(밴드 TRP2 TC3).
// shared/ui/data-table/ui/DataTable.tsx:90(머리)·:138(몸)과 같은 꼴 — 묶음마다 <tbody>·펼침 줄 때문에 부품을 못 쓴다(DataTable 은 tbody 하나·평평한 줄).
// 공통화(DataTable 이 펼침 줄을 받게)는 후속. DataTable 의 꼴이 바뀌면 여기도 같이 바꾼다.
export const TABLE_CLASS = 'w-full border-collapse';
export const TH_CLASS =
  'h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-left text-style-pre-body-05 text-text-tertiary';
export const TD_CLASS =
  'h-14 border-b border-solid border-border-tertiary px-4 text-left text-style-pre-body-06 text-text-secondary';
