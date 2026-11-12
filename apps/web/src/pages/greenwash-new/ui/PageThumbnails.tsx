// 쪽 썸네일 고르기(밴드 FW1b ②·③, 시안 GW-02_r1 카드 2). 고른 파일을 열어 작게(scale 0.2) 그리고, 쪽을 누르거나 끌어서 칠한다.
//
// - 파일은 useObjectUrl 로 object URL 을 열고, 파일이 바뀌거나 언마운트되면 revoke 한다(검토 쪽 칸과 같은 훅, 밴드 WC1 ③).
// - PDF 를 여는 구현(openPdf)은 props 로 받는다(ui 는 widgets/doc-viewer/pdfjs.ts 를 가져오지 못한다. 층 시험).
// - 한 번에 40쪽, 「더 보기」로 다음 40쪽을 이어 붙인다. 그리기 끝은 캔버스의 data-render-state="done".
// - 끌기 칠하기는 마우스만이다(③ 에서 정함). 누르면(pointerdown) 끌기 시작, 누른 채 움직이면(창의 pointermove) 그 자리의 쪽까지 칠하고,
//   손을 떼면(창의 pointerup·pointercancel) 끝. 포인터가 썸네일 칸 밖으로 나가도 칸 가장자리의 쪽까지 칠한다.
//   끄는 중 포인터가 썸네일 칸(위아래 가장자리 EDGE)이나 화면 위아래 가장자리에 닿으면 자동으로 스크롤한다(먼저 칸, 칸이 끝이면 페이지).
// - 터치·펜은 끌어 칠하지 않는다: 손가락으로 끌면 칸과 페이지가 스크롤된다(touch-action 그대로). 쪽을 톡 누르면(click) 하나씩 넣거나 뺀다.
// - 키보드 Enter·Space 는 click(detail 0)으로 누르기 토글. 마우스 click 은 pointerdown 이 이미 칠했으므로 무시한다.
// - 칸 틀은 쪽 그림에 붙는다(밴드 FW2 ⓪, 디자인 대조 「따로 적는 것 3」): 틀이 칸 폭을 다 채우지 않고 그림 크기를 따라가므로 칠한 쪽의 양옆에 색 띠가 없다.
// - PDF 를 못 열면 칸 안에 오류 글을 둔다. 쪽 수는 서버 값(pageCount)을 따른다: 문서 뷰어 PdfHandle 이 PDF 의 쪽 수를 내지 않아
//   min(pageCount, PDF 쪽 수) 로 자르지 못했다 — 그리지 못한 쪽은 칸 안에 「그릴 수 없음」을 보인다(보고 「감독에게 물을 것」, sid:MARC-ISSUE-99 7).
import { useCallback, useEffect, useRef, useState } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  PART_KEYS,
  formatPageRange,
  partsOfPage,
} from '../../../entities/greenwash/model/index.ts';
import type { PartPages } from '../../../entities/greenwash/model/index.ts';
import { useObjectUrl } from '../../../entities/greenwash/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { PageCanvas, usePdf } from '../../../widgets/doc-viewer/index.ts';
import type { OpenPdf, PdfHandle } from '../../../widgets/doc-viewer/index.ts';
import type { NewCheckForm } from '../hooks/index.ts';
import { OVERLAP_LOOK, PART_LOOK, PLAIN_LOOK } from './partLook.ts';

/** 한 번에 보이는 쪽 수. */
export const THUMB_PAGE_STEP = 40;
/** 썸네일 배율(1 포인트 = 0.2 CSS 픽셀). */
export const THUMB_SCALE = 0.2;
/** 끄는 중 자동 스크롤이 시작되는 가장자리 너비(px). */
const EDGE = 48;
/** 자동 스크롤의 한 프레임 최대 거리(px). */
const MAX_STEP = 20;

/** 가장자리 [top, bottom] 안쪽 EDGE 에 들면 스크롤 거리(위 음수, 아래 양수). 밖으로 나가면 최대. */
function edgeStep(y: number, top: number, bottom: number): number {
  if (bottom - top < EDGE * 2) return 0;
  if (y < top + EDGE)
    return -Math.ceil(Math.min(1, (top + EDGE - y) / EDGE) * MAX_STEP);
  if (y > bottom - EDGE)
    return Math.ceil(Math.min(1, (y - (bottom - EDGE)) / EDGE) * MAX_STEP);
  return 0;
}

const clamp = (value: number, low: number, high: number) =>
  Math.min(Math.max(value, low), high);

const words = GW_TEXT.newCheck.parts;

export interface PageThumbnailsProps {
  file: File;
  pageCount: number;
  form: NewCheckForm;
  openPdf: OpenPdf;
}

export function PageThumbnails({
  file,
  pageCount,
  form,
  openPdf,
}: PageThumbnailsProps) {
  const url = useObjectUrl(file);
  if (url === null) return null;
  return (
    <ThumbGrid
      key={url}
      url={url}
      pageCount={pageCount}
      form={form}
      openPdf={openPdf}
    />
  );
}

function ThumbGrid({
  url,
  pageCount,
  form,
  openPdf,
}: Omit<PageThumbnailsProps, 'file'> & { url: string }) {
  const loaded = usePdf(url, openPdf);
  const [shown, setShown] = useState(Math.min(THUMB_PAGE_STEP, pageCount));
  const boxRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  /** 끄는 중 마지막 포인터 자리. null 이면 끌지 않는 중. */
  const dragRef = useRef<{ x: number; y: number } | null>(null);
  const frameRef = useRef(0);
  const { endPaint, paintTo } = form;

  /** 포인터 자리의 쪽까지 칠한다. 칸 밖이면 칸(과 화면) 가장자리로 당긴 자리에서 찾는다. */
  const paintAt = useCallback(
    (x: number, y: number) => {
      const box = boxRef.current;
      const grid = gridRef.current;
      if (!box || !grid) return;
      const boxRect = box.getBoundingClientRect();
      const gridRect = grid.getBoundingClientRect();
      const top = Math.max(boxRect.top, 0);
      const bottom = Math.min(boxRect.bottom, window.innerHeight);
      if (bottom <= top) return;
      const under = document
        .elementFromPoint(
          clamp(x, gridRect.left + 1, gridRect.right - 1),
          clamp(y, top + 1, bottom - 1),
        )
        ?.closest<HTMLElement>('[data-page]');
      if (!under || !grid.contains(under)) return;
      const page = Number(under.dataset.page);
      if (Number.isInteger(page) && page > 0) paintTo(page);
    },
    [paintTo],
  );

  const stopDrag = useCallback(() => {
    dragRef.current = null;
    cancelAnimationFrame(frameRef.current);
    endPaint();
  }, [endPaint]);

  /** 끌기를 시작한다. 끄는 동안 프레임마다: 가장자리면 칸(끝이면 페이지)을 스크롤하고 새로 들어온 쪽까지 칠한다. */
  const startDrag = useCallback(
    (x: number, y: number) => {
      dragRef.current = { x, y };
      const loop = () => {
        const drag = dragRef.current;
        const box = boxRef.current;
        if (!drag || !box) return;
        let moved = false;
        const rect = box.getBoundingClientRect();
        const boxStep = edgeStep(
          drag.y,
          Math.max(rect.top, 0),
          Math.min(rect.bottom, window.innerHeight),
        );
        if (boxStep !== 0) {
          const before = box.scrollTop;
          box.scrollTop = before + boxStep;
          moved = box.scrollTop !== before;
        }
        if (!moved) {
          const pageStep = edgeStep(drag.y, 0, window.innerHeight);
          if (pageStep !== 0) {
            const before = window.scrollY;
            window.scrollBy(0, pageStep);
            moved = window.scrollY !== before;
          }
        }
        if (moved) paintAt(drag.x, drag.y);
        frameRef.current = requestAnimationFrame(loop);
      };
      cancelAnimationFrame(frameRef.current);
      frameRef.current = requestAnimationFrame(loop);
    },
    [paintAt],
  );

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      if (!dragRef.current) return;
      // 창 밖에서 단추를 놓아 pointerup 을 못 받은 경우
      if (!(event.buttons & 1)) return stopDrag();
      dragRef.current = { x: event.clientX, y: event.clientY };
      paintAt(event.clientX, event.clientY);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', stopDrag);
    window.addEventListener('pointercancel', stopDrag);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', stopDrag);
      window.removeEventListener('pointercancel', stopDrag);
      cancelAnimationFrame(frameRef.current);
    };
  }, [paintAt, stopDrag]);

  const pages = Array.from({ length: shown }, (_, i) => i + 1);
  const hidden = hiddenPainted(form.parts, shown, pageCount);
  return (
    <div
      data-testid="thumbnails"
      data-pdf-state={loaded.state}
      className="flex flex-col gap-3 rounded-component border border-solid border-border-tertiary bg-background-secondary p-4"
    >
      <div
        ref={boxRef}
        data-testid="thumbnails-scroll"
        className="max-h-[520px] overflow-auto"
      >
        {loaded.state === 'error' && (
          <p
            role="alert"
            data-testid="thumbnails-error"
            className="m-0 text-style-pre-caption-03 text-support-error"
          >
            {words.pdfError}
          </p>
        )}
        <div ref={gridRef} className="grid grid-cols-10 gap-2.5">
          {loaded.state === 'ready' &&
            pages.map((page) => (
              <Thumb
                key={page}
                page={page}
                pdf={loaded.pdf}
                form={form}
                onDragStart={startDrag}
              />
            ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {words.viewing(1, shown)}
          {hidden.length > 0 &&
            ` · ${words.hiddenPainted(shown + 1, pageCount, hidden)}`}
        </p>
        {shown < pageCount && (
          <Button
            variant="outlineGrey"
            size="sm"
            onClick={() =>
              setShown((n) => Math.min(n + THUMB_PAGE_STEP, pageCount))
            }
          >
            {words.more(
              shown + 1,
              Math.min(shown + THUMB_PAGE_STEP, pageCount),
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

function Thumb({
  page,
  pdf,
  form,
  onDragStart,
}: {
  page: number;
  pdf: PdfHandle;
  form: NewCheckForm;
  onDragStart(x: number, y: number): void;
}) {
  /** 마지막 pointerdown 의 종류. 마우스면 click 을 무시한다(pointerdown 이 칠했다). */
  const pointerRef = useRef<string | null>(null);
  const painted = partsOfPage(form.parts, page);
  const look =
    painted.length > 1 ? OVERLAP_LOOK
    : painted.length === 1 ? PART_LOOK[painted[0]!]
    : PLAIN_LOOK;
  return (
    <button
      type="button"
      aria-label={words.thumbLabel(
        page,
        painted.map((key) => words.names[key]),
      )}
      data-page={page}
      data-parts={painted.join(' ') || undefined}
      className="flex min-w-0 cursor-pointer select-none flex-col items-center gap-1 border-0 bg-transparent p-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary"
      onPointerDown={(event) => {
        pointerRef.current = event.pointerType;
        if (event.pointerType !== 'mouse' || event.button !== 0) return;
        event.preventDefault();
        form.beginPaint(page);
        onDragStart(event.clientX, event.clientY);
      }}
      onClick={(event) => {
        // 키보드(detail 0)와 터치·펜의 톡 누르기. 마우스 누름은 pointerdown 이 칠했다.
        if (event.detail === 0 || pointerRef.current !== 'mouse')
          form.pressPage(page);
        pointerRef.current = null;
      }}
    >
      <span
        data-thumb-frame
        className={cn(
          'box-border inline-flex max-w-full items-center justify-center overflow-hidden rounded-control',
          look.frame,
        )}
      >
        {/* 그림 = 종이(시안 .g-th .pg, GW3R2 SC5). 칸이 좁으면 폭과 높이를 같이 줄인다: 캔버스의 인라인 크기(pdfjs.ts)를 !h-auto 로 풀어
            높이가 캔버스 본래 비율을 따른다(옛 꼴은 폭만 줄어 가로로 눌렸다). multiply 로 흰 종이가 틀 바탕 색(파트 tint)을 받는다. */}
        <PageCanvas
          pdf={pdf}
          pageNumber={page}
          scale={THUMB_SCALE}
          rotation={0}
          className="block !h-auto max-w-full mix-blend-multiply"
          errorFallback={
            <span className="text-style-pre-caption-03 text-text-quaternary">
              {words.thumbError}
            </span>
          }
        />
      </span>
      <span
        aria-hidden
        className={cn(
          'inline-flex items-center gap-1 text-style-pre-caption-02',
          look.number,
        )}
      >
        {page}
        {painted.length > 1 &&
          painted.map((key) => (
            <span
              key={key}
              data-part-dot={key}
              className={cn('size-1.5 rounded-full', PART_LOOK[key].swatch)}
            />
          ))}
      </span>
    </button>
  );
}

/** 보이는 쪽(1~shown) 밖에 칠한 파트와 그 범위. */
function hiddenPainted(
  parts: PartPages,
  shown: number,
  pageCount: number,
): { name: string; range: string }[] {
  if (shown >= pageCount) return [];
  return PART_KEYS.flatMap((key) => {
    const outside = parts[key].filter((page) => page > shown);
    return outside.length === 0 ?
        []
      : [{ name: words.names[key], range: formatPageRange(outside) }];
  });
}
