// 수가 바뀔 때 앞 값에서 굴러 올라가는 숫자(밴드 GA1 — 시연 다듬기). 그리는 글자만 굴린다:
//   - 움직임을 줄인 사용자·matchMedia 가 없는 곳(jsdom 시험)은 처음부터 끝 값을 그린다 — 단위 시험의 글자 단언이 그대로다.
//   - 처음 나타날 때는 0 에서, 그 뒤 바뀌면 보이던 값에서 굴린다. 길이는 durationMs(기본 700).
// 값의 뜻(aria-valuenow 등)은 쓰는 쪽이 끝 값으로 따로 단다.
import { useEffect, useRef, useState } from 'react';

import './motion.css';

function moves(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function')
    return false;
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** 0 에서(또는 앞 값에서) value 로 굴러가는 수. 움직임이 없으면 value 그대로. */
export function useCountUp(
  value: number,
  durationMs = 700,
  { from = 0 }: { from?: number } = {},
): number {
  const [shown, setShown] = useState(() => (moves() ? from : value));
  const shownRef = useRef(shown);
  useEffect(() => {
    if (!moves()) {
      shownRef.current = value;
      setShown(value);
      return;
    }
    const from = shownRef.current;
    if (from === value) return;
    let frame = 0;
    // 시작 시각은 첫 프레임의 시각으로 잡는다 — performance.now() 와 섞으면 rAF 시각이 앞서 t 가 0 아래로 내려가 수가 튄다
    let start: number | null = null;
    const tick = (now: number) => {
      start ??= now;
      const t = Math.min(1, (now - start) / durationMs);
      // easeOutCubic
      const next = Math.round(from + (value - from) * (1 - (1 - t) ** 3));
      shownRef.current = next;
      setShown(next);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, durationMs]);
  return shown;
}

export function CountUp({
  value,
  durationMs,
}: {
  value: number;
  durationMs?: number;
}) {
  return <>{useCountUp(value, durationMs)}</>;
}
