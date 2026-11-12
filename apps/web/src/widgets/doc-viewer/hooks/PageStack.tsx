// 세로로 쌓은 쪽들과 그것을 담은 스크롤 상자. 모양 없는 컴포넌트다.
//
// 쪽을 전부 그리지 않는다. 쪽마다 크기를 미리 아니까(입력 계약의 pages) 빈 자리를 먼저 다 잡아 두고,
// 보이는 쪽과 그 앞뒤 한 쪽만 그린다(무엇을 그릴지는 usePaneView 가 정한다). 스크롤 막대의 길이는 처음부터 맞다.
//
//   <div onScroll>            스크롤 상자. overflow: auto 만 스스로 갖는다
//     {notice}
//     <div>                   쌓는 판. 높이 = 쪽을 다 쌓은 높이
//       <div data-page>       그릴 쪽마다 하나. 위에서부터의 거리와 크기를 스스로 갖고, 가로로는 가운데에 놓인다
//         {renderPage(쪽 번호, 쪽 크기)}     보통 <PageCanvas> 와 <HighlightOverlay>
//
// ★ 훅(usePaneView)과의 선: 훅은 「어디로 갈지」를 말하고 이 컴포넌트가 간다. 스크롤 상자를 읽고 쓰는 곳은 이 파일뿐이다.
//   - 훅이 scrollRequest 로 「이 높이로」 → 여기서 scrollTop 을 쓴다(새 높이로 그려진 직후에)
//   - useDocViewer 가 reveal 로 「이 상자가 보이게」 → 여기서 스크롤 상자의 크기를 읽어 픽셀로 셈하고(셈은 domain 의 순수 함수) 옮긴 뒤 훅에 알린다
//   - 사람이 스크롤하거나 상자의 크기가 바뀌면 → 훅에 알린다
// ★ 쓰는 쪽이 해야 할 것 하나: 스크롤 상자의 높이를 정해 준다(classNames.scroller 로. 예: flex: 1; min-height: 0).
//   높이가 정해지지 않으면 상자가 쪽을 다 쌓은 높이만큼 늘어나, 전부 「보이는 쪽」이 되어 전부 그린다.
import { useEffect, useLayoutEffect, useRef } from 'react';
import type { ReactNode } from 'react';

import {
  pageScreenSize,
  scrollLeftForBox,
  scrollTopForBox,
} from '../model/index.ts';
import type { PageSize } from '../model/index.ts';
import type { Reveal } from './useDocViewer.ts';
import type { PaneView } from './usePaneView.ts';

export interface PageStackProps {
  /** usePaneView 가 돌려준 것을 통째로. */
  pane: PaneView;
  /** 「이 상자가 보이게 가라」. useDocViewer 의 revealFor(문서 id). */
  reveal: Reveal | null;
  classNames?: { scroller?: string; stack?: string; page?: string };
  /** 스크롤 상자 안, 쪽들 위에 놓을 것(예: PDF 를 열지 못했다는 안내). */
  notice?: ReactNode;
  /** 쪽 하나의 속을 그린다. page 는 그 쪽의 크기(PDF 좌표). */
  renderPage(pageNumber: number, page: PageSize): ReactNode;
}

export function PageStack({
  pane,
  reveal,
  classNames,
  notice,
  renderPage,
}: PageStackProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const { pages, scale, rotation } = pane;

  // ── 스크롤 상자의 크기: 훅이 물을 수 있게 맡기고, 보이는 높이가 바뀌면 알린다(창 크기가 바뀔 때) ──
  useLayoutEffect(() => {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    pane.attachViewport(() => ({
      width: scroller.clientWidth,
      height: scroller.clientHeight,
    }));
    pane.reportViewportHeight(scroller.clientHeight);
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() =>
      pane.reportViewportHeight(scroller.clientHeight),
    );
    observer.observe(scroller);
    return () => observer.disconnect();
    // 한 번만 단다. 훅이 내주는 세 함수는 그릴 때마다 같은 일을 한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 훅이 「이 높이로 가라」고 했다(쪽 이동, 배율·회전을 바꾼 뒤 보던 자리 지키기) ──
  // 배율을 바꾸면 쪽들의 높이가 바뀐다. 새 높이로 그려진 직후(useLayoutEffect)에 옮겨야 스크롤 상자가 그 자리를 받아 준다.
  useLayoutEffect(() => {
    const scroller = scrollerRef.current;
    if (scroller && pane.scrollRequest)
      scroller.scrollTop = pane.scrollRequest.top;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pane.scrollRequest?.seq]);

  // ── 강조로 가기 ──
  useEffect(() => {
    if (!reveal) return;
    const scroller = scrollerRef.current;
    // 세로: 상자의 윗변을 화면의 보는 줄에 놓는다. 코드로 옮길 때는 DOM 과 훅의 상태를 같이 바꾼다(스크롤 이벤트를 기다리지 않아도 그릴 쪽이 바로 정해진다).
    const top = scrollTopForBox(
      reveal.page,
      reveal.box,
      scroller?.clientHeight ?? 0,
      pages,
      scale,
      rotation,
    );
    if (scroller) scroller.scrollTop = top;
    pane.reportScroll(top);
    // 가로: 상자가 문서 칸보다 넓으면(좁은 창에서 크게 확대) 가운데만 보이고 양 끝은 화면 밖에 남는다. 그때는 가로로 민다.
    // 가로는 그릴 것을 정하는 데 쓰지 않으므로 훅에 알리지 않는다.
    if (scroller)
      scroller.scrollLeft = scrollLeftForBox(
        reveal.page,
        reveal.box,
        scroller.clientWidth,
        pages,
        scale,
        rotation,
      );
    // 배율을 바꿨다고 다시 강조로 끌려가면 안 된다. 요청(reveal)이 새로 올 때만 간다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reveal?.seq, reveal?.highlightId]);

  return (
    <div
      ref={scrollerRef}
      className={classNames?.scroller}
      style={{ overflow: 'auto' }}
      onScroll={(event) => pane.reportScroll(event.currentTarget.scrollTop)}
    >
      {notice}
      <div
        className={classNames?.stack}
        style={{
          position: 'relative',
          height: pane.stackHeight,
          minWidth: pane.stackMinWidth,
        }}
      >
        {pane.visiblePages.map((pageNumber) => {
          const page = pages[pageNumber - 1]!;
          return (
            // left·right 0 에 margin auto: 폭이 정해진 쪽을 가로 가운데에 둔다.
            <div
              key={pageNumber}
              className={classNames?.page}
              data-page={pageNumber}
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                margin: '0 auto',
                top: pane.offsets[pageNumber - 1],
                ...pageScreenSize(page, scale, rotation),
              }}
            >
              {renderPage(pageNumber, page)}
            </div>
          );
        })}
      </div>
    </div>
  );
}
