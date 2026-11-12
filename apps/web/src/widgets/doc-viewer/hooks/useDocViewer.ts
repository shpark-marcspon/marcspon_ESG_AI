// 뷰어 하나의 상태와 동작. 마크업도 모양도 모른다.
//
// 이 훅이 드는 것은 넷이다:
//   고른 항목        selection   목록에서 누르거나, 문서의 상자를 누르거나, j·k 로 바뀐다
//   가리킨 항목      pointed     목록에서 마우스를 올린 것과 키보드 초점이 간 것. 마우스가 먼저다
//   꺼 둔 종류       hiddenKinds 범례에서 끈 것
//   좁힌 자리로 보기 useInnerBox
// 나머지(목록의 줄, 범례, 무엇을 그릴지, 문서 칸이 갈 곳)는 전부 이 넷과 입력에서 셈한 값이다.
//
// 화면이 할 일:
//   1) 뿌리 요소에 tabIndex 와 onKeyDown 을 단다(j·k)
//   2) rows 를 목록으로 그린다. 누르면 select, 마우스를 올리거나 초점이 가면 point
//   3) legend 를 그린다. 누르면 toggleKind
//   4) 문서 칸마다 usePaneView 와 <PageStack reveal={revealFor(문서 id)}> 를 두고,
//      쪽마다 <HighlightOverlay highlights={highlightsOn(문서 id, 쪽)} draw={draw} onPick={pick}> 를 얹는다
import { useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';

import {
  DEFAULT_HIGHLIGHT_MODE,
  innerBoxesOf,
  kindLooks,
  neighborItem,
  pickFromHighlights,
  shapeOf,
  unionBox,
} from '../model/index.ts';
import type {
  Box,
  DrawOptions,
  Highlight,
  HighlightMode,
  Item,
  KindLook,
  ReviewState,
  ViewerInput,
} from '../model/index.ts';

export interface DocViewerOptions {
  /** parseViewerInput 을 통과한 자료. */
  input: ViewerInput;
  /** 항목별 검토 상태. 이 훅은 읽기만 한다(바꾸는 것은 useReviews). */
  reviews: ReadonlyMap<string, ReviewState>;
  /** 강조 상자의 보기 방식. 안 주면 「옅게」(outline). 뜻은 domain/highlightMode.ts 에. */
  highlightMode?: HighlightMode;
}

/** 어디서 가리켰는가. 마우스를 올린 것(hover)이 키보드 초점(focus)보다 먼저다. */
export type PointSource = 'hover' | 'focus';

/** 목록의 한 줄. */
export interface ItemRow {
  item: Item;
  selected: boolean;
  review: ReviewState;
  /** 이 항목의 강조들이 가진 종류(겹치지 않게). 종류 표시 점을 그릴 때 쓴다. */
  kinds: string[];
  /** 이 항목의 강조가 전부 범례에서 꺼 둔 종류인가. 화면은 숨기지 않고 흐리게만 한다(숨기면 j·k 가 안 보이는 항목을 밟는다). */
  kindHidden: boolean;
}

/** 범례의 한 칸. */
export interface LegendEntry {
  kind: string;
  look: KindLook;
  shown: boolean;
}

/** 무엇을 그릴지 정하는 값 묶음. HighlightOverlay 에 그대로 넘긴다. */
export interface DrawState extends DrawOptions {
  useInnerBox: boolean;
}

/** 「이 상자가 보이게 가라」는 요청. 같은 강조로 다시 가라고 할 수 있게 seq 를 올려 보낸다. 가는 것은 PageStack 이 한다. */
export interface Reveal {
  highlightId: string;
  page: number;
  /** 강조의 상자가 여럿이면(여러 줄에 걸친 문장) 전부를 감싼 상자. */
  box: Box;
  seq: number;
}

export interface DocViewer {
  mode: HighlightMode;
  looks: ReadonlyMap<string, KindLook>;
  legend: LegendEntry[];
  toggleKind(kind: string): void;
  /** 좁힌 자리(innerBoxes)를 가진 강조가 하나라도 있는가. 없으면 「좁힌 자리로 보기」를 보일 까닭이 없다. */
  hasInnerBoxes: boolean;
  useInnerBox: boolean;
  setUseInnerBox(value: boolean): void;
  rows: ItemRow[];
  selectedItemId: string | null;
  /** 항목을 고른다. 같은 항목을 다시 골라도 문서 칸은 그 자리로 다시 간다. null 은 아무 일도 하지 않는다. */
  select(itemId: string | null): void;
  /** 항목을 가리켰다(떼면 null). 가리킨 것만으로는 고르지도 스크롤하지도 않는다. */
  point(source: PointSource, itemId: string | null): void;
  /** 문서의 상자를 눌렀다. 같은 자리에 겹친 강조의 id 를 전부 받는다. 가리키는 항목이 여럿이면 누를 때마다 다음 것으로 돈다. */
  pick(highlightIds: readonly string[]): void;
  /** j 다음 항목, k 이전 항목. 글자를 적는 중(textarea, input)과 Ctrl·Meta·Alt 와 같이 누른 것은 흘려보낸다. */
  onKeyDown(event: KeyboardEvent): void;
  draw: DrawState;
  /** 그 문서의 그 쪽에 있는 강조들(입력의 차례대로). */
  highlightsOn(documentId: string, page: number): readonly Highlight[];
  /** 문서 칸 하나가 갈 곳: 골라진 항목의 강조 가운데 그 문서에 있는 첫 번째. 없으면 null. */
  revealFor(documentId: string): Reveal | null;
}

const NO_IDS: ReadonlySet<string> = new Set();
const NO_HIGHLIGHTS: readonly Highlight[] = [];

export function useDocViewer({
  input,
  reviews,
  highlightMode = DEFAULT_HIGHLIGHT_MODE,
}: DocViewerOptions): DocViewer {
  // seq: 같은 항목을 다시 눌러도 그 자리로 다시 가게 하려고 누를 때마다 올린다.
  const [selection, setSelection] = useState<{
    itemId: string;
    seq: number;
  } | null>(null);
  const [useInnerBox, setUseInnerBox] = useState(true);
  // 범례에서 꺼 둔 종류. 뷰어는 종류의 뜻을 모른다. 입력이 준 종류를 켜고 끌 뿐이다.
  const [hiddenKinds, setHiddenKinds] = useState<ReadonlySet<string>>(NO_IDS);
  // 목록에서 가리킨 항목: 마우스를 올린 것이 먼저, 없으면 키보드 초점이 간 것.
  const [pointed, setPointed] = useState<{
    hover: string | null;
    focus: string | null;
  }>({ hover: null, focus: null });

  const looks = useMemo(() => kindLooks(input), [input]);
  const highlightById = useMemo(
    () => new Map(input.highlights.map((h) => [h.id, h])),
    [input],
  );
  const hasInnerBoxes = useMemo(
    () => input.highlights.some((h) => innerBoxesOf(h).length > 0),
    [input],
  );

  const selectedItemId = selection?.itemId ?? null;
  const selectedItem = input.items.find((item) => item.id === selectedItemId);
  const selectedIds = useMemo(
    () => new Set(selectedItem?.highlightIds ?? []),
    [selectedItem],
  );
  const pointedItemId = pointed.hover ?? pointed.focus;
  const pointedIds = useMemo(
    () =>
      pointedItemId === null ? NO_IDS : (
        new Set(
          input.items.find((item) => item.id === pointedItemId)?.highlightIds ??
            [],
        )
      ),
    [input, pointedItemId],
  );
  // 문서 → 쪽 → 강조들.
  const highlightsByPlace = useMemo(() => {
    const byDocument = new Map<string, Map<number, Highlight[]>>();
    for (const h of input.highlights) {
      const byPage =
        byDocument.get(h.documentId) ?? new Map<number, Highlight[]>();
      byDocument.set(h.documentId, byPage);
      byPage.set(h.page, [...(byPage.get(h.page) ?? []), h]);
    }
    return byDocument;
  }, [input]);

  function toggleKind(kind: string) {
    setHiddenKinds((previous) => {
      const next = new Set(previous);
      if (!next.delete(kind)) next.add(kind);
      return next;
    });
  }
  // 같은 값이면 상태를 그대로 돌려줘 다시 그리지 않는다(마우스가 한 항목 안에서 움직일 때).
  function point(source: PointSource, itemId: string | null) {
    setPointed((previous) =>
      previous[source] === itemId ?
        previous
      : { ...previous, [source]: itemId },
    );
  }

  function select(itemId: string | null) {
    if (itemId === null) return;
    setSelection((previous) => ({ itemId, seq: (previous?.seq ?? 0) + 1 }));
    // 항목을 눌러 고르면 초점이 그 단추에 남는다. 그 뒤 j·k 나 상자로 다른 항목을 고르면 초점은 옛 항목에 그대로라,
    // 옛 항목의 상자가 「가리킨 것」으로 남는다. 다른 항목을 고르는 순간 초점으로 가리킨 것은 지운다(마우스로 가리킨 것은 둔다).
    setPointed((previous) =>
      previous.focus !== null && previous.focus !== itemId ?
        { ...previous, focus: null }
      : previous,
    );
  }

  function onKeyDown(event: KeyboardEvent) {
    // 사유를 적는 중에는 글자 입력이다.
    if (
      event.target instanceof HTMLTextAreaElement ||
      event.target instanceof HTMLInputElement
    )
      return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === 'j') select(neighborItem(input.items, selectedItemId, 1));
    else if (event.key === 'k')
      select(neighborItem(input.items, selectedItemId, -1));
    else return;
    event.preventDefault();
  }

  function revealFor(documentId: string): Reveal | null {
    if (!selection || !selectedItem) return null;
    const first = selectedItem.highlightIds
      .map((id) => highlightById.get(id))
      .find((h): h is Highlight => h?.documentId === documentId);
    if (!first) return null;
    // 상자가 여럿이면 전부를 감싼 상자로 잰다: 세로는 그 윗변(= 첫 줄)을 보는 줄에 놓고, 가로는 그 가운데를 화면 가운데에 둔다.
    // 첫 줄의 상자만으로 재면, 줄 끝에서 시작하는 문장은 가로로 확대했을 때 오른쪽 끝만 보인다.
    return {
      highlightId: first.id,
      page: first.page,
      box: unionBox(shapeOf(first, useInnerBox).boxes),
      seq: selection.seq,
    };
  }

  const rows = input.items.map((item): ItemRow => {
    const kinds = [
      ...new Set(item.highlightIds.map((id) => highlightById.get(id)?.kind)),
    ];
    return {
      item,
      selected: item.id === selectedItemId,
      review: reviews.get(item.id) ?? item.review,
      kinds: kinds.filter((kind): kind is string => kind !== undefined),
      kindHidden:
        kinds.length > 0 &&
        kinds.every((kind) => kind !== undefined && hiddenKinds.has(kind)),
    };
  });

  return {
    mode: highlightMode,
    looks,
    legend: [...looks].map(([kind, look]) => ({
      kind,
      look,
      shown: !hiddenKinds.has(kind),
    })),
    toggleKind,
    hasInnerBoxes,
    useInnerBox,
    setUseInnerBox,
    rows,
    selectedItemId,
    select,
    point,
    pick: (highlightIds) =>
      select(pickFromHighlights(input.items, highlightIds, selectedItemId)),
    onKeyDown,
    draw: {
      mode: highlightMode,
      hiddenKinds,
      selectedIds,
      pointedIds,
      useInnerBox,
    },
    highlightsOn: (documentId, page) =>
      highlightsByPlace.get(documentId)?.get(page) ?? NO_HIGHLIGHTS,
    revealFor,
  };
}
