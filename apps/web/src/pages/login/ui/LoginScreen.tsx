// 로그인 화면(밴드 LG1 ②, 시안 CM-01·01a·01b). 라우터를 모른다: 로그인은 onLogin, 안내 내리기는 onDismissNotice(경로 컴포넌트가 잇는다).
// 아이디 저장·회원가입·SSO·아이디 찾기는 없다(시안). 두 칸 다 차야 [로그인] 이 켜지고, 제출 중에는 단추 안 도는 표시·두 번 제출 막음.
// 실패 글은 비밀번호 칸 아래 한 줄(role="alert"). 세션의 안내(잠김·처음부터)는 같은 자리에 role="status" 로, 실패가 있으면 실패가 이긴다.
// 세션 끝남(expired)만 카드 위 주황 띠(role="status", 시안 CM-03 상태 예시 7 — 밴드 DT1 C1). 카드 안 실패 글과 따로라 같이 보일 수 있다(critic 반영 3).
// 부팅 복원이 서버에 닿지 못함(unreachable)도 카드 위 띠 — 오류 꼴(시안 e-info--invalid) + [다시 시도](onRetry, 밴드 SN1).
//   role="status": 화면에 들어올 때부터 있는 안내다(AuthAlert 의 규칙). 누르는 동안은 aria-disabled(초점은 남음), 두 번 눌러도 한 번.
import { useId, useRef, useState } from 'react';

import { Input } from '@marcspon/ui/components/input';
import { Label } from '@marcspon/ui/components/label';

import type { LoginOutcome } from '../../../entities/session/api/index.ts';
import { SESSION_TEXT } from '../../../entities/session/config/text.ts';
import type { SessionNotice } from '../../../entities/session/model/index.ts';
import {
  AuthAlert,
  AuthCard,
  PasswordInput,
} from '../../../entities/session/ui/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { useLoginForm } from '../hooks/index.ts';
import { ForgotPasswordDialog } from './ForgotPasswordDialog.tsx';

const words = SESSION_TEXT.login;

export interface LoginScreenProps {
  /** 세션이 남긴 안내(만료·잠김·처음부터 다시). 없으면 null. */
  notice: SessionNotice | null;
  onLogin: (username: string, password: string) => Promise<LoginOutcome>;
  onDismissNotice: () => void;
  /** unreachable 띠의 [다시 시도] — 부팅 복원을 한 번 더. 풀릴 때까지 단추가 꺼진다. 주지 않으면 단추가 없다. */
  onRetry?: () => Promise<void>;
}

export function LoginScreen({
  notice,
  onLogin,
  onDismissNotice,
  onRetry,
}: LoginScreenProps) {
  const form = useLoginForm({ onLogin, onDismissNotice });
  const [retrying, setRetrying] = useState(false);
  const retryBusy = useRef(false);
  const retry = async () => {
    if (retryBusy.current || !onRetry) return;
    retryBusy.current = true;
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      retryBusy.current = false;
      setRetrying(false);
    }
  };
  const id = useId();
  const titleId = `${id}-title`;
  const usernameId = `${id}-username`;
  const passwordId = `${id}-password`;
  const inCard =
    notice === 'expired' || notice === 'unreachable' ? null : notice;
  return (
    <AuthCard
      screen="login"
      labelledBy={titleId}
      notice={
        notice === 'expired' ?
          <AuthAlert role="status" reason={notice} tone="important">
            {SESSION_TEXT.notice[notice]}
          </AuthAlert>
        : notice === 'unreachable' ?
          <AuthAlert role="status" reason={notice}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span>{SESSION_TEXT.notice[notice]}</span>
              {onRetry && (
                <Button
                  asChild
                  disabled={retrying}
                  variant="outlineGrey"
                  size="sm"
                >
                  <button
                    type="button"
                    className="aria-disabled:cursor-not-allowed aria-disabled:opacity-40"
                    onClick={() => void retry()}
                  >
                    {words.retry}
                  </button>
                </Button>
              )}
            </div>
          </AuthAlert>
        : null
      }
      heading={
        <>
          <h1 className="m-0 text-style-nanum-display-01 font-black text-text-primary">
            <span className="border-0 border-b border-dashed border-border-secondary px-1">
              {SESSION_TEXT.brand.service}
            </span>
          </h1>
          <h2 id={titleId} className="sr-only">
            {words.title}
          </h2>
        </>
      }
    >
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void form.submit();
        }}
      >
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={usernameId}>{words.username}</Label>
          <Input
            id={usernameId}
            name="username"
            autoComplete="username"
            placeholder={words.usernamePlaceholder}
            value={form.username}
            onChange={(event) => form.setUsername(event.target.value)}
            className="h-10"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={passwordId}>{words.password}</Label>
          <PasswordInput
            ref={form.passwordRef}
            id={passwordId}
            name="password"
            autoComplete="current-password"
            placeholder={words.passwordPlaceholder}
            showLabel={words.showPassword}
            value={form.password}
            onChange={(event) => form.setPassword(event.target.value)}
          />
        </div>
        {form.failure ?
          <AuthAlert
            role="alert"
            reason={form.failure}
            lock={form.failure === 'locked'}
          >
            {words[form.failure]}
          </AuthAlert>
        : inCard ?
          <AuthAlert
            role="status"
            reason={inCard}
            tone={inCard === 'relogin' ? 'info' : 'error'}
            lock={inCard === 'locked'}
          >
            {SESSION_TEXT.notice[inCard]}
          </AuthAlert>
        : null}
        <Button
          type="submit"
          variant="solidBlack"
          shape="round"
          size="lg"
          className="w-full"
          disabled={!form.ready}
          loading={form.pending}
          loadingLabel={words.submitting}
        >
          {words.submit}
        </Button>
        <ForgotPasswordDialog
          trigger={
            <Button variant="text" size="md" className="self-center underline">
              {words.forgot}
            </Button>
          }
        />
      </form>
      <p className="m-0 text-center text-style-pre-caption-02 text-text-tertiary">
        {words.foot}
      </p>
    </AuthCard>
  );
}
