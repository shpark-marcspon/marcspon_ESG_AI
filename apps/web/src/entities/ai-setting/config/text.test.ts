// AD-02 문구 원문(밴드 AD2W — 디자인 판 AD-02_r3). 화면·e2e 시험은 이 표의 값으로 단언하므로 판 원문·결정(MARC-ENT-269)은 여기서 글자로 박는다.
import { describe, expect, it } from 'vitest';

import { AI_SETTING_TEXT } from './text.ts';

const t = AI_SETTING_TEXT;

describe('AD-02 문구 원문(r3)', () => {
  it('머리·설명·적용 곁 글·판 열', () => {
    expect(t.title('그린워싱')).toBe('AI 설정 — 그린워싱');
    expect(t.description).toBe(
      '적용 중인 버전은 하나예요. 구성과 단계를 오가며 고친 것은 [새 버전으로 저장] 한 번에 새 버전 하나로 남고, [이 버전 적용]을 눌러야 다음 실행부터 쓰여요.',
    );
    expect(t.applyAfterSave).toBe('저장한 뒤에 적용할 수 있어요');
    expect(t.newVersionNote).toBe(
      '고치지 않고 그대로 새 버전으로 복제해요(이름 창이 떠요)',
    );
    expect(t.status).toEqual({
      testing: '초안',
      applied: '적용 중',
      past: '지난 버전',
      default: '기본',
    });
    expect(t.defaultSum).toBe('번호 없음 · 처음부터 있는 설정');
    expect(t.editingSum('v3')).toBe('v3 바탕으로 고치는 중');
  });

  it('구성 열 꼬리·저장 막대·프롬프트 상세', () => {
    expect(t.components.modelOne).toBe('모든 단계에 하나');
    expect(t.components.modelSlots(2)).toBe('2칸');
    expect(t.components.promptFixed(1, 4)).toBe('1단계 · 4칸');
    expect(t.components.edited(1)).toBe('고침 1');
    expect(t.saveBar.count(3)).toBe('고친 것 3개 · 아직 저장 전이에요');
    // 저장 막대 셈 규칙 줄은 없다(모든 모듈 — GW3R A10, 338).
    expect('rule' in t.saveBar).toBe(false);
    expect('ruleSlots' in t.saveBar).toBe(false);
    expect(t.prompt.notice('v2')).toBe(
      '고친 것은 위 [새 버전으로 저장]으로 다른 구성의 고침과 함께 새 버전 하나로 남아요. 적용 중인 v2 는 바뀌지 않아요.',
    );
    expect(t.prompt.outputNote).toBe(
      '[출력(JSON …)]으로 시작하는 절은 결과를 읽는 형식이에요. 이 절을 고치면 결과를 읽지 못할 수 있어요.',
    );
    expect(t.prompt.stepLabel).toBe('단계');
    expect(Object.keys(t)).not.toContain('editTag'); // 「편집중」 꼬리표 없음(GW3R A11)
    expect(Object.keys(t.model)).not.toContain('note'); // AS3b K9 (가): 모델 카드 곁 글은 모듈 글 표로(그린워싱 글자는 그 표의 시험이 본다)
    expect(t.fixedNote).toBe('고정 값이라 바꿀 수 없어요');
  });

  it('모달 일곱(r3 ①~⑦)', () => {
    expect(t.save.title).toBe('새 버전으로 저장할까요?');
    expect(t.save.body(t.baseName('v3', false), 3, 'v2')).toBe(
      'v3 를 바탕으로 고친 것 3개가 새 버전으로 남아요. 적용 중인 v2 는 바뀌지 않아요.',
    );
    expect(t.save.body(t.baseName('기본 설정', true), 1, 'v2')).toBe(
      '기본 설정을 바탕으로 고친 것 1개가 새 버전으로 남아요. 적용 중인 v2 는 바뀌지 않아요.',
    );
    expect(t.save.nameEmpty).toBe(
      '버전 이름을 적어야 저장할 수 있어요 · 1~40자',
    );
    expect(t.save.failed).toBe(
      '새 버전을 저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.',
    );
    expect(t.save.done('v4')).toBe(
      'v4 를 저장했어요. 쓰려면 [이 버전 적용]을 눌러요.',
    );
    expect(t.revert.title(3)).toBe('고친 것 3개를 되돌릴까요?');
    expect(t.revert.body('v3')).toBe(
      '저장하지 않은 고침이 모두 사라지고 v3 그대로 돌아가요.',
    );
    expect([t.leave.title, t.leave.body]).toEqual([
      '저장하지 않고 나갈까요?',
      '저장하지 않은 고침이 있어요. 나가면 고친 내용이 사라져요.',
    ]);
    expect(t.applyDialog.title('v3')).toBe('v3 을 적용할까요?');
    expect(t.applyDialog.body('v3', 'v2')).toBe(
      '다음 실행부터 v3 을 써요. 이미 돌고 있는 실행은 v2 로 끝나요.',
    );
  });

  it('옛 목 글(판정 기준 표·의심 단어·처리 값·예시 데이터 띠)은 걷었다(sid:MARC-ISSUE-278)', () => {
    for (const key of ['mockBand', 'picks', 'criteria', 'terms', 'params'])
      expect(key in t, key).toBe(false);
  });

  it('모델 칸·묶음 여럿(AP1W — e9 Q2·Q4 (나)·덧)', () => {
    expect(t.model.uses(['가', '나 다'])).toBe('가 · 나 다에 쓰여요');
    expect(t.changed.slotModel('지어낸 칸')).toBe('모델 설정 · 지어낸 칸');
    expect(t.changed.slotPrompt(1, '지어낸 묶음', '지어낸 칸')).toBe(
      '1. 지어낸 묶음 · 지어낸 칸',
    );
  });

  it('한 문장 글은 끝 마침표 없음(MARC-ENT-269)', () => {
    for (const line of [
      t.applyAfterSave,
      t.newVersionNote,
      t.pending,
      t.failed,
      t.fixedNote,
      t.model.temperatureRange,
      t.prompt.untouched,
      t.prompt.memoNote,
      t.prompt.outputLost,
      t.saveBar.count(2),
      t.save.nameEmpty,
      t.save.title,
    ])
      expect(line.endsWith('.'), line).toBe(false);
  });
});
