// 이 화면만 쓰는 업무 로직의 공개 표면(밴드 FS1 ②). 옛 greenwash/domain/index.ts 에서 옮겨 왔다.
export {
  countsAgree,
  failedPagesOf,
  isExtraTermRow,
  levelCountsOf,
  partSummaries,
  termFrequency,
} from './summary.ts';
export type { PartSummary, TermScope } from './summary.ts';
