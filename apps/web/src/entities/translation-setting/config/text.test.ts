// AD-02 영문번역 탭 문구 원문(밴드 TRA1 — 시안 AD-02-TR r1). 화면·e2e 시험은 이 표의 값으로 단언하므로 시안 원문은 여기서 글자로 박는다.
//   모듈 이름이 메뉴·감사 낱말과 같은지는 모듈 줄 시험(app/admin/ai-setting-modules.test.ts)이 본다(entities 끼리 가져오지 않는다).
import { describe, expect, it } from 'vitest';

import { TRANSLATION_SETTING_TEXT } from './text.ts';

const t = TRANSLATION_SETTING_TEXT;

describe('AD-02 영문번역 탭 문구', () => {
  it('모듈 이름 「영문번역」 · 고정 규칙 머리·꼬리와 줄 넷(시안 원문)', () => {
    expect(t.module.name).toBe('영문번역');
    expect(t.module.codeRules).toEqual({
      title: '고정 규칙 · 읽기 전용',
      foot: '고정 규칙은 프롬프트 글에서 고칠 수 없어요. 바꾸려면 흐름(코드)을 고쳐요.',
    });
    expect(t.fixedRules).toHaveLength(4);
    expect(t.fixedRules[1]).toBe(
      '용어집은 원문에 그 낱말이 그대로 있을 때만 맞춰요. 평가용어집과 고객사 용어집이 겹치면 고객사 용어집을 따라요.',
    );
  });

  it('흐름 띠: 마디 다섯의 하는 일·빈도와 소묶음 머리 셋(시안 원문)', () => {
    expect(Object.keys(t.flow.steps)).toEqual([
      'translate',
      'polish',
      'editorial_qa',
      'review',
      'autofix',
    ]);
    expect(t.flow.steps.translate).toEqual({
      does: '파트 톤·문체로 옮겨요',
      runs: '페이지마다 · 표 24칸',
    });
    expect(t.flow.steps.editorial_qa.runs).toBe('96점 관문');
    expect(
      ['common', 'part', 'style'].map(
        (key) => t.flow.sections[key as 'common'].title,
      ),
    ).toEqual(['모든 파트 공통', '파트마다 하나', '고른 문체 하나']);
    expect(Object.keys(t.flow.notes)).toHaveLength(6);
    expect(t.flow.sectionCount(4, true)).toBe('칸 4개 · 펼침');
    expect(t.flow.sectionCount(3, false)).toBe('칸 3개 · 접힘');
    expect(t.flow.sectionEdited(2)).toBe('고침 2');
    expect(t.flow.nodeLabel(1, '번역', true)).toBe(
      '1. 번역 프롬프트 보기, 고침',
    );
  });

  // 밴드 TRW4(결정 sid:MARC-ENT-459): 쪽수 단위는 「페이지」 — 함수 글은 대표 인자로 불러 본다. 방향 「쪽」만 남는다.
  it('전수 검사: 고정 글·함수 글에 쪽수 단위 「쪽」이 없다', () => {
    const collect = (value: unknown): string[] => {
      if (typeof value === 'function')
        return collect(value(...Array<unknown>(value.length).fill(5)));
      if (typeof value === 'string') return [value];
      if (value && typeof value === 'object')
        return Object.values(value).flatMap(collect);
      return [];
    };
    const texts = collect(t);
    expect(texts.length).toBeGreaterThan(30);
    for (const text of texts) {
      expect(text).not.toMatch(/\d쪽|쪽 칸|가운데 쪽/);
      expect(text.replace(/(왼|오른|위|아래|안|바깥)쪽/g, '')).not.toContain(
        '쪽',
      );
    }
    expect(t.flow.notes.pre).toBe(
      'CEO 메시지는 최대 6페이지 · 넘으면 시작하지 않아요',
    );
  });
});
