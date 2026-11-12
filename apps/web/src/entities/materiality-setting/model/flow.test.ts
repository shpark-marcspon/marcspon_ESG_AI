// 중대성평가 IRO 흐름 마디·자리 표(밴드 IRA2 — 발주서 §3-1-4). 자리 표는 서버 engines/colab_155/texts.py REQUIRED 의 사본 —
//   판 칸 넷(규제 지시 글 + 2부 날 글 셋 — 1부 가변 입력 셋은 판 칸이 아니다, IRA3), 자리 글자·차례는 서버 PLACEHOLDERS 와 같다.
import { describe, expect, it } from 'vitest';

import {
  ANALYSIS_SLOT,
  FLOW_GROUPS,
  REQUIRED_PLACEHOLDERS,
  WHITELIST_GROUP,
  flowNodes,
} from './index.ts';

const PART2 = [
  '{기업명}',
  '{산업 정의}',
  '{가치사슬 활동}',
  '{토픽}',
  '{서브토픽}',
  '{서브토픽 설명}',
  '{컨트로버시 리서치의 답}',
  '{규제·정책 리서치의 답}',
];

describe('중대성평가 IRO 흐름 model', () => {
  it('자리 표는 판 칸 넷 — 자리 글자·차례는 서버 REQUIRED 와 같음 · 옛 가변 입력 셋 없음(IRA3)', () => {
    expect(REQUIRED_PLACEHOLDERS).toEqual({
      regulation_system: ['{신뢰 출처 목록}'],
      impact_input: PART2,
      financial_input: PART2,
      pathway_input: ['{재무 영향 정의의 답}'],
    });
    for (const key of [
      'regulation_input',
      'keywords_input',
      'controversy_input',
      'regulation_prefix',
      'keywords_system',
      'keywords_prefix',
      'controversy_system',
      'controversy_prefix',
      'impact_system',
      'financial_system',
      'pathway_system',
      'whitelist_non_financial',
      'whitelist_financial',
    ])
      expect(REQUIRED_PLACEHOLDERS[key]).toBeUndefined();
  });

  it('마디 = 번호 다섯(흐름 차례) + 신뢰 출처(번호 없음, 끝) · 응답에 없는 key 는 group null', () => {
    expect(FLOW_GROUPS).toEqual([
      'regulation',
      'controversy',
      'impact',
      'financial',
      'pathway',
    ]);
    expect(WHITELIST_GROUP).toBe('whitelist');
    expect(ANALYSIS_SLOT).toBe('analysis');
    expect(
      flowNodes([
        { key: 'whitelist', label: '지어낸 출처' },
        { key: 'impact', label: '지어낸 셋' },
        { key: 'regulation', label: '지어낸 하나' },
      ]),
    ).toEqual([
      { key: 'regulation', group: 2, label: '지어낸 하나', n: 1 },
      { key: 'controversy', group: null, label: null, n: 2 },
      { key: 'impact', group: 1, label: '지어낸 셋', n: 3 },
      { key: 'financial', group: null, label: null, n: 4 },
      { key: 'pathway', group: null, label: null, n: 5 },
      { key: 'whitelist', group: 0, label: '지어낸 출처', n: null },
    ]);
  });
});
