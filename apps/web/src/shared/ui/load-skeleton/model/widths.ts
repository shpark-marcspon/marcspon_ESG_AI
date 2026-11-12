// 표 스켈레톤 막대의 폭(밴드 LD1 ②, sid:MARC-ENT-443 ②, 6c 표 막대 폭). 순수 TypeScript 다(React·DOM 을 모른다).
// 줄마다 폭이 다르되 무작위가 아니다: 정해진 차례를 줄 번호로 돈다(그릴 때마다 같은 꼴 — 시험과 스크린숏이 흔들리지 않게).

/**
 * 칸 막대의 폭. 'long'(기본) = 긴 글 칸, 줄마다 54~78%. 수 = 고정 px(연도 40 · 날짜 112).
 * 짝 [최소, 최대] = 줄마다 그 사이(버전 48~64 · 쪽 수 24~32 · 상태 48~80 · 다음 할 일 72~88).
 */
export type SkeletonWidth =
  'long' | number | readonly [min: number, max: number];
/** 칸 맞춤(표의 칸 정렬과 같은 꼴). */
export type SkeletonAlign = 'left' | 'center' | 'right';

/** 긴 글 칸의 줄별 폭(%). */
export const LONG_STEPS = [66, 54, 78, 60, 72] as const;
/** 짝의 줄별 자리(0 = 최소, 1 = 최대): 가운데·최소·최대·¼·¾. */
export const RANGE_STEPS = [0.5, 0, 1, 0.25, 0.75] as const;

/** row 번째 줄(0부터)의 막대 폭 → CSS 폭 글자('66%' · '112px'). */
export function skeletonWidthAt(width: SkeletonWidth, row: number): string {
  const step =
    ((row % LONG_STEPS.length) + LONG_STEPS.length) % LONG_STEPS.length;
  if (width === 'long') return `${LONG_STEPS[step]}%`;
  if (typeof width === 'number') return `${width}px`;
  const [min, max] = width;
  return `${Math.round(min + (max - min) * RANGE_STEPS[step]!)}px`;
}
