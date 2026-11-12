// 로그인 칸의 상태(밴드 LG1 ②). 제출 중에는 두 번 보내지 않는다. 결과는 쓰는 쪽(경로 컴포넌트)이 준 onLogin 이 낸다.
//   ok      → 그대로 둔다(단추는 도는 채로 — 경로가 첫 화면으로 넘긴다)
//   invalid → 「아이디 또는 비밀번호가 맞지 않아요」, 비밀번호 칸을 비우고 그리로 초점(시안 CM-01a)
//   locked·failed → 그 글. 칸은 그대로
// 제출하면 세션의 안내(만료 등)는 내린다(onDismissNotice).
import { useRef, useState } from 'react';

import type { LoginOutcome } from '../../../entities/session/api/index.ts';
import { canSubmitLogin } from '../model/index.ts';

export type LoginFailure = Extract<LoginOutcome, { ok: false }>['reason'];

export interface UseLoginFormOptions {
  onLogin: (username: string, password: string) => Promise<LoginOutcome>;
  onDismissNotice: () => void;
}

export function useLoginForm({
  onLogin,
  onDismissNotice,
}: UseLoginFormOptions) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [failure, setFailure] = useState<LoginFailure | null>(null);
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const passwordRef = useRef<HTMLInputElement>(null);
  const ready = canSubmitLogin(username, password);

  const submit = async () => {
    if (busy.current || !ready) return;
    busy.current = true;
    setPending(true);
    setFailure(null);
    onDismissNotice();
    const outcome = await onLogin(username.trim(), password);
    if (outcome.ok) return;
    busy.current = false;
    setPending(false);
    setFailure(outcome.reason);
    if (outcome.reason === 'invalid') {
      setPassword('');
      passwordRef.current?.focus();
    }
  };

  return {
    username,
    setUsername,
    password,
    setPassword,
    passwordRef,
    failure,
    pending,
    ready,
    submit,
  };
}
export type LoginForm = ReturnType<typeof useLoginForm>;
