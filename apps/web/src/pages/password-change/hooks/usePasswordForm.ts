// 첫 로그인 비밀번호 바꾸기 칸의 상태(밴드 LG1 ③). 제출 중에는 두 번 보내지 않는다. 결과는 쓰는 쪽이 준 onChange 가 낸다.
//   ok       → 그대로 둔다(경로가 첫 화면으로 넘긴다)
//   rejected → 「이 비밀번호는 쓸 수 없어요」, 칸은 그대로(서버 message 는 보이지 않는다 — 감독 판단 5)
//   failed   → 「비밀번호를 바꾸지 못했어요」
//   ended    → 세션이 끝났다(잠김·지금 비밀번호 틀림·임시 비밀번호 잃음). 경로가 /login 으로 넘기고 그 화면이 안내한다
import { useRef, useState } from 'react';

import type { PasswordChangeOutcome } from '../../../entities/session/api/index.ts';
import {
  canSubmitPassword,
  confirmMismatch,
  meetsLength,
} from '../model/index.ts';

export type PasswordFailure = 'rejected' | 'failed';

export interface UsePasswordFormOptions {
  onChange: (newPassword: string) => Promise<PasswordChangeOutcome>;
}

export function usePasswordForm({ onChange }: UsePasswordFormOptions) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [failure, setFailure] = useState<PasswordFailure | null>(null);
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const ready = canSubmitPassword(password, confirm);

  const submit = async () => {
    if (busy.current || !ready) return;
    busy.current = true;
    setPending(true);
    setFailure(null);
    const outcome = await onChange(password);
    if (outcome.ok || outcome.reason === 'ended') return;
    busy.current = false;
    setPending(false);
    setFailure(outcome.reason);
  };

  return {
    password,
    setPassword,
    confirm,
    setConfirm,
    lengthMet: meetsLength(password),
    mismatch: confirmMismatch(password, confirm),
    failure,
    pending,
    ready,
    submit,
  };
}
export type PasswordForm = ReturnType<typeof usePasswordForm>;
