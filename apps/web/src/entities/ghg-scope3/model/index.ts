// 온실가스 Scope 3 model 칸의 공개 표면(밴드 S3W1 ①). 순수 함수와 타입 — React·DOM·통신을 모른다.
export { CATEGORIES, CATEGORY_IDS, toggleCategory } from './category.ts';
export type { Category, CategoryId } from './category.ts';
export { MAX_UPLOAD_BYTES, acceptFile } from './file.ts';
export type { FileProblem } from './file.ts';
export {
  EDIT_KINDS,
  FACTOR_CHOICES,
  currentCards,
  currentFailedSheets,
  currentRunIds,
  currentTotal,
  overlayResult,
} from './current.ts';
export type {
  CurrentCard,
  EditHistoryLine,
  EditHistoryPage,
  EditKind,
  EditPerson,
  FactorChoice,
  RowEdit,
  RowEditResult,
  RowFactor,
  RowFactorAi,
  RowFactorInput,
  RunEdits,
  Scope3Year,
  YearCategory,
  YearCurrent,
} from './current.ts';
export { parseNumber } from './number.ts';
export {
  ACTIVITY_KINDS,
  BIOGENIC_CARDS,
  C12_BRANCHES,
  C12_TREATMENTS,
  ENERGY_KINDS,
  INPUT_KEYS,
  OPTIONAL_INPUT_KEYS,
  REJECT_REASONS,
  ROW_KINDS,
  summarize,
} from './result.ts';
export {
  PAGE_SIZE,
  SHEET_COLUMNS,
  SHEET_LAYOUTS,
  SORT_COLUMNS,
  categorySheets,
  cellOf,
  SOURCE_ESTIMATE,
  SOURCE_KINDS,
  fcfPercent,
  filterRows,
  layoutOf,
  pageOf,
  rowNumber,
  searchable,
  shareOf,
  sortRows,
} from './detail.ts';
export type {
  CellValue,
  ColumnId,
  DetailSheet,
  KnownLayout,
  RowPage,
  RowSort,
  SheetLayout,
  SourceCell,
  SortDirection,
} from './detail.ts';
export {
  HISTORY_PAGE_SIZE,
  ROW_EDIT_MAX,
  ROW_REASON_MAX,
  leadColumn,
  overRowLimit,
  pick,
  pickState,
  reasonFault,
  rowIdsOf,
  rowsToSend,
} from './rowEdit.ts';
export type { RowEditKind } from './rowEdit.ts';
export {
  factorWindowOf,
  isAiGroup,
  openingColumn,
  opensFactorWindow,
} from './factorWindow.ts';
export type {
  FactorWindow,
  TreatmentLine,
  TreatmentTable,
  WindowBase,
} from './factorWindow.ts';
export {
  FACTOR_CUSTOM_FIELDS,
  FACTOR_DECIMALS,
  FACTOR_RANK_LAST,
  FACTOR_TEXT_MAX,
  aiRowOf,
  customFaults,
  decimalText,
  factorBlock,
  factorInput,
  factorTextFault,
  factorValueFault,
  initialCustom,
  initialPick,
  recommendable,
  recommendationsOf,
  sameFactorPick,
} from './factorEdit.ts';
export type {
  FactorBlock,
  FactorCustomDraft,
  FactorCustomFaults,
  FactorCustomField,
  FactorPick,
  FactorTextFault,
  FactorValueFault,
} from './factorEdit.ts';
export type {
  ActivityKind,
  AmountCells,
  C12Branch,
  C12Treatment,
  C12TreatmentPart,
  C12Treatments,
  DistanceCells,
  EnergyKind,
  FactorCells,
  RowRecommendation,
  InputKey,
  InvestmentCells,
  RejectReason,
  ResultCard,
  ResultRow,
  ResultSheet,
  ResultSummary,
  RowDetail,
  RowInput,
  RowKind,
  RowOrigin,
  Scope3Done,
  Scope3Rejected,
  Scope3Result,
} from './result.ts';
export {
  SCOPE3_FLOW_ID,
  SCOPE3_MODULE,
  STEP_KEYS,
  failureKind,
  runPhase,
  steps,
} from './run.ts';
export type {
  FailureKind,
  RunPhase,
  RunStatus,
  Scope3Run,
  Scope3Stage,
  StepKey,
} from './run.ts';
export { seoulYear, yearIn, yearsOf } from './year.ts';
export {
  RUN_STEP_NAMES,
  RUN_STEP_STATUSES,
  progressOf,
} from './runProgress.ts';
export type { RunProgress, RunStep } from './runProgress.ts';
export { SPARKLE } from './sparkle.ts';
