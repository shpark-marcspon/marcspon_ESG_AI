// 보고서 작성 흐름 마디·자리 표(밴드 RPA3 — 발주서 §3-1-4). 자리 표는 서버 drafting/flows/prompt_model_v2.py REQUIRED 의 사본 —
//   입력 글 두 칸, 자리 글자(engines/v2/texts.py OUTLINE_SLOT·PAGES_SLOT·TITLE_SLOT·REQUIREMENT_SLOT — 재료 자리 v2 `{페이지 글}`)·차례는 서버 PLACEHOLDERS 와 같다.
import { describe, expect, it } from 'vitest';

import { FLOW_GROUPS, REQUIRED_PLACEHOLDERS, flowNodes } from './index.ts';

describe('보고서 작성 흐름 model', () => {
  it('자리 표는 입력 글 두 칸 — 자리 글자·차례는 서버 REQUIRED 와 같음 · 지시 글 둘은 0', () => {
    expect(REQUIRED_PLACEHOLDERS).toEqual({
      map_user: ['{목차}', '{페이지 글}'],
      draft_user: ['{제목 경로}', '{요구 내용}', '{페이지 글}'],
    });
    for (const key of ['map_system', 'draft_system'])
      expect(REQUIRED_PLACEHOLDERS[key]).toBeUndefined();
  });

  it('마디 = 번호 둘(흐름 차례) · 응답에 없는 key 는 group null', () => {
    expect(FLOW_GROUPS).toEqual(['map', 'draft']);
    expect(flowNodes([{ key: 'draft', label: '지어낸 둘' }])).toEqual([
      { key: 'map', group: null, label: null, n: 1 },
      { key: 'draft', group: 0, label: '지어낸 둘', n: 2 },
    ]);
    expect(
      flowNodes([
        { key: 'map', label: '지어낸 하나' },
        { key: 'draft', label: '지어낸 둘' },
      ]).map((one) => one.group),
    ).toEqual([0, 1]);
  });
});
