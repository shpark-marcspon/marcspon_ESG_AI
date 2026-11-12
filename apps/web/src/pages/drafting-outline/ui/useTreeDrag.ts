// RP-03 트리 끌어 옮기기의 손(밴드 RPW7 §1-D). 라이브러리 없이 포인터 이벤트로 — pages/greenwash-new/ui/PageThumbnails.tsx 꼴(HTML5 draggable 을 쓰지 않는다).
// 끄는 동안은 상태만 바꾸고 목록은 놓을 때 한 번 바뀐다(onDrop). 셈은 model/drop.ts. 터치·펜은 끌지 않는다(줄 아이콘 탭으로 옮긴다).
import { useCallback, useEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, RefObject } from 'react';

import type { OutlineNode } from '../../../entities/drafting/model/index.ts';
import { dropOf, gapAt, lineAt, subtreeEnd, wantOf } from '../model/index.ts';
import type { Drop } from '../model/index.ts';

/** 이만큼 움직이면 끌기 시작(그 전에 놓으면 클릭 = 고르기). */
const START_PX = 4;
// EDGE·MAX_STEP·edgeStep 은 pages/greenwash-new/ui/PageThumbnails.tsx 에서 옮겨 적음(같은 층 다른 슬라이스 import 금지 — app/guards/layers.test.ts).
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

/** 끄는 중인 모습. */
export interface TreeDragView extends Drop {
  /** 끌리는 줄 자리. */
  index: number;
  /** 묶음 끝(그 전까지 흐리게). */
  end: number;
  /** 선이 그 줄 바로 앞에 서는 목록 자리(nodes.length = 끝). */
  line: number;
  /** 포인터. */
  x: number;
  y: number;
  /** 선의 화면 y(목록 안으로 자름) · 목록 오른쪽 끝 — 빨간 툴팁 자리. */
  lineY: number;
  listRight: number;
}

interface Press {
  index: number;
  startX: number;
  startY: number;
  x: number;
  y: number;
  started: boolean;
}

export function useTreeDrag({
  listRef,
  nodes,
  disabled,
  onPick,
  onDrop,
  onEnd,
}: {
  listRef: RefObject<HTMLElement>;
  nodes: readonly OutlineNode[];
  disabled: boolean;
  /** 끌기가 시작될 때 그 줄을 고른다. */
  onPick(index: number): void;
  /** `ok` 인 자리에 놓았을 때만. */
  onDrop(index: number, drop: Drop): void;
  /** 끌기가 끝났을 때(놓음·취소 모두 — 초점을 줄로 돌린다). */
  onEnd(): void;
}) {
  const [view, setView] = useState<TreeDragView | null>(null);
  const press = useRef<Press | null>(null);
  const last = useRef<TreeDragView | null>(null);
  const frame = useRef(0);
  const latest = useRef({ nodes, onPick, onDrop, onEnd });
  latest.current = { nodes, onPick, onDrop, onEnd };

  /** 지금 포인터로 틈·단계를 다시 잰다. */
  const measure = useCallback(() => {
    const now = press.current;
    const list = listRef.current;
    if (!now?.started || !list) return;
    const { nodes: all } = latest.current;
    const end = subtreeEnd(all, now.index);
    const rows = [...list.querySelectorAll('[role="option"]')];
    const mids = rows
      .filter((_, at) => at < now.index || at >= end)
      .map((row) => {
        const rect = row.getBoundingClientRect();
        return (rect.top + rect.bottom) / 2;
      });
    const drop = dropOf(
      all,
      now.index,
      gapAt(mids, now.y),
      wantOf(all[now.index]!.depth, now.x - now.startX),
    );
    const line = lineAt(all, now.index, drop.gap);
    const box = list.getBoundingClientRect();
    const raw =
      rows[line]?.getBoundingClientRect().top ??
      rows[rows.length - 1]?.getBoundingClientRect().bottom ??
      box.top;
    const next: TreeDragView = {
      ...drop,
      index: now.index,
      end,
      line,
      x: now.x,
      y: now.y,
      lineY: Math.min(Math.max(raw, box.top), box.bottom),
      listRight: box.right,
    };
    last.current = next;
    setView(next);
  }, [listRef]);

  const stop = useCallback(() => {
    const wasDragging = press.current?.started ?? false;
    press.current = null;
    last.current = null;
    cancelAnimationFrame(frame.current);
    setView(null);
    if (wasDragging) latest.current.onEnd();
  }, []);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const now = press.current;
      if (!now) return;
      // 창 밖에서 단추를 놓아 pointerup 을 못 받은 경우 — 취소.
      if (!(event.buttons & 1)) return stop();
      now.x = event.clientX;
      now.y = event.clientY;
      if (!now.started) {
        if (Math.hypot(now.x - now.startX, now.y - now.startY) < START_PX)
          return;
        now.started = true;
        latest.current.onPick(now.index);
        // 프레임마다: 목록 가장자리면 목록을, 목록이 끝이면 창을 굴리고 틈을 다시 잰다.
        const loop = () => {
          const drag = press.current;
          const list = listRef.current;
          if (!drag || !list) return;
          let moved = false;
          const rect = list.getBoundingClientRect();
          const boxStep = edgeStep(
            drag.y,
            Math.max(rect.top, 0),
            Math.min(rect.bottom, window.innerHeight),
          );
          if (boxStep !== 0) {
            const before = list.scrollTop;
            list.scrollTop = before + boxStep;
            moved = list.scrollTop !== before;
          }
          if (!moved) {
            const pageStep = edgeStep(drag.y, 0, window.innerHeight);
            if (pageStep !== 0) {
              const before = window.scrollY;
              window.scrollBy(0, pageStep);
              moved = window.scrollY !== before;
            }
          }
          if (moved) measure();
          frame.current = requestAnimationFrame(loop);
        };
        frame.current = requestAnimationFrame(loop);
      }
      measure();
    };
    const onUp = () => {
      const now = press.current;
      const shown = last.current;
      stop();
      if (now?.started && shown?.verdict === 'ok')
        latest.current.onDrop(now.index, shown);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', stop);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', stop);
      cancelAnimationFrame(frame.current);
    };
  }, [listRef, measure, stop]);

  // 잡은 동안 목록이 바뀌면(편집 칸 단추를 키보드로 누름 등) 잡은 자리 번호가 어긋나니 취소.
  useEffect(() => {
    if (press.current) stop();
  }, [nodes, stop]);

  // 끄는 중 저장·시작이 돌면(busy) 취소.
  useEffect(() => {
    if (disabled && press.current) stop();
  }, [disabled, stop]);

  // 끄는 동안 창 어디서나 움켜쥔 커서 · 글 고름 없음.
  const active = view !== null;
  useEffect(() => {
    if (!active) return;
    const { cursor, userSelect } = document.body.style;
    document.body.style.cursor = 'grabbing';
    document.body.style.userSelect = 'none';
    return () => {
      document.body.style.cursor = cursor;
      document.body.style.userSelect = userSelect;
    };
  }, [active]);

  /** 손잡이 pointerdown — 마우스 왼쪽 단추만. */
  const onGripDown = useCallback(
    (event: ReactPointerEvent, index: number) => {
      if (disabled || event.pointerType !== 'mouse' || event.button !== 0)
        return;
      event.preventDefault();
      press.current = {
        index,
        startX: event.clientX,
        startY: event.clientY,
        x: event.clientX,
        y: event.clientY,
        started: false,
      };
    },
    [disabled],
  );

  /** 손잡이를 잡고 있는가(끌기 시작 전 4px 안 포함). */
  const held = useCallback(() => press.current !== null, []);

  return { view, onGripDown, held };
}
