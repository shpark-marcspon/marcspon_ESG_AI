// [다시 시도] 뒤 초점(밴드 LA1 ①, sid:MARC-ISSUE-131 2). 누르면 상자가 내려가 초점이 body 로 떨어지는 것을 막는다.
//   - arm(fn): 표식을 세우고 fn 을 부르는 누름 처리기를 낸다(쓰는 쪽이 [다시 시도]의 onClick 에 단다).
//   - phase 가 바뀐 뒤(effect): 표식이 서 있으면 failed 는 actionRef(새 [다시 시도]), ready 는 doneRef(제목 줄 등)로 초점을 옮기고 표식을 내린다.
//     loading 에서는 아무것도 하지 않는다(표식은 그대로 서 있다).
//   - 첫 진입에서는 옮기지 않는다(표식은 처음 내려 있다). 한 번 옮긴 뒤에는 다시 누를 때까지 옮기지 않는다.
// 마운트 때 초점을 주는 콜백 ref 꼴은 쓰지 않는다: 다시 읽는 동안 먼저 마운트되는 칸(GW-02 고르기)이나
//   실패→로딩→ready 내내 같은 마디인 제목(GW-04 h2)은 다시 붙지 않는다.
// doneRef 의 마디는 초점을 받을 수 있어야 한다(제목이면 tabIndex -1).
import { useCallback, useEffect, useRef } from 'react';
import type { RefObject } from 'react';

export type RetryPhase = 'loading' | 'failed' | 'ready';

export interface RetryFocus<D extends HTMLElement> {
  /** 표식을 세우고 fn 을 부르는 누름 처리기. */
  arm(fn: () => void): () => void;
  /** 실패면 초점을 받을 [다시 시도]. */
  actionRef: RefObject<HTMLButtonElement>;
  /** 성공이면 초점을 받을 마디. */
  doneRef: RefObject<D>;
}

export function useRetryFocus<D extends HTMLElement = HTMLElement>(
  phase: RetryPhase,
): RetryFocus<D> {
  const armed = useRef(false);
  const actionRef = useRef<HTMLButtonElement>(null);
  const doneRef = useRef<D>(null);

  useEffect(() => {
    if (!armed.current || phase === 'loading') return;
    (phase === 'failed' ? actionRef : doneRef).current?.focus();
    armed.current = false;
  }, [phase]);

  const arm = useCallback(
    (fn: () => void) => () => {
      armed.current = true;
      fn();
    },
    [],
  );

  return { arm, actionRef, doneRef };
}
