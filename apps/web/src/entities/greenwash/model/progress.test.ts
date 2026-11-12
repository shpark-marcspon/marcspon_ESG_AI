// (밴드 FS1 ③: form-progress.test.ts 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 새 점검 폼 검사 사유 코드와 실행 진행 모델(밴드 FW1b ①).
import { describe, expect, it } from 'vitest';

import { failurePoint, overallPercent, stageStates } from './progress.ts';
import type { RunProgress } from './progress.ts';

describe('실행 진행 모델', () => {
  const at = (
    state: RunProgress['state'],
    stage: RunProgress['stage'],
    done = 0,
    total = 44,
  ): RunProgress => ({ state, stage, judge: { done, total } });

  it('전체 진행률: 추출 10 · 판정 80(쪽 비례) · 정리 10', () => {
    expect(overallPercent(at('running', 'extract'))).toBe(0);
    expect(overallPercent(at('running', 'judge', 0))).toBe(10);
    expect(overallPercent(at('running', 'judge', 22))).toBe(50);
    expect(overallPercent(at('running', 'judge', 28))).toBe(60);
    expect(overallPercent(at('running', 'judge', 44))).toBe(90);
    expect(overallPercent(at('running', 'summarize', 44))).toBe(90);
    expect(overallPercent(at('done', 'summarize', 44))).toBe(100);
    expect(overallPercent(at('running', 'judge', 0, 0))).toBe(10);
  });

  it('단계 상태: 앞은 완료, 지금은 진행 중(실패면 실패), 뒤는 대기', () => {
    expect(stageStates(at('running', 'judge', 28))).toEqual({
      extract: 'done',
      judge: 'now',
      summarize: 'todo',
    });
    expect(stageStates(at('failed', 'judge', 28))).toEqual({
      extract: 'done',
      judge: 'failed',
      summarize: 'todo',
    });
    expect(stageStates(at('done', 'summarize'))).toEqual({
      extract: 'done',
      judge: 'done',
      summarize: 'done',
    });
  });

  it('실패 지점: 판정 단계면 쪽까지, 다른 단계면 단계만, 실패가 아니면 null', () => {
    expect(failurePoint(at('failed', 'judge', 28))).toEqual({
      stage: 'judge',
      judge: { done: 28, total: 44 },
    });
    expect(failurePoint(at('failed', 'extract'))).toEqual({
      stage: 'extract',
    });
    expect(failurePoint(at('running', 'judge', 28))).toBeNull();
  });
});
