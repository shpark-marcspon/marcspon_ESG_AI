// 파일 드롭존의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
//
//   model/     파일 판정(judgeFiles: 형식·크기·같은 이름·개수, 걸러서 통과). 순수 TypeScript
//   hooks/     useFileDropzone: 목록·끌어다 놓기·파일 창 열기·키보드. 모양을 모른다
//   ui/        FileDropzone. 클래스 이름은 여기에만 있다
export * from './model/index.ts';
export * from './hooks/index.ts';
export { FileDropzone } from './ui/FileDropzone.tsx';
export type {
  FileDropzoneProps,
  FileDropzoneText,
  FileDropzoneTextInput,
  RejectLimits,
  RejectReasonText,
} from './ui/FileDropzone.tsx';
