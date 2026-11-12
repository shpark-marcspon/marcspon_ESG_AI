// 영문번역 hooks 칸의 공개 표면(밴드 TRW1a ①). 화면 둘 이상이 쓰는 읽기 훅. 모양을 모른다.
export { useBatch } from './useBatch.ts';
export type { BatchHandle, BatchWatch } from './useBatch.ts';
export { useBatches } from './useBatches.ts';
export type { BatchesHandle, BatchesState } from './useBatches.ts';
export { useResult } from './useResult.ts';
export type { ResultHandle, ResultState } from './useResult.ts';
// PDF 결과 읽기(밴드 TRW6 ①).
export { useLayout } from './useLayout.ts';
export type { LayoutHandle, LayoutState } from './useLayout.ts';
export { useRunInfo } from './useRunInfo.ts';
export type { RunInfoHandle, RunInfoState } from './useRunInfo.ts';
export { useRunPdf } from './useRunPdf.ts';
export type { RunPdfHandle, RunPdfState } from './useRunPdf.ts';
