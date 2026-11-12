// 문서 뷰어 부품의 맨 위. 왼쪽에 항목 목록, 오른쪽에 문서 하나 또는 둘.
//
// 이 부품이 하는 일은 「골라진 항목」 하나를 들고 양쪽을 잇는 것이다.
//   - 목록에서 항목을 누르면 → 문서 칸마다 그 항목의 강조로 간다
//   - 문서에서 상자를 누르면 → 그 상자를 가리키는 항목이 골라진다(그리고 다른 문서 칸도 따라간다)
//   - j / k → 다음 / 이전 항목
//   - 목록의 항목에 마우스를 올리거나 초점이 가면 → 그 항목의 상자가 진해진다(스크롤하지는 않는다)
// 그 상태와 규칙은 전부 헤드리스 층의 useDocViewer 에 있다. 이 파일은 그것을 화면으로 옮길 뿐이다.
// 검토 상태는 밖에서 받는다(reviews, onReview). 이 부품은 저장을 모른다.
import { useDocViewer } from '../hooks/index.ts';
import type { OpenPdf } from '../hooks/index.ts';
import type {
  HighlightMode,
  ReviewAction,
  ReviewState,
  TransitionResult,
  ViewerInput,
} from '../model/index.ts';
import { ItemList } from './ItemList.tsx';
import { PdfPane } from './PdfPane.tsx';
import './viewer.css';

export interface DocumentViewerProps {
  /** parseViewerInput 을 통과한 자료. */
  input: ViewerInput;
  /** PDF 를 여는 함수. 보통 doc-viewer/pdfjs.ts 의 openPdf. 테스트는 가짜를 넣는다. */
  openPdf: OpenPdf;
  reviews: ReadonlyMap<string, ReviewState>;
  onReview(itemId: string, action: ReviewAction): TransitionResult;
  /** 강조 상자의 보기 방식. 안 주면 「옅게」(outline). 뜻은 domain/highlightMode.ts 에. */
  highlightMode?: HighlightMode;
}

export function DocumentViewer({
  input,
  openPdf,
  reviews,
  onReview,
  highlightMode,
}: DocumentViewerProps) {
  const viewer = useDocViewer({ input, reviews, highlightMode });

  return (
    // tabIndex: 키보드 이동을 받으려면 초점을 가질 수 있어야 한다.
    <div
      className="dv-root"
      data-layout={input.documents.length === 2 ? 'side-by-side' : 'single'}
      tabIndex={0}
      onKeyDown={viewer.onKeyDown}
    >
      <aside className="dv-side">
        {input.notice && <p className="dv-notice">{input.notice}</p>}
        {/* 범례가 곧 켜고 끄는 단추다. 꺼도 고른 항목과 가리킨 항목의 상자는 보인다. */}
        <div
          className="dv-legend"
          role="group"
          aria-label="종류별로 상자 켜고 끄기"
        >
          {viewer.legend.map(({ kind, look, shown }) => (
            <button
              key={kind}
              type="button"
              className="dv-kind"
              data-kind={kind}
              aria-pressed={shown}
              title={
                shown ? '누르면 이 종류의 상자를 숨긴다' : (
                  '누르면 이 종류의 상자를 다시 보인다'
                )
              }
              onClick={() => viewer.toggleKind(kind)}
            >
              <i className="dv-dot" style={{ background: look.color }} />
              {look.label}
            </button>
          ))}
        </div>
        {viewer.hasInnerBoxes && (
          <label className="dv-toggle">
            <input
              type="checkbox"
              checked={viewer.useInnerBox}
              onChange={(event) => viewer.setUseInnerBox(event.target.checked)}
            />
            좁힌 자리로 보기(끄면 표·문단 전체 상자)
          </label>
        )}
        {/* 「고른 것만」에서는 고르지 않은 상자가 없어 문서에서 눌러 고를 수 없다. 그 사실을 여기서 알린다. */}
        {viewer.mode === 'selected' && (
          <p className="dv-mode-note" data-testid="dv-mode-note">
            고른 항목의 상자만 그린다. 문서에서 상자를 눌러 고를 수 없으니
            목록이나 <kbd>j</kbd>·<kbd>k</kbd> 로 고른다.
          </p>
        )}
        <p className="dv-help">
          항목 {input.items.length}개 · <kbd>j</kbd> 다음 <kbd>k</kbd> 이전
        </p>
        <ItemList viewer={viewer} onReview={onReview} />
      </aside>
      <div className="dv-panes">
        {input.documents.map((doc) => (
          <PdfPane
            key={doc.id}
            document={doc}
            viewer={viewer}
            openPdf={openPdf}
          />
        ))}
      </div>
    </div>
  );
}
