// 셀렉터 한 꼴(sid:MARC-ENT-430 — 시안 .e-select): 거르기 칸(FilterSelect)과 기본 select(NativeSelect)가 이 자리 하나를 쓴다.
// 쓰는 자리에서 select 꼴 클래스를 다시 적지 않는다. 값: 높이 36·모서리 8(component)·좌우 16·테두리 tertiary·글 pre-body-06 secondary,
//   초점 2px border-secondary(밖 2), 꺼짐은 키트 꺼짐 꼴(opacity 40). 최소 너비 140 은 토큰이 없어 임의 값(AD4R ③).

/** 최소 너비(쓰는 쪽 className 이 이긴다). */
export const SELECT_MIN_WIDTH = 'min-w-[140px]';

/** 상자 꼴 — 테두리·바탕·글·초점·꺼짐. 폭과 늘어놓기는 쓰는 쪽이 정한다. */
export const SELECT_LOOK =
  'box-border h-9 cursor-pointer rounded-component border border-solid border-border-tertiary bg-background-primary px-4 text-style-pre-body-06 text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary disabled:cursor-not-allowed disabled:opacity-40';

/** ▾ 꼴(16·tertiary). */
export const SELECT_CHEVRON = 'size-4 text-text-tertiary';
