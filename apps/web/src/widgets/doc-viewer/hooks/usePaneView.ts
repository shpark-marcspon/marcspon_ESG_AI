// 문서 칸 하나의 보기 상태: 배율, 회전, 스크롤 위치에서 셈한 「지금 쪽」과 「그릴 쪽들」.
//
// ★ 이 훅은 요소를 읽거나 쓰지 않는다. 스크롤 상자를 읽고 쓰는 것은 <PageStack> 이 한다. 둘 사이에 오가는 것:
//   훅 → 컴포넌트   scrollRequest      「이 높이로 가라」(쪽 이동, 배율·회전을 바꾼 뒤 보던 자리 지키기)
//   컴포넌트 → 훅   reportScroll       사람이 스크롤했다 / 강조로 갔다
//                   reportViewportHeight 스크롤 상자의 보이는 높이가 바뀌었다
//                   attachViewport     「지금 스크롤 상자의 크기」를 물을 수 있는 함수를 맡긴다(폭 맞춤이 쓴다)
// 이렇게 가른 까닭: 「어디로 갈지」는 숫자의 셈이라 화면 없이 시험할 수 있고, 「가는 것」은 요소가 있어야 한다.
// 쓰는 쪽은 <PageStack pane={usePaneView(pages)}> 로 통째로 넘기면 된다.
import { useCallback, useRef, useState } from 'react';

import {
  PAGE_GAP,
  pageAtScroll,
  pageOffsets,
  pageScreenSize,
  scrollTopAfterResize,
  totalHeight,
  visiblePageRange,
} from '../model/index.ts';
import type { PageSize, Rotation } from '../model/index.ts';

export const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3];

export interface ViewportSize {
  width: number;
  height: number;
}

export interface PaneView {
  pages: readonly PageSize[];
  /** 1 포인트 = 몇 CSS 픽셀. */
  scale: number;
  rotation: Rotation;
  /** 화면의 보는 줄에 걸린 쪽(1부터). */
  currentPage: number;
  /** 지금 그릴 쪽들: 보이는 쪽과 그 앞뒤 한 쪽. */
  visiblePages: number[];
  /** 쪽마다 위에서부터의 거리(px). */
  offsets: number[];
  /** 쪽을 다 쌓은 높이(px). 스크롤 막대의 길이가 처음부터 맞는다. */
  stackHeight: number;
  /** 쌓는 판의 최소 폭(px): 가장 넓은 쪽 + 양옆 틈. */
  stackMinWidth: number;
  canZoomIn: boolean;
  canZoomOut: boolean;
  zoomIn(): void;
  zoomOut(): void;
  /** 지금 쪽의 폭을 스크롤 상자의 폭에 맞춘다. */
  fitWidth(): void;
  /** 시계 방향으로 90도. */
  rotate(): void;
  /** 그 쪽의 맨 위로. 범위를 벗어난 번호는 끝 쪽으로 끌어온다. */
  goToPage(pageNumber: number): void;

  // ── <PageStack> 과 주고받는 것 ──
  scrollRequest: { top: number; seq: number } | null;
  reportScroll(top: number): void;
  reportViewportHeight(height: number): void;
  attachViewport(read: (() => ViewportSize) | null): void;
}

export function usePaneView(pages: readonly PageSize[]): PaneView {
  const [view, setView] = useState<{ scale: number; rotation: Rotation }>({
    scale: 1,
    rotation: 0,
  });
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [scrollRequest, setScrollRequest] = useState<{
    top: number;
    seq: number;
  } | null>(null);
  const readViewport = useRef<(() => ViewportSize) | null>(null);
  const { scale, rotation } = view;

  const offsets = pageOffsets(pages, scale, rotation);
  const range = visiblePageRange(
    scrollTop,
    viewportHeight,
    pages,
    scale,
    rotation,
  );
  const currentPage = pageAtScroll(
    scrollTop,
    viewportHeight,
    pages,
    scale,
    rotation,
  );
  const widest = Math.max(
    ...pages.map((page) => pageScreenSize(page, scale, rotation).width),
  );
  const visiblePages: number[] = [];
  for (let n = range.first; n <= range.last; n++) visiblePages.push(n);

  // 스크롤 위치(상태)를 바로 바꾸고, 컴포넌트에게 DOM 도 옮기라고 한다. 스크롤 이벤트를 기다리지 않아도 보이는 쪽이 바로 정해진다.
  function scrollTo(top: number) {
    setScrollTop(top);
    setScrollRequest((previous) => ({ top, seq: (previous?.seq ?? 0) + 1 }));
  }
  // 배율·회전을 바꾸면 쪽들의 높이가 바뀐다. 보던 자리가 새 높이에서 어디인지 셈해 그리로 간다.
  // (컴포넌트는 새 높이로 그려진 직후에 옮긴다. PageStack 의 useLayoutEffect)
  function changeView(next: { scale: number; rotation: Rotation }) {
    scrollTo(scrollTopAfterResize(scrollTop, pages, view, next));
    setView(next);
  }
  function zoom(direction: 1 | -1) {
    const next =
      direction === 1 ?
        ZOOM_STEPS.find((step) => step > scale + 0.001)
      : [...ZOOM_STEPS].reverse().find((step) => step < scale - 0.001);
    if (next !== undefined) changeView({ scale: next, rotation });
  }

  return {
    pages,
    scale,
    rotation,
    currentPage,
    visiblePages,
    offsets,
    stackHeight: totalHeight(pages, scale, rotation),
    stackMinWidth: widest + 2 * PAGE_GAP,
    canZoomIn: scale < ZOOM_STEPS.at(-1)!,
    canZoomOut: scale > ZOOM_STEPS[0]!,
    zoomIn: () => zoom(1),
    zoomOut: () => zoom(-1),
    fitWidth() {
      const width = readViewport.current?.().width ?? 0;
      const page = pages[currentPage - 1];
      if (!page || width === 0) return;
      const pageWidth = pageScreenSize(page, 1, rotation).width;
      // 소수 둘째 자리까지만. 화면에 보이는 배율과 실제 배율이 같아야 한다.
      changeView({
        scale:
          Math.floor(((width - 2 * PAGE_GAP - 16) / pageWidth) * 100) / 100,
        rotation,
      });
    },
    rotate: () =>
      changeView({ scale, rotation: ((rotation + 90) % 360) as Rotation }),
    goToPage(pageNumber) {
      const clamped = Math.min(pages.length, Math.max(1, pageNumber));
      scrollTo(Math.max(0, offsets[clamped - 1]! - PAGE_GAP));
    },
    scrollRequest,
    reportScroll: setScrollTop,
    reportViewportHeight: setViewportHeight,
    // 그릴 때마다 같은 함수다(PageStack 이 처음 한 번만 맡긴다). reportScroll·reportViewportHeight 도 setState 라 늘 같다.
    attachViewport: useCallback((read) => {
      readViewport.current = read;
    }, []),
  };
}
