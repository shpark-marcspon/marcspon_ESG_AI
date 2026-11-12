// 첫 불러오기 판정(밴드 LD1 ①, sid:MARC-ENT-443 ①). 빈/안내 판정(Empty·DV-00·intro)은 이것이 거짓일 때만 한다.
// 마운트 뒤 'loading' 이 아닌 상태를 한 번도 못 봤고 지금 'loading' 이면 참. 한 번 ready·failed 를 본 뒤 다시 loading(거르기·탭 바꿈·다시 시도)이면 거짓.
// 「그리기 중 state 고치기」 꼴이다(shared/lib/useLoad 의 useSameKey 처럼 — 버려지는 그리기가 ref 를 고치지 않게 ref 를 쓰지 않는다).
import { useState } from 'react';

export function useFirstLoad(state: string): boolean {
  const [settled, setSettled] = useState(state !== 'loading');
  if (!settled && state !== 'loading') setSettled(true);
  return !settled && state === 'loading';
}
