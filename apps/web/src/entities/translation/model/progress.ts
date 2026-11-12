// 진행 카드의 전체 단계 진행 값(밴드 TRP2 TE10, 시안 TR-03 .g-bar 「2 / 3단계 · 번역 20 / 38쪽」 → 51).
// 셈(감독 정의 10-25): ((단계 - 1) + 쪽 비) / 3 × 100 을 반올림. 쪽 진행이 없거나 분모가 0 이면 쪽 비는 0, 1 을 넘지 않는다.

/** 단계 수(준비 · 번역·검수·자동 수정 · Word 만들기). */
const STAGE_COUNT = 3;

/** 0~100 정수. */
export function stageProgress(
  stageIndex: 1 | 2 | 3,
  pages?: { done: number; total: number },
): number {
  const ratio =
    pages === undefined || pages.total <= 0 ?
      0
    : Math.min(1, Math.max(0, pages.done / pages.total));
  return Math.round(((stageIndex - 1 + ratio) / STAGE_COUNT) * 100);
}
