// AD-02 실서버 판의 문구 원문(밴드 AD2R ①). 화면·e2e 시험은 이 표의 값으로 단언하므로 디자인 원문·서버 문장은 여기서 글자로 박는다.
import { describe, expect, it } from 'vitest';

import { CRITERIA_REFUSED, GREENWASH_SETTING_TEXT } from './text.ts';

const t = GREENWASH_SETTING_TEXT;

describe('AD-02 실서버 판 문구', () => {
  it('받기 거절은 서버 code 15개 — SCHEMA_VERSION·VERSION 둘만 웹 글로 갈음(디자인 D5)', () => {
    expect(Object.keys(CRITERIA_REFUSED)).toHaveLength(15);
    expect(CRITERIA_REFUSED.CRITERIA_SCHEMA_VERSION).toBe(
      CRITERIA_REFUSED.CRITERIA_SHAPE,
    );
    expect(CRITERIA_REFUSED.CRITERIA_VERSION).toBe(t.saveFailed);
    expect(CRITERIA_REFUSED.CRITERIA_KEYWORD_NAME).toBe(
      '대상 키워드 묶음의 이름은 바꿀 수 없어요',
    );
    for (const [code, text] of Object.entries(CRITERIA_REFUSED))
      expect(text, code).not.toMatch(/schemaVersion|1~64자/);
  });

  it('디자인 답 원문(D1·D2·D3·D5·D6, G2c 답)', () => {
    expect(t.saveNotice).toBe(
      '저장하면 이 표로 새 버전이 만들어져요. 지금 버전과 적용 중인 버전은 바뀌지 않아요. 사용을 끈 줄은 프롬프트에서 빠져요.',
    );
    expect(t.defaultRow).toEqual({ badge: '기본', sum: '코랩 원본' });
    expect(t.apply.title('v3')).toBe('v3 을 적용할까요?');
    expect(t.apply.body('v3', 'v2')).toBe(
      '다음 실행부터 v3 을 써요. 이미 돌고 있는 실행은 v2 으로 끝나요.',
    );
    expect(t.apply.done('v3')).toBe(
      'v3 을 적용했어요. 다음 실행부터 v3 을 써요.',
    );
    expect(t.apply.failed).toBe('적용하지 못했어요. 다시 눌러 주세요.');
    expect(t.detailFailed).toBe('판정 기준을 불러오지 못했어요');
    expect(t.saveFailed).toBe('저장하지 못했어요. 다시 저장해 주세요.');
    expect(t.textProblem.tooLong).toBe('300자까지 쓸 수 있어요');
    expect(t.emptyMemo).toBe('–');
    expect(t.guidelineNote).toBe('기록용 · 판정에 쓰이지 않아요');
    expect(t.fixedRules).toHaveLength(4);
  });

  it('AS3b ① K9: 공통 표에서 옮긴 모듈 글 — 글자 그대로', () => {
    expect(t.module.name).toBe('그린워싱');
    expect(t.module.modelNote).toBe(
      '모든 단계에 같이 쓰여요 · 모델 하나로 네 프롬프트를 불러요',
    );
    expect(t.module.codeRules).toEqual({
      title: '고정 규칙 · 읽기 전용',
      foot: '고정 규칙은 프롬프트 글에서 고칠 수 없어요. 바꾸려면 흐름(코드)을 고쳐요.',
    });
  });

  it('AS3b ① 대상 단어 카드 글(D1~D4·D6)과 거절 글 넷', () => {
    expect(t.terms.foot(42, 40, 0)).toBe('42개 · 사용 40개');
    expect(t.terms.foot(42, 40, 2)).toBe(
      '42개 · 사용 40개 · 새로 더한 2개는 저장 전이에요',
    );
    expect(t.terms.noneEnabled).toBe(
      '켠 단어가 하나 이상 있어야 저장할 수 있어요',
    );
    expect(Object.values(t.terms.problem)).toEqual([
      '1~30자로 써 주세요',
      '괄호와 따옴표는 쓸 수 없어요',
      '이미 있는 단어예요',
      '단어는 100개까지 넣을 수 있어요',
    ]);
    expect(Object.keys(t.terms.refused)).toEqual([
      'TERMS_TEXT',
      'TERMS_DUPLICATE',
      'TERMS_COUNT',
      'TERMS_NONE_ENABLED',
    ]);
    expect(t.terms.sum(37)).toBe('37개');
  });

  it('AS3b ① 한 문장 글은 끝 마침표 없음, 두 문장 이상은 둠(MARC-ENT-269)', () => {
    for (const line of [
      t.module.modelNote,
      t.terms.noneEnabled,
      t.terms.placeholder,
      t.terms.foot(3, 2, 1),
      ...Object.values(t.terms.problem),
      ...Object.values(t.terms.refused),
    ])
      expect(line, line).not.toMatch(/\.$/);
    for (const line of [t.module.codeRules.foot, t.terms.notice])
      expect(line, line).toMatch(/\.$/);
  });
});
