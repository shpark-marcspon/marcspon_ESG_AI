// 항목별 검토 상태를 화면 안에만 들고 있는다. 새로 고치면 사라진다.
//
// ★ 서버를 붙일 자리는 apply 하나다. 지금은 전이 규칙(review.ts)을 돌려 state 만 바꾼다.
//   서버가 생기면: 여기서 요청을 보내고, 성공하면 state 를 바꾸고, 실패하면 오류를 돌려준다.
//   전이 규칙은 서버도 같은 것을 검사해야 한다(화면의 검사는 빠른 안내일 뿐이다).
//   누가·언제·왜 바꿨는지의 기록(이력)은 여기 없다. 반려 사유는 지금 상태에만 들어 있고, 되돌리면 사라진다.
import { useCallback, useState } from 'react';

import { transition } from '../model/index.ts';
import type {
  Item,
  ReviewAction,
  ReviewState,
  TransitionResult,
} from '../model/index.ts';

export interface Reviews {
  states: ReadonlyMap<string, ReviewState>;
  apply(itemId: string, action: ReviewAction): TransitionResult;
}

export function useReviews(items: readonly Item[]): Reviews {
  const [states, setStates] = useState<ReadonlyMap<string, ReviewState>>(
    () => new Map(items.map((item) => [item.id, item.review])),
  );

  const apply = useCallback(
    (itemId: string, action: ReviewAction): TransitionResult => {
      const from = states.get(itemId) ?? { status: 'pending' };
      const result = transition(from, action);
      if (result.ok) {
        setStates((previous) => new Map(previous).set(itemId, result.state));
      }
      return result;
    },
    [states],
  );

  return { states, apply };
}
