// 문서 하나를 보여 주는 칸: 도구 줄(쪽 이동, 확대·축소, 회전) + 세로로 쌓은 쪽들.
//
// 쪽을 전부 그리지 않는다. 쪽마다 크기를 미리 아니까(입력 계약의 pages) 빈 자리를 먼저 다 잡아 두고,
// 보이는 쪽과 그 앞뒤 한 쪽만 캔버스를 만든다. 스크롤 막대의 길이는 처음부터 맞다.
// 「어느 쪽이 보이는가」와 배율·회전은 헤드리스 층의 usePaneView 가 들고, 쪽을 쌓고 스크롤하는 것은 <PageStack> 이 한다.
// 이 파일에 남은 것은 도구 줄의 생김과, 헤드리스 컴포넌트에 입히는 모양(클래스 이름, 종류의 색, 겹친 개수 딱지)이다.
import {
  HighlightOverlay,
  PageCanvas,
  PageStack,
  usePaneView,
  usePdf,
} from '../hooks/index.ts';
import type { DocViewer, OpenPdf, PieceLook } from '../hooks/index.ts';
import { MIXED_COLOR } from '../model/index.ts';
import type { HighlightGroup, ViewerDocument } from '../model/index.ts';

interface Props {
  document: ViewerDocument;
  viewer: DocViewer;
  openPdf: OpenPdf;
}

const STACK_CLASSES = {
  scroller: 'dv-scroller',
  stack: 'dv-stack',
  page: 'dv-page',
};
const OVERLAY_CLASSES = {
  layer: 'dv-highlights',
  group: 'dv-group',
  context: 'dv-context',
};

export function PdfPane({ document: doc, viewer, openPdf }: Props) {
  const pane = usePaneView(doc.pages);
  const loaded = usePdf(doc.url, openPdf);
  const { pages, scale, rotation, currentPage } = pane;

  // 조각 하나의 모양. 색은 종류마다 다르다: color 로 주고 viewer.css 가 currentColor 로 받아 쓴다. 종류가 섞인 묶음은 회색.
  function pieceLook(group: HighlightGroup): PieceLook {
    const look = group.kind === null ? undefined : viewer.looks.get(group.kind);
    const count = group.highlightIds.length;
    return {
      className: 'dv-highlight',
      style: { color: look?.color ?? MIXED_COLOR },
      title: [
        look?.label,
        group.text,
        count > 1 ? `겹친 강조 ${count}개. 누를 때마다 다음 항목` : '',
      ]
        .filter(Boolean)
        .join(' · '),
    };
  }

  return (
    <section
      className="dv-pane"
      data-document-id={doc.id}
      data-scale={scale}
      data-rotation={rotation}
      data-current-page={currentPage}
    >
      <header className="dv-toolbar">
        <strong className="dv-title" title={doc.title ?? doc.id}>
          {doc.title ?? doc.id}
        </strong>
        <span className="dv-tools">
          <button
            type="button"
            onClick={() => pane.goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            aria-label="이전 페이지"
          >
            ◀
          </button>
          <label>
            <input
              className="dv-page-input"
              type="number"
              min={1}
              max={pages.length}
              value={currentPage}
              onChange={(event) =>
                pane.goToPage(Number(event.target.value) || 1)
              }
              aria-label="페이지 번호"
            />
            <span> / {pages.length}</span>
          </label>
          <button
            type="button"
            onClick={() => pane.goToPage(currentPage + 1)}
            disabled={currentPage >= pages.length}
            aria-label="다음 페이지"
          >
            ▶
          </button>
        </span>
        <span className="dv-tools">
          <button
            type="button"
            onClick={pane.zoomOut}
            disabled={!pane.canZoomOut}
            aria-label="축소"
          >
            −
          </button>
          <output className="dv-zoom">{Math.round(scale * 100)}%</output>
          <button
            type="button"
            onClick={pane.zoomIn}
            disabled={!pane.canZoomIn}
            aria-label="확대"
          >
            +
          </button>
          <button type="button" onClick={pane.fitWidth}>
            폭 맞춤
          </button>
          <button
            type="button"
            onClick={pane.rotate}
            aria-label="시계 방향으로 돌리기"
          >
            ⟳
          </button>
        </span>
      </header>

      <PageStack
        pane={pane}
        reveal={viewer.revealFor(doc.id)}
        classNames={STACK_CLASSES}
        notice={
          loaded.state === 'error' && (
            <p className="dv-error">PDF 를 열지 못했다: {loaded.message}</p>
          )
        }
        renderPage={(pageNumber, page) => (
          <>
            {loaded.state === 'ready' && (
              <PageCanvas
                pdf={loaded.pdf}
                pageNumber={pageNumber}
                scale={scale}
                rotation={rotation}
                errorFallback={
                  <p className="dv-page-error">이 페이지를 그리지 못했다.</p>
                }
              />
            )}
            <HighlightOverlay
              highlights={viewer.highlightsOn(doc.id, pageNumber)}
              page={page}
              scale={scale}
              rotation={rotation}
              draw={viewer.draw}
              onPick={viewer.pick}
              classNames={OVERLAY_CLASSES}
              pieceProps={pieceLook}
              // 겹친 개수 딱지. 자리(상자 바깥 오른쪽)와 생김은 viewer.css 의 .dv-count.
              renderCount={(count) => <span className="dv-count">{count}</span>}
            />
          </>
        )}
      />
    </section>
  );
}
