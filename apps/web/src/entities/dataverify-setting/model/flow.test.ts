// 데이터 검증 흐름 마디·입력 글 자리 표(밴드 DVA2 — 발주서 §3-1-4). 자리 표는 서버 engines/colab_156/prompts.py REQUIRED 의 사본 —
//   글자는 DVA1 보고 「자리 이름」 표와 같다(걸음 자리 {최대 걸음 − 4} 류는 지시 글 자리라 표에 없음).
import { describe, expect, it } from 'vitest';

import { FLOW_GROUPS, REQUIRED_PLACEHOLDERS, flowNodes } from './index.ts';

const COMPANY = ['{기업명}', '{SASB 산업분류}', '{중대토픽}', '{보고연도}'];

describe('데이터 검증 흐름 model', () => {
  it('입력 글 자리 표는 입력 글 셋만 — 자리 글자는 서버 REQUIRED 와 같음 · 계산 검토는 기업 자리 0', () => {
    expect(REQUIRED_PLACEHOLDERS).toEqual({
      plan_user: [...COMPANY, '{입력 데이터 JSON}'],
      review_user: ['{계산 계획의 산식 목록}', '{입력 데이터 JSON}'],
      insight_user: [...COMPANY, '{입력 데이터 JSON}'],
    });
    expect(JSON.stringify(REQUIRED_PLACEHOLDERS)).not.toContain('걸음');
    for (const key of ['plan_system', 'review_system', 'insight_system'])
      expect(REQUIRED_PLACEHOLDERS[key]).toBeUndefined();
  });

  it('마디 셋 = 흐름 차례 · 응답에 없는 key 는 group null · 번호는 흐름 차례', () => {
    expect(FLOW_GROUPS).toEqual(['plan', 'review', 'insight']);
    expect(
      flowNodes([
        { key: 'insight', label: '지어낸 셋' },
        { key: 'plan', label: '지어낸 하나' },
      ]),
    ).toEqual([
      { key: 'plan', group: 1, label: '지어낸 하나', n: 1 },
      { key: 'review', group: null, label: null, n: 2 },
      { key: 'insight', group: 0, label: '지어낸 셋', n: 3 },
    ]);
  });
});
