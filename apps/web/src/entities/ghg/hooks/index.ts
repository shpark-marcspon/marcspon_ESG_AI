// 온실가스 hooks 칸의 공개 표면(밴드 W12-0a ①). 화면 둘 이상이 쓰는 읽기 훅. 모양을 모른다.
export {
  useAdminFacilityCodes,
  useBranch,
  useBranches,
  useDashboard,
  useFacilityCodes,
} from './useRead.ts';
export type { DetailState, ReadHandle, ReadState } from './useRead.ts';
export { rollMoves, useRoll } from './useRoll.ts';
