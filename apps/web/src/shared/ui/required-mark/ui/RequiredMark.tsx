// 필수 칸 표시(밴드 DT1 C4, 시안 gw-r1.css .e-label--req). 라벨 글 뒤 4px 주황 점, 라벨과 사이 4.
// 빨간 「*」를 갈음한다(CM-02·AD-01a·AD-03). 화면 읽기는 칸의 required 가 알리므로 점은 aria-hidden.
// 바탕 bg-text-brand = --text-brand(orange.500 #F25C2C) — GW 제외 이유 모달의 점과 같은 값.
export function RequiredMark() {
  return (
    <span
      aria-hidden
      data-required-mark=""
      className="ml-1 inline-block size-1 shrink-0 rounded-full bg-text-brand align-middle"
    />
  );
}
