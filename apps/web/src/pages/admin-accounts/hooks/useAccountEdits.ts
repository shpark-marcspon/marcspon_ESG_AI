// AD-01 계정 수정(밴드 UA1W ② — 실서버 PATCH /users/{id}). 이름 고침과 여럿 사용 중지·다시 사용을 어댑터로 보낸다(화면은 그 갈래로 그린다).
//   - 보내는 중에는 다시 보내지 않는다(ref). applying 은 단추의 꺼짐·도는 표시.
//   - rename: 다듬은 이름이 지금 이름과 같으면 보내지 않는다(unchanged — 서버도 멱등이나 감사 줄이 남는다, 감독 판단 Q5).
//     renamed·missing 이면 목록을 조용히 다시 받는다(missing 은 그 줄이 빠진다). invalid·failed 는 다시 받지 않는다(바뀐 것이 없다).
//   - setActive: 어댑터가 id 마다 차례로 보내고 {done, failed}(성공·실패 id) 를 그대로 돌려준다. 성공분이 배지에 보이게 늘 목록을 조용히 다시 받는다(감독 판단 Q4).
import { useRef, useState } from 'react';

import type {
  AccountsPort,
  SetActiveOutcome,
} from '../../../entities/account/api/index.ts';
import type { Account } from '../../../entities/account/model/index.ts';

export type RenameResult =
  'renamed' | 'unchanged' | 'missing' | 'invalid' | 'failed';

export interface AccountEdits {
  applying: boolean;
  /** 보내는 중이면 null(아무것도 하지 않았다). */
  rename(
    account: Pick<Account, 'id' | 'name'>,
    name: string,
  ): Promise<RenameResult | null>;
  /** 성공·실패한 id(차례 그대로). 보내는 중이면 null. */
  setActive(
    accounts: readonly Pick<Account, 'id'>[],
    isActive: boolean,
  ): Promise<SetActiveOutcome | null>;
}

export function useAccountEdits({
  port,
  onChanged,
}: {
  port: AccountsPort;
  /** 서버 값이 바뀌었을 수 있을 때(목록을 조용히 다시 받는다). */
  onChanged(): void;
}): AccountEdits {
  const [applying, setApplying] = useState(false);
  const sending = useRef(false);

  async function guarded<T>(send: () => Promise<T>): Promise<T | null> {
    if (sending.current) return null;
    sending.current = true;
    setApplying(true);
    try {
      return await send();
    } finally {
      sending.current = false;
      setApplying(false);
    }
  }

  return {
    applying,
    rename: (account, name) =>
      guarded(async (): Promise<RenameResult> => {
        if (name === account.name) return 'unchanged';
        const outcome = await port.rename(account, name);
        if (outcome.kind === 'renamed' || outcome.kind === 'missing')
          onChanged();
        return outcome.kind;
      }),
    setActive: (accounts, isActive) =>
      guarded(async () => {
        const outcome = await port.setActive(accounts, isActive);
        onChanged();
        return outcome;
      }),
  };
}
