// 「무엇이 골라졌는가」에 관한 순수 함수들. headless 의 useDocViewer 가 쓴다.
import type { Item } from './contract.ts';

/**
 * 상자를 눌렀을 때 고를 항목. 그 상자(들)를 가리키는 항목이 여럿이면, 누를 때마다 다음 것으로 돈다.
 * 가리키는 항목이 없으면 null.
 */
export function pickFromHighlights(
  items: readonly Item[],
  highlightIds: readonly string[],
  currentItemId: string | null,
): string | null {
  const wanted = new Set(highlightIds);
  const candidates = items.filter((item) =>
    item.highlightIds.some((id) => wanted.has(id)),
  );
  if (candidates.length === 0) return null;
  const at = candidates.findIndex((item) => item.id === currentItemId);
  return candidates[(at + 1) % candidates.length]!.id;
}

/** 키보드의 다음·이전. 끝에서 멈춘다(돌지 않는다). 아무것도 안 골라졌으면 첫 항목. */
export function neighborItem(
  items: readonly Item[],
  currentItemId: string | null,
  step: 1 | -1,
): string | null {
  if (items.length === 0) return null;
  const at = items.findIndex((item) => item.id === currentItemId);
  if (at === -1) return items[0]!.id;
  return items[Math.min(items.length - 1, Math.max(0, at + step))]!.id;
}
