// 골라진 항목의 검토 조작: 적고 있는 반려 사유와, 거부된 까닭.
// 조작을 실제로 돌리는 것은 밖에서 받은 onAction 이다(보통 useReviews 의 apply). 이 훅은 그 결과를 보고 입력을 비우거나 오류를 든다.
import { useState } from 'react';

import type {
  ReviewAction,
  TransitionError,
  TransitionResult,
} from '../model/index.ts';

export interface ReviewDraft {
  reason: string;
  setReason(reason: string): void;
  /** 마지막 조작이 거부된 까닭. 받아들여졌으면 null. 글로 바꾸는 표는 domain 의 ERROR_MESSAGE. */
  error: TransitionError | null;
  confirm(): void;
  /** 적어 둔 사유로 반려한다. */
  reject(): void;
  reopen(): void;
}

export function useReviewDraft(
  onAction: (action: ReviewAction) => TransitionResult,
): ReviewDraft {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<TransitionError | null>(null);

  function run(action: ReviewAction) {
    const result = onAction(action);
    setError(result.ok ? null : result.error);
    if (result.ok) setReason('');
  }

  return {
    reason,
    setReason,
    error,
    confirm: () => run({ type: 'confirm' }),
    reject: () => run({ type: 'reject', reason }),
    reopen: () => run({ type: 'reopen' }),
  };
}
