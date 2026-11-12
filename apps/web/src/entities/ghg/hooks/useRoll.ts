// 온실가스 제목 숫자 굴림 훅(밴드 DB4 — sid:MARC-TICK-543 · 발주서 §2-③ + 감독 판단 3·4). 모양을 모른다(글자만 돌려줌).
//   - 붙을 때(마운트) 한 번만 0 에서 끝 글자로 굴린다. 그 뒤 끝 글자가 바뀌면(같은 해 다시 읽기·고침) 굴리지 않고 바로 끝 글자.
//     「해를 바꾸면 다시」는 쓰는 쪽이 key={year} 로 다시 붙여서 한다(DB3 값 문서 ③).
//   - 움직임을 줄인 사용자·matchMedia 가 없는 곳(jsdom 시험)·꺼 둔 자리(enabled false — 덮개 뒤 판, 접었다 편 카드)는 처음부터 끝 글자.
//     판정은 CSS 의 움직임 클래스와 같은 조건 `(prefers-reduced-motion: no-preference)` 이다.
//   - rAF 는 언마운트·끝 글자 바뀜에 취소한다. 시작 시각은 첫 프레임 시각(공용 useCountUp 과 같은 까닭).
//   돌려주는 값: 굴리는 중이면 그 프레임 글자, 아니면 null(쓰는 쪽은 끝 글자를 지금 그대로 그린다).
import { useEffect, useRef, useState } from 'react';

import { rollFrame, rollPlanOf, rollTiming } from '../model/index.ts';

/** 움직여도 되는가(CSS 의 gw-m-* 와 같은 조건). matchMedia 가 없으면 아니다. */
export function rollMoves(): boolean {
  if (typeof matchMedia !== 'function') return false;
  return matchMedia('(prefers-reduced-motion: no-preference)').matches;
}

/**
 * 끝 글자 text 를 delay(ms) 뒤부터 굴린다. 굴리는 중이면 프레임 글자, 아니면 null.
 * enabled 는 붙을 때의 값만 본다(굴림 여부는 첫 그림에서 정해진다).
 */
export function useRoll(
  text: string,
  { delay, enabled = true }: { delay: number; enabled?: boolean },
): string | null {
  // 붙을 때의 끝 글자 — 이것만 굴린다(뒤에 바뀐 글자는 바로).
  const first = useRef(text);
  const [frame, setFrame] = useState<string | null>(() => {
    const plan = enabled && rollMoves() ? rollPlanOf(text) : null;
    return plan ? rollFrame(plan, 0) : null;
  });
  const rolling = useRef(frame !== null);
  useEffect(() => {
    if (!rolling.current) return;
    if (text !== first.current) {
      rolling.current = false;
      setFrame(null);
      return;
    }
    const plan = rollPlanOf(text);
    if (!plan) return;
    const { delay: wait, duration } = rollTiming(delay);
    let id = 0;
    let start: number | null = null;
    const tick = (now: number) => {
      start ??= now;
      const spent = now - start - wait;
      const progress =
        spent <= 0 ? 0
        : duration <= 0 ? 1
        : spent / duration;
      if (progress >= 1) {
        rolling.current = false;
        setFrame(null);
        return;
      }
      setFrame(rollFrame(plan, progress));
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
    // delay 는 붙을 때 값으로 충분하다(자리마다 고정).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);
  return frame;
}
