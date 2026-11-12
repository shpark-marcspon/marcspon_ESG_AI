// 뷰어가 PDF 라이브러리에게 바라는 것 전부. 이 넷뿐이다.
// 뷰어 부품은 이 인터페이스만 알고, pdf.js 는 pdfjs.ts 한 파일에만 나온다.
// 다른 라이브러리로 바꾸거나 테스트에서 가짜를 넣을 때 이 꼴만 맞추면 된다.
import type { Rotation } from '../model/index.ts';

export interface RenderJob {
  /** 다 그려지면 풀린다. 취소해도 (오류 없이) 풀린다. 취소는 오류가 아니다. 그리다 실패했을 때만 거절된다. */
  done: Promise<void>;
  cancel(): void;
}

export interface PdfHandle {
  /**
   * 쪽 하나를 캔버스에 그린다. 캔버스의 크기(픽셀 수와 CSS 크기)는 이 함수가 정한다.
   * scale 은 「1 포인트 = 몇 CSS 픽셀」, rotation 은 보는 사람이 더 돌린 각도다.
   */
  renderPage(
    pageNumber: number,
    canvas: HTMLCanvasElement,
    scale: number,
    rotation: Rotation,
  ): RenderJob;
  /** 문서를 닫고 메모리를 돌려준다. */
  close(): void;
}

export type OpenPdf = (url: string) => Promise<PdfHandle>;
