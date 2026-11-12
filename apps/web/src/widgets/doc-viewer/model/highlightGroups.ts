// 한 쪽에 그릴 상자들을 정한다.
//
// 같은 자리를 가리키는 강조가 여럿일 수 있다(한 표의 칸 서른 개가 전부 「그 표」 상자를 가진다).
// 그대로 그리면 서른 겹이 되므로, 자리가 같은 것끼리 묶어 상자 하나로 그린다.
// 묶음을 누르면 그 안의 항목을 차례로 돈다(selection.ts 의 pickFromHighlights).
//
// 강조 하나의 모양은 상자 하나가 아니라 상자 여럿일 수 있다(여러 줄에 걸친 문장은 줄마다 하나).
// 「같은 자리」는 그 상자들이 전부 같다는 뜻이다. 묶음 하나가 상자 여럿을 가지고, 화면에서는 한 덩어리로 다룬다.
import { innerBoxesOf } from './contract.ts';
import type { Highlight } from './contract.ts';
import type { Box } from './geometry.ts';

export interface HighlightGroup {
  key: string;
  /** 그릴 상자들. 하나 이상이다. 좁힌 자리가 여러 줄이면 줄마다 하나. */
  boxes: readonly Box[];
  highlightIds: string[];
  /** 묶음 안의 종류가 하나면 그 종류, 섞였으면 null. */
  kind: string | null;
  selected: boolean;
  /** 목록에서 가리킨(마우스를 올렸거나 초점이 간) 항목의 강조가 들어 있는가. */
  pointed: boolean;
  /** 좁힌 자리(innerBoxes)로 그린 것인가. */
  narrowed: boolean;
  text?: string;
}

/** 강조 하나를 어느 상자(들)로 그리는가: 좁힌 자리를 쓰기로 했고 있으면 그것, 아니면 표·문단 전체 상자 하나. */
export function shapeOf(
  highlight: Highlight,
  useInnerBox: boolean,
): { boxes: readonly Box[]; narrowed: boolean } {
  const inner = useInnerBox ? innerBoxesOf(highlight) : [];
  if (inner.length > 0) return { boxes: inner, narrowed: true };
  return { boxes: [highlight.box], narrowed: false };
}

/** 상자들을 전부 감싸는 상자. 강조로 갈 때의 스크롤 자리를 여기서 잰다(headless 의 useDocViewer). */
export function unionBox(boxes: readonly Box[]): Box {
  return [
    Math.min(...boxes.map((b) => b[0])),
    Math.min(...boxes.map((b) => b[1])),
    Math.max(...boxes.map((b) => b[2])),
    Math.max(...boxes.map((b) => b[3])),
  ];
}

const NONE: ReadonlySet<string> = new Set();
const area = (boxes: readonly Box[]) =>
  boxes.reduce((sum, box) => sum + (box[2] - box[0]) * (box[3] - box[1]), 0);

export function groupHighlights(
  highlights: readonly Highlight[],
  selectedIds: ReadonlySet<string>,
  useInnerBox: boolean,
  pointedIds: ReadonlySet<string> = NONE,
): HighlightGroup[] {
  const groups = new Map<string, HighlightGroup>();
  for (const h of highlights) {
    const { boxes, narrowed } = shapeOf(h, useInnerBox);
    const key = boxes.map((box) => box.join(',')).join(';');
    const group = groups.get(key);
    if (group) {
      group.highlightIds.push(h.id);
      if (group.kind !== h.kind) group.kind = null;
      if (selectedIds.has(h.id)) group.selected = true;
      if (pointedIds.has(h.id)) group.pointed = true;
    } else {
      groups.set(key, {
        key,
        boxes,
        highlightIds: [h.id],
        kind: h.kind,
        selected: selectedIds.has(h.id),
        pointed: pointedIds.has(h.id),
        narrowed,
        text: h.text,
      });
    }
  }
  // 큰 상자를 먼저(아래에), 작은 상자를 나중에(위에) 그려야 큰 상자 안의 작은 상자를 누를 수 있다.
  return [...groups.values()].sort((a, b) => area(b.boxes) - area(a.boxes));
}

/**
 * 좁힌 자리로 그린 강조가 골라졌을 때, 그것이 든 표·문단 전체(box)도 점선으로 보여 준다.
 * 숫자 하나만 강조되어 있으면 어느 표·어느 문단의 것인지 한눈에 안 들어오기 때문이다.
 */
export function contextBoxes(
  highlights: readonly Highlight[],
  selectedIds: ReadonlySet<string>,
  useInnerBox: boolean,
): Box[] {
  const seen = new Set<string>();
  const boxes: Box[] = [];
  for (const h of highlights) {
    if (!selectedIds.has(h.id) || !shapeOf(h, useInnerBox).narrowed) continue;
    const key = h.box.join(',');
    if (seen.has(key)) continue;
    seen.add(key);
    boxes.push(h.box);
  }
  return boxes;
}
