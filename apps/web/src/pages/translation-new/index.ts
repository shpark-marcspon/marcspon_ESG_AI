// 새 번역 화면 폴더의 공개 표면(밴드 TRW0a ② — 모양 부품과 model 만. 화면 조립·경로는 TRW1).
export {
  GRID_STEP,
  cellState,
  hiddenPainted,
  visibleCount,
} from './model/index.ts';
export { GlossaryField } from './ui/GlossaryField.tsx';
export type { GlossaryFieldProps } from './ui/GlossaryField.tsx';
export { PageGrid } from './ui/PageGrid.tsx';
export type { PageGridProps } from './ui/PageGrid.tsx';
export { PartRangeFields } from './ui/PartRangeFields.tsx';
export type { PartRangeFieldsProps } from './ui/PartRangeFields.tsx';
export { PreflightCard } from './ui/PreflightCard.tsx';
export type { PreflightCardProps } from './ui/PreflightCard.tsx';
// 새 번역 화면(밴드 TRW1a ② — app/translation 의 경로 컴포넌트가 가져온다).
export { NewTranslationScreen } from './ui/NewTranslationScreen.tsx';
export type {
  NewTranslationScreenProps,
  StartedBatch,
} from './ui/NewTranslationScreen.tsx';
