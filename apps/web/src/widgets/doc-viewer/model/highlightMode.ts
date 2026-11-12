// 강조 상자의 보기 방식. 부품의 입력값 하나(DocumentViewer 의 highlightMode)로 고른다.
//
// ★ 셋을 다 둔 것은 띄워 놓고 견주어 보기 위해서다. 하나로 굳히면 나머지를 지운다. 지울 곳:
//   1) 이 파일의 HIGHLIGHT_MODES 와 isDrawn 의 가지(mode 를 지우면 타입 검사가 아래를 전부 짚어 준다)
//   2) ui/viewer.css 의 「보기 방식」 구획(방식마다 한 덩어리)
//   3) DocumentViewer 의 highlightMode 입력과 「고른 것만」 안내 글, useDocViewer 가 그것을 draw 에 실어 HighlightOverlay 로 넘기는 mode 와 data-mode
//   4) 띄워 보는 화면(App.tsx)의 고르기 조작과 주소의 ?mode=
//   5) 재는 도구의 --mode(tools/capture.ts, tools/measure-hover.ts)와 방식별 테스트(highlightMode.test.ts, useDocViewer.test.ts, ui/DocumentViewer.test.tsx, pages/demo-viewer/behavior.test.tsx, e2e/viewer.spec.ts)
//
//   outline   옅게(기본값). 고른 항목의 상자와 마우스를 올린 상자만 채운다. 나머지는 채움 없이 옅은 테두리. 누를 수 있다
//   selected  고른 것만. 나머지는 그리지 않는다. 그래서 누를 수도 없다(상자 → 항목 방향이 없다)
//   fill      전체 채움. 모든 상자를 채운다(처음의 모양)
import type { Highlight } from './contract.ts';

export type HighlightMode = 'outline' | 'selected' | 'fill';

export const DEFAULT_HIGHLIGHT_MODE: HighlightMode = 'outline';

export const HIGHLIGHT_MODES: readonly {
  mode: HighlightMode;
  label: string;
}[] = [
  { mode: 'outline', label: '옅게' },
  { mode: 'selected', label: '고른 것만' },
  { mode: 'fill', label: '전체 채움' },
];

export function isHighlightMode(value: unknown): value is HighlightMode {
  return HIGHLIGHT_MODES.some((entry) => entry.mode === value);
}

export interface DrawOptions {
  mode: HighlightMode;
  /** 범례에서 꺼 둔 종류. */
  hiddenKinds: ReadonlySet<string>;
  /** 고른 항목의 강조. */
  selectedIds: ReadonlySet<string>;
  /** 목록에서 마우스를 올렸거나 키보드 초점이 간 항목의 강조. */
  pointedIds: ReadonlySet<string>;
}

/**
 * 이 강조의 상자를 그리는가.
 * 고른 것과 가리킨 것은 늘 그린다(종류가 꺼져 있어도, 「고른 것만」 방식에서도). 사람이 방금 짚은 것이 안 보이면 안 된다.
 * 나머지는 「고른 것만」 방식이 아니고 종류가 켜져 있을 때만 그린다.
 */
export function isDrawn(
  highlight: Highlight,
  { mode, hiddenKinds, selectedIds, pointedIds }: DrawOptions,
): boolean {
  if (selectedIds.has(highlight.id) || pointedIds.has(highlight.id))
    return true;
  if (mode === 'selected') return false;
  return !hiddenKinds.has(highlight.kind);
}
