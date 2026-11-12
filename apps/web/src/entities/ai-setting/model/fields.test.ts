// 저장 거절 칸 경로 풀이(밴드 AD2W ④): 서버 fields 경로 prompts.steps.<i>.prompts.<j>.text|memo → (단계, 칸, 칸 종류), 모르는 경로는 null.
import { describe, expect, it } from 'vitest';

import { promptFieldOf } from './fields.ts';

describe('promptFieldOf', () => {
  it('prompts.steps.0.prompts.3.memo → (0, 3, memo), …1.text → (0, 1, text), 두 자리 수도', () => {
    expect(promptFieldOf('prompts.steps.0.prompts.3.memo')).toEqual({
      group: 0,
      prompt: 3,
      field: 'memo',
    });
    expect(promptFieldOf('prompts.steps.0.prompts.1.text')).toEqual({
      group: 0,
      prompt: 1,
      field: 'text',
    });
    expect(promptFieldOf('prompts.steps.12.prompts.10.text')).toEqual({
      group: 12,
      prompt: 10,
      field: 'text',
    });
  });

  it('모르는 경로는 null(총 크기 prompts · 단계 목록 · 칸 목록 · 앞 0 · 다른 칸 · 꼬리)', () => {
    for (const path of [
      'prompts',
      'prompts.steps',
      'prompts.steps.0.prompts',
      'prompts.steps.01.prompts.1.text',
      'prompts.steps.0.prompts.1.key',
      'prompts.steps.0.prompts.1.text.x',
      'title',
      'modelSettings.steps.0.route',
    ])
      expect(promptFieldOf(path), path).toBeNull();
  });
});
