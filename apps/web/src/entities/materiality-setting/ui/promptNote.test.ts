// 중대성평가 IRO 칸 아래 안내(밴드 IRA3 — 발주서 Q5). 자리 지킴 칸 넷은 IRA2 자리 안내 그대로, 1부 입력 글 셋은 inputNote, 그 밖 null.
import { describe, expect, it } from 'vitest';

import { MATERIALITY_SETTING_TEXT } from '../config/text.ts';
import { INPUT_PREFIXES, materialityPromptNote } from './index.ts';

const t = MATERIALITY_SETTING_TEXT;
const p = t.placeholders;

describe('중대성평가 IRO 칸 아래 안내', () => {
  it('자리 지킴 칸 넷 = 그 칸 자리 안내 · 규제 지시 글은 신뢰 출처 글 · 경로는 1부 자리 낱말 0', () => {
    expect(materialityPromptNote('regulation_system')).toBe(
      `${p.whitelist(['{신뢰 출처 목록}'])} · ${p.tail}`,
    );
    const impact = materialityPromptNote('impact_input')!;
    expect(impact).toBe(
      `${p.lead(['{기업명}', '{산업 정의}', '{가치사슬 활동}', '{토픽}', '{서브토픽}', '{서브토픽 설명}', '{컨트로버시 리서치의 답}', '{규제·정책 리서치의 답}'])} — ${p.from.impact_input} · ${p.tail}`,
    );
    expect(materialityPromptNote('financial_input')).toBe(impact);
    const pathway = materialityPromptNote('pathway_input')!;
    expect(pathway).toBe(
      `${p.lead(['{재무 영향 정의의 답}'])} — ${p.from.pathway_input} · ${p.tail}`,
    );
    for (const word of ['검색', '토픽', '키워드', '산업', '신뢰 출처'])
      expect(pathway).not.toContain(word);
  });

  it('1부 입력 글 셋 = inputNote(시안 v211 「{ } 칸은…」)', () => {
    expect(INPUT_PREFIXES).toEqual([
      'regulation_prefix',
      'keywords_prefix',
      'controversy_prefix',
    ]);
    for (const key of INPUT_PREFIXES)
      expect(materialityPromptNote(key), key).toBe(t.inputNote);
  });

  it('그 밖 칸 · 옛 가변 입력 셋 · 모르는 칸은 null', () => {
    for (const key of [
      'keywords_system',
      'controversy_system',
      'impact_system',
      'financial_system',
      'pathway_system',
      'whitelist_non_financial',
      'whitelist_financial',
      'regulation_input',
      'keywords_input',
      'controversy_input',
      'x',
    ])
      expect(materialityPromptNote(key), key).toBeNull();
  });
});
