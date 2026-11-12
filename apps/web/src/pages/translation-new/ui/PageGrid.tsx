// 쪽 칸 그리드(밴드 TRW0a ②, 시안 TR-02 「2. 파트별 쪽 범위」 — GW-02 r2 의 쪽 칸 꼴, 결정 sid:MARC-ENT-392). 모양 부품: props 만 받는다.
//
// - 칸은 자리 그림이다(추출본에 쪽 그림이 없다): [PAGE n] 번호와 빈 쪽 모양만. 칸 수 = pageCount, 처음 step(40)개 + [더 보기].
//   PDF 입력은 thumbs 를 받아 ready 면 칸 안에 그 쪽 그림(보이는 칸만, 밴드 TRW9). 틀 색·배율은 그린워싱 PageThumbnails 와 같은 값 — 공통화 0(플랫폼-웹 허락 4, 아래 EDGE 와 같은 까닭).
//   썸네일 상자는 A 판 비율로 미리 박는다(쪽 크기는 이 화면에 없다 — PdfHandle·confirm 에 없음). 그리는 중·실패·가로 쪽도 같은 높이(이슈 494-3).
//   열기 전·열기 실패도 같은 비율의 빈 쪽 모양, thumbs 없음(워드)은 빈 쪽 모양 그대로, 한 쪽 그리기 실패는 그 칸만 회색 상자 + 번호(글 0).
// - 끌기(마우스, 밴드 TRW3 — 그린워싱 PageThumbnails 꼴): pointerdown 한 쪽이 끌기 전 구간 밖이면 칠하기, 안이면 지우개(paintRange).
//   창의 pointermove 로 닿은 쪽까지 미리 그 결과를 칠하고(칸 밖이면 칸 상자 안으로 당긴 자리의 쪽), 손을 떼면(창의 pointerup·
//   pointercancel, 또는 왼쪽 단추가 떨어진 pointermove) onPaint(고른 파트, paintRange) 를 한 번 부른다. 움직이지 않고 떼면 누름과 같다.
// - 누름(키보드 Enter·Space, 터치·펜의 톡): 구간 밖의 쪽이면 거기까지 늘리고, 구간 안의 쪽이면 뺀다 — 가운데 쪽이면 가까운 끝까지
//   같이, 한 쪽만 남은 쪽이면 파트 비움(pressRange, 파트마다 이어진 한 구간 sid:MARC-ENT-392).
//   키보드는 keydown 에서 처리하고 기본 동작(단추의 click)을 막는다. 마우스 click 은 pointerup 이 처리했으므로 무시한다.
// - 끄는 중 포인터가 칸 상자(위아래 가장자리 EDGE)나 화면 위아래 가장자리에 닿으면 자동으로 스크롤한다(그린워싱 PageThumbnails 의
//   edgeStep 과 같은 셈·상수를 옮겨 적음 — 공통화하지 않는다, 플랫폼-웹 허락 4).
// - 겹친 쪽(둘 이상): 중립 틀(data-overlap) + 쪽 번호 옆 파트 점(겹친 파트 수만큼, aria-hidden).
import { useCallback, useEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent as ReactPointerEvent } from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  PART_KEYS,
  formatRange,
  paintRange,
  pressRange,
} from '../../../entities/translation/model/index.ts';
import type {
  PartKey,
  Range,
} from '../../../entities/translation/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { PageCanvas } from '../../../widgets/doc-viewer/index.ts';
import type { LoadedPdf } from '../../../widgets/doc-viewer/index.ts';
import {
  GRID_STEP,
  cellState,
  hiddenPainted,
  visibleCount,
} from '../model/index.ts';
import { OVERLAP_LOOK, PART_LOOK, PLAIN_LOOK } from './partLook.ts';

const words = TR_TEXT.grid;
const names = TR_TEXT.parts.names;

/** 끄는 중 자동 스크롤이 시작되는 가장자리 너비(px). 그린워싱 PageThumbnails 와 같은 값. */
const EDGE = 48;
/** 자동 스크롤의 한 프레임 최대 거리(px). 그린워싱 PageThumbnails 와 같은 값. */
const MAX_STEP = 20;
/** 썸네일 배율(1 포인트 = 0.2 CSS 픽셀). 그린워싱 PageThumbnails 와 같은 값. */
const THUMB_SCALE = 0.2;

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

/** 쪽 칸 번호(칸이 아니면 null). */
function pageOf(target: EventTarget | null): number | null {
  const cell =
    target instanceof Element ?
      target.closest<HTMLElement>('[data-page]')
    : null;
  const page = Number(cell?.dataset.page);
  return Number.isInteger(page) && page > 0 ? page : null;
}

export interface PageGridProps {
  /** 추출본의 쪽 수(칸 수). */
  pageCount: number;
  ranges: Readonly<Record<PartKey, Range | null>>;
  /** 칠할 파트. */
  active: PartKey;
  /** 끌기를 마치거나 쪽을 누를 때 한 번. */
  onPaint(part: PartKey, range: Range | null): void;
  /** 한 번에 더 보이는 칸 수(기본 40). */
  step?: number;
  /** 연 PDF(usePdf 의 반환). 안 주면 칸은 자리 그림 그대로 — 워드 칸(밴드 TRW9). */
  thumbs?: LoadedPdf;
}

interface Drag {
  anchor: number;
  current: number;
  moved: boolean;
  /** 끄는 파트와 끌기 전 구간 — 미리 보기·끝 모두 이것 기준(그린워싱 paintRange(base, …) 꼴). */
  part: PartKey;
  base: Range | null;
}

export function PageGrid({
  pageCount,
  ranges,
  active,
  onPaint,
  step = GRID_STEP,
  thumbs,
}: PageGridProps) {
  // 더 보기로 늘린 칸 수. 보이는 칸은 쪽 수를 따른다(sid:MARC-ISSUE-307 1 — 0쪽으로 뜬 뒤 쪽 수가 오면 첫 칸들이 나오고,
  //   쪽 수가 줄면 마지막 쪽 너머 칸이 없다). 쪽 수가 바뀌면 늘린 수도 쪽 수 안으로 되맞춘다.
  const [opened, setShown] = useState(0);
  const shown = Math.min(
    pageCount,
    Math.max(opened, visibleCount(pageCount, 0, step)),
  );
  useEffect(() => {
    setShown((n) => Math.min(n, pageCount));
  }, [pageCount]);
  const [drag, setDrag] = useState<Drag | null>(null);
  const dragRef = useRef<Drag | null>(null);
  /** 끄는 중 마지막 포인터 자리(자동 스크롤용). */
  const pointRef = useRef<{ x: number; y: number } | null>(null);
  /** 마지막 pointerdown 의 종류. 마우스면 click 을 무시한다(pointerup 이 처리했다). */
  const pointerTypeRef = useRef<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef(0);
  // 창 이벤트가 최신 값을 보게 한다(끄는 중 props 가 바뀌어도).
  const latest = useRef({ ranges, active, onPaint });
  latest.current = { ranges, active, onPaint };

  const press = useCallback((page: number) => {
    const { ranges: now, active: part, onPaint: paint } = latest.current;
    paint(part, pressRange(now[part], page));
  }, []);

  /** 포인터 자리의 쪽. 칸 밖이면 칸 상자(와 화면) 가장자리로 당긴 자리에서 찾는다(그린워싱 paintAt 과 같은 셈). */
  const pageAt = useCallback((x: number, y: number): number | null => {
    const box = boxRef.current;
    const grid = gridRef.current;
    if (!box || !grid) return null;
    const boxRect = box.getBoundingClientRect();
    const gridRect = grid.getBoundingClientRect();
    const top = Math.max(boxRect.top, 0);
    const bottom = Math.min(boxRect.bottom, window.innerHeight);
    if (bottom <= top) return null;
    const under = document
      .elementFromPoint?.(
        clamp(x, gridRect.left + 1, gridRect.right - 1),
        clamp(y, top + 1, bottom - 1),
      )
      ?.closest<HTMLElement>('[data-page]');
    return under && grid.contains(under) ? pageOf(under) : null;
  }, []);

  const moveTo = useCallback((page: number | null) => {
    const current = dragRef.current;
    if (!current || page === null || page === current.current) return;
    dragRef.current = { ...current, current: page, moved: true };
    setDrag(dragRef.current);
  }, []);

  const stopDrag = useCallback(() => {
    const current = dragRef.current;
    dragRef.current = null;
    pointRef.current = null;
    cancelAnimationFrame(frameRef.current);
    setDrag(null);
    if (!current) return;
    if (current.moved)
      latest.current.onPaint(
        current.part,
        paintRange(current.base, current.anchor, current.current),
      );
    else press(current.anchor);
  }, [press]);

  /** 끄는 동안 프레임마다: 가장자리면 칸 상자(끝이면 페이지)를 스크롤하고 포인터 아래 쪽까지 늘린다. */
  const autoScroll = useCallback(() => {
    const loop = () => {
      const point = pointRef.current;
      const box = boxRef.current;
      if (!dragRef.current || !point || !box) return;
      let moved = false;
      const rect = box.getBoundingClientRect();
      const boxStep = edgeStep(
        point.y,
        Math.max(rect.top, 0),
        Math.min(rect.bottom, window.innerHeight),
      );
      if (boxStep !== 0) {
        const before = box.scrollTop;
        box.scrollTop = before + boxStep;
        moved = box.scrollTop !== before;
      }
      if (!moved) {
        const pageStep = edgeStep(point.y, 0, window.innerHeight);
        if (pageStep !== 0) {
          const before = window.scrollY;
          window.scrollBy(0, pageStep);
          moved = window.scrollY !== before;
        }
      }
      if (moved) moveTo(pageAt(point.x, point.y));
      frameRef.current = requestAnimationFrame(loop);
    };
    cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(loop);
  }, [moveTo, pageAt]);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      if (!dragRef.current) return;
      // 창 밖에서 단추를 놓아 pointerup 을 못 받은 경우
      if (!(event.buttons & 1)) return stopDrag();
      pointRef.current = { x: event.clientX, y: event.clientY };
      // 칸 위면 그 칸, 칸 밖이면 칸 상자 안으로 당긴 자리의 칸
      const target = pageOf(event.target);
      moveTo(
        target !== null && gridRef.current?.contains(event.target as Node) ?
          target
        : pageAt(event.clientX, event.clientY),
      );
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
  }, [moveTo, pageAt, stopDrag]);

  const onPointerDown = (page: number, event: ReactPointerEvent) => {
    pointerTypeRef.current = event.pointerType;
    if (event.pointerType !== 'mouse' || event.button !== 0) return;
    event.preventDefault();
    const { ranges: now, active: part } = latest.current;
    dragRef.current = {
      anchor: page,
      current: page,
      moved: false,
      part,
      base: now[part],
    };
    pointRef.current = { x: event.clientX, y: event.clientY };
    setDrag(dragRef.current);
    autoScroll();
  };

  const onKeyDown = (page: number, event: KeyboardEvent) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    press(page);
  };

  const shownRanges =
    drag ?
      {
        ...ranges,
        [drag.part]: paintRange(drag.base, drag.anchor, drag.current),
      }
    : ranges;
  const pages = Array.from({ length: shown }, (_, i) => i + 1);
  const hidden = hiddenPainted(shownRanges, shown);
  return (
    <div
      data-testid="page-grid"
      data-pdf-state={thumbs?.state}
      className="flex flex-col gap-3 rounded-component border border-solid border-border-tertiary bg-background-secondary p-4"
    >
      <div ref={boxRef} className="max-h-[520px] overflow-auto">
        <div ref={gridRef} className="grid grid-cols-10 gap-4">
          {pages.map((page) => {
            const { parts, overlap } = cellState(page, shownRanges);
            const look =
              overlap ? OVERLAP_LOOK
              : parts.length === 1 ? PART_LOOK[parts[0]!]
              : PLAIN_LOOK;
            return (
              <button
                key={page}
                type="button"
                data-page={page}
                data-parts={parts.join(' ') || undefined}
                data-overlap={overlap || undefined}
                aria-pressed={parts.includes(active)}
                aria-label={words.cellLabel(
                  page,
                  parts.map((part) => names[part]),
                )}
                className="flex min-w-0 cursor-pointer select-none flex-col items-center gap-1 border-0 bg-transparent p-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary"
                onPointerDown={(event) => onPointerDown(page, event)}
                onKeyDown={(event) => onKeyDown(page, event)}
                onClick={() => {
                  // 터치·펜의 톡 누르기. 마우스 누름은 pointerup 이 처리했고, 키보드는 keydown 이 처리했다(click 을 막음).
                  if (
                    pointerTypeRef.current !== null &&
                    pointerTypeRef.current !== 'mouse'
                  )
                    press(page);
                  pointerTypeRef.current = null;
                }}
              >
                {thumbs?.state === 'ready' ?
                  <span
                    aria-hidden
                    data-thumb-frame
                    className={cn(
                      'relative box-border flex aspect-[1/1.414] w-full items-center justify-center overflow-hidden rounded-control',
                      look.frame,
                    )}
                  >
                    <PageCanvas
                      pdf={thumbs.pdf}
                      pageNumber={page}
                      scale={THUMB_SCALE}
                      rotation={0}
                      className="block !h-full !w-full object-contain mix-blend-multiply"
                      errorFallback={
                        <span
                          aria-hidden
                          data-thumb-failed
                          className="absolute inset-0 bg-grey-100"
                        />
                      }
                    />
                  </span>
                : <span
                    aria-hidden
                    className={cn(
                      thumbs === undefined ?
                        'box-border aspect-[3/4] w-full rounded-control'
                      : 'box-border aspect-[1/1.414] w-full rounded-control',
                      look.frame,
                    )}
                  />
                }
                <span
                  aria-hidden
                  className={cn(
                    'inline-flex items-center gap-1 text-style-pre-caption-02',
                    look.number,
                  )}
                >
                  {page}
                  {overlap &&
                    parts.map((part) => (
                      <span
                        key={part}
                        data-part-dot={part}
                        className={cn(
                          'size-1.5 rounded-full',
                          PART_LOOK[part].swatch,
                        )}
                      />
                    ))}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* 400 12(밴드 TRP3 ② N2 — 시안 g-small) */}
        <p
          data-testid="grid-viewing"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          {words.viewing(1, shown)}
          {hidden.length > 0 &&
            ` · ${words.hiddenPainted(
              shown + 1,
              pageCount,
              hidden.map(({ part, range }) =>
                words.hiddenItem(names[part], formatRange(range)),
              ),
            )}`}
        </p>
        {shown < pageCount && (
          <Button
            variant="outlineGrey"
            size="sm"
            onClick={() => setShown(visibleCount(pageCount, shown, step))}
          >
            {words.more(shown + 1, visibleCount(pageCount, shown, step))}
          </Button>
        )}
      </div>
    </div>
  );
}

/**
 * 범례(파트 색 셋 + 겹친 쪽)와 누름 안내 — 쪽 칸 상자 밖, 글자 칸 앞(밴드 TRP2 TE7, 시안 TR-02 .g-legend).
 * 쪽 칸과 같이 그린다(쪽 수를 모르면 둘 다 없음).
 */
export function PageGridLegend() {
  return (
    <div className="flex flex-col gap-3">
      {/* 범례 400 12(밴드 TRP3 ② N2 — 시안 g-legend) */}
      <ul
        data-testid="grid-legend"
        className="m-0 flex list-none flex-wrap gap-4 p-0 text-style-pre-caption-03 text-text-tertiary"
      >
        {PART_KEYS.map((part) => (
          <li key={part} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className={cn('size-3 rounded-sm', PART_LOOK[part].swatch)}
            />
            {names[part]}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn('box-border size-3 rounded-sm', OVERLAP_LOOK.swatch)}
          />
          {words.legendOverlap}
        </li>
      </ul>
      <p
        data-testid="grid-note"
        className="m-0 text-style-pre-caption-03 text-text-quaternary"
      >
        {words.note}
      </p>
    </div>
  );
}
