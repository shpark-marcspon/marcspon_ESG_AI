// 문서 뷰어의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(import 방향 테스트가 지킨다).
//
//   model/     업무 로직. 순수 TypeScript
//   hooks/     상태와 동작을 든 훅, 그리고 모양 없는 컴포넌트. 모양(색·테두리·글꼴)을 모른다
//   ui/        화면. 바꿔 끼우는 층
//
// 표면이 둘 더 있다:
//   model/index.ts   화면 없는 표면. node 에서 도는 스크립트(tools/)가 쓴다
//   pdfjs.ts         PDF 를 여는 구현(pdf.js). 번들러의 `?url` 과 워커를 쓰므로 node 와 jsdom 이 읽지 못해 따로 둔다
export * from './model/index.ts';
export * from './hooks/index.ts';
export { DocumentViewer } from './ui/DocumentViewer.tsx';
export type { DocumentViewerProps } from './ui/DocumentViewer.tsx';
