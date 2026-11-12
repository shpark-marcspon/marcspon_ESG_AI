// 검토 표의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(import 방향 테스트가 지킨다).
//
//   model/     업무 로직. 순수 TypeScript
//   hooks/     TanStack Table·Virtual 을 감싼 훅, 그리고 모양 없는 컴포넌트(RowStack, RowFrame). 모양(색·테두리·글꼴)을 모른다
//   ui/        화면. 바꿔 끼우는 층
//
// 표면이 하나 더 있다:
//   model/index.ts   화면 없는 표면. node 에서 도는 스크립트(tools/)가 쓴다
export * from './model/index.ts';
export * from './hooks/index.ts';
export { ReviewTable } from './ui/ReviewTable.tsx';
export type { ReviewTableProps } from './ui/ReviewTable.tsx';
