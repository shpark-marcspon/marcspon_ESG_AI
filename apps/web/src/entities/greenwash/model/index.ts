// 그린워싱 model 칸의 공개 표면(밴드 FW1b ①, 화면 둘 이상이 쓰는 것). 순수 함수만 있다: 바깥 패키지·바깥 파일·DOM 을 쓰지 않는다(app/guards/layers.test.ts).
export {
  CHECK_ROW_TABS,
  NEXT_ACTION,
  buildCheckRows,
  filterCheckRows,
  runOrdinal,
  runStatusOf,
} from './checkRows.ts';
export type {
  CheckRow,
  CheckRowFilter,
  CheckRowStatus,
  CheckRowTab,
  CheckRowsSource,
  ListedDocument,
  ListedRun,
  NextAction,
} from './checkRows.ts';
export { termKey } from './extraTerms.ts';
export {
  MAX_PAGE_COUNT,
  MAX_UPLOAD_MB,
  PAGE_RANGE_ERRORS,
  formatPageRange,
  parsePageRange,
  sortPages,
} from './pageRange.ts';
export type {
  PageRangeError,
  PageRangeErrorCode,
  PageRangeResult,
} from './pageRange.ts';
export {
  EMPTY_PARTS,
  PART_KEYS,
  SERVER_PART_NAMES,
  allPartsEmpty,
  overlapOf,
  overlapPages,
  partKeyOf,
  partsOfPage,
  totalPages,
  unionPages,
} from './parts.ts';
export type { PartKey, PartPages } from './parts.ts';
export {
  RUN_STAGES,
  STAGE_WEIGHTS,
  failurePoint,
  overallPercent,
  stageStates,
} from './progress.ts';
export type {
  RunProgress,
  RunStage,
  RunState,
  StageState,
} from './progress.ts';
export {
  LEVELS,
  RESULT_SHAPE,
  REVIEW_SHAPE,
  REVIEW_STATES,
  failedPagesOf,
  isScanResult,
} from './result.ts';
export type {
  Box,
  CandidateStats,
  CheckerConfig,
  ChunkingConfig,
  DryRun,
  DryRunResult,
  FailedPage,
  GreenwashResult,
  GreenwashReview,
  Level,
  LevelCounts,
  PageTermCounts,
  ResultConfig,
  ResultCounts,
  ResultItem,
  ResultModels,
  ResultPart,
  ResultPosition,
  ResultSource,
  EvidenceAdded,
  Rejudged,
  RejudgeStatus,
  ReviewDecision,
  ReviewEdit,
  ReviewEditedFix,
  ReviewEditedLevel,
  ReviewEditedReasons,
  ReviewEditIn,
  ReviewEvidence,
  ReviewEvidenceIn,
  ReviewMark,
  ReviewRejudge,
  ReviewReviewer,
  ReviewState,
  ReviewUpdate,
  ScanResult,
  Tally,
  TallyByKind,
  TermCount,
  TokenCount,
  WordCounts,
} from './result.ts';
export {
  aiChangedSince,
  basisOf,
  confirmUpdate,
  editUpdate,
  evidenceNow,
  evidenceUpdate,
  excludeReasonText,
  filterReviewRows,
  flatEdit,
  joinReview,
  markUpdate,
  reasonsFromText,
  nothingToRejudge,
  reasonsText,
  reviewTally,
  shownValues,
} from './review.ts';
export type {
  Basis,
  EditChange,
  EvidenceChange,
  ExcludeReasonResult,
  MarkChange,
  ReviewFilter,
  ReviewRow,
  ReviewTab,
  ReviewTally,
} from './review.ts';
export { SERVER_STAGE, progressFromServer } from './serverRun.ts';
export type {
  ServerRunStatus,
  ServerStep,
  ServerStepStatus,
} from './serverRun.ts';
export {
  formatKst,
  formatKstMonthDay,
  formatKstTime,
  toKstIso,
} from '../../../shared/lib/time.ts';
export {
  NO_TEXT_LAYER,
  SETUP_ERROR,
  canRerun,
  failureKind,
} from './failure.ts';
export type { FailureKind } from './failure.ts';
export { fallbackReportName, fileNameFromDisposition } from './report.ts';
