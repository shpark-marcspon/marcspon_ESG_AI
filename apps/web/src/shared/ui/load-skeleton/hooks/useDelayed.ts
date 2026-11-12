// 늦춘 참(밴드 LE1 ①, sid:MARC-ENT-260 ①). on 이 ms 동안 이어서 참이어야 참을 낸다. on 이 거짓이 되면 바로 거짓.
// 불러오기가 300ms 안에 끝나면 스켈레톤을 한 번도 그리지 않게 한다(깜빡임 막기 — 300 은 흔한 값, 측정 아님).
// 다시 참이 되면(다시 시도) 처음부터 ms 를 다시 센다.
import { useEffect, useState } from 'react';

/** 스켈레톤을 보이기 전에 기다리는 시간(ms). */
export const LOAD_DELAY_MS = 300;

export function useDelayed(on: boolean, ms: number = LOAD_DELAY_MS): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!on) {
      setShown(false);
      return;
    }
    const timer = setTimeout(() => setShown(true), ms);
    return () => clearTimeout(timer);
  }, [on, ms]);
  return on && shown;
}
