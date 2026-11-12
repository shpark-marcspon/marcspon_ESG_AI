// 둘째 화면: 같은 헤드리스 훅과 같은 모양 없는 컴포넌트 위에 얹은, 생김이 다른 뷰어. 증명용이고 제품이 아니다.
// 보이려는 것: 화면을 통째로 바꿔도 업무 로직과 헤드리스 층은 그대로 쓴다.
// 그래서 doc-viewer/ui 의 것을 하나도 가져오지 않고, 공개 표면(doc-viewer/index.ts)만 쓴다.
// 같은 동작 테스트(src/pages/demo-viewer/behavior.test.tsx)가 본 화면과 이 화면 둘 다에서 통과한다.
//
// 본 화면과 다른 것:
//   배치       목록이 오른쪽에 있고, 범례는 맨 위의 띠다. 도구 줄은 문서 칸의 아래에 있다
//   목록       한 줄에 한 항목(제목 한 줄, 상태는 글자 하나). 검토 단추는 항목 안이 아니라 목록 아래의 칸에 있다
//   쪽 위 강조  상자가 아니라 형광펜(채움)과 밑줄. 겹친 개수는 조각의 왼쪽 위에 작은 글자로
// 같은 것(전부 헤드리스 층에서 온다): 고르기·가리키기·종류 켜고 끄기·j·k·겹친 상자 돌기, 쪽 쌓기와 스크롤, 강조의 자리와 data-* 표시.
import { useEffect, useRef } from 'react';

import {
  ERROR_MESSAGE,
  HighlightOverlay,
  MIXED_COLOR,
  PageCanvas,
  PageStack,
  STATUS_LABEL,
  useDocViewer,
  usePaneView,
  usePdf,
  useReviewDraft,
} from '../../widgets/doc-viewer/index.ts';
import type {
  DocViewer,
  DocumentViewerProps,
  HighlightGroup,
  ItemRow,
  OpenPdf,
  PieceLook,
  ReviewAction,
  TransitionResult,
  ViewerDocument,
} from '../../widgets/doc-viewer/index.ts';
import './compact.css';

export function CompactViewer({
  input,
  openPdf,
  reviews,
  onReview,
  highlightMode,
}: DocumentViewerProps) {
  const viewer = useDocViewer({ input, reviews, highlightMode });
  const selectedRow = viewer.rows.find((row) => row.selected);

  return (
    <div
      className="cv-root"
      data-layout={input.documents.length === 2 ? 'side-by-side' : 'single'}
      tabIndex={0}
      onKeyDown={viewer.onKeyDown}
    >
      <header className="cv-top">
        <span role="group" aria-label="종류별로 강조 켜고 끄기">
          {viewer.legend.map(({ kind, look, shown }) => (
            <button
              key={kind}
              type="button"
              className="cv-kind"
              data-kind={kind}
              aria-pressed={shown}
              style={{ borderBottomColor: look.color }}
              onClick={() => viewer.toggleKind(kind)}
            >
              {look.label}
            </button>
          ))}
        </span>
        {viewer.hasInnerBoxes && (
          <label>
            <input
              type="checkbox"
              checked={viewer.useInnerBox}
              onChange={(event) => viewer.setUseInnerBox(event.target.checked)}
            />
            좁힌 자리로 보기
          </label>
        )}
        {viewer.mode === 'selected' && (
          <span data-testid="dv-mode-note">
            고른 항목만 그린다. 문서에서 눌러 고를 수 없다.
          </span>
        )}
        {input.notice && <span className="cv-notice">{input.notice}</span>}
      </header>
      <div className="cv-panes">
        {input.documents.map((doc) => (
          <CompactPane
            key={doc.id}
            document={doc}
            viewer={viewer}
            openPdf={openPdf}
          />
        ))}
      </div>
      <aside className="cv-side">
        <CompactList viewer={viewer} />
        {/* key: 다른 항목으로 가면 적다 만 사유를 버린다(본 화면과 같다). */}
        {selectedRow && (
          <CompactReview
            key={selectedRow.item.id}
            row={selectedRow}
            onAction={(action) => onReview(selectedRow.item.id, action)}
          />
        )}
      </aside>
    </div>
  );
}

function CompactList({ viewer }: { viewer: DocViewer }) {
  const selectedRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    selectedRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [viewer.selectedItemId]);

  return (
    <ul className="cv-items">
      {viewer.rows.map(({ item, selected, review, kinds, kindHidden }) => (
        <li
          key={item.id}
          ref={selected ? selectedRef : undefined}
          className="cv-item"
          data-item-id={item.id}
          data-selected={selected}
          data-kind-hidden={kindHidden}
          onMouseEnter={() => viewer.point('hover', item.id)}
          onMouseLeave={() => viewer.point('hover', null)}
        >
          <button
            type="button"
            aria-current={selected}
            onClick={() => viewer.select(item.id)}
            onFocus={() => viewer.point('focus', item.id)}
            onBlur={() => viewer.point('focus', null)}
          >
            <i
              className="cv-bar"
              style={{
                background:
                  kinds.length === 1 ?
                    viewer.looks.get(kinds[0]!)?.color
                  : MIXED_COLOR,
              }}
            />
            <span className="cv-title">{item.title}</span>
            <b
              className="cv-status"
              data-status={review.status}
              title={STATUS_LABEL[review.status]}
            >
              {STATUS_LABEL[review.status]}
            </b>
          </button>
        </li>
      ))}
    </ul>
  );
}

function CompactReview({
  row,
  onAction,
}: {
  row: ItemRow;
  onAction(action: ReviewAction): TransitionResult;
}) {
  const draft = useReviewDraft(onAction);
  const { item, review } = row;
  return (
    <section className="cv-review" data-review-for={item.id}>
      <strong>{item.title}</strong>
      {item.detail && <p>{item.detail}</p>}
      {review.status === 'rejected' && <p>반려 사유: {review.reason}</p>}
      {review.status === 'pending' ?
        <>
          <textarea
            value={draft.reason}
            onChange={(event) => draft.setReason(event.target.value)}
            aria-label="반려 사유"
            placeholder="반려 사유"
            rows={2}
          />
          <span>
            <button type="button" onClick={draft.confirm}>
              확정
            </button>
            <button type="button" onClick={draft.reject}>
              반려
            </button>
          </span>
        </>
      : <button type="button" onClick={draft.reopen}>
          검토대기로 되돌리기
        </button>
      }
      {draft.error && <p role="alert">{ERROR_MESSAGE[draft.error]}</p>}
    </section>
  );
}

const STACK_CLASSES = { scroller: 'cv-scroller', page: 'cv-page' };
const OVERLAY_CLASSES = {
  layer: 'cv-marks',
  group: 'cv-mark-group',
  context: 'cv-context',
};

function CompactPane({
  document: doc,
  viewer,
  openPdf,
}: {
  document: ViewerDocument;
  viewer: DocViewer;
  openPdf: OpenPdf;
}) {
  const pane = usePaneView(doc.pages);
  const loaded = usePdf(doc.url, openPdf);
  const { scale, rotation, currentPage } = pane;

  function markLook(group: HighlightGroup): PieceLook {
    const look = group.kind === null ? undefined : viewer.looks.get(group.kind);
    return {
      className: 'cv-mark',
      style: { color: look?.color ?? MIXED_COLOR },
      title: look?.label,
    };
  }

  return (
    <section
      className="cv-pane"
      data-document-id={doc.id}
      data-scale={scale}
      data-rotation={rotation}
      data-current-page={currentPage}
    >
      <PageStack
        pane={pane}
        reveal={viewer.revealFor(doc.id)}
        classNames={STACK_CLASSES}
        notice={
          loaded.state === 'error' && (
            <p role="alert">PDF 를 열지 못했다: {loaded.message}</p>
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
              pieceProps={markLook}
              renderCount={(count) => <sup className="cv-count">{count}</sup>}
            />
          </>
        )}
      />
      <footer className="cv-tools">
        <span className="cv-doc">{doc.title ?? doc.id}</span>
        <button
          type="button"
          onClick={() => pane.goToPage(currentPage - 1)}
          disabled={currentPage <= 1}
          aria-label="이전 페이지"
        >
          이전
        </button>
        <input
          type="number"
          min={1}
          max={pane.pages.length}
          value={currentPage}
          onChange={(event) => pane.goToPage(Number(event.target.value) || 1)}
          aria-label="페이지 번호"
        />
        <span>/ {pane.pages.length}</span>
        <button
          type="button"
          onClick={() => pane.goToPage(currentPage + 1)}
          disabled={currentPage >= pane.pages.length}
          aria-label="다음 페이지"
        >
          다음
        </button>
        <button
          type="button"
          onClick={pane.zoomOut}
          disabled={!pane.canZoomOut}
          aria-label="축소"
        >
          작게
        </button>
        <output>{Math.round(scale * 100)}%</output>
        <button
          type="button"
          onClick={pane.zoomIn}
          disabled={!pane.canZoomIn}
          aria-label="확대"
        >
          크게
        </button>
        <button type="button" onClick={pane.fitWidth}>
          폭 맞춤
        </button>
        <button
          type="button"
          onClick={pane.rotate}
          aria-label="시계 방향으로 돌리기"
        >
          돌리기
        </button>
      </footer>
    </section>
  );
}
