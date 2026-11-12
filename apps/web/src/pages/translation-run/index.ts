// 영문번역 상태·결과 화면 폴더의 공개 표면(밴드 TRW0b — 모양 부품과 model 만. 화면 조립·경로는 TRW1).
export { filterIssues, severityCounts } from './model/index.ts';
export type { IssueFilter, QaIssue } from './model/index.ts';
export { AllSummary } from './ui/AllSummary.tsx';
export type { AllSummaryProps, AllSummaryRow } from './ui/AllSummary.tsx';
export { GlossaryMissTable } from './ui/GlossaryMissTable.tsx';
export type { GlossaryMissTableProps } from './ui/GlossaryMissTable.tsx';
export { PagesToCheck, ResultNotices, StepLine } from './ui/PagesToCheck.tsx';
export type {
  PagesToCheckProps,
  ResultNoticesProps,
  StepLineProps,
} from './ui/PagesToCheck.tsx';
export { PartResultHeader } from './ui/PartResultHeader.tsx';
export type { Loader, PartResultHeaderProps } from './ui/PartResultHeader.tsx';
export { QaIssueTable } from './ui/QaIssueTable.tsx';
export type { QaIssueTableProps } from './ui/QaIssueTable.tsx';
// 묶음 화면(밴드 TRW1a ③ — app/translation 의 경로 컴포넌트가 가져온다).
export { RunScreen } from './ui/RunScreen.tsx';
export type { RunScreenProps } from './ui/RunScreen.tsx';
// PDF 보기(밴드 TRW6 ③ — app/translation 의 PdfViewRoute 가 가져온다).
export { PdfView } from './ui/pdf/PdfView.tsx';
export type { PdfViewProps } from './ui/pdf/PdfView.tsx';
export type { PdfOpenFocus } from './model/index.ts';
