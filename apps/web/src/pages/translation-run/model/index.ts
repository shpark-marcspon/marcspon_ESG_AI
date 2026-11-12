// 영문번역 결과 화면 폴더 model 의 공개 표면(밴드 TRW0b). 순수 함수와 타입만.
export { filterIssues, severityCounts } from './issues.ts';
export type { IssueFilter, QaIssue } from './issues.ts';
// 결과·요약 → 화면 꼴(밴드 TRW1a ③).
export {
  checkRowsOf,
  issuesOf,
  reviewedRangeOf,
  missesOf,
  numbersOf,
  stepLineOf,
  sumNumbers,
} from './adapt.ts';
export type { CheckRow, PartNumbers, StepValue } from './adapt.ts';
// PDF 보기(밴드 TRW6 ③).
export {
  looseWarningsOf,
  pdfPageLinesOf,
  pdfPageOf,
  stageOf as pdfStageOf,
  variantLabelsOf,
} from './pdfView.ts';
export type {
  BoxLook,
  PdfBox,
  PdfCellAt,
  PdfGrid,
  PdfGridCell,
  PdfPageLine,
  PdfPageView,
  PdfPair,
  PdfWarning,
} from './pdfView.ts';
export { attachToPairs, normalizeText, placesOf } from './pdfAttach.ts';
export type {
  Attached,
  AttachInput,
  PdfOpenFocus,
  PdfPlace,
} from './pdfAttach.ts';
// PDF 보기 짝 칸의 밑줄·표(밴드 TRW7 ①).
export { marksOf, pairMarksOf } from './pdfMarks.ts';
export type {
  MarkKind,
  MarkPiece,
  MarkTag,
  MarkWant,
  Marked,
} from './pdfMarks.ts';
export { pipeTableOf } from './pdfTable.ts';
// PDF 보기 「번역 복사」 글(밴드 TRW14 ③).
export { copyTextOf } from './pdfCopy.ts';
// PDF 보기 문체 바꿈에 머물 항목(밴드 TRW8 ④).
export { samePairIn } from './pdfSame.ts';
export type { PipeTable } from './pdfTable.ts';
