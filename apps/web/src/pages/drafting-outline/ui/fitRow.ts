// 고른 줄 보이기(밴드 RPW7 §1-G + critic 1). scrollIntoView 는 쓰지 않는다 — 가운데 맞춤·창 움직임을 고를 수 없다.
// 먼저 목록만 넘친 만큼 굴리고(pages/greenwash-review/ui/ReviewPagePane.tsx fitInside 꼴), 그래도 줄이 창 밖이면 창을 넘친 만큼만 굴린다.
// 올림: scrollTop 은 정수로 맞춰져 틀 자리가 소수면 줄 끝이 조금 잘린다(1280 에서 0.375px 잼).
export function fitRow(box: HTMLElement, row: HTMLElement) {
  const outer = box.getBoundingClientRect();
  const before = row.getBoundingClientRect();
  if (before.top < outer.top)
    box.scrollTop -= Math.ceil(outer.top - before.top);
  else if (before.bottom > outer.bottom)
    box.scrollTop += Math.ceil(before.bottom - outer.bottom);
  const inner = row.getBoundingClientRect();
  if (inner.top < 0) window.scrollBy(0, Math.floor(inner.top));
  else if (inner.bottom > window.innerHeight)
    window.scrollBy(0, Math.ceil(inner.bottom - window.innerHeight));
}
