// layout 상자(PDF 포인트, 왼쪽 위 원점) → 그려진 쪽 위 CSS 픽셀(밴드 TRW6 ③). 셈은 공용 뷰어 boxToScreenRect(회전 0) 그대로 —
// 쪽 크기(layout pages[].width·height)를 못 찾아 0 이면 null(상자를 그리지 않는다 — 0 나눔·엉뚱한 자리를 막는다).
import { boxToScreenRect } from '../../../../widgets/doc-viewer/index.ts';
import type { ScreenRect } from '../../../../widgets/doc-viewer/index.ts';

export function screenRectOf(
  bbox: readonly [number, number, number, number],
  page: { width: number; height: number },
  scale: number,
): ScreenRect | null {
  if (!(page.width > 0 && page.height > 0)) return null;
  return boxToScreenRect(bbox, page, scale);
}

/** 쪽 그림 칸 크기(CSS 픽셀). 쪽 크기를 모르면 null. */
export const pageBoxOf = (
  page: { width: number; height: number },
  scale: number,
): { width: number; height: number } | null =>
  page.width > 0 && page.height > 0 ?
    { width: page.width * scale, height: page.height * scale }
  : null;

/**
 * 칸 폭에 맞춘 쪽 그림 배율(밴드 TRW6 ⑤ — 6c B1: 1280 에서 쪽 그림이 짝 칸을 덮음). 칸이 쪽보다 좁으면 칸 폭 ÷ 쪽 폭으로 줄이고
 * (넓으면 base 그대로 — 키우지 않음), 0.01 단위로 내림(창 폭이 1px 바뀔 때마다 다시 그리지 않게). 칸 폭·쪽 폭을 모르면 base.
 */
export function fitScale(
  available: number,
  pageWidth: number,
  base: number,
): number {
  if (!(available > 0 && pageWidth > 0)) return base;
  const fit = Math.floor((available / pageWidth) * 100) / 100;
  return Math.min(base, Math.max(fit, 0.01));
}

/** 칸 폭이 이만큼 넘게 늘어야 받는다(CSS 픽셀 — 일반 스크롤바 폭 15~17 보다 크게). */
export const WIDEN_SLACK = 20;

/**
 * 잰 칸 폭을 받을지(밴드 TRW13 A — 컨설턴트 댓글: 가로 쪽에서 확인할 곳을 누르면 쪽이 흔들림). 공간을 차지하는 스크롤바 아래에서
 * 스크롤바 생김 → 폭 줄어 배율 줄어 → 쪽이 낮아져 스크롤바 사라짐 → 폭 늘어 → … 가 돈다. 줄어듦은 바로 받고(쪽이 칸을 넘지 않게),
 * 늘어남은 WIDEN_SLACK 을 넘을 때만 받는다 — 스크롤바 하나만큼 다시 넓어진 것은 무시해 순환이 멈춘다.
 * 값: 창을 20px 안에서만 넓히면 쪽 그림이 그만큼 작게 남는다(감독 0f 11-10 받아들임). 처음(held 0)은 그대로 받는다.
 */
export function settleWidth(held: number, measured: number): number {
  if (held <= 0 || measured <= held) return measured;
  return measured - held > WIDEN_SLACK ? measured : held;
}
