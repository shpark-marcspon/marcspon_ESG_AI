// 표 위 가로 막대(밴드 W12-1c ② #12, 감독 처분 Q5 — 판 S12-03 `.f12b-sbar`): 12 높이 회색 바탕 + 주황 커서.
//   표 스크롤 칸의 scrollLeft 와 맞물린다(스크롤 → 커서 이동 · 커서 끌기 → 스크롤). 막대는 aria-hidden — 키보드·휠은 표가 그대로 받는다.
//   표 자체 막대는 숨기지 않는다.
import { useEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, RefObject } from 'react';

export interface ScrollBarProps {
  target: RefObject<HTMLElement | null>;
  testId?: string;
}

interface Thumb {
  left: number;
  width: number;
}

/** 커서 자리(px) — 막대 폭 track, 보이는 비율만큼 폭, 스크롤 비율만큼 왼쪽. 넘침 없으면 꽉. */
export function thumbOf(
  track: number,
  client: number,
  scroll: number,
  left: number,
): Thumb {
  if (track <= 0 || scroll <= client) return { left: 0, width: track };
  const width = Math.max(24, (client / scroll) * track);
  const room = track - width;
  return { left: (left / (scroll - client)) * room, width };
}

export function ScrollBar({ target, testId }: ScrollBarProps) {
  const track = useRef<HTMLDivElement>(null);
  const [thumb, setThumb] = useState<Thumb>({ left: 0, width: 0 });
  const drag = useRef<{ x: number; start: number } | null>(null);

  useEffect(() => {
    const box = target.current;
    if (!box) return;
    const measure = () =>
      setThumb(
        thumbOf(
          track.current?.clientWidth ?? 0,
          box.clientWidth,
          box.scrollWidth,
          box.scrollLeft,
        ),
      );
    measure();
    box.addEventListener('scroll', measure, { passive: true });
    const watch =
      typeof ResizeObserver === 'undefined' ? null : (
        new ResizeObserver(measure)
      );
    watch?.observe(box);
    if (box.firstElementChild) watch?.observe(box.firstElementChild);
    return () => {
      box.removeEventListener('scroll', measure);
      watch?.disconnect();
    };
  }, [target]);

  const move = (event: ReactPointerEvent<HTMLSpanElement>) => {
    const box = target.current;
    const width = track.current?.clientWidth ?? 0;
    if (!drag.current || !box) return;
    const room = width - thumb.width;
    if (room <= 0) return;
    const ratio = (event.clientX - drag.current.x) / room;
    box.scrollLeft =
      drag.current.start + ratio * (box.scrollWidth - box.clientWidth);
  };

  return (
    <div
      ref={track}
      aria-hidden
      data-testid={testId}
      className="relative box-border h-3 shrink-0 bg-background-quaternary"
    >
      <span
        data-testid={testId ? `${testId}-cursor` : undefined}
        className="absolute top-[3px] h-1.5 cursor-grab touch-none rounded-[10px] bg-text-brand"
        style={{ left: thumb.left, width: thumb.width }}
        onPointerDown={(event) => {
          drag.current = {
            x: event.clientX,
            start: target.current?.scrollLeft ?? 0,
          };
          event.currentTarget.setPointerCapture?.(event.pointerId);
        }}
        onPointerMove={move}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
      />
    </div>
  );
}
