// PDF 하나를 열고, 다 쓰면 닫는다. 주소가 바뀌면 앞의 것을 닫고 새로 연다.
//
// 여는 함수(openPdf)가 바뀐 것만으로는 다시 열지 않는다. 다시 여는 까닭은 주소 하나다.
//   쓰는 쪽이 `openPdf={(url) => …}` 처럼 그릴 때마다 새 함수를 넘겨도 된다. 전에는 [url, openPdf] 에 걸려 있어서,
//   그렇게 넘기면 「열림 → 상태 바뀜 → 다시 그리기 → 새 함수 → 다시 열기」가 끝없이 돌았다.
//   그래서 함수는 ref 에 최신 것을 적어 두고, 여는 순간에 그것을 읽는다.
// 잃는 것: 같은 주소를 다른 함수로 다시 열게 할 수 없다(예: PDF 라이브러리를 도중에 바꿔 끼우기).
//   그럴 일이 생기면 쓰는 쪽이 부품의 key 를 바꿔 새로 만든다.
import { useEffect, useRef, useState } from 'react';

import type { OpenPdf, PdfHandle } from './pdfBackend.ts';

export type LoadedPdf =
  | { state: 'loading' }
  | { state: 'ready'; pdf: PdfHandle }
  | { state: 'error'; message: string };

export function usePdf(url: string, openPdf: OpenPdf): LoadedPdf {
  const [loaded, setLoaded] = useState<LoadedPdf>({ state: 'loading' });

  // 가장 최근에 받은 여는 함수. 그린 뒤에 적는다(그리는 중에 ref 를 고치지 않는다).
  // 의존 목록이 없는 effect 라 그릴 때마다 돌고, 아래의 여는 effect 보다 먼저 선언돼 있어 먼저 돈다.
  const openRef = useRef(openPdf);
  useEffect(() => {
    openRef.current = openPdf;
  });

  useEffect(() => {
    let alive = true;
    let opened: PdfHandle | undefined;
    setLoaded({ state: 'loading' });
    openRef.current(url).then(
      (pdf) => {
        opened = pdf;
        if (alive) setLoaded({ state: 'ready', pdf });
        else pdf.close();
      },
      (error: unknown) => {
        if (alive)
          setLoaded({
            state: 'error',
            message: error instanceof Error ? error.message : String(error),
          });
      },
    );
    return () => {
      alive = false;
      opened?.close();
    };
  }, [url]);

  return loaded;
}
