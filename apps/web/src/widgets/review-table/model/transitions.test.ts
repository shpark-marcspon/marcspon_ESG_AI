import { describe, expect, it } from 'vitest';

import {
  STATUSES,
  currentCandidate,
  currentCategory,
  currentEmission,
} from './row.ts';
import type { ReviewRow, ReviewStatus } from './row.ts';
import { candidate, makeRow } from './testing.ts';
import {
  TRANSITIONS,
  allowedActions,
  applyAction,
  applyRecalculated,
  checkAction,
} from './transitions.ts';
import type { ActionType, ReviewAction } from './transitions.ts';

const ACTIONS: ActionType[] = [
  'accept',
  'decline',
  'edit',
  'rerequest',
  'reject',
  'finalize',
  'reopen',
  'unfinalize',
];

/** 조건(후보, 사유, 재계산)에 걸리지 않는 동작. 전이표만 보려고 쓴다. */
function validAction(type: ActionType): ReviewAction {
  if (type === 'edit') return { type, candidateId: 'b' };
  if (type === 'reject') return { type, reason: '사유' };
  return { type };
}

/** 그 상태에 있을 법한 행. 조건에 걸리지 않게 후보와 배출량을 갖춘다. */
function rowIn(status: ReviewStatus): ReviewRow {
  if (status === 'edited')
    return makeRow({
      status,
      edit: { candidateId: 'b', emission: 250, recalcPending: false },
    });
  if (status === 'rejected') return makeRow({ status, rejectReason: '사유' });
  return makeRow({ status });
}

// 이 표가 전이표의 기대값이다. TRANSITIONS 를 고치면 여기도 같이 고쳐야 한다(일부러 따로 적었다).
const EXPECTED: Record<
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
  rerequested: { reopen: 'pending' },
  rejected: { reopen: 'pending' },
  finalized: { unfinalize: 'accepted' },
};

describe('전이표: 일곱 상태 × 여덟 동작의 모든 칸', () => {
  for (const status of STATUSES) {
    for (const type of ACTIONS) {
      const to = EXPECTED[status][type];
      it(`${status} + ${type} → ${to ?? '거부'}`, () => {
        const result = applyAction(rowIn(status), validAction(type));
        if (to === undefined) {
          expect(result).toEqual({ ok: false, error: 'not_allowed' });
        } else {
          // 최종확정을 취소하면 수정값이 있던 행은 수정으로 돌아간다(아래에서 따로 본다). rowIn("finalized") 는 수정값이 없다.
          expect(result.ok && result.row.status).toBe(to);
        }
      });
    }
  }

  it('TRANSITIONS 가 기대값과 같다(칸이 더 있거나 빠지지 않았다)', () => {
    expect(TRANSITIONS).toEqual(EXPECTED);
  });

  it('allowedActions 는 전이표의 그 줄이다', () => {
    expect(allowedActions('rejected')).toEqual(['reopen']);
    expect(allowedActions('finalized')).toEqual(['unfinalize']);
  });
});

describe('조건', () => {
  it('사유 없는 반려는 거부한다(빈칸뿐인 것도)', () => {
    expect(applyAction(makeRow(), { type: 'reject', reason: '' })).toEqual({
      ok: false,
      error: 'reason_required',
    });
    expect(applyAction(makeRow(), { type: 'reject', reason: '   ' })).toEqual({
      ok: false,
      error: 'reason_required',
    });
    const done = applyAction(makeRow(), {
      type: 'reject',
      reason: ' 계수가 맞지 않는다 ',
    });
    expect(done.ok && done.row).toMatchObject({
      status: 'rejected',
      rejectReason: '계수가 맞지 않는다',
    });
  });

  it('후보가 0개인 행: 반영도 최종 확정도 안 되고, 미반영·반려·재추천 요청·카테고리 수정은 된다', () => {
    const row = makeRow({ candidates: [] });
    expect(currentCandidate(row)).toBeNull();
    expect(currentEmission(row)).toBeNull();
    expect(checkAction(row, { type: 'accept' })).toBe('no_candidate');
    expect(checkAction(row, { type: 'decline' })).toBeNull();
    expect(checkAction(row, { type: 'rerequest' })).toBeNull();
    expect(
      checkAction(row, { type: 'reject', reason: '후보 없음' }),
    ).toBeNull();
    const edited = applyAction(row, { type: 'edit', category: '나' });
    expect(
      edited.ok &&
        checkAction(applyRecalculated(edited.row, null), { type: 'finalize' }),
    ).toBe('no_candidate');
  });

  it('수정은 고친 것이 있어야 하고, 그 행에 있는 후보만 고를 수 있다', () => {
    expect(checkAction(makeRow(), { type: 'edit' })).toBe('empty_edit');
    expect(
      checkAction(makeRow(), { type: 'edit', candidateId: '없는 후보' }),
    ).toBe('unknown_candidate');
  });

  it('배출량이 없으면(대표 후보의 배출량이 비어 있으면) 최종 확정이 안 된다', () => {
    const row = makeRow({
      status: 'accepted',
      candidates: [candidate('a', null)],
    });
    expect(checkAction(row, { type: 'finalize' })).toBe('no_emission');
  });
});

describe('수정: 원본값과 수정값을 따로 둔다', () => {
  const original = makeRow();
  const edited = applyAction(original, {
    type: 'edit',
    candidateId: 'b',
    category: '나',
  });
  if (!edited.ok) throw new Error('수정이 거부됐다');

  it('원본값(ai)이 그대로 남는다', () => {
    expect(edited.row.ai).toEqual(original.ai);
    expect(edited.row.ai.category).toBe('가');
    expect(edited.row.ai.candidates[0]!.id).toBe('a');
    // 받은 행 객체도 고치지 않는다.
    expect(original).toEqual(makeRow());
  });

  it('지금 값은 수정값이다', () => {
    expect(edited.row.status).toBe('edited');
    expect(currentCategory(edited.row)).toBe('나');
    expect(currentCandidate(edited.row)!.id).toBe('b');
  });

  it('수정하면 재계산 대기가 되고, 그동안 배출량이 없고 최종 확정이 안 된다', () => {
    expect(edited.row.edit).toMatchObject({
      recalcPending: true,
      emission: null,
    });
    expect(currentEmission(edited.row)).toBeNull();
    expect(applyAction(edited.row, { type: 'finalize' })).toEqual({
      ok: false,
      error: 'recalc_pending',
    });
  });

  it('재계산이 끝나면 그 값이 지금 배출량이 되고 최종 확정이 된다', () => {
    const recalculated = applyRecalculated(edited.row, 250);
    expect(recalculated.edit).toMatchObject({
      recalcPending: false,
      emission: 250,
    });
    expect(currentEmission(recalculated)).toBe(250);
    expect(recalculated.ai.candidates[0]!.emission).toBe(100);
    const finalized = applyAction(recalculated, { type: 'finalize' });
    expect(finalized.ok && finalized.row.status).toBe('finalized');
  });

  it('재계산의 답이 「배출량 없음」(null)이면 최종 확정이 안 된다', () => {
    expect(
      checkAction(applyRecalculated(edited.row, null), { type: 'finalize' }),
    ).toBe('no_emission');
  });

  it('두 번 고치면 앞의 수정 위에 얹힌다', () => {
    const first = applyAction(makeRow(), { type: 'edit', category: '나' });
    const second =
      first.ok && applyAction(first.row, { type: 'edit', candidateId: 'b' });
    expect(second && second.ok && second.row.edit).toMatchObject({
      category: '나',
      candidateId: 'b',
      recalcPending: true,
    });
  });

  it('수정한 행을 반영하면 수정값을 버리고 AI 제안으로 돌아간다. 되돌리기도 수정값을 버린다', () => {
    for (const type of ['accept', 'reopen'] as const) {
      const result = applyAction(applyRecalculated(edited.row, 250), { type });
      expect(result.ok && result.row.edit).toBeNull();
      expect(result.ok && currentEmission(result.row)).toBe(100);
    }
  });

  it('수정한 행을 확정했다가 취소하면 수정 상태로 돌아가고 수정값이 남는다', () => {
    const finalized = applyAction(applyRecalculated(edited.row, 250), {
      type: 'finalize',
    });
    const back =
      finalized.ok && applyAction(finalized.row, { type: 'unfinalize' });
    expect(back && back.ok && back.row).toMatchObject({
      status: 'edited',
      edit: { candidateId: 'b', emission: 250 },
    });
  });

  it('반려를 되돌리면 사유가 사라진다', () => {
    const rejected = applyAction(makeRow(), { type: 'reject', reason: '사유' });
    const back = rejected.ok && applyAction(rejected.row, { type: 'reopen' });
    expect(back && back.ok && 'rejectReason' in back.row).toBe(false);
  });
});
