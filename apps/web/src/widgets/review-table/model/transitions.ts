// 검토 상태의 전이. 허용 전이표를 자료(TRANSITIONS)로 두고, 조건(checkAction)을 그 옆에 둔다.
//
// ★ 요구 문서에 있는 것: 상태의 이름, 「반영은 최종 확정이 아니다」, 「반려는 사유 필수」,
//   「수정하면 배출량을 재계산하고 원본값과 수정값을 둘 다 남긴다」.
//   전이표 자체는 요구 문서에 없다. 아래 표는 전부 이 부품이 정한 기본값이다.
//   규칙을 바꾸려면 TRANSITIONS 의 줄을 고친다. 테스트(transitions.test.ts)가 표의 모든 칸을 돈다.
import {
  currentCandidate,
  currentEmission,
  isRecalcFailed,
  isRecalcPending,
} from './row.ts';
import type { ReviewRow, ReviewStatus } from './row.ts';

export type ReviewAction =
  | { type: 'accept' } // 반영: AI 제안 그대로(대표 후보). 수정값이 있었으면 버린다
  | { type: 'decline' } // 미반영
  | { type: 'edit'; category?: string; candidateId?: string } // 수정: 카테고리를 고치거나 다른 후보를 고른다
  | { type: 'rerequest' } // 재추천 요청
  | { type: 'reject'; reason: string } // 반려
  | { type: 'finalize' } // 최종 확정
  | { type: 'reopen' } // 검토대기로 되돌린다. 수정값과 반려 사유를 버린다
  | { type: 'unfinalize' }; // 확정 취소. 확정 전의 상태(반영 또는 수정)로 돌아간다

export type ActionType = ReviewAction['type'];

/**
 * 허용 전이표.  TRANSITIONS[지금 상태][동작] = 다음 상태.  칸이 없으면 그 동작은 안 된다.
 *
 * 한 가지 예외: 최종확정 → 확정 취소의 다음 상태는 수정값이 남아 있으면 "edited" 다(applyAction 에서 정한다).
 */
export const TRANSITIONS: Record<
  ReviewStatus,
  Partial<Record<ActionType, ReviewStatus>>
> = {
  pending: {
    accept: 'accepted',
    decline: 'declined',
    edit: 'edited',
    rerequest: 'rerequested',
    reject: 'rejected',
  },
  accepted: {
    decline: 'declined',
    edit: 'edited',
    rerequest: 'rerequested',
    reject: 'rejected',
    finalize: 'finalized',
    reopen: 'pending',
  },
  edited: {
    accept: 'accepted',
    decline: 'declined',
    edit: 'edited',
    rerequest: 'rerequested',
    reject: 'rejected',
    finalize: 'finalized',
    reopen: 'pending',
  },
  declined: {
    accept: 'accepted',
    edit: 'edited',
    rerequest: 'rerequested',
    reject: 'rejected',
    reopen: 'pending',
  },
  // 재추천을 기다리는 동안과 반려된 뒤에는 되돌리기만 된다. 재추천의 결과가 어떻게 돌아오는지는 서버의 일이다.
  rerequested: { reopen: 'pending' },
  rejected: { reopen: 'pending' },
  // 확정한 뒤에는 확정 취소만 된다.
  finalized: { unfinalize: 'accepted' },
};

/** 동작의 이름(단추에 적는 말). 수정은 단추가 아니라 후보·카테고리를 고르는 것으로 일어난다. */
export const ACTION_LABEL: Record<ActionType, string> = {
  accept: '반영',
  decline: '미반영',
  edit: '수정',
  rerequest: '재추천 요청',
  reject: '반려',
  finalize: '최종 확정',
  reopen: '되돌리기',
  unfinalize: '확정 취소',
};

export type ActionError =
  | 'not_allowed' // 전이표에 없는 동작
  | 'no_candidate' // 후보가 없어 반영·확정할 것이 없다
  | 'reason_required' // 사유 없는 반려
  | 'recalc_pending' // 재계산을 기다리는 중
  | 'recalc_failed' // 재계산이 실패했다. 다시 시도해야 한다
  | 'no_emission' // 배출량이 없다(계산해도 값이 나오지 않는다. 계산이 실패한 것은 recalc_failed)
  | 'empty_edit' // 고친 것이 없는 수정
  | 'unknown_candidate'; // 그 행에 없는 후보를 골랐다

export const ACTION_ERROR_MESSAGE: Record<ActionError, string> = {
  not_allowed: '지금 상태에서는 할 수 없는 동작이다.',
  no_candidate: '후보가 없다.',
  reason_required: '반려하려면 사유를 적어야 한다.',
  recalc_pending: '재계산을 기다리는 중이다.',
  recalc_failed: '계산하지 못했다(계산이 실패했다). 다시 계산해야 한다.',
  no_emission: '배출량이 없다(계산해도 값이 나오지 않는다).',
  empty_edit: '고친 것이 없다.',
  unknown_candidate: '이 행에 없는 후보다.',
};

export type ActionResult =
  { ok: true; row: ReviewRow } | { ok: false; error: ActionError };

/** 이 행에 이 동작을 할 수 없는 까닭. 할 수 있으면 null. */
export function checkAction(
  row: ReviewRow,
  action: ReviewAction,
): ActionError | null {
  if (TRANSITIONS[row.status][action.type] === undefined) return 'not_allowed';
  switch (action.type) {
    case 'accept':
      return row.ai.candidates.length === 0 ? 'no_candidate' : null;
    case 'edit':
      if (action.category === undefined && action.candidateId === undefined)
        return 'empty_edit';
      if (
        action.candidateId !== undefined &&
        !row.ai.candidates.some(
          (candidate) => candidate.id === action.candidateId,
        )
      )
        return 'unknown_candidate';
      return null;
    case 'reject':
      return action.reason.trim() === '' ? 'reason_required' : null;
    case 'finalize':
      if (currentCandidate(row) === null) return 'no_candidate';
      if (isRecalcPending(row)) return 'recalc_pending';
      // 「배출량이 없다」보다 먼저 묻는다. 실패한 행은 다시 계산하면 풀릴 수 있어 까닭을 따로 알린다.
      if (isRecalcFailed(row)) return 'recalc_failed';
      if (currentEmission(row) === null) return 'no_emission';
      return null;
    default:
      return null;
  }
}

/** 동작 하나를 행에 적용한다. 행을 고치지 않고 새 행을 돌려준다. */
export function applyAction(
  row: ReviewRow,
  action: ReviewAction,
): ActionResult {
  const error = checkAction(row, action);
  if (error) return { ok: false, error };
  const status = TRANSITIONS[row.status][action.type]!;
  // 반려 사유는 반려 상태에만 붙는다. 다른 상태로 가면 사라진다.
  const { rejectReason: _dropped, ...rest } = row;

  switch (action.type) {
    case 'accept':
      return { ok: true, row: { ...rest, status, edit: null } };
    case 'edit':
      // 원본값(row.ai)은 건드리지 않는다. 앞서 고친 것 위에 이번에 고친 것을 얹고, 재계산을 기다린다.
      return {
        ok: true,
        row: {
          ...rest,
          status,
          edit: {
            ...(row.edit?.category !== undefined ?
              { category: row.edit.category }
            : {}),
            ...(row.edit?.candidateId !== undefined ?
              { candidateId: row.edit.candidateId }
            : {}),
            ...(action.category !== undefined ?
              { category: action.category }
            : {}),
            ...(action.candidateId !== undefined ?
              { candidateId: action.candidateId }
            : {}),
            emission: null,
            recalcPending: true,
          },
        },
      };
    case 'reject':
      return {
        ok: true,
        row: { ...rest, status, rejectReason: action.reason.trim() },
      };
    case 'reopen':
      return { ok: true, row: { ...rest, status, edit: null } };
    case 'unfinalize':
      return {
        ok: true,
        row: { ...rest, status: row.edit ? 'edited' : status },
      };
    case 'decline':
    case 'rerequest':
    case 'finalize':
      return { ok: true, row: { ...rest, status } };
  }
}

/** 재계산이 끝났다. 계산해도 값이 나오지 않았으면 emission 이 null 이다(계산이 실패한 것은 applyRecalcFailed). 수정값이 없는 행은 그대로 돌려준다. */
export function applyRecalculated(
  row: ReviewRow,
  emission: number | null,
): ReviewRow {
  if (!row.edit) return row;
  const { recalcFailed: _cleared, ...edit } = row.edit;
  return { ...row, edit: { ...edit, emission, recalcPending: false } };
}

/**
 * 재계산이 실패했다(계산 함수가 거부했거나 예외를 냈다). 배출량은 비고, 실패했다는 표시가 남는다.
 * 검토 상태는 바뀌지 않는다(전이가 아니다). 수정값이 없는 행은 그대로 돌려준다.
 */
export function applyRecalcFailed(row: ReviewRow): ReviewRow {
  if (!row.edit) return row;
  return {
    ...row,
    edit: {
      ...row.edit,
      emission: null,
      recalcPending: false,
      recalcFailed: true,
    },
  };
}

/**
 * 실패한 재계산을 다시 시도한다: 실패 표시를 지우고 재계산 대기로 돌린다. 계산을 부르는 것은 이 함수 밖의 일이다.
 * 검토 상태는 바뀌지 않는다(전이가 아니라서 TRANSITIONS 에 없다). 실패한 행이 아니면 그대로 돌려준다.
 */
export function retryRecalc(row: ReviewRow): ReviewRow {
  if (!row.edit?.recalcFailed) return row;
  const { recalcFailed: _cleared, ...edit } = row.edit;
  return { ...row, edit: { ...edit, emission: null, recalcPending: true } };
}

/** 전이표가 허용하는 동작의 이름들(조건은 보지 않는다). 화면이 어떤 단추를 보일지 정할 때 쓴다. */
export function allowedActions(status: ReviewStatus): ActionType[] {
  return Object.keys(TRANSITIONS[status]) as ActionType[];
}
