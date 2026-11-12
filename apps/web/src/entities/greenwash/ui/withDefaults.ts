// 부품의 text prop(바꿀 문구)을 문구 표 위에 덮을 때, 값이 undefined 인 칸은 덮지 않는다(밴드 FW1 ③, 가지 리뷰 지적).
// 빈 글자('')는 쓰는 쪽의 의도로 보고 그대로 둔다(덮는다). undefined 만 건너뛴다.
// { ...base, ...text } 는 text 에 { title: undefined } 가 오면 기본 문구를 지운다. 이 함수는 그 칸을 건너뛴다.
export function withDefaults<T extends object>(
  base: T,
  override: Partial<T> | undefined,
): T {
  const out = { ...base };
  if (!override) return out;
  for (const key of Object.keys(override) as (keyof T)[]) {
    const value = override[key];
    if (value !== undefined) out[key] = value as T[keyof T];
  }
  return out;
}
