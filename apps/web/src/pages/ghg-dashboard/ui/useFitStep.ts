// 넘치면 한 단계씩 내리는 단(밴드 DB2 감독 판단 14 범례 · 밴드 DB3 넘김 e6 정함 3 배출원별 줄 — 같은 꼴을 한 훅으로).
//   - 잴 줄 하나라도 그려진 scrollWidth > clientWidth 면 다 같이 한 단계 내림(마지막 단까지).
//   - 넘김 R3(밴드 DB3): 자리(부모 칸) 폭이 바뀌면 0 부터 다시 — 줄·목록 폭은 내용 폭이라 단이 내려간 뒤 바뀌지 않는다.
//     자리 폭은 단과 무관하게 바깥 배치가 정한다(범례 = 404 고정 칸 안 줄 · 배출원별 = flex-1 판 안 칸) → 단을 바꿔도 다시 불리지 않아 되풀이 없음.
//     높이만 바뀌는 것(단 2 의 두 줄)은 무시한다.
//   - 글 폭이 바뀌면(웹 글꼴이 늦게 옴) 다시 잰다.
//   - key(그리는 값)가 바뀌면 0 부터 다시.
import { useLayoutEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';

export interface FitStepParts {
  /** 잴 줄들. */
  rows(root: HTMLElement): HTMLElement[];
  /** 글 폭이 바뀌면 다시 잴 요소들. */
  ink(root: HTMLElement): Element[];
  /** 폭이 바뀌면 0 부터 다시 재는 자리. */
  place(root: HTMLElement): HTMLElement | null;
}

export function useFitStep(
  rootRef: RefObject<HTMLElement>,
  steps: number,
  key: string,
  parts: FitStepParts,
): number {
  const [step, setStep] = useState(0);
  const [seen, setSeen] = useState(key);
  if (seen !== key) {
    setSeen(key);
    setStep(0);
  }
  const stepRef = useRef(step);
  stepRef.current = step;
  const partsRef = useRef(parts);
  partsRef.current = parts;
  const measure = useRef(() => {
    const root = rootRef.current;
    if (!root) return;
    const over = partsRef.current
      .rows(root)
      .some((row) => row.scrollWidth > row.clientWidth + 0.5);
    if (over && stepRef.current < steps - 1) setStep(stepRef.current + 1);
  }).current;
  useLayoutEffect(measure, [step, key, measure]);
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (typeof ResizeObserver === 'undefined' || !root) return;
    const place = partsRef.current.place(root);
    let width: number | null = null;
    const box = new ResizeObserver(() => {
      const now = place?.clientWidth ?? null;
      const changed = width !== null && now !== width;
      width = now;
      if (!changed) return;
      if (stepRef.current === 0) measure();
      else setStep(0);
    });
    if (place) box.observe(place);
    const ink = new ResizeObserver(measure);
    partsRef.current.ink(root).forEach((node) => ink.observe(node));
    let live = true;
    void document.fonts?.ready.then(() => live && measure());
    return () => {
      live = false;
      box.disconnect();
      ink.disconnect();
    };
  }, [rootRef, key, measure]);
  return step;
}
