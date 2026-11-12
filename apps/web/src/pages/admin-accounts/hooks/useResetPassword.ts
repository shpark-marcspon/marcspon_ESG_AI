// 비밀번호 초기화 확인 → 보내기(밴드 AD1 ②). 모달 안에서만 산다 — 닫히면 상태째 사라진다.
//   - 보내는 중에는 다시 보내지 않는다(ref). 결과의 임시 비밀번호는 이 훅의 상태 하나에만.
//   - 404 USER_NOT_FOUND → missing(목록을 다시 받는다), 그 밖 실패 → failed. 사용 중지 계정도 초기화된다(서버가 받는다).
import { useRef, useState } from 'react';

import type { AccountsPort } from '../../../entities/account/api/index.ts';
import type { Account } from '../../../entities/account/model/index.ts';
import type { Issued } from './useCreateAccount.ts';

export interface ResetPasswordFlow {
  pending: boolean;
  error: 'missing' | 'failed' | null;
  issued: Issued | null;
  submit(): Promise<void>;
}

export function useResetPassword({
  port,
  account,
  onChanged,
}: {
  port: AccountsPort;
  account: Pick<Account, 'id'>;
  /** 초기화했거나 없는 계정이었을 때(목록을 다시 받는다). */
  onChanged(): void;
}): ResetPasswordFlow {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<'missing' | 'failed' | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const sending = useRef(false);

  const submit = async () => {
    if (sending.current || issued || error === 'missing') return;
    sending.current = true;
    setPending(true);
    setError(null);
    try {
      const outcome = await port.resetPassword(account);
      if (outcome.kind === 'reset') {
        setIssued({ account: outcome.account, password: outcome.password });
        onChanged();
      } else {
        setError(outcome.kind);
        if (outcome.kind === 'missing') onChanged();
      }
    } finally {
      sending.current = false;
      setPending(false);
    }
  };

  return { pending, error, issued, submit };
}
