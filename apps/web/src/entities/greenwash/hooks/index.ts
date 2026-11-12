// 그린워싱 hooks 칸의 공개 표면(밴드 FW1b ①, FS1 ②). 화면 둘 이상이 쓰는 상태·동작 훅. 모양(색·클래스)을 모른다.
// 저장소 인터페이스와 계약 거울은 api/index.ts 로 갔다. 문서 뷰어(usePdf·PageCanvas·OpenPdf)는 다시 내보내지 않는다 —
//   쓰는 화면(pages/greenwash-*)이 widgets/doc-viewer/index.ts 를 직접 가져온다(FS1 ② 감독 결정). PDF 를 여는 구현(pdfjs.ts)은 app/greenwash/GreenwashRoutes.tsx 만.
export { useRerun, useRerunAction } from './useRerun.ts';
export type { Rerun } from './useRerun.ts';
export { useResult } from './useResult.ts';
export type { ResultHandle, ResultState } from './useResult.ts';
export { REJUDGE_POLL_MS, useReview } from './useReview.ts';
export type {
  ReviewHandle,
  ReviewReadState,
  ReviewSaveError,
} from './useReview.ts';
