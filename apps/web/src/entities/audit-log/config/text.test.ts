// AD-05 문구 원문(밴드 AD2 ①, 실서버 AD5R ② — 디자인 원문 캔버스 v99). 화면·e2e 시험은 이 표의 값으로 단언하므로 시안 원문과 결정(MARC-ENT-269 마침표)은 여기서 글자로 박는다.
import { describe, expect, it } from 'vitest';

import { AUDIT_TEXT } from './text.ts';

describe('AD-05 문구 원문', () => {
  it('시안 원문(두 문장 글은 끝 마침표 둠)·디자인 원문', () => {
    expect(AUDIT_TEXT.title).toBe('감사 기록');
    expect(AUDIT_TEXT.description).toBe(
      '누가 언제 무엇을 했는지 남아요. 기록은 고치거나 지울 수 없어요.',
    );
    expect(AUDIT_TEXT.notice).toBe(
      '행동: 로그인 · 로그아웃 · 업로드 · 실행 · 내려받기 · 설정 변경 · 채택 · 제외 · 확정. 계정 줄은 계정 관리로 이어져요. 이름이 회색인 줄은 사람을 찾을 수 없는 기록이에요.',
    );
    // 안내 띠의 행동 아홉 = 행동 표의 글 아홉(같은 차례).
    expect(AUDIT_TEXT.notice).toContain(
      `행동: ${Object.values(AUDIT_TEXT.actions).join(' · ')}.`,
    );
    // 예시 데이터 띠·바닥글은 AD-05 에서 걷었다(sid:MARC-ENT-285).
    expect('mockBand' in AUDIT_TEXT).toBe(false);
    expect('foot' in AUDIT_TEXT).toBe(false);
    expect(AUDIT_TEXT.failed).toBe('감사 기록을 불러오지 못했어요');
    expect(AUDIT_TEXT.noMatch).toBe('조건에 맞는 기록이 없어요');
    expect(AUDIT_TEXT.searchPlaceholder).toBe('사람·대상 검색');
    expect(AUDIT_TEXT.failure('비밀번호 틀림')).toBe('실패 · 비밀번호 틀림');
    expect(AUDIT_TEXT.failure('')).toBe('실패');
    expect(AUDIT_TEXT.count(128)).toBe('128건');
    expect(AUDIT_TEXT.countOf(128, 50)).toBe('128건 중 50건');
    expect(AUDIT_TEXT.more).toBe('더 보기');
    expect(AUDIT_TEXT.moreFailed).toBe('기록을 더 불러오지 못했어요');
    expect(AUDIT_TEXT.clearFilter).toBe('거르기 풀기');
    expect(AUDIT_TEXT.emptyPeriod(AUDIT_TEXT.period.options.week)).toBe(
      '이번 주 기록이 없어요',
    );
    expect(AUDIT_TEXT.widenPeriod).toBe('기간을 넓혀 보세요.');
    expect(AUDIT_TEXT.emptyAll).toBe('아직 기록이 없어요');
    expect(AUDIT_TEXT.entry.actor).toEqual({
      command: '관리 명령',
      anonymous: '없는 아이디',
      unknown: '알 수 없는 사람',
      admin: ' · 운영 관리자',
    });
    expect(Object.values(AUDIT_TEXT.columns)).toEqual([
      '시각',
      '사람',
      '행동',
      '대상',
      '결과',
    ]);
  });

  it('한 문장 글은 끝 마침표 없음(MARC-ENT-269)', () => {
    for (const line of [
      AUDIT_TEXT.failed,
      AUDIT_TEXT.noMatch,
      AUDIT_TEXT.moreFailed,
    ])
      expect(line.endsWith('.'), line).toBe(false);
  });
});
