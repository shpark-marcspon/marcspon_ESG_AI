// 헤드리스 층의 공개 표면. 화면 층은 여기서만 가져다 쓴다.
export type { OpenPdf, PdfHandle, RenderJob } from './pdfBackend.ts';
export type {
  DocViewer,
  DocViewerOptions,
  DrawState,
  ItemRow,
  LegendEntry,
  PointSource,
  Reveal,
} from './useDocViewer.ts';
export { useDocViewer } from './useDocViewer.ts';
export type { PaneView, ViewportSize } from './usePaneView.ts';
export { usePaneView } from './usePaneView.ts';
export type { LoadedPdf } from './usePdf.ts';
export { usePdf } from './usePdf.ts';
export type { ReviewDraft } from './useReviewDraft.ts';
export { useReviewDraft } from './useReviewDraft.ts';
export type { Reviews } from './useReviews.ts';
export { useReviews } from './useReviews.ts';

// 모양 없는 컴포넌트. 구조와 자리(인라인 style)와 상태 표시(data-*)는 갖고, 색·선·글꼴은 쓰는 쪽이 입힌다.
export type { HighlightOverlayProps, PieceLook } from './HighlightOverlay.tsx';
export { HighlightOverlay } from './HighlightOverlay.tsx';
export type { PageCanvasProps } from './PageCanvas.tsx';
export { PageCanvas } from './PageCanvas.tsx';
export type { PageStackProps } from './PageStack.tsx';
export { PageStack } from './PageStack.tsx';
