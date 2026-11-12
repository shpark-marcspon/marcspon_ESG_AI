// AD-01 의 고름 판정(밴드 AD1 ③). 걸러 보기는 서버 q·status 로 옮겼다(UA1W ② — 거르기의 꼴과 쿼리는 entities/account/model).
import type { Account } from '../../../entities/account/model/index.ts';

/** 고른 계정이 모두 사용 중지인가(같은 자리 단추가 [다시 사용]이 된다 — 시안 메모 ad-a-01c). 고른 것이 없으면 거짓. */
export const allInactive = (accounts: readonly Account[]) =>
  accounts.length > 0 && accounts.every((account) => !account.isActive);
