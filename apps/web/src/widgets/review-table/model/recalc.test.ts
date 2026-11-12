// 계산 실패. 「계산하지 못했다」(계산 함수가 거부하거나 예외를 냈다)는 「배출량이 없다」(계산해 보니 값이 없다)와 다른 상태다.
import { describe, expect, it } from 'vitest';

import { applyBulk, describeSkip } from './bulk.ts';
import { parseTableInput } from './input.ts';
import { currentEmission, isRecalcFailed, isRecalcPending } from './row.ts';
import { summarize } from './summary.ts';
import { candidate, makeRow } from './testing.ts';
import {
  ACTION_ERROR_MESSAGE,
  TRANSITIONS,
  applyAction,
  applyRecalcFailed,
  applyRecalculated,
  checkAction,
  retryRecalc,
} from './transitions.ts';

/** 후보 b 를 골라 수정한 행(재계산 대기). */
function edited() {
  const result = applyAction(makeRow(), { type: 'edit', candidateId: 'b' });
  if (!result.ok) throw new Error(result.error);
  return result.row;
}

describe('계산 실패', () => {
  it('실패하면 배출량이 비고 실패 표시가 남는다. 재계산 대기는 풀린다. 검토 상태와 수정값·원본값은 그대로다', () => {
    const failed = applyRecalcFailed(edited());
    expect(failed.edit).toEqual({
      candidateId: 'b',
      emission: null,
      recalcPending: false,
      recalcFailed: true,
    });
    expect(isRecalcFailed(failed)).toBe(true);
    expect(isRecalcPending(failed)).toBe(false);
    expect(currentEmission(failed)).toBeNull();
    expect(failed.status).toBe('edited');
    expect(failed.ai).toEqual(makeRow().ai);
  });

  it('「계산해 보니 값이 없다」(null)는 실패가 아니다. 둘은 최종 확정을 막는 까닭도 다르다', () => {
    const noValue = applyRecalculated(edited(), null);
    const failed = applyRecalcFailed(edited());
    expect(isRecalcFailed(noValue)).toBe(false);
    expect(noValue.edit).not.toHaveProperty('recalcFailed');
    expect(checkAction(noValue, { type: 'finalize' })).toBe('no_emission');
    expect(checkAction(failed, { type: 'finalize' })).toBe('recalc_failed');
    expect(ACTION_ERROR_MESSAGE.recalc_failed).not.toBe(
      ACTION_ERROR_MESSAGE.no_emission,
    );
    expect(ACTION_ERROR_MESSAGE.recalc_failed).toContain('계산하지 못했다');
    // 두 까닭이 일괄 결과에 나란히 나온다. 「계산하지 못했다」는 실패 쪽에만 쓴다.
    expect(ACTION_ERROR_MESSAGE.no_emission).not.toContain('계산하지 못했다');
  });

  it('실패한 행은 최종 확정이 안 된다', () => {
    expect(
      applyAction(applyRecalcFailed(edited()), { type: 'finalize' }),
    ).toEqual({ ok: false, error: 'recalc_failed' });
  });

  it('다시 시도하면 실패 표시가 지워지고 재계산 대기가 된다. 답이 오면 그 값으로 최종 확정이 된다', () => {
    const retried = retryRecalc(applyRecalcFailed(edited()));
    expect(retried.edit).toEqual({
      candidateId: 'b',
      emission: null,
      recalcPending: true,
    });
    expect(checkAction(retried, { type: 'finalize' })).toBe('recalc_pending');
    const done = applyRecalculated(retried, 250);
    expect(done.edit).toEqual({
      candidateId: 'b',
      emission: 250,
      recalcPending: false,
    });
    const finalized = applyAction(done, { type: 'finalize' });
    expect(finalized.ok && finalized.row.status).toBe('finalized');
  });

  it('다시 시도가 또 실패할 수 있다', () => {
    const again = applyRecalcFailed(retryRecalc(applyRecalcFailed(edited())));
    expect(isRecalcFailed(again)).toBe(true);
  });

  it('실패한 행이 아니면 다시 시도는 아무것도 바꾸지 않는다(같은 객체)', () => {
    const pending = edited();
    const done = applyRecalculated(pending, 250);
    const untouched = makeRow();
    expect(retryRecalc(pending)).toBe(pending);
    expect(retryRecalc(done)).toBe(done);
    expect(retryRecalc(untouched)).toBe(untouched);
    expect(applyRecalcFailed(untouched)).toBe(untouched);
  });

  it('재계산이 성공하면 앞선 실패 표시가 지워진다', () => {
    const recovered = applyRecalculated(applyRecalcFailed(edited()), 250);
    expect(isRecalcFailed(recovered)).toBe(false);
    expect(recovered.edit).toEqual({
      candidateId: 'b',
      emission: 250,
      recalcPending: false,
    });
  });

  it('실패한 행을 다시 고치면 실패 표시가 지워지고 재계산 대기가 된다. 반영하거나 되돌리면 수정값과 함께 사라진다', () => {
    const failed = applyRecalcFailed(edited());
    const reedited = applyAction(failed, { type: 'edit', candidateId: 'a' });
    expect(reedited.ok && reedited.row.edit).toEqual({
      candidateId: 'a',
      emission: null,
      recalcPending: true,
    });
    for (const type of ['accept', 'reopen'] as const) {
      const result = applyAction(failed, { type });
      expect(result.ok && isRecalcFailed(result.row)).toBe(false);
      expect(result.ok && result.row.edit).toBeNull();
    }
  });

  it('다시 시도는 전이가 아니다: 전이표에 그런 동작이 없다', () => {
    for (const actions of Object.values(TRANSITIONS))
      expect(Object.keys(actions)).not.toContain('retry');
  });
});

describe('계산 실패: 요약과 일괄', () => {
  const failed = { ...applyRecalcFailed(edited()), id: 'failed' };
  const noValue = { ...applyRecalculated(edited(), null), id: 'no-value' };
  const pending = { ...edited(), id: 'pending' };
  const fine = { ...applyRecalculated(edited(), 250), id: 'fine' };
  const noEmissionCandidate = makeRow({
    id: 'accepted-null',
    status: 'accepted',
    candidates: [candidate('a', null)],
  });
  const rows = [failed, noValue, pending, fine, noEmissionCandidate];

  it('요약은 실패한 행의 수를 센다. 배출량이 없는 행의 수가 아니다', () => {
    const summary = summarize(rows);
    expect(summary.recalcFailed).toBe(1);
    expect(summary.recalcPending).toBe(1);
    // 배출량이 없는 행은 넷(실패, 값 없음, 대기, 후보의 값 없음)이다. 그 가운데 실패는 하나다.
    expect(rows.filter((row) => currentEmission(row) === null)).toHaveLength(4);
    expect(summarize([fine]).recalcFailed).toBe(0);
  });

  it('일괄 최종 확정은 실패한 행을 건너뛰고, 건너뛴 까닭에 「계산하지 못했다」가 따로 나온다', () => {
    const result = applyBulk(
      rows,
      rows.map((row) => row.id),
      { type: 'finalize' },
    );
    expect(result.changed.map((row) => row.id)).toEqual(['fine']);
    expect(result.skipped).toEqual(
      expect.arrayContaining([
        { error: 'recalc_failed', status: 'edited', count: 1 },
        { error: 'no_emission', status: 'edited', count: 1 },
        { error: 'recalc_pending', status: 'edited', count: 1 },
        { error: 'no_emission', status: 'accepted', count: 1 },
      ]),
    );
    expect(result.skipped).toHaveLength(4);
    const line = describeSkip(
      result.skipped.find((skip) => skip.error === 'recalc_failed')!,
    );
    expect(line).toBe(
      '수정 1개: 계산하지 못했다(계산이 실패했다). 다시 계산해야 한다.',
    );
  });
});

describe('계산 실패: 입력', () => {
  const input = (edit: unknown) => ({
    version: 2,
    unit: 'tCO2eq',
    categories: ['가'],
    rows: [
      {
        id: 'r1',
        raw: {},
        ai: { category: '가', candidates: [candidate('a'), candidate('b')] },
        review: { status: 'edited', edit },
      },
    ],
  });

  it('실패한 채로 저장된 행을 받는다', () => {
    const result = parseTableInput(
      input({ candidateId: 'b', emission: null, recalcFailed: true }),
    );
    expect(result.ok && result.input.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: null,
      recalcPending: false,
      recalcFailed: true,
    });
    expect(result.ok && isRecalcFailed(result.input.rows[0]!)).toBe(true);
  });

  it('그 필드가 없는 자료(앞서 있던 꼴)는 그대로 받고, 실패가 아니다', () => {
    const result = parseTableInput(input({ candidateId: 'b', emission: null }));
    expect(result.ok && result.input.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: null,
      recalcPending: false,
    });
    expect(result.ok && isRecalcFailed(result.input.rows[0]!)).toBe(false);
  });

  it('실패인데 배출량이 있으면 받지 않는다', () => {
    const withEmission = parseTableInput(
      input({ candidateId: 'b', emission: 5, recalcFailed: true }),
    );
    expect(!withEmission.ok && withEmission.errors[0]).toContain(
      '계산 실패인데 배출량이 있다',
    );
  });

  it('recalcFailed: false 는 필드가 없는 것과 같다(행에 false 를 남기지 않는다)', () => {
    const result = parseTableInput(
      input({ candidateId: 'b', emission: 5, recalcFailed: false }),
    );
    expect(result.ok && result.input.rows[0]!.edit).toEqual({
      candidateId: 'b',
      emission: 5,
      recalcPending: false,
    });
  });
});
