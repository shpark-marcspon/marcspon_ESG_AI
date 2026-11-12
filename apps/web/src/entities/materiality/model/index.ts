// 중대성평가 model 칸의 공개 표면(밴드 IRW1 ①). 순수 함수와 타입 — React·DOM·통신을 모른다.
export { LIST_TABS, nextOf, rowTargetOf, statusesOf } from './list.ts';
export type { ListTab, NextAction, RowTarget } from './list.ts';
export { kstDay, periodOf, runDay } from './period.ts';
export type { Period } from './period.ts';
export {
  REPORT_FILE_NAME,
  RESEARCH_FILE_NAME,
  SIDES,
  SUMMARY_LIMIT,
  finOf,
  financialKindOf,
  impactLines,
  impactToneOf,
  impactUndecided,
  mergedItems,
  pathwayLines,
  pathwayUndecided,
  researchMissing,
  resultCards,
  riskTypeView,
  shortlistLines,
  subtopicTotal,
  subtopicsOf,
  summariesOf,
  summaryPositions,
  undecidedImpact,
  undecidedPathway,
  undecidedSubtopics,
} from './result.ts';
export type {
  Cell,
  Context,
  ContextItem,
  FinancialKind,
  FinancialRow,
  ImpactLine,
  ImpactRow,
  ImpactTone,
  ItemAt,
  ItemLabel,
  MaterialityInput,
  MaterialityResult,
  MaterialityRun,
  MergedItem,
  Outcome,
  Part1Topic,
  Part2Topic,
  PathwayLine,
  PathwayRow,
  ResearchStatus,
  ResultCards,
  RowAt,
  RunStatus,
  RunStep,
  Sector,
  ShortlistCell,
  ShortlistLine,
  Side,
  StepStatus,
  SubtopicRef,
  SummaryAt,
  SubtopicResult,
  Warning,
} from './result.ts';
export {
  EDIT_LIMITS,
  POINTER_PATTERN,
  canonicalItem,
  changesOf,
  checkDrafts,
  codepoints,
  editOfCell,
  editSummary,
  editedClock,
  editedStamp,
  groupOf,
  groupsOf,
  impactFields,
  itemFields,
  itemPointer,
  lineContext,
  outgoing,
  pathwayFields,
  rowPointer,
  shortlistCellPointers,
  summaryCellPointers,
  summaryFields,
} from './edits.ts';
export type {
  EditError,
  EditField,
  FieldKind,
  ItemGroup,
  ItemField,
  ItemRef,
  PathwayCell,
  ResultEdit,
  RowField,
} from './edits.ts';
export { RUN_STATUSES, atText } from './status.ts';
export {
  STEP_LINES,
  UnknownStepError,
  currentLine,
  lineOfStep,
  stepLines,
} from './steps.ts';
export type { LineStatus, StepLine, StepLineView } from './steps.ts';
export { WARNING_LINES, warningViews } from './warnings.ts';
export type { WarningLine, WarningView } from './warnings.ts';
export {
  DEFAULT_START_DATE,
  blankTopic,
  draftProblems,
  initialDraft,
  isCalendarDay,
  seoulDay,
} from './draft.ts';
export type { DraftProblem } from './draft.ts';
export {
  OPTIONS_MAX_OCTETS,
  STANDARDS,
  buildInput,
  buildOptions,
  filledSubtopics,
  optionsOctets,
  optionsTooLarge,
  pyJson,
} from './input.ts';
export type {
  IndustryDraft,
  RunDraft,
  Standard,
  SubtopicDraft,
  TopicDraft,
} from './input.ts';
export {
  VALUE_CHAIN_HEADER,
  VALUE_CHAIN_KEYS,
  VALUE_CHAIN_MAX_CHARS,
  VALUE_CHAIN_MAX_ROWS,
  blankValueChainRow,
  businessUnitCount,
  normalizeStage,
  rowsFromPaste,
  rowsFromServer,
  splitPaste,
  stagelessRows,
} from './valueChain.ts';
export type {
  ValueChainKey,
  ValueChainParsed,
  ValueChainRow,
} from './valueChain.ts';
export { VALUE_CHAIN_STAGES } from './wire.ts';
export type { ValueChainStage } from './wire.ts';
