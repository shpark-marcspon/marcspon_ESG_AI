// 데이터 검증 model 칸의 공개 표면(밴드 DV2a ①). 순수 함수와 타입 — React·DOM·통신을 모른다.
export {
  checkLines,
  onlyProblems,
  resultCounts,
  riskCount,
  ruleOfTool,
  summarize,
} from './checks.ts';
export type {
  CheckLine,
  CheckSummary,
  ItemsView,
  Term,
  Verdict,
  YearLine,
} from './checks.ts';
export {
  EDK_KEYS,
  THEME_ENV,
  isEdkData,
  isWellFormed,
  k,
  previewOf,
  readEdk,
} from './edk.ts';
export type { EdkData, EdkItem, EdkPreview, EdkRead, EdkValue } from './edk.ts';
export { decimalSum, explain } from './explain.ts';
export type { Explanation } from './explain.ts';
export {
  INPUT_SHAPE,
  OPTIONS_MAX_OCTETS,
  buildInput,
  buildOptions,
  isTooLarge,
  pyJson,
  pyJsonOctets,
  pyNumber,
} from './options.ts';
export type { Company, DataverifyInput } from './options.ts';
export {
  PASTE_SOURCE,
  SOURCE_NAME_MAX,
  SOURCE_NAME_PATTERN,
  fileSource,
  isSourceName,
} from './source.ts';
export type { InputSource } from './source.ts';
export { isWebLink } from './webUrl.ts';
export { FAILURE_KINDS, REPORT_FILE_NAME, STEP_NAMES } from './result.ts';
export type {
  Check,
  CheckRule,
  DataverifyResult,
  DataverifyRun,
  Failure,
  FailureKind,
  InsightRow,
  InsightStage,
  PlanStage,
  ReviewStage,
  RowsParsed,
  RunStatus,
  RunStep,
  Scope,
  StepName,
  StepStatus,
  WebSource,
  YearNote,
  YearResult,
  YearStatus,
} from './result.ts';
export {
  NO_TARGET_THEME,
  STAGES,
  atText,
  currentStep,
  failureReason,
  hasNoTarget,
  notices,
  someStageFailed,
  stageState,
  stepViews,
} from './status.ts';
export type {
  FailureReason,
  Notice,
  Stage,
  StageState,
  StepView,
} from './status.ts';
