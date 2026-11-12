// Scope 3 카테고리 C1~C15(밴드 S3W1 ①). 이름은 config/text.ts 의 S3_TEXT.categories(판 S3-02 글자 그대로).
// 1차는 C10 을 고를 수 없다(sid:MARC-ENT-315 — 판 S3-02 「비활성」). 고른 것은 화면 상태로만 쓴다 — 서버 요청에 싣지 않는다
//   (사용자 10-29 「화면 표시만」: 서버는 통합 템플릿 한 권을 코랩대로 다 센다, sid:MARC-ENT-442).

export const CATEGORY_IDS = [
  'C1',
  'C2',
  'C3',
  'C4',
  'C5',
  'C6',
  'C7',
  'C8',
  'C9',
  'C10',
  'C11',
  'C12',
  'C13',
  'C14',
  'C15',
] as const;
export type CategoryId = (typeof CATEGORY_IDS)[number];

export interface Category {
  id: CategoryId;
  /** 1~15. */
  number: number;
  /** 고를 수 없음(1차 C10). */
  disabled: boolean;
}

/** 1차에서 고를 수 없는 카테고리. */
const DISABLED: readonly CategoryId[] = ['C10'];

export const CATEGORIES: readonly Category[] = CATEGORY_IDS.map(
  (id, index) => ({
    id,
    number: index + 1,
    disabled: DISABLED.includes(id),
  }),
);

/** 고른 것을 하나 넣거나 뺀다(고를 수 없는 것은 그대로 — 고른 차례는 C 번호 차례). */
export function toggleCategory(
  chosen: readonly CategoryId[],
  id: CategoryId,
): CategoryId[] {
  const category = CATEGORIES.find((one) => one.id === id);
  if (!category || category.disabled) return [...chosen];
  const next =
    chosen.includes(id) ? chosen.filter((one) => one !== id) : [...chosen, id];
  return CATEGORY_IDS.filter((one) => next.includes(one));
}
