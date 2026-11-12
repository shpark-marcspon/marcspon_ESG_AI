// 추정 표식 꼴 하나(밴드 W12-1c ② #7, 감독 처분 Q9 — S2 InventoryTable 의 손 그림 물결을 빼 S2·S3 가 같이 쓴다).
//   20 상자 · radius 2 · 켬 bg-background-brand text-text-brand / 끔 bg-button-white text-text-tertiary. 꼴만 — 뜻·글·동작은 부르는 쪽(sid:MARC-ENT-462 답 대기).

/** 상자 꼴(켬/끔). */
export const estimatedBox = (on: boolean) =>
  `inline-flex size-5 shrink-0 items-center justify-center rounded-[2px] ${
    on ?
      'bg-background-brand text-text-brand'
    : 'bg-button-white text-text-tertiary'
  }`;

/** 물결 두 줄 — 판 S12-03 `.f12b-est` path(x 4→16 · 8·12 · 선 1.4, W12-1d N4)(늘 aria-hidden — 이름은 감싸는 쪽이 준다). */
export function EstimatedWave() {
  return (
    <svg
      aria-hidden
      data-mark="estimated-wave"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeMiterlimit="10"
      strokeLinecap="round"
      className="size-full"
    >
      <path d="M4 8C5.49538 5.33333 8.49538 5.33333 10 8C11.4954 10.6667 14.5046 10.6667 16 8" />
      <path d="M4 12C5.49538 9.33333 8.50462 9.33333 10 12C11.4954 14.6667 14.5046 14.6667 16 12" />
    </svg>
  );
}
