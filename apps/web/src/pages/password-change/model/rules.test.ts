// 새 비밀번호 규칙(밴드 LG1 ③, 발주서 §4 단위 ③ — 단추 켜짐 조건 7자·8자·다름).
import { describe, expect, it } from 'vitest';

import {
  MIN_PASSWORD_LENGTH,
  canSubmitPassword,
  confirmMismatch,
  meetsLength,
} from './rules.ts';

describe('비밀번호 규칙', () => {
  it('최소 길이는 8', () => expect(MIN_PASSWORD_LENGTH).toBe(8));

  it('7자는 꺼짐, 8자는 켜짐(두 칸 같을 때)', () => {
    expect(canSubmitPassword('1234567', '1234567')).toBe(false);
    expect(canSubmitPassword('12345678', '12345678')).toBe(true);
    expect(meetsLength('1234567')).toBe(false);
    expect(meetsLength('12345678')).toBe(true);
  });

  it('두 칸이 다르면 꺼짐, 빈 확인 칸은 아직 「다름」을 보이지 않는다', () => {
    expect(canSubmitPassword('greenpaper', 'greenpape')).toBe(false);
    expect(canSubmitPassword('greenpaper', '')).toBe(false);
    expect(confirmMismatch('greenpaper', 'greenpape')).toBe(true);
    expect(confirmMismatch('greenpaper', '')).toBe(false);
    expect(confirmMismatch('greenpaper', 'greenpaper')).toBe(false);
  });

  it('글자 수는 코드 포인트로 센다(한글·그림 글자 하나가 한 자)', () => {
    expect(meetsLength('가나다라마바사아')).toBe(true);
    expect(meetsLength('😀😀😀😀😀😀😀')).toBe(false);
    expect(meetsLength('😀😀😀😀😀😀😀😀')).toBe(true);
  });
});
