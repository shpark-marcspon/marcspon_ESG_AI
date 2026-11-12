import { describe, expect, it } from 'vitest';

import { transition } from './review.ts';
import type { ReviewState } from './review.ts';

const pending: ReviewState = { status: 'pending' };
const confirmed: ReviewState = { status: 'confirmed' };
const rejected: ReviewState = { status: 'rejected', reason: '단위가 다르다' };

describe('transition', () => {
  it('검토대기 → 확정', () => {
    expect(transition(pending, { type: 'confirm' })).toEqual({
      ok: true,
      state: confirmed,
    });
  });

  it('검토대기 → 반려: 사유가 남는다(앞뒤 공백은 뗀다)', () => {
    expect(
      transition(pending, { type: 'reject', reason: '  단위가 다르다 ' }),
    ).toEqual({ ok: true, state: rejected });
  });

  it('사유 없는 반려는 거부한다', () => {
    expect(transition(pending, { type: 'reject', reason: '' })).toEqual({
      ok: false,
      error: 'reason_required',
    });
    expect(transition(pending, { type: 'reject', reason: '   \n' })).toEqual({
      ok: false,
      error: 'reason_required',
    });
  });

  it('확정·반려 → 다시 검토대기', () => {
    expect(transition(confirmed, { type: 'reopen' })).toEqual({
      ok: true,
      state: pending,
    });
    expect(transition(rejected, { type: 'reopen' })).toEqual({
      ok: true,
      state: pending,
    });
  });

  it('확정에서 곧바로 반려로, 반려에서 곧바로 확정으로 가지 못한다', () => {
    expect(transition(confirmed, { type: 'reject', reason: '사유' })).toEqual({
      ok: false,
      error: 'not_pending',
    });
    expect(transition(rejected, { type: 'confirm' })).toEqual({
      ok: false,
      error: 'not_pending',
    });
    expect(transition(confirmed, { type: 'confirm' })).toEqual({
      ok: false,
      error: 'not_pending',
    });
  });

  it('검토대기를 다시 검토대기로 되돌릴 수 없다', () => {
    expect(transition(pending, { type: 'reopen' })).toEqual({
      ok: false,
      error: 'already_pending',
    });
  });
});
