// 양식 줄의 꼴(밴드 DT1 ③, sid:MARC-ISSUE-384). 시안 .e-formrows(gw-r1.css 87-91): 묶음 위 선, 줄마다 아래 선·높이 64 이상,
// 160 라벨 칸은 옅은 회색 바탕·오른쪽 선·500 14 회색 글, 값 칸은 위아래 12·좌우 16. DV-00 의 값 글 400 16(시안 DV-00_r1 66-71)은 FORM_VALUE_BODY_CLASS.
// 모듈 사본 넷(greenwash-new·translation-new·dataverify-new·dataverify-intro 의 ui/formRows.ts)을 걷으려고 올렸다 — 클래스 상수만(글 0, 구성 요소 아님).
// 묶음의 m-0 은 div 에서는 그림이 같고 dl·ul 에서 바깥 여백을 0 으로 한다(dataverify-intro 꼴).

/** 줄 묶음(위 선). */
export const FORM_ROWS_CLASS =
  'm-0 flex flex-col border-0 border-t border-solid border-border-tertiary';
/** 줄 하나(아래 선, 높이 64 이상). */
export const FORM_ROW_CLASS =
  'flex min-h-16 items-stretch border-0 border-b border-solid border-border-tertiary';
/** 라벨 칸(160). */
export const FORM_LABEL_CLASS =
  'box-border flex w-40 shrink-0 items-center gap-1 border-0 border-r border-solid border-border-tertiary bg-support-grey-subtle px-6 text-style-pre-body-05 text-text-tertiary';
/** 값 칸(입력·컨트롤을 담는 자리). */
export const FORM_VALUE_CLASS = 'flex min-w-0 flex-1 px-4 py-3';
/** 값 칸 — 글만 담는 꼴(400 16, 가운데 맞춤. DV-00). */
export const FORM_VALUE_BODY_CLASS =
  'm-0 flex min-w-0 flex-1 items-center px-4 py-3 text-style-pre-body-03 text-text-secondary';
