// 영문번역 파트(밴드 TRW0a ②, 결정 sid:MARC-ENT-392 — 파트마다 실행 하나). 이름 글은 config/text.ts.
// 서버의 파트 이름(ceo_message 꼴)과 잇는 것은 어댑터 몫이다(이 밴드 밖).

/** 파트 셋. 차례가 화면의 차례다(알약·글자 칸·범례·겹친 쪽 점). */
export const PART_KEYS = ['ceo', 'story', 'general'] as const;
export type PartKey = (typeof PART_KEYS)[number];
/** 파트 → 차례(0부터). 겹친 쪽의 파트를 차례대로 늘어놓을 때 쓴다. */
export const PART_ORDER: Readonly<Record<PartKey, number>> = {
  ceo: 0,
  story: 1,
  general: 2,
};
