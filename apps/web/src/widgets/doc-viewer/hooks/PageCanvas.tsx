// 쪽 하나를 캔버스에 그린다. 배율이나 회전이 바뀌면 캔버스를 새로 만든다(key).
// 같은 캔버스에 두 번 겹쳐 그리게 하면 pdf.js 가 오류를 내기 때문에, 고쳐 그리지 않고 갈아 끼운다.
// 모양 없는 컴포넌트다. 캔버스의 크기는 PdfHandle 이 정하고, 여기서는 줄 아래의 틈이 생기지 않게 display: block 만 준다.
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import type { Rotation } from '../model/index.ts';
import type { PdfHandle } from './pdfBackend.ts';

export interface PageCanvasProps {
  pdf: PdfHandle;
  pageNumber: number;
  scale: number;
  rotation: Rotation;
  className?: string;
  /** 이 쪽을 그리지 못했을 때 캔버스 뒤에 보일 것. 안 주면 아무것도 없다(캔버스의 data-render-state="error" 는 붙는다). */
  errorFallback?: ReactNode;
}

export function PageCanvas(props: PageCanvasProps) {
  // 설정이 바뀌면 통째로 새로 만든다. 그러면 안쪽은 「한 번 그리고 끝」만 생각하면 된다.
  return <OneRender key={`${props.scale}/${props.rotation}`} {...props} />;
}

function OneRender({
  pdf,
  pageNumber,
  scale,
  rotation,
  className,
  errorFallback,
}: PageCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [state, setState] = useState<'rendering' | 'done' | 'error'>(
    'rendering',
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let alive = true;
    const job = pdf.renderPage(pageNumber, canvas, scale, rotation);
    job.done.then(
      () => alive && setState('done'),
      (error: unknown) => {
        // 떠난 뒤의 거절은 취소(cancel)·문서 닫힘(close) 탓이라 찍지 않는다 — sid:MARC-ISSUE-419
        if (!alive) return;
        console.error(`${pageNumber}페이지를 그리지 못했다`, error);
        setState('error');
      },
    );
    return () => {
      alive = false;
      job.cancel();
    };
  }, [pdf, pageNumber, scale, rotation]);

  // data-render-state: 브라우저 테스트가 「다 그려졌는가」를 물어 기다리는 데 쓴다.
  return (
    <>
      <canvas
        ref={canvasRef}
        className={className}
        style={{ display: 'block' }}
        data-render-state={state}
      />
      {state === 'error' && errorFallback}
    </>
  );
}
