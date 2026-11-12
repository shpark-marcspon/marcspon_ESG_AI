// 문구 표의 원문(밴드 AD1). 화면·e2e 시험은 이 표의 값으로 단언하므로, 시안 원문과 결정(MARC-ENT-269 마침표)은 여기서 글자로 박는다.
import { describe, expect, it } from 'vitest';

import { ACCOUNT_TEXT } from './text.ts';

describe('AD-01 문구 원문', () => {
  it('시안 원문(두 문장 글은 끝 마침표 둠)', () => {
    expect(ACCOUNT_TEXT.create.taken).toBe(
      '이미 쓰고 있는 아이디예요. 다른 아이디를 입력해 주세요.',
    );
    expect(ACCOUNT_TEXT.password.important).toBe(
      '이 창을 닫으면 다시 볼 수 없어요. 잊으면 다시 초기화해요.',
    );
    expect(ACCOUNT_TEXT.create.usernameHelp).toBe(
      '영문 · 숫자와 . @ + - _ 만 쓸 수 있어요 · 만든 뒤에는 바꿀 수 없어요',
    );
    expect(ACCOUNT_TEXT.password.title).toBe('임시 비밀번호를 전해 주세요');
    expect(ACCOUNT_TEXT.reset.title('user02')).toBe(
      'user02 의 비밀번호를 초기화할까요?',
    );
    expect(ACCOUNT_TEXT.password.created('user07', '담당자 G')).toBe(
      'user07 · 담당자 G · 계정을 만들었어요',
    );
  });

  it('한 문장 글은 끝 마침표 없음(MARC-ENT-269)', () => {
    for (const line of [
      ACCOUNT_TEXT.list.foot,
      ACCOUNT_TEXT.reset.body,
      ACCOUNT_TEXT.list.failed,
      ACCOUNT_TEXT.list.empty,
      ACCOUNT_TEXT.create.notice,
      ACCOUNT_TEXT.create.invalid,
      ACCOUNT_TEXT.password.next,
      ACCOUNT_TEXT.reset.missing,
    ])
      expect(line.endsWith('.'), line).toBe(false);
  });

  it('UA1W 디자인 원문 — 만든 날 열, 사용 중지 본문(분은 넣어 받음), 일부 실패·이름 고침 실패 글', () => {
    expect(ACCOUNT_TEXT.list.columns.createdAt).toBe('만든 날');
    expect(ACCOUNT_TEXT.active.deactivateBody(30)).toBe(
      '사용 중지한 계정은 로그인할 수 없어요. 이미 로그인한 사람도 30분 안에 끊겨요. 올린 문서와 기록은 그대로 남아요.',
    );
    expect(ACCOUNT_TEXT.active.deactivateFailed(2)).toBe(
      '계정 2개를 사용 중지하지 못했어요. 잠시 뒤 다시 시도해 주세요.',
    );
    expect(ACCOUNT_TEXT.active.reactivateFailed(1)).toBe(
      '계정 1개를 다시 사용하지 못했어요. 잠시 뒤 다시 시도해 주세요.',
    );
    expect(ACCOUNT_TEXT.active.deactivatePartly(2, 1)).toBe(
      '계정 2개는 사용 중지했어요. 1개는 하지 못했어요. 잠시 뒤 다시 시도해 주세요.',
    );
    expect(ACCOUNT_TEXT.active.reactivatePartly(1, 2)).toBe(
      '계정 1개는 다시 사용하게 했어요. 2개는 다시 사용하게 하지 못했어요. 잠시 뒤 다시 시도해 주세요.',
    );
    expect(ACCOUNT_TEXT.list.rename).toEqual({
      missing: ACCOUNT_TEXT.reset.missing,
      invalid: ACCOUNT_TEXT.create.invalid,
      failed: '이름을 바꾸지 못했어요. 잠시 뒤 다시 시도해 주세요.',
    });
  });

  it('상태 배지 넷(디자인 원문)', () => {
    expect(ACCOUNT_TEXT.status).toEqual({
      inactive: '사용 중지',
      locked: '잠김',
      initial: '초기화 대기',
      active: '사용 중',
    });
  });
});
