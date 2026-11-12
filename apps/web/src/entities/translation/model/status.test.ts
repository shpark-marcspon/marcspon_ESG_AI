// 파트 상태 셈(밴드 TRW0b, 발주서 §3-1): 묶음 셈 차례(★A — 완료·진행 중·대기·실패, 실패 둘은 하나로) · 화면 제목 세 갈래 · 완료 수 · 다음 할 일 · 실패 갈래(393).
import { describe, expect, it } from 'vitest';

import {
  batchNext,
  batchSummary,
  doneCount,
  failureKindOf,
  screenTitleKey,
} from './status.ts';
import type { TabState } from './status.ts';
import { AT_1150, AT_1155, AT_1205, AT_1422 } from './testing.ts';

const parts = (...states: TabState[]) => states.map((state) => ({ state }));

describe('batchSummary', () => {
  it('완료 2 · 진행 중 1 — 있는 상태만, 판 차례', () => {
    expect(batchSummary(parts('running', 'done', 'done'))).toEqual([
      { state: 'done', n: 2 },
      { state: 'running', n: 1 },
    ]);
  });

  it('차례: 완료 → 진행 중 → 대기 → 실패(넣은 차례와 상관없이)', () => {
    expect(
      batchSummary(parts('failed', 'queued', 'running', 'done')).map(
        ({ state }) => state,
      ),
    ).toEqual(['done', 'running', 'queued', 'failed']);
  });

  it('실패 둘(failed·failed_partial)은 「실패」 하나로 센다', () => {
    expect(batchSummary(parts('failed', 'failed_partial', 'done'))).toEqual([
      { state: 'done', n: 1 },
      { state: 'failed', n: 2 },
    ]);
  });
});

describe('screenTitleKey', () => {
  it('하나라도 돌거나 기다리면 running', () => {
    expect(screenTitleKey(AT_1155)).toBe('running');
    expect(screenTitleKey(AT_1150)).toBe('running');
    expect(screenTitleKey(parts('failed', 'queued'))).toBe('running');
  });

  it('모두 완료면 done', () => {
    expect(screenTitleKey(AT_1422)).toBe('done');
  });

  it('도는 것 없이 실패가 있으면 needs_retry(일부 쪽도)', () => {
    expect(screenTitleKey(AT_1205)).toBe('needs_retry');
    expect(screenTitleKey(parts('done', 'failed'))).toBe('needs_retry');
  });
});

describe('doneCount · batchNext · failureKindOf', () => {
  it('완료 수는 done 만(일부 쪽 실패는 세지 않음)', () => {
    expect(doneCount(AT_1155)).toBe(1);
    expect(doneCount(AT_1205)).toBe(2);
    expect(doneCount(AT_1422)).toBe(3);
  });

  it('돌거나 기다리는 파트가 있으면 progress, 아니면 result', () => {
    expect(batchNext(AT_1150)).toBe('progress');
    expect(batchNext(AT_1205)).toBe('result');
  });

  it('실패 갈래: 까닭 있음 = rejected, 없음 = server_error, 일부 쪽 = partial, 그 밖 null', () => {
    expect(failureKindOf({ state: 'failed', reason: 'too_large' })).toBe(
      'rejected',
    );
    expect(failureKindOf({ state: 'failed' })).toBe('server_error');
    expect(failureKindOf({ state: 'failed_partial' })).toBe('partial');
    expect(failureKindOf({ state: 'done' })).toBeNull();
  });
});
