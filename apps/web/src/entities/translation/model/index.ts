// 영문번역 model 의 공개 표면(밴드 TRW0a ② · TRW0b 파트 상태). 순수 함수와 타입만 — 화면·서버를 모른다.
export { PART_KEYS, PART_ORDER } from './parts.ts';
export type { PartKey } from './parts.ts';
export {
  CEO_PAGE_LIMIT,
  ceoError,
  ceoOverLimit,
  extendRange,
  formatRange,
  intersectRange,
  overlapOf,
  pageCountOf,
  paintRange,
  parseRange,
  pressRange,
} from './range.ts';
export type { Range, RangeError, RangeErrorCode, RangeRead } from './range.ts';
export {
  ISSUE_TYPE_KEYS,
  REJECTION_KEYS,
  SEVERITIES,
  SUMMARY_ORDER,
  TAB_STATES,
  batchNext,
  batchSummary,
  doneCount,
  failureKindOf,
  isActive,
  screenTitleKey,
  summaryStateOf,
} from './status.ts';
export { stageProgress } from './progress.ts';
export type {
  FailureKind,
  IssueTypeKey,
  RejectionKey,
  ScreenTitleKey,
  Severity,
  SummaryState,
  TabState,
} from './status.ts';
// 서버 꼴의 타입과 묶음 → 화면 꼴 잇기(밴드 TRW1a ①).
export { SERVER_PARTS, SERVER_REJECTION_KINDS } from './batch.ts';
export type {
  BatchEarlier,
  ServerBatchPart,
  BatchPerson,
  BatchRun,
  BatchState,
  BatchStep,
  DigestFiles,
  DigestVariant,
  GlossaryMiss,
  Outcome,
  PageBounds,
  ResultFragment,
  ResultPage,
  ResultVariant,
  ResultWarning,
  ReviewIssue,
  RunStatus,
  ServerPart,
  ServerRejectionKind,
  SeverityCounts,
  StepStatus,
  StyleChoice,
  TranslationBatch,
  TranslationBatchDetail,
  TranslationBatchPage,
  TranslationDigest,
  TranslationResult,
  VariantLabel,
} from './batch.ts';
export {
  batchRowId,
  batchViewOf,
  pageProgressOf,
  partKeyOf,
  partViewOf,
  rangeOf,
  rejectionKeyOf,
  runStateOf,
  serverPartOf,
  splitBatchRowId,
  stageOf,
  styleKeyOf,
  tabStateOf,
} from './adapt.ts';
export type { BatchView, PartView, StageState, StyleKey } from './adapt.ts';
// 옵션의 서버 크기 셈(밴드 TRP1 W3 — 파이썬 json.dumps 꼴).
export { pyJson, pyJsonOctets } from './options.ts';
// PDF 흐름·layout@1 화면 꼴(밴드 TRW6 ①).
export {
  LAYOUT_SHAPE,
  PDF_FLOW_ID,
  PDF_FLOW_PREFIX,
  isPdfFlow,
} from './layout.ts';
export type {
  LayoutBox,
  LayoutCell,
  LayoutMember,
  LayoutPage,
  LayoutUnit,
  LayoutUnitKind,
  LayoutVariant,
  LayoutVariantLabel,
  LayoutWarning,
  LayoutWarningCode,
  PlacedLevel,
  PlacedUnit,
  TranslationLayout,
} from './layout.ts';
