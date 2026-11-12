// pdf.js 로 PDF 를 열고 쪽을 그린다. 이 패키지에서 pdf.js 를 부르는 곳은 여기뿐이다(tools/ 의 측정 스크립트 제외).
import * as pdfjs from 'pdfjs-dist';
// Vite 의 `?url`: 이 파일을 빌드 결과에 따로 담고 그 주소를 돌려준다. pdf.js 는 PDF 해석을 이 워커에서 한다.
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import type { OpenPdf, PdfHandle, RenderJob } from './hooks/index.ts';

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

// pdf.js 가 필요할 때 내려받는 부속 파일(한글 등 CJK 글꼴의 문자 대응표, 기본 글꼴, 그림 해독기).
// tools/prepare.ts 가 node_modules 에서 public/pdfjs/ 로 복사해 둔다.
const ASSETS = `${import.meta.env.BASE_URL}pdfjs/`;

// 캔버스 하나의 픽셀 수 상한. 크게 확대해도 메모리가 터지지 않게 선명도를 낮춘다.
const MAX_CANVAS_PIXELS = 16_000_000;

const load = (url: string) =>
  pdfjs.getDocument({
    url,
    cMapUrl: `${ASSETS}cmaps/`,
    standardFontDataUrl: `${ASSETS}standard_fonts/`,
    wasmUrl: `${ASSETS}wasm/`,
    iccUrl: `${ASSETS}iccs/`,
  });

/**
 * PDF 의 쪽 수만 센다(밴드 GW1R Q2 — 그린워싱 올리기가 서버에 쪽 수를 묻기 전에 브라우저에서 센다). 다 세면 문서를 닫는다.
 * PDF 가 아니거나 깨졌으면 거절한다.
 */
export async function countPdfPages(url: string): Promise<number> {
  const task = load(url);
  try {
    const doc = await task.promise;
    return doc.numPages;
  } finally {
    void task.destroy();
  }
}

export const openPdf: OpenPdf = async (url) => {
  const doc = await load(url).promise;

  const handle: PdfHandle = {
    renderPage(pageNumber, canvas, scale, rotation): RenderJob {
      let cancelled = false;
      let cancelRender: (() => void) | undefined;

      const done = (async () => {
        const page = await doc.getPage(pageNumber);
        if (cancelled) return;

        // page.rotate: PDF 에 적힌 쪽 자체의 회전. 거기에 보는 사람이 돌린 각도를 더한다.
        const viewport = page.getViewport({
          scale,
          rotation: (page.rotate + rotation) % 360,
        });

        // 화면 픽셀 밀도만큼 더 촘촘히 그리고(선명하게), CSS 크기는 그대로 둔다.
        const density = Math.min(
          window.devicePixelRatio || 1,
          Math.sqrt(MAX_CANVAS_PIXELS / (viewport.width * viewport.height)),
        );
        canvas.width = Math.floor(viewport.width * density);
        canvas.height = Math.floor(viewport.height * density);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;

        const task = page.render({
          canvas,
          viewport,
          transform: density === 1 ? undefined : [density, 0, 0, density, 0, 0],
        });
        cancelRender = () => task.cancel();
        try {
          await task.promise;
        } catch (error) {
          // 취소하면 pdf.js 가 RenderingCancelledException 을 던진다. 그것은 삼킨다.
          if (!cancelled) throw error;
        }
      })();

      return {
        done,
        cancel() {
          cancelled = true;
          cancelRender?.();
        },
      };
    },

    close() {
      void doc.loadingTask.destroy();
    },
  };
  return handle;
};
