// 진행 셈(밴드 S3W3d ③). 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import { RUN_STEP_NAMES, progressOf } from './runProgress.ts';
import type { RunStep, RunStepStatus } from './runProgress.ts';

/** 앞 n 단계 done, 그다음 next, 나머지 pending. */
const steps = (n: number, next: RunStepStatus = 'pending'): RunStep[] =>
  RUN_STEP_NAMES.map((step, index) => ({
    step,
    status:
      index < n ? 'done'
      : index === n ? next
      : 'pending',
  }));

describe('progressOf', () => {
  it('단계 열다섯 · 분모는 카테고리 단계 열넷(마무리 뺌)', () => {
    expect(RUN_STEP_NAMES).toHaveLength(15);
    expect(RUN_STEP_NAMES).not.toContain('c10');
  });

  it('처음 0/14 · 중간은 끝난 수 · 도는 단계는 세지 않는다', () => {
    expect(progressOf(steps(0))).toEqual({
      kind: 'counting',
      done: 0,
      total: 14,
    });
    expect(progressOf(steps(5, 'running'))).toEqual({
      kind: 'counting',
      done: 5,
      total: 14,
    });
  });

  it('끝은 14/14 · 마무리가 돌면 수 없이 마무리 · 마무리가 끝나도 분모는 14', () => {
    expect(progressOf(steps(14))).toEqual({
      kind: 'counting',
      done: 14,
      total: 14,
    });
    expect(progressOf(steps(14, 'running'))).toEqual({ kind: 'assembling' });
    expect(progressOf(steps(15))).toEqual({
      kind: 'counting',
      done: 14,
      total: 14,
    });
  });

  it('실패 단계는 끝난 수에 들지 않는다', () => {
    expect(progressOf(steps(3, 'failed'))).toEqual({
      kind: 'counting',
      done: 3,
      total: 14,
    });
  });

  it('수를 되돌려 받아도 받은 값대로(다시 도는 시도)', () => {
    expect(progressOf(steps(6))).toMatchObject({ done: 6 });
    expect(progressOf(steps(2, 'running'))).toMatchObject({ done: 2 });
  });

  it('단계를 못 읽음: 빈 steps · 마무리만 있음 → null', () => {
    expect(progressOf([])).toBeNull();
    expect(progressOf([{ step: 'assemble', status: 'running' }])).toBeNull();
  });
});
