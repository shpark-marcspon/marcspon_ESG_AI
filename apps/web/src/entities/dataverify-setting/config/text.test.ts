// AD-02 데이터 검증 탭 문구 원문(밴드 DVA2 — 시안 AD-02-DV r1 · 흐름 코드와 대 봄). 화면·e2e 시험은 이 표의 값으로 단언하므로 원문은 여기서 글자로 박는다.
//   모듈 이름이 메뉴·감사 낱말과 같은지는 모듈 줄 시험(app/admin/ai-setting-modules.test.ts)이 본다(entities 끼리 가져오지 않는다).
//   입력 글 자리 표(REQUIRED_PLACEHOLDERS)는 model 칸 시험(model/flow.test.ts)이 본다 — 문구 표는 아무것도 가져오지 않는다(시험도 같은 칸 규칙).
import { describe, expect, it } from 'vitest';

import { DATAVERIFY_SETTING_TEXT } from './text.ts';

const t = DATAVERIFY_SETTING_TEXT;
/** 계산 검토 입력 글의 자리(서버 REQUIRED review_user 사본). */
const REVIEW_SLOTS = ['{계산 계획의 산식 목록}', '{입력 데이터 JSON}'];

/** 칸 안내 글 전부(자리 안내 · 출력 안내 둘 · 고정 규칙 · 흐름 글). */
const allNotes = () => [
  t.placeholders.lead(REVIEW_SLOTS),
  t.placeholders.company,
  t.placeholders.review,
  t.placeholders.tail,
  ...Object.values(t.outputNotes),
  ...t.fixedRules,
  t.module.codeRules.foot,
  t.module.modelNote,
  t.flow.note,
];

describe('AD-02 데이터 검증 탭 문구', () => {
  it('모듈 이름 「데이터 검증」 · 상세 라벨 「칸」 · 모델 곁 글 · 고정 규칙 머리·꼬리와 줄 여섯(시안 원문)', () => {
    expect(t.module.name).toBe('데이터 검증');
    expect(t.module.slotLabel).toBe('칸');
    expect(t.module.modelNote).toBe(
      '세 단계에 같이 쓰여요 · 모델 하나로 세 프롬프트를 불러요',
    );
    expect(t.module.codeRules).toEqual({
      title: '고정 규칙 · 읽기 전용',
      foot: '고정 규칙은 여기서 고칠 수 없어요',
    });
    expect(t.fixedRules).toHaveLength(6);
    expect(t.fixedRules[2]).toBe(
      '「1. 계산 계획」이 실패하거나 답을 산식 목록으로 읽지 못하면 「2. 계산 검토」는 건너뛰고 「3. 리스크 진단」은 돌아요',
    );
  });

  it('자리 안내: 그 칸의 자리를 늘어놓음 · 계산 검토는 기업 낱말 0', () => {
    expect(t.placeholders.lead(['{가}', '{나}'])).toBe(
      '{가} · {나} 자리에는 실행 때 값이 끼워져요',
    );
    const review = [
      t.placeholders.lead(REVIEW_SLOTS),
      t.placeholders.review,
    ].join(' ');
    for (const word of ['기업명', 'SASB', '중대토픽', '보고연도'])
      expect(review).not.toContain(word);
    expect(t.placeholders.company).toContain('기업명 · SASB 산업분류');
  });

  it('출력 안내는 계산 계획·인사이트 지시 글 둘만(서버 OUTPUT_MARKS 칸) — 절 머리 글자가 서버 머리와 같음', () => {
    expect(Object.keys(t.outputNotes)).toEqual([
      'plan_system',
      'insight_system',
    ]);
    expect(t.outputNotes.plan_system).toMatch(/^출력 규칙 · 출력 예시 절/);
    expect(t.outputNotes.insight_system).toMatch(/^# 출력 형식 절/);
  });

  it('흐름 띠: 마디 셋의 하는 일·빈도 · 갈래 글(시안 원문) · 걸음 수 글자 0', () => {
    expect(Object.keys(t.flow.steps)).toEqual(['plan', 'review', 'insight']);
    expect(t.flow.steps.review).toEqual({
      does: '산식마다 계산 도구로 값을 맞대 봐요',
      runs: '산식마다',
    });
    expect([t.flow.yes, t.flow.no]).toEqual(['예', '아니요']);
    expect(t.flow.nodeLabel(2, '계산 검토', true)).toBe(
      '2. 계산 검토 프롬프트 보기, 고침',
    );
    expect(t.flow.stepHead(1, '계산 계획')).toBe('단계 1 계산 계획');
    expect(JSON.stringify(t.flow.steps)).not.toMatch(/걸음|\d+/);
  });

  it('rv-note 글(「기본 메모 예시」·「시안에서는」·「상태 예시」)과 칠하기 낱말은 어느 글에도 0', () => {
    for (const note of allNotes())
      for (const word of ['기본 메모 예시', '시안에서는', '상태 예시', '회색'])
        expect(note, note).not.toContain(word);
  });
});

describe('낱말 통일(밴드 DV17)', () => {
  it('글 전부에 「인사이트」 0 · 세 번째 단계는 「리스크 진단」', () => {
    const texts = (value: unknown): string[] =>
      typeof value === 'string' ? [value]
      : typeof value === 'function' ? [String(value)]
      : value && typeof value === 'object' ? Object.values(value).flatMap(texts)
      : [];
    expect(texts(t).filter((text) => text.includes('인사이트'))).toEqual([]);
    expect(t.flow.skip).toBe(
      '계획이 실패하거나 답을 읽지 못하면 검토를 건너뛰고 리스크 진단으로',
    );
  });
});
