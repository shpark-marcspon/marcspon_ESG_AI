// 영문번역 ui 의 공개 표면(밴드 TRW0b — 두 화면 이상이 쓰는 모양 부품과 상태 글). 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts).
export { BatchTable } from './BatchTable.tsx';
export type { BatchPart, BatchRow, BatchTableProps } from './BatchTable.tsx';
export {
  partStatusLabel,
  rejectionText,
  remainingLine,
  screenTitle,
  summaryItems,
  tabLabel,
} from './labels.ts';
export { PartFailureCard } from './PartFailureCard.tsx';
export type { PartFailureCardProps } from './PartFailureCard.tsx';
export {
  PART_STATUS_LOOK,
  PartStatusText,
  StatusBadge,
} from './PartStatusText.tsx';
export type {
  PartStatusTextProps,
  StatusBadgeProps,
  StatusLook,
} from './PartStatusText.tsx';
export { PartTabs } from './PartTabs.tsx';
export type { PartTab, PartTabKey, PartTabsProps } from './PartTabs.tsx';
export { StageCard } from './StageCard.tsx';
export type { StageCardProps, StageState } from './StageCard.tsx';
export { StatTiles } from './StatTiles.tsx';
export type { StatTile, StatTilesProps } from './StatTiles.tsx';
// PDF 보기의 원본 PDF 주소(밴드 TRW6 ③).
export { useObjectUrl } from './useObjectUrl.ts';
