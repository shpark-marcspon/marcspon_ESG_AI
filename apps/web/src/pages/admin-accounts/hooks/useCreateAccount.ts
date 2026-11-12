// AD-01a 계정 만들기의 입력·보내기(밴드 AD1 ②). 모달 안에서만 산다 — 모달이 닫히면(마운트가 풀리면) 상태째 사라진다.
//   - 두 칸이 차야(아이디 꼴·다듬은 이름 1~20자) 보낼 수 있다. 보내는 중에는 다시 보내지 않는다(같은 렌더 안의 두 번 제출도 — ref).
//   - 결과의 임시 비밀번호는 이 훅의 상태 하나에만 둔다(URL·storage·로그·쿼리 캐시 0). 쓰는 쪽(모달)이 닫히면 지워진다.
//   - 409 → 아이디 칸 오류(아이디를 고치면 지운다), 422 → fields 의 칸 오류, 그 밖 → 쓰기 실패 글. 서버 message 는 보이지 않는다.
//   - 만든 뒤와 409·쓰기 실패 뒤에는 목록을 다시 받는다 — 응답을 잃었거나 꼴 밖이면 행이 생겼을 수 있다(가지 리뷰 3).
import { useRef, useState } from 'react';

import type {
  AccountField,
  AccountsPort,
} from '../../../entities/account/api/index.ts';
import {
  nameLength,
  nameToSend,
  usernameProblem,
} from '../../../entities/account/model/index.ts';
import type { Account } from '../../../entities/account/model/index.ts';

export type CreateError =
  | { kind: 'taken' }
  | { kind: 'invalid'; fields: AccountField[] }
  | { kind: 'failed' };

/** 만든 계정과 그 임시 비밀번호(한 번만 보인다). */
export interface Issued {
  account: Account;
  password: string;
}

export interface CreateAccountForm {
  username: string;
  name: string;
  setUsername(value: string): void;
  setName(value: string): void;
  /** 아이디에 쓸 수 없는 글자가 있는가(빈 칸은 아니다). */
  usernameInvalid: boolean;
  nameCount: number;
  ready: boolean;
  pending: boolean;
  error: CreateError | null;
  issued: Issued | null;
  submit(): Promise<void>;
}

export function useCreateAccount({
  port,
  onChanged,
}: {
  port: AccountsPort;
  /** 만든 뒤·409·쓰기 실패 뒤(목록을 다시 받는다). */
  onChanged(): void;
}): CreateAccountForm {
  const [username, setUsernameValue] = useState('');
  const [name, setNameValue] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<CreateError | null>(null);
  const [issued, setIssued] = useState<Issued | null>(null);
  const sending = useRef(false);

  const problem = usernameProblem(username);
  const trimmed = nameToSend(name);
  const ready = problem === null && trimmed !== null;

  const submit = async () => {
    if (!ready || sending.current || issued) return;
    sending.current = true;
    setPending(true);
    setError(null);
    try {
      const outcome = await port.create({ username, name: trimmed });
      if (outcome.kind === 'created')
        setIssued({ account: outcome.account, password: outcome.password });
      else setError(outcome);
      if (outcome.kind !== 'invalid') onChanged();
    } finally {
      sending.current = false;
      setPending(false);
    }
  };

  return {
    username,
    name,
    setUsername: (value) => {
      setUsernameValue(value);
      if (error?.kind === 'taken') setError(null);
    },
    setName: setNameValue,
    usernameInvalid: problem === 'format',
    nameCount: nameLength(name),
    ready,
    pending,
    error,
    issued,
    submit,
  };
}
