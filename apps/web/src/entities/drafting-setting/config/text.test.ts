// AD-02 보고서 작성 탭 문구 원문(밴드 RPA3 — 시안 AD-02-RP r1 · 흐름 코드와 대 봄). 화면·e2e 시험은 이 표의 값으로 단언하므로 원문은 여기서 글자로 박는다.
//   모듈 이름이 메뉴·감사 낱말과 같은지는 모듈 줄 시험(app/admin/ai-setting-modules.test.ts)이 본다(entities 끼리 가져오지 않는다 — 중대성평가 꼴).
//   자리 표(REQUIRED_PLACEHOLDERS)는 model 칸 시험(model/flow.test.ts)이 본다 — 문구 표는 아무것도 가져오지 않는다(시험도 같은 칸 규칙).
import { describe, expect, it } from 'vitest';

import { DRAFTING_SETTING_TEXT } from './text.ts';

const t = DRAFTING_SETTING_TEXT;

/** 칸 안내 글 전부(자리 안내 · 흐름 글). */
const allNotes = () => [
  t.placeholders.lead(['{가}']),
  t.placeholders.tail,
  t.flow.note,
  ...t.flow.start,
  t.flow.check,
  t.flow.end.title,
  ...t.flow.end.lines,
  t.flow.branch,
  ...Object.values(t.flow.steps).flatMap((step) => Object.values(step)),
];

describe('AD-02 보고서 작성 탭 문구', () => {
  it('모듈 이름 「보고서 작성」(메뉴 · 시안 제목) · 상세 라벨 「칸」', () => {
    expect(t.module.name).toBe('보고서 작성');
    expect(t.module.slotLabel).toBe('칸');
  });

  it('모델 카드 곁 글(모의 공급사 안내) 없음 — 밴드 RPA4, 이슈 490 처분 Q1 (가) 뒤집음', () => {
    expect(Object.keys(t.module)).toEqual(['name', 'slotLabel']);
    expect('modelNote' in t.module).toBe(false);
    expect(JSON.stringify(t)).not.toContain('4,000');
    expect(JSON.stringify(t)).not.toContain('모의');
  });

  it('자리 안내: 그 칸의 자리를 늘어놓음 · 꼬리 「지우면 저장할 수 없어요」', () => {
    expect(t.placeholders.lead(['{가}', '{나}'])).toBe(
      '{가} · {나} 자리는 실행 때 채워요',
    );
    expect(t.placeholders.tail).toBe('지우면 저장할 수 없어요');
  });

  it('흐름 띠: 마디 둘의 하는 일·빈도 · 시작·출처 확인·끝 상자 · 갈래 글(시안 원문)', () => {
    expect(Object.keys(t.flow.steps)).toEqual(['map', 'draft']);
    expect(t.flow.steps.draft.head).toBe('목차마다 한 번');
    expect(t.flow.start).toEqual(['전년도 보고서', '· 목차']);
    expect(t.flow.end).toEqual({
      title: '결과',
      lines: ['목차마다', 'bullet · 출처'],
    });
    expect(t.flow.branch).toBe('맞는 페이지가 없는 목차는 짓지 않아요');
    expect(t.flow.nodeLabel(2, '초안 짓기', true)).toBe(
      '2. 초안 짓기 프롬프트 보기, 고침',
    );
    expect(t.flow.stepHead(1, '목차 달기')).toBe('단계 1 목차 달기');
    expect(JSON.stringify(t.flow.steps)).not.toMatch(/\d/);
  });

  it('rv-note 글·칠하기 낱말·시안 처리 값 숫자·「잎」은 어느 글에도 0', () => {
    for (const note of allNotes())
      for (const word of [
        '기본값이 서면',
        '시안 예시',
        '실제 값이 서면',
        '회색',
        '20페이지',
        '12페이지',
        '잎',
      ])
        expect(note, note).not.toContain(word);
  });
});
