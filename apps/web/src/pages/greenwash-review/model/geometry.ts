// 하이라이트 바깥 상자(밴드 FW2 ①, GW-05 가운데 칸). 순수 함수만.
// 결과의 position.boxes(줄마다 상자)를 모두 감싸는 상자 하나를 짓는다 — 문서 뷰어의 강조 box 에 쓴다(shapes.py Position 설명).
// position 이 null 이면 화면은 쪽 이동만 한다(그 판단은 쓰는 쪽).
import type { Box } from '../../../entities/greenwash/model/index.ts';

/** 상자들의 합집합 바깥 상자. 빈 목록이면 null. */
export function outerBox(boxes: readonly Box[]): Box | null {
  if (boxes.length === 0) return null;
  let [left, top, right, bottom] = boxes[0]!;
  for (const [l, t, r, b] of boxes) {
    left = Math.min(left, l);
    top = Math.min(top, t);
    right = Math.max(right, r);
    bottom = Math.max(bottom, b);
  }
  return [left, top, right, bottom];
}

/**
 * 쪽 그림 배율을 칸 폭에 맞춘다(밴드 GFS1, sid:MARC-ISSUE-449 — 영문번역 TRW6 의 셈과 같다). 칸이 쪽보다 좁으면 칸 폭 ÷ 쪽 폭으로 줄이고
 * (넓으면 base 그대로 — 키우지 않음), 0.01 단위로 내림(창 폭이 1px 바뀔 때마다 다시 그리지 않게). 칸 폭·쪽 폭을 모르면(0) base.
 */
export function fitScale(
  available: number,
  pageWidth: number,
  base = 1,
): number {
  if (!(available > 0 && pageWidth > 0)) return base;
  const fit = Math.floor((available / pageWidth) * 100) / 100;
  return Math.min(base, Math.max(fit, 0.01));
}
