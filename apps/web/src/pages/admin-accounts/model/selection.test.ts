// AD-01 고름 판정(밴드 AD1 ③): [다시 사용] 판정. 걸러 보기는 서버로 옮겼다(UA1W — entities/account/model 의 accountQuery 시험).
import { describe, expect, it } from 'vitest';

import { fakeAccount } from '../../../entities/account/api/testing.ts';
import { allInactive } from './index.ts';

const rows = [
  fakeAccount(1, { username: 'Kim.A', name: '재무팀' }),
  fakeAccount(2, { isLocked: true }),
  fakeAccount(3, { isInitial: true }),
  fakeAccount(4, { isActive: false }),
];

describe('allInactive — 같은 자리 단추가 [다시 사용]', () => {
  it('고른 것이 모두 사용 중지일 때만, 비면 거짓', () => {
    expect(allInactive([rows[3]!])).toBe(true);
    expect(allInactive([rows[3]!, rows[0]!])).toBe(false);
    expect(allInactive([])).toBe(false);
  });
});
