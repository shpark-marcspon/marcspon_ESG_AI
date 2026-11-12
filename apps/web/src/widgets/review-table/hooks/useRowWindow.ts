// 보이는 행만 그리기(TanStack Virtual)와, 그 위의 「지금 행」·펼침·키보드 이동.
// 마크업과 스타일을 모른다. 이 훅이 준 것을 DOM 에 놓는 일은 모양 없는 컴포넌트 <RowStack>(과 <RowFrame>)이 한다:
//   1) 스크롤되는 요소에 scrollRef 를 단다
//   2) 그 안에 높이 totalSize 인 상자를 두고, items 의 행을 첫 행의 start 만큼 내려서 그린다
//   3) 행의 요소마다 ref={measureRef} 와 data-index={item.index} 를 단다(실제 높이를 잰다)
// 화면은 <RowStack window={…}> 에 통째로 넘기면 되고, 직접 쓰는 것은 activeId·setActiveId·expandedIds·toggleExpanded 정도다.
//
// ★ 뷰어의 usePaneView 와 다른 곳: 거기서는 훅이 요소를 모르고 「어디로」만 값으로 낸다. 여기서는 훅이 scrollRef 를 쥔다.
//   TanStack Virtual 이 스크롤 요소를 직접 지켜보고(스크롤 위치, 크기) 「이 행이 보이게」(scrollToIndex)도 스스로 옮기기 때문이다.
//   값으로만 말하게 하려면 그 연결(observeElementRect·observeElementOffset·scrollToFn)을 우리가 다시 써야 한다. 그러지 않았다.
//
// 높이가 다른 행(펼친 행): 높이를 미리 계산하지 않고, 그려진 뒤에 잰 값을 쓴다(measureRef).
// 아직 그려 본 적 없는 행은 estimateRowHeight 로 친다. 그래서 스크롤 막대의 길이는 어림이다가 지나가면서 맞춰진다.
// 다시 그려진 행(펼침·접기)은 그 그리기 안에서 remeasure 로 다시 잰다 — ResizeObserver 만 기다리면 한두 프레임 늦어 펼친 직후
// End 가 옛 끝에서 멈춘다(언제 재는지 셋은 RowFrame.tsx 머리 「높이 재기」, 밴드 PL1 ③).
import { useCallback, useMemo, useRef, useState } from 'react';
import type { MutableRefObject } from 'react';

import { useVirtualizer } from '@tanstack/react-virtual';

import type { ReviewRow } from '../model/index.ts';

export interface RowWindowOptions {
  /** 접힌 행 하나의 높이(px) 어림값. 화면 층의 CSS 와 맞춘다. */
  estimateRowHeight: number;
  /** 화면 밖으로 위아래 몇 행을 더 그려 둘지. 기본 8. */
  overscan?: number;
  /** 지금 행에서 Space 를 눌렀을 때. */
  onToggleSelected?(rowId: string): void;
}

export interface WindowItem {
  row: ReviewRow;
  /** 걸러 보고 정렬한 결과에서의 순서(0부터). */
  index: number;
  /** 위에서부터의 거리(px). */
  start: number;
}

export interface RowWindow {
  scrollRef: MutableRefObject<HTMLDivElement | null>;
  measureRef(element: Element | null): void;
  /**
   * 이미 놓인 행의 높이를 지금 DOM 에서 다시 읽어 반영한다. <RowFrame> 이 그 행을 다시 그린 직후에 부른다.
   * measureRef 로는 안 된다: 한 번 잰 행은 TanStack 이 적어 둔 값을 돌려준다(크기 변화는 ResizeObserver 로 뒤늦게 온다).
   */
  remeasure(element: HTMLElement): void;
  totalSize: number;
  /** 지금 그릴 행들. 화면에 보이는 것과 위아래 여유분. */
  items: WindowItem[];
  /** 「지금 행」. 키보드로 옮기고, 화면이 눌러서 정할 수도 있다. */
  activeId: string | null;
  setActiveId(rowId: string | null): void;
  expandedIds: ReadonlySet<string>;
  toggleExpanded(rowId: string): void;
  /**
   * 키 하나를 처리한다. 처리했으면 true(<RowStack> 이 기본 동작을 막는다). 입력 칸 안의 키와 조합키를 거르는 것도 <RowStack> 이 한다.
   *   ↓ j / ↑ k   다음·이전 행        PageDown / PageUp   열 행씩
   *   Home / End  처음·끝 행          Space 고르기        Enter 펼치기·접기
   */
  handleKey(key: string): boolean;
}

const PAGE = 10;

export function useRowWindow(
  rows: readonly ReviewRow[],
  options: RowWindowOptions,
): RowWindow {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => options.estimateRowHeight,
    // 정렬이 바뀌어도 잰 높이가 그 행을 따라가게 한다.
    getItemKey: (index) => rows[index]!.id,
    overscan: options.overscan ?? 8,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const items = virtualItems.flatMap((item): WindowItem[] => {
    const row = rows[item.index];
    // 행이 줄어든 직후 한 번, 없는 자리를 가리킬 수 있다.
    return row ? [{ row, index: item.index, start: item.start }] : [];
  });

  const indexOf = useMemo(
    () => new Map(rows.map((row, index) => [row.id, index])),
    [rows],
  );

  const toggleExpanded = useCallback((rowId: string) => {
    setExpandedIds((previous) => {
      const next = new Set(previous);
      if (!next.delete(rowId)) next.add(rowId);
      return next;
    });
  }, []);

  // 가상 스크롤 객체는 처음 만든 것이 끝까지 간다(useVirtualizer 가 그렇게 쥔다). 그래서 이 함수도 늘 같은 함수다(행의 memo 를 뚫지 않는다).
  // 높이는 정수로 읽는다(offsetHeight). TanStack 이 ResizeObserver 로 받는 값도 반올림한 정수다.
  const remeasure = useCallback(
    (element: HTMLElement) =>
      virtualizer.resizeItem(
        virtualizer.indexFromElement(element),
        element.offsetHeight,
      ),
    [virtualizer],
  );

  function moveTo(index: number) {
    const target = rows[Math.max(0, Math.min(rows.length - 1, index))];
    if (!target) return;
    setActiveId(target.id);
    virtualizer.scrollToIndex(indexOf.get(target.id)!, { align: 'auto' });
  }

  function handleKey(key: string): boolean {
    // 걸러서 지금 행이 사라졌으면 처음부터 다시 센다.
    const current = activeId !== null ? indexOf.get(activeId) : undefined;
    const step = (delta: number) =>
      moveTo(current === undefined ? 0 : current + delta);
    switch (key) {
      case 'ArrowDown':
      case 'j':
        step(1);
        return true;
      case 'ArrowUp':
      case 'k':
        step(-1);
        return true;
      case 'PageDown':
        step(PAGE);
        return true;
      case 'PageUp':
        step(-PAGE);
        return true;
      case 'Home':
        moveTo(0);
        return true;
      case 'End':
        moveTo(rows.length - 1);
        return true;
      case ' ':
        if (current === undefined) return false;
        options.onToggleSelected?.(activeId!);
        return true;
      case 'Enter':
        if (current === undefined) return false;
        toggleExpanded(activeId!);
        return true;
      default:
        return false;
    }
  }

  return {
    scrollRef,
    measureRef: virtualizer.measureElement,
    remeasure,
    totalSize: virtualizer.getTotalSize(),
    items,
    activeId: activeId !== null && indexOf.has(activeId) ? activeId : null,
    setActiveId,
    expandedIds,
    toggleExpanded,
    handleKey,
  };
}
