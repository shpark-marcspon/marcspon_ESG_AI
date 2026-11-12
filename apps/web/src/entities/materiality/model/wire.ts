// 중대성평가 서버 값 글자(밴드 IRW1 ①). 모델·서버가 내는 값 글자는 이 파일 한 곳에만 둔다 — 다른 model·ui 는 여기 상수를 쓴다
// (발주서 §2-1 — §4 한국어 줄 검사의 예외 하나). 화면에 보이는 글은 config/text.ts(IR_TEXT) 다.
// 정본: apps/api-py/esgapi/materiality/contracts/shapes.py(영향 유형·리스크 종류 — 시킨 값) · contracts/wire.py:763-766(dateRange 문법).

/** 환경·사회 영향 유형(시킨 값 — shapes.py MaterialityImpactRow.impactType). */
export const IMPACT_POSITIVE = '긍정';
export const IMPACT_NEGATIVE = '부정';
/** 재무 영향 유형(시킨 값 — shapes.py MaterialityFinancialRow.impactType). */
export const FINANCIAL_RISK = '리스크';
export const FINANCIAL_OPPORTUNITY = '기회';
/** 리스크 종류의 머리(시킨 값 「리스크-규제 및 법률」 꼴 — 화면은 떼고 보인다). */
export const RISK_TYPE_PREFIX = '리스크-';
/** dateRange 의 끝 「오늘까지」(wire.py UNTIL_TODAY). */
export const UNTIL_TODAY = '오늘까지';

// ── 새 평가 입력(밴드 IRW2 ② — 발주서 Q2·Q7, 부록 A3). 정본: contracts/shapes.py:95-118(materiality.input@1).
/** 입력 꼴 id(shapes.py INPUT_SHAPE). */
export const INPUT_SHAPE = 'materiality.input@1';
/** 검색 언어(Q7 — 하나). */
export const MAIN_LANGUAGE = '한국어';
/** 기준 국가(Q7 — 하나, `^[A-Z]{2}$`). */
export const USER_LOCATION = 'KR';
/** 밸류체인 서버 값(Q2 — 코랩 값). */
export const VALUE_CHAIN_STAGES = [
  'upstream',
  'own operations',
  'downstream',
] as const;
export type ValueChainStage = (typeof VALUE_CHAIN_STAGES)[number];
/** 밸류체인 칸에 적힌 글 → 서버 값(Q2 — 화면·템플릿의 한국어 셋과 코랩 영어 셋 + 단수 own operation(IRW15 ②). 공백·밑줄·붙임표·대소문자는
 *  model/valueChain.ts 가 무시). */
export const VALUE_CHAIN_STAGE_WORDS: Readonly<
  Record<ValueChainStage, readonly string[]>
> = {
  upstream: ['업스트림', 'upstream'],
  'own operations': ['자체운영', 'own operations', 'own operation'],
  downstream: ['다운스트림', 'downstream'],
};
