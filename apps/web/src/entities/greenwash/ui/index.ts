// 그린워싱 모양 부품의 공개 표면. 이 칸 밖(demo-parts·e2e·pages/greenwash-* 의 화면)은 여기로만 들어온다
// (app/guards/layers.test.ts 가 지킨다). 부품은 모두 props 만 받는 모양 부품이다: 상태·저장·흐름을 모른다.
export { COMPARE_KINDS, CompareBadge } from './CompareBadge.tsx';
export type { CompareBadgeProps, CompareKind } from './CompareBadge.tsx';
export { ConfirmReviewDialog } from './ConfirmReviewDialog.tsx';
export { CountUp, useCountUp } from '../../../shared/ui/motion/index.ts';
export type { ConfirmReviewDialogProps } from './ConfirmReviewDialog.tsx';
export {
  EXCLUDE_REASONS,
  ExcludeReasonDialog,
} from './ExcludeReasonDialog.tsx';
export type {
  ExcludeReason,
  ExcludeReasonDialogProps,
  ExcludeReasonValue,
} from './ExcludeReasonDialog.tsx';
export { GwDownloads } from './GwDownloads.tsx';
export type { GwDownloadsProps } from './GwDownloads.tsx';
export { LOAD_FAILURE_KINDS, LoadFailure } from './LoadFailure.tsx';
export type { LoadFailureKind, LoadFailureProps } from './LoadFailure.tsx';
export { LockBanner } from './LockBanner.tsx';
export { partName } from './partName.ts';
export type { LockBannerProps } from './LockBanner.tsx';
export { REVIEW_VALUES, ReviewChoice, ReviewMark } from './ReviewChoice.tsx';
export {
  AddedMark,
  AiOriginal,
  EditedMark,
  LevelPicker,
  NonRiskBadge,
  RejudgedMark,
} from './ReviewEdit.tsx';
export type {
  AiOriginalProps,
  EditedMarkProps,
  LevelPickerProps,
} from './ReviewEdit.tsx';
export type {
  ReviewChoiceProps,
  ReviewMarkProps,
  ReviewPick,
  ReviewValue,
} from './ReviewChoice.tsx';
export { RISK_LEVELS, RiskBadge } from './RiskBadge.tsx';
export type { RiskBadgeProps, RiskLevel } from './RiskBadge.tsx';
export { RUN_STATUS_KINDS, RunStatusBadge } from './RunStatusBadge.tsx';
export type {
  RunStatus,
  RunStatusBadgeProps,
  RunStatusKind,
} from './RunStatusBadge.tsx';
export { StepFlow } from './StepFlow.tsx';
export type { StepFlowProps } from './StepFlow.tsx';
export { VersionFlowStrip } from './VersionFlowStrip.tsx';
export type {
  VersionFlowItem,
  VersionFlowStripProps,
} from './VersionFlowStrip.tsx';
export { useObjectUrl } from './useObjectUrl.ts';
