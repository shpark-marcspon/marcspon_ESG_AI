// 검토 상태와 전이 규칙. React 도, 서버도 모르는 순수 함수다.
//
//   검토대기 ──확정──▶ 확정 ──되돌리기──▶ 검토대기
//      │
//      └──반려(사유 필수)──▶ 반려 ──되돌리기──▶ 검토대기
//
// 확정에서 곧바로 반려로(또는 그 반대로) 가지 못한다. 검토대기로 되돌린 뒤 다시 정한다.

export type ReviewState =
  | { status: 'pending' }
  | { status: 'confirmed' }
  | { status: 'rejected'; reason: string };

export type ReviewAction =
  { type: 'confirm' } | { type: 'reject'; reason: string } | { type: 'reopen' };

export type TransitionResult =
  { ok: true; state: ReviewState } | { ok: false; error: TransitionError };

export type TransitionError =
  'reason_required' | 'not_pending' | 'already_pending';

export const STATUS_LABEL: Record<ReviewState['status'], string> = {
  pending: '검토대기',
  confirmed: '확정',
  rejected: '반려',
};

export const ERROR_MESSAGE: Record<TransitionError, string> = {
  reason_required: '반려하려면 사유를 적어야 한다.',
  not_pending:
    '검토대기 상태에서만 확정하거나 반려할 수 있다. 먼저 검토대기로 되돌린다.',
  already_pending: '이미 검토대기 상태다.',
};

export function transition(
  state: ReviewState,
  action: ReviewAction,
): TransitionResult {
  switch (action.type) {
    case 'confirm':
      if (state.status !== 'pending')
        return { ok: false, error: 'not_pending' };
      return { ok: true, state: { status: 'confirmed' } };

    case 'reject': {
      if (state.status !== 'pending')
        return { ok: false, error: 'not_pending' };
      const reason = action.reason.trim();
      if (reason === '') return { ok: false, error: 'reason_required' };
      return { ok: true, state: { status: 'rejected', reason } };
    }

    case 'reopen':
      if (state.status === 'pending')
        return { ok: false, error: 'already_pending' };
      return { ok: true, state: { status: 'pending' } };
  }
}
