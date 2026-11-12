// AD-02 중대성평가 IRO 탭 문구 원문(밴드 IRA2 — 시안 AD-02-IR r1 · 흐름 코드와 대 봄). 화면·e2e 시험은 이 표의 값으로 단언하므로 원문은 여기서 글자로 박는다.
//   모듈 이름이 감사 낱말과 같은지는 모듈 줄 시험(app/admin/ai-setting-modules.test.ts)이 본다(entities 끼리 가져오지 않는다).
//   자리 표(REQUIRED_PLACEHOLDERS)는 model 칸 시험(model/flow.test.ts)이 본다 — 문구 표는 아무것도 가져오지 않는다(시험도 같은 칸 규칙).
import { describe, expect, it } from 'vitest';

import { MATERIALITY_SETTING_TEXT } from './text.ts';

const t = MATERIALITY_SETTING_TEXT;
/** 1부 자리 낱말(경로 입력 글 안내에는 0). */
const PART1_WORDS = ['검색', '토픽', '키워드', '산업', '신뢰 출처'];

/** 칸 안내 글 전부(자리 안내 · 출력 안내 · 고정 규칙 · 흐름 글). */
const allNotes = () => [
  t.placeholders.lead(['{가}']),
  t.placeholders.whitelist(['{가}']),
  ...Object.values(t.placeholders.from),
  t.placeholders.tail,
  t.inputNote,
  ...Object.values(t.outputNotes),
  ...t.fixedRules,
  t.module.codeRules.foot,
  t.module.modelNote,
  t.flow.note,
  t.flow.whitelist.does,
  t.flow.whitelist.head,
  ...Object.values(t.flow.steps).flatMap((step) => Object.values(step)),
];

describe('AD-02 중대성평가 IRO 탭 문구', () => {
  it('모듈 이름 「중대성평가 IRO」(감사 낱말 · 시안 제목) · 상세 라벨 「칸」 · 모델 곁 글 · 고정 규칙 머리·꼬리와 줄 여섯(시안 원문)', () => {
    expect(t.module.name).toBe('중대성평가 IRO');
    expect(t.module.slotLabel).toBe('칸');
    expect(t.module.modelNote).toBe(
      '모델 칸 둘 · 리서치 두 단계는 리서치 모델, 영향 · 재무 세 단계는 분석 모델을 불러요',
    );
    expect(t.module.codeRules).toEqual({
      title: '고정 규칙 · 읽기 전용',
      foot: '고정 규칙은 여기서 고칠 수 없어요',
    });
    expect(t.fixedRules).toHaveLength(6);
    expect(t.fixedRules[4]).toBe('분석 모델에는 temperature 를 싣지 않아요');
    expect(t.fixedRules[0]).toContain('중대성 점수는 매기지 않아요.');
  });

  it('자리 안내: 그 칸의 자리를 늘어놓음 · 영향·재무는 가치사슬 활동 · 경로는 1부 자리 낱말 0', () => {
    expect(t.placeholders.lead(['{가}', '{나}'])).toBe(
      '{가} · {나} 자리에는 실행 때 값이 끼워져요',
    );
    expect(Object.keys(t.placeholders.from)).toEqual([
      'impact_input',
      'financial_input',
      'pathway_input',
    ]);
    expect(t.placeholders.from.impact_input).toContain('가치사슬 활동');
    expect(t.placeholders.from.financial_input).toBe(
      t.placeholders.from.impact_input,
    );
    for (const word of PART1_WORDS)
      expect(t.placeholders.from.pathway_input).not.toContain(word);
    expect(t.placeholders.whitelist(['{신뢰 출처 목록}'])).toMatch(
      /^\{신뢰 출처 목록\} 자리에는 실행 때 입력의 업종 구분/,
    );
  });

  it('출력 안내는 서버 OUTPUT_MARKS 여섯 칸만 — 절 머리 글자가 서버 머리와 같음', () => {
    expect(Object.keys(t.outputNotes)).toEqual([
      'regulation_system',
      'keywords_prefix',
      'controversy_system',
      'impact_system',
      'financial_system',
      'pathway_system',
    ]);
    expect(t.outputNotes.regulation_system).toMatch(
      /^\[9\] URL 출력 형식 · \[10\] 출력 형식 강제 /,
    );
    expect(t.outputNotes.keywords_prefix).toMatch(/^3\) 아래 JSON 형식으로만 /);
    expect(t.outputNotes.controversy_system).toMatch(
      /^\[OUTPUT\] 출력 형식 강제 /,
    );
    for (const key of ['impact_system', 'financial_system', 'pathway_system'])
      expect(t.outputNotes[key]).toMatch(/^\[FINAL OUTPUT — JSON ONLY\] /);
  });

  it('1부 입력 글 안내 · 규제 지시 글 출력 안내는 시안 v211 원문(IRA3)', () => {
    expect(t.inputNote).toBe('{ } 칸은 실행할 때 평가 만들기 입력이 들어가요');
    expect(t.outputNotes.regulation_system).toBe(
      '[9] URL 출력 형식 · [10] 출력 형식 강제 두 절은 답(JSON)과 주소를 읽는 꼴이에요. 이 절을 고치면 리서치 결과를 읽지 못할 수 있어요.',
    );
  });

  it('흐름 띠: 마디 다섯의 하는 일·빈도 · 신뢰 출처 곁 글(시안 원문) · 걸음 수·칸 수 글자 0', () => {
    expect(Object.keys(t.flow.steps)).toEqual([
      'regulation',
      'controversy',
      'impact',
      'financial',
      'pathway',
    ]);
    expect(t.flow.steps.controversy.head).toBe(
      '키워드는 실행마다 한 번 · 이슈는 토픽마다',
    );
    expect(t.flow.nodeLabel(2, '컨트로버시 리서치', true)).toBe(
      '2. 컨트로버시 리서치 프롬프트 보기, 고침',
    );
    expect(t.flow.whitelistLabel('신뢰 출처 목록', false)).toBe(
      '신뢰 출처 목록 보기',
    );
    expect(t.flow.stepHead(1, '규제·정책 리서치')).toBe(
      '단계 1 규제·정책 리서치',
    );
    expect(JSON.stringify(t.flow.steps)).not.toMatch(/걸음|웹 검색|칸 |\d+/);
  });

  it('rv-note 글(「기본 메모 예시」·「시안에서는」·「상태 예시」)과 칠하기 낱말은 어느 글에도 0', () => {
    for (const note of allNotes())
      for (const word of ['기본 메모 예시', '시안에서는', '상태 예시', '회색'])
        expect(note, note).not.toContain(word);
  });
});
